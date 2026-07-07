#!/usr/bin/env bash
# Hermetic tests for scripts/install.sh — drives the REAL installer against a
# fake uv tarball and fake manifests served over 127.0.0.1. No external
# network, runs in seconds. Each scenario gets a fresh sandbox (HOME +
# install root) and asserts on exit code, filesystem state, and messages.
#
#   tests/installer/run_tests.sh                   # run everything
#   tests/installer/run_tests.sh checksum_abort    # run a subset

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
INSTALL_SH="$REPO/scripts/install.sh"
TESTS_TMP="$(mktemp -d)"
FIXTURES="$TESTS_TMP/fixtures"
SERVER_PID=""
PASS=0
FAIL=0

cleanup() {
    # The wait reaps the server so bash 3.2 doesn't print "Terminated".
    [ -n "$SERVER_PID" ] && { kill "$SERVER_PID" 2>/dev/null; wait "$SERVER_PID" 2>/dev/null; }
    rm -rf "$TESTS_TMP"
}
trap cleanup EXIT

# Without setsid we can't guarantee a detached tty; force no-modify-path then.
HAVE_SETSID=""
command -v setsid >/dev/null 2>&1 && HAVE_SETSID=1

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
    else shasum -a 256 "$1" | awk '{print $1}'; fi
}

# ---------------------------------------------------------------------------
# Fixtures: fake uv tarball + manifest variants, served over localhost HTTP
# ---------------------------------------------------------------------------

build_fake_uv() {
    local dir="$TESTS_TMP/uv-build/uv-test"
    mkdir -p "$dir"
    cat > "$dir/uv" <<'EOF'
#!/bin/sh
# Fake uv: handles `uv venv DIR ...` and `uv pip install --python PY ... SPEC`
set -e
if [ "$1" = "venv" ]; then
    mkdir -p "$2/bin"
    printf '#!/bin/sh\nexit 0\n' > "$2/bin/python"
    chmod +x "$2/bin/python"
elif [ "$1" = "pip" ]; then
    py="" prev="" last=""
    for a in "$@"; do
        [ "$prev" = "--python" ] && py="$a"
        prev="$a"; last="$a"
    done
    bindir="$(dirname "$py")"
    for name in vastai serve-vast-deployment register-python-argcomplete; do
        printf '#!/bin/sh\necho "%s"\n' "${last#vastai==}" > "$bindir/$name"
        chmod +x "$bindir/$name"
    done
fi
exit 0
EOF
    chmod +x "$dir/uv"
    tar -czf "$FIXTURES/uv.tar.gz" -C "$TESTS_TMP/uv-build" uv-test
    UV_SHA="$(sha256_of "$FIXTURES/uv.tar.gz")"
}

# write_manifest SUBDIR LATEST [SHA [WHEEL_URL WHEEL_SHA]]
write_manifest() {
    local dir="$FIXTURES/$1" latest="$2" sha="${3:-$UV_SHA}"
    local wheel_url="${4:-}" wheel_sha="${5:-}" key
    mkdir -p "$dir"
    {
        echo "SCHEMA=1"
        echo "CHANNEL=stable"
        echo "LATEST=$latest"
        echo "PYTHON=3.12"
        [ -n "$wheel_url" ] && echo "WHEEL_URL=$wheel_url"
        [ -n "$wheel_sha" ] && echo "WHEEL_SHA256=$wheel_sha"
        echo "UV_VERSION=0.0.0-test"
        for key in LINUX_X86_64 LINUX_X86_64_MUSL LINUX_AARCH64 LINUX_AARCH64_MUSL DARWIN_ARM64 DARWIN_X86_64; do
            echo "UV_URL_$key=$SERVER/uv.tar.gz"
            echo "UV_SHA256_$key=$sha"
        done
    } > "$dir/manifest.env"
}

start_server() {
    local port
    port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
    (cd "$FIXTURES" && exec python3 -m http.server "$port" --bind 127.0.0.1 >/dev/null 2>&1) &
    SERVER_PID=$!
    SERVER="http://127.0.0.1:$port"
    for _ in $(seq 1 50); do
        python3 -c "import urllib.request; urllib.request.urlopen('$SERVER/', timeout=1)" 2>/dev/null && return 0
        sleep 0.1
    done
    echo "FATAL: fixture http server did not start" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

new_sandbox() {
    SB="$TESTS_TMP/sb-$1"
    SB_HOME="$SB/home"
    SB_ROOT="$SB/root"
    SB_OUT="$SB/out.log"
    mkdir -p "$SB_HOME"
}

# run_install [VAR=VAL ...] — real install.sh, detached from any tty
run_install() {
    local envs=("HOME=$SB_HOME" "VASTAI_INSTALL_DIR=$SB_ROOT" "VASTAI_CLI_BASE_URL=$SERVER/good" "SHELL=/bin/bash" "$@")
    [ -z "$HAVE_SETSID" ] && envs+=("VASTAI_NO_MODIFY_PATH=1")
    if [ -n "$HAVE_SETSID" ]; then
        setsid -w env "${envs[@]}" bash "$INSTALL_SH" >"$SB_OUT" 2>&1 </dev/null
    else
        env "${envs[@]}" bash "$INSTALL_SH" >"$SB_OUT" 2>&1 </dev/null
    fi
}

assert() { # assert DESC command...
    local desc="$1"; shift
    "$@" || { echo "    assert failed: $desc"; return 1; }
}

out_contains() { grep -q "$1" "$SB_OUT"; }
out_lacks()    { ! grep -qa "$1" "$SB_OUT"; }

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

test_fresh_install() { # happy path: fixed env symlink, runnable CLI, managed layout
    new_sandbox fresh
    run_install || { cat "$SB_OUT"; return 1; }
    assert "vastai symlink -> env bin" \
        [ "$(readlink "$SB_ROOT/bin/vastai")" = "../env/bin/vastai" ] &&
    assert "installed CLI runs" [ "$("$SB_ROOT/bin/vastai" --version)" = "1.2.3" ] &&
    assert "managed-install markers present (env/ + bin/uv)" \
        [ -d "$SB_ROOT/env" ] && [ -x "$SB_ROOT/bin/uv" ] &&
    assert "local bin link exists" [ -L "$SB_HOME/.local/bin/vastai" ]
}

test_pinned_reinstall() { # VASTAI_VERSION pin replaces env in place, no retention
    new_sandbox reinstall
    run_install || { cat "$SB_OUT"; return 1; }
    run_install VASTAI_VERSION=0.9.9 || { cat "$SB_OUT"; return 1; }
    assert "pinned version live" [ "$("$SB_ROOT/bin/vastai" --version)" = "0.9.9" ] &&
    assert "single active install, no version retention" [ ! -e "$SB_ROOT/versions" ] &&
    assert "no leftover temp env" [ ! -e "$SB_ROOT/.env.new" ]
}

test_wheel_url_install() { # latest installs the manifest's hash-pinned release wheel
    new_sandbox wheelurl
    write_manifest wheelurl 1.2.3 "" \
        "http://release.invalid/v1.2.3/vastai-1.2.3-py3-none-any.whl" "cafe123"
    run_install "VASTAI_CLI_BASE_URL=$SERVER/wheelurl" || { cat "$SB_OUT"; return 1; }
    assert "uv received the URL+sha spec" \
        [ "$("$SB_ROOT/bin/vastai" --version)" = "vastai @ http://release.invalid/v1.2.3/vastai-1.2.3-py3-none-any.whl#sha256=cafe123" ]
}

test_wheel_url_pin_fallback() { # a pinned version must ignore latest's wheel URL
    new_sandbox wheelpin
    write_manifest wheelpin 1.2.3 "" \
        "http://release.invalid/v1.2.3/vastai-1.2.3-py3-none-any.whl" "cafe123"
    run_install "VASTAI_CLI_BASE_URL=$SERVER/wheelpin" VASTAI_VERSION=0.9.9 \
        || { cat "$SB_OUT"; return 1; }
    assert "pin used the plain version spec" \
        [ "$("$SB_ROOT/bin/vastai" --version)" = "0.9.9" ]
}

test_checksum_abort() { # tampered artifact -> abort with zero residue
    new_sandbox badsha
    write_manifest badsha 1.2.3 "$(printf 'a%.0s' $(seq 64))"
    run_install "VASTAI_CLI_BASE_URL=$SERVER/badsha" && { echo "    expected failure"; return 1; }
    assert "names the mismatch" out_contains "checksum mismatch for uv" &&
    assert "no install root created" [ ! -e "$SB_ROOT" ]
}

test_truncation_guard() { # partial download executes nothing (main()-last)
    new_sandbox trunc
    local size n
    size="$(wc -c < "$INSTALL_SH")"
    for n in 200 $((size * 2 / 5)) $((size * 19 / 20)); do
        head -c "$n" "$INSTALL_SH" | env HOME="$SB_HOME" VASTAI_INSTALL_DIR="$SB_ROOT" \
            VASTAI_CLI_BASE_URL="$SERVER/good" bash >"$SB_OUT" 2>&1 </dev/null
        assert "cut at $n/$size bytes: no side effects" \
            [ ! -e "$SB_ROOT" ] || return 1
    done
}

test_glibc_floor() { # below the glibc floor -> clean abort to pip, zero residue
    new_sandbox glibc_floor
    # The gate only applies to glibc; musl/Darwin skip it. On a glibc host, an
    # impossibly high floor forces the bail without needing an ancient distro.
    case "$(uname -s)" in Darwin*) echo "    (skipped: Darwin host)"; return 0 ;; esac
    if ls /lib/ld-musl-* >/dev/null 2>&1; then echo "    (skipped: musl host)"; return 0; fi
    run_install VASTAI_GLIBC_FLOOR=99.0 && { echo "    expected failure below floor"; return 1; }
    assert "names the required floor" out_contains "older than the required 99.0" &&
    assert "points at pip" out_contains "pip install vastai" &&
    assert "no install root created" [ ! -e "$SB_ROOT" ]
}

test_rc_safety() { # never edits shell rc non-interactively; rc line idempotent
    new_sandbox rc
    run_install VASTAI_NO_MODIFY_PATH=1 || { cat "$SB_OUT"; return 1; }
    assert "prints rc instructions" out_contains "add this line to your shell rc" &&
    assert "no bashrc created" [ ! -e "$SB_HOME/.bashrc" ] || return 1

    new_sandbox rc2
    printf '[ -f "%s/env.sh" ] && . "%s/env.sh"  # vastai shell setup\n' "$SB_ROOT" "$SB_ROOT" > "$SB_HOME/.bashrc"
    cp "$SB_HOME/.bashrc" "$SB/before"
    run_install || { cat "$SB_OUT"; return 1; }
    assert "rc untouched when line present" cmp -s "$SB_HOME/.bashrc" "$SB/before" &&
    assert "no setup instructions when already configured" out_lacks "To finish setup"
}

test_env_sh() { # env.sh carries PATH precedence + completion for both shells
    new_sandbox envsh
    run_install || { cat "$SB_OUT"; return 1; }
    assert "env.sh generated" [ -s "$SB_ROOT/env.sh" ] &&
    assert "prepends .local/bin unless already first" grep -q 'export PATH=' "$SB_ROOT/env.sh" &&
    assert "sources bash completion" grep -q 'vastai-completion.bash' "$SB_ROOT/env.sh" &&
    assert "sources zsh completion" grep -q 'vastai-completion.zsh' "$SB_ROOT/env.sh"
}

test_pip_shadowing() { # pip vastai earlier in PATH -> warning; sourcing env.sh out-ranks it
    new_sandbox pipshadow
    mkdir -p "$SB/pipbin" "$SB_HOME/.local/bin"
    printf '#!/bin/sh\necho 1.0.13\n' > "$SB/pipbin/vastai"
    chmod +x "$SB/pipbin/vastai"
    run_install "PATH=$SB/pipbin:$SB_HOME/.local/bin:$PATH" || { cat "$SB_OUT"; return 1; }
    local resolved
    resolved="$(env "PATH=$SB/pipbin:$SB_HOME/.local/bin:/usr/bin:/bin" HOME="$SB_HOME" \
        bash -c ". '$SB_ROOT/env.sh'; command -v vastai" 2>/dev/null)"
    assert "detects the foreign vastai" out_contains "another vastai is on your PATH" &&
    assert "prints the env.sh line for manual setup" out_contains "env.sh" &&
    assert "sourcing env.sh out-ranks the pip vastai" [ "$resolved" = "$SB_HOME/.local/bin/vastai" ] &&
    assert "never advises uninstalling the pip package (it may be the SDK)" \
        out_lacks "pip uninstall"
}

test_pip_shadowing_quiet() { # rc update resolves coexistence -> no warning, just the use-it-now hint
    new_sandbox pipquiet
    command -v script >/dev/null 2>&1 || { echo "    (skipped: no script(1))"; return 0; }
    mkdir -p "$SB/pipbin" "$SB_HOME/.local/bin"
    printf '#!/bin/sh\necho 1.0.13\n' > "$SB/pipbin/vastai"
    chmod +x "$SB/pipbin/vastai"
    # A pty lets the installer write the rc line, settling precedence — no warning.
    # PATH is pinned to sandbox dirs + system bins so the pip fake outranks ours.
    local cmd=(env "HOME=$SB_HOME" "VASTAI_INSTALL_DIR=$SB_ROOT" \
        "VASTAI_CLI_BASE_URL=$SERVER/good" "SHELL=/bin/bash" \
        "PATH=$SB/pipbin:$SB_HOME/.local/bin:/usr/bin:/bin" /bin/bash "$INSTALL_SH")
    case "$(uname -s)" in
        Darwin*) script -q /dev/null "${cmd[@]}" >"$SB_OUT" 2>&1 </dev/null ;;
        *)       script -qec "${cmd[*]}" /dev/null >"$SB_OUT" 2>&1 </dev/null ;;
    esac
    assert "rc gained the env.sh line" grep -q 'env\.sh' "$SB_HOME/.bashrc" &&
    assert "no coexistence warning once resolved" out_lacks "another vastai" &&
    assert "current-shell hint printed" out_contains "Use it now"
}

test_pip_shadowing_rerun() { # re-run with new shadowing: rc line idempotent, no spurious warning
    new_sandbox piprerun
    command -v script >/dev/null 2>&1 || { echo "    (skipped: no script(1))"; return 0; }
    mkdir -p "$SB/pipbin" "$SB_HOME/.local/bin" "$SB_HOME/dotfiles"
    # .bashrc as a symlink (dotfile-manager layout): the append must write through it.
    touch "$SB_HOME/dotfiles/bashrc"
    ln -s dotfiles/bashrc "$SB_HOME/.bashrc"
    local cmd=(env "HOME=$SB_HOME" "VASTAI_INSTALL_DIR=$SB_ROOT" \
        "VASTAI_CLI_BASE_URL=$SERVER/good" "SHELL=/bin/bash" \
        "PATH=$SB_HOME/.local/bin:/usr/bin:/bin" /bin/bash "$INSTALL_SH")
    case "$(uname -s)" in
        Darwin*) script -q /dev/null "${cmd[@]}" >"$SB_OUT" 2>&1 </dev/null ;;
        *)       script -qec "${cmd[*]}" /dev/null >"$SB_OUT" 2>&1 </dev/null ;;
    esac
    assert "rc gained the env.sh line" grep -q 'env\.sh' "$SB_HOME/.bashrc" || return 1
    # A pip vastai now outranks ours: the re-run is a quiet no-op (env.sh wins at shell startup).
    printf '#!/bin/sh\necho 1.0.13\n' > "$SB/pipbin/vastai"
    chmod +x "$SB/pipbin/vastai"
    cp "$SB_HOME/dotfiles/bashrc" "$SB/before"
    local cmd2=(env "HOME=$SB_HOME" "VASTAI_INSTALL_DIR=$SB_ROOT" \
        "VASTAI_CLI_BASE_URL=$SERVER/good" "SHELL=/bin/bash" \
        "PATH=$SB/pipbin:$SB_HOME/.local/bin:/usr/bin:/bin" /bin/bash "$INSTALL_SH")
    case "$(uname -s)" in
        Darwin*) script -q /dev/null "${cmd2[@]}" >"$SB_OUT" 2>&1 </dev/null ;;
        *)       script -qec "${cmd2[*]}" /dev/null >"$SB_OUT" 2>&1 </dev/null ;;
    esac
    assert "re-run leaves the rc untouched" cmp -s "$SB_HOME/dotfiles/bashrc" "$SB/before" &&
    assert "rc line present exactly once" [ "$(grep -c 'env\.sh' "$SB_HOME/.bashrc")" -eq 1 ] &&
    assert "rc symlink survives" [ -L "$SB_HOME/.bashrc" ] &&
    assert "no spurious warning when rc already resolves precedence" out_lacks "another vastai" &&
    assert "use-it-now hint printed for the shadowed shell" out_contains "Use it now"
}

test_completion_files_generated() { # static completion scripts precomputed under share/
    new_sandbox compgen
    run_install || { cat "$SB_OUT"; return 1; }
    assert "bash completion file present" [ -s "$SB_ROOT/share/vastai-completion.bash" ] &&
    assert "zsh completion file present" [ -s "$SB_ROOT/share/vastai-completion.zsh" ] &&
    assert "env.sh sources the static file, not a per-startup eval" \
        grep -q 'vastai-completion' "$SB_ROOT/env.sh" &&
    assert "no per-startup register-python-argcomplete eval" \
        [ "$(grep -c 'eval.*register-python-argcomplete' "$SB_ROOT/env.sh")" -eq 0 ]
}

test_tty_install() { # interactive install (stderr on a pty) must survive old bash
    # install.sh empties its pyquiet array at a TTY ([ -t 2 ]), and on bash
    # < 4.4 expanding an empty array under `set -u` is fatal ("pyquiet[@]:
    # unbound variable") — macOS's stock /bin/bash is 3.2. The other scenarios
    # never hit this: they run detached from any tty, so the array stays
    # non-empty. Runs the real installer on a pty via script(1) under
    # ${VASTAI_TEST_TTY_BASH:-/bin/bash}; the regression guarantee comes from
    # hosts whose /bin/bash predates 4.4 (the macOS leg of installer CI).
    new_sandbox tty
    command -v script >/dev/null 2>&1 || { echo "    (skipped: no script(1))"; return 0; }
    local tty_bash="${VASTAI_TEST_TTY_BASH:-/bin/bash}"
    local cmd=(env "HOME=$SB_HOME" "VASTAI_INSTALL_DIR=$SB_ROOT" \
        "VASTAI_CLI_BASE_URL=$SERVER/good" "SHELL=/bin/bash" \
        "VASTAI_NO_MODIFY_PATH=1" "$tty_bash" "$INSTALL_SH")
    case "$(uname -s)" in
        Darwin*) script -q /dev/null "${cmd[@]}" >"$SB_OUT" 2>&1 </dev/null ;;
        # util-linux script wants one string; sandbox paths contain no spaces.
        *)       script -qec "${cmd[*]}" /dev/null >"$SB_OUT" 2>&1 </dev/null ;;
    esac
    assert "no set -u explosion at a TTY" out_lacks "unbound variable" &&
    assert "install completed" out_contains "vastai 1.2.3 installed" &&
    assert "installed CLI runs" [ "$("$SB_ROOT/bin/vastai" --version)" = "1.2.3" ]
}

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_TESTS=(fresh_install pinned_reinstall wheel_url_install wheel_url_pin_fallback checksum_abort truncation_guard glibc_floor rc_safety env_sh pip_shadowing pip_shadowing_quiet pip_shadowing_rerun completion_files_generated tty_install)
# No "${@:-...}": expanding $@ with zero args under set -u is itself fatal on
# old bash, and this harness must run under macOS's stock bash 3.2 (see
# test_tty_install).
if [ "$#" -gt 0 ]; then SELECTED=("$@"); else SELECTED=("${ALL_TESTS[@]}"); fi

mkdir -p "$FIXTURES"
start_server
build_fake_uv
write_manifest good 1.2.3

echo "install.sh hermetic tests (fixtures at $SERVER)"
for t in "${SELECTED[@]}"; do
    if "test_$t"; then
        echo "PASS $t"
        PASS=$((PASS + 1))
    else
        echo "FAIL $t  (output below)"
        sed 's/^/    | /' "$SB_OUT" 2>/dev/null
        FAIL=$((FAIL + 1))
    fi
done

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
