#!/usr/bin/env bash
# Vast.ai CLI installer.
#
#   curl -fsSL https://vast.ai/install.sh | bash
#
# Installs a self-contained vastai CLI following the XDG Base Directory
# Specification (no Python required on the machine, no sudo): the program
# lives under $XDG_DATA_HOME/vastai (default ~/.local/share/vastai), state
# under $XDG_STATE_HOME/vastai (default ~/.local/state/vastai), and the
# binary is symlinked into ~/.local/bin. Nothing outside those directories is
# touched except one setup line in your shell rc (enabled by default at a
# real terminal; skip with --no-modify-path; never written non-interactively/CI).
# Design: install-design.md in https://github.com/vast-ai/vast-cli
#
# Options (env vars, or flags after `bash -s --`):
#   VASTAI_VERSION=1.2.3       install a specific version (default: latest)
#   VASTAI_INSTALL_DIR=DIR     install root (default: $XDG_DATA_HOME/vastai)
#   VASTAI_CLI_BASE_URL=URL    manifest base (default: https://vast.ai/cli)
#   VASTAI_NO_MODIFY_PATH=1    never edit shell rc files  (flag: --no-modify-path)
#   VASTAI_PIP_SPEC=...        what to install instead of vastai==VERSION
#                              (dev/CI only: e.g. a local wheel path)
#   VASTAI_GLIBC_FLOOR=2.31    minimum glibc; below this, bail to pip
#
# Uninstall:  rm -rf "$XDG_DATA_HOME/vastai" ~/.local/bin/vastai
#             (default XDG_DATA_HOME is ~/.local/share; use whatever
#             VASTAI_INSTALL_DIR/XDG_DATA_HOME you installed with, if
#             overridden. Config in ~/.config/vastai and cache/state are
#             left alone.)

set -euo pipefail

BASE_URL="${VASTAI_CLI_BASE_URL:-https://vast.ai/cli}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
ROOT="${VASTAI_INSTALL_DIR:-$XDG_DATA_HOME/vastai}"
LOCAL_BIN="$HOME/.local/bin"
NO_MODIFY_PATH="${VASTAI_NO_MODIFY_PATH:-}"
WORKDIR=""
RC_UPDATED=""
NEEDS_PATH_HINT=""

say()  { printf '  %s\n' "$*"; }
warn() { printf '  warning: %s\n' "$*" >&2; }
die()  { printf '  error: %s\n' "$*" >&2; exit 1; }

cleanup() { [ -n "$WORKDIR" ] && rm -rf "$WORKDIR"; }
trap cleanup EXIT

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

# download URL DEST [progress] — non-empty progress shows a bar (TTY only).
download() {
    local url="$1" dest="$2" progress="${3:-}"
    if command -v curl >/dev/null 2>&1; then
        local vflags=(-fsS)
        [ -n "$progress" ] && [ -t 2 ] && vflags=(-f --progress-bar)
        case "$url" in
            https://*) curl --proto '=https' --tlsv1.2 "${vflags[@]}" -L --retry 3 -o "$dest" "$url" ;;
            *)         curl "${vflags[@]}" -L --retry 3 -o "$dest" "$url" ;;
        esac
    elif command -v wget >/dev/null 2>&1; then
        local wflags=(-q)
        [ -n "$progress" ] && [ -t 2 ] && wflags=(-q --show-progress)
        wget "${wflags[@]}" -O "$dest" "$url"
    else
        die "need curl or wget to download files"
    fi
}

# sha256_of FILE
sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        die "need sha256sum or shasum to verify downloads"
    fi
}

# verify_sha FILE EXPECTED LABEL
verify_sha() {
    local actual
    actual="$(sha256_of "$1")"
    [ "$actual" = "$2" ] || die "checksum mismatch for $3 (expected $2, got $actual) — aborting, nothing was installed"
}

# manifest_get KEY  (from $WORKDIR/manifest.env; empty if absent)
manifest_get() {
    sed -n "s/^$1=//p" "$WORKDIR/manifest.env" | head -n 1 | tr -d '\r'
}

# link_swap TARGET LINK — atomic-replace a symlink
link_swap() {
    local tmp
    tmp="$(dirname "$2")/.$(basename "$2").tmp"
    rm -f "$tmp"
    ln -s "$1" "$tmp"
    mv -f "$tmp" "$2"
}

# Minimum glibc for the managed runtime. Ubuntu 20.04 / Debian 11 (2.31) work;
# older (18.04 = 2.27, CentOS 7 = 2.17) lack wheels for some deps under the
# pinned CPython, so those users are sent to pip rather than failing mid-build.
GLIBC_FLOOR="${VASTAI_GLIBC_FLOOR:-2.31}"

# is_musl — true on a musl libc system. Checks the ld-musl loader directly:
# musl's `ldd` exits non-zero on `--version`, so `set -o pipefail` would discard
# a successful grep (the loader check has no such hazard; ldd is a guarded fallback).
is_musl() {
    local f
    for f in /lib/ld-musl-*; do [ -e "$f" ] && return 0; done
    { ldd --version 2>&1 || true; } | grep -qi musl
}

# require_min_glibc — on glibc Linux, abort cleanly (point at pip) below the floor.
require_min_glibc() {
    local v smallest
    # Guard each probe with `|| true`: a missing getconf or a no-match grep must
    # leave $v empty (→ undetectable, don't block), never trip `set -e`/pipefail.
    v="$({ getconf GNU_LIBC_VERSION 2>/dev/null || true; } | awk '{print $NF}')"
    [ -n "$v" ] || v="$({ ldd --version 2>/dev/null || true; } | head -1 | grep -oE '[0-9]+\.[0-9]+' | tail -1 || true)"
    [ -n "$v" ] || return 0  # undetectable — don't block
    smallest="$(printf '%s\n%s\n' "$GLIBC_FLOOR" "$v" | sort -V | head -1)"
    if [ "$smallest" = "$v" ] && [ "$v" != "$GLIBC_FLOOR" ]; then
        die "glibc $v is older than the required $GLIBC_FLOOR (Ubuntu 20.04+/Debian 11+) — install with pip instead: pip install vastai"
    fi
}

detect_platform() {
    local os arch libc=""
    os="$(uname -s)"
    arch="$(uname -m)"
    case "$os" in
        Linux)  os="LINUX" ;;
        Darwin) os="DARWIN" ;;
        *) die "unsupported OS: $os — install with pip instead: pip install vastai" ;;
    esac
    case "$arch" in
        x86_64|amd64)  arch="X86_64" ;;
        aarch64|arm64) [ "$os" = "DARWIN" ] && arch="ARM64" || arch="AARCH64" ;;
        *) die "unsupported architecture: $arch — install with pip instead: pip install vastai" ;;
    esac
    # An x86_64 shell under Rosetta 2 reports the emulated arch; install the
    # native arm64 build instead. (sysctl key absent on Intel Macs → empty → no-op.)
    if [ "$os" = "DARWIN" ] && [ "$arch" = "X86_64" ] \
        && [ "$(sysctl -n sysctl.proc_translated 2>/dev/null || true)" = "1" ]; then
        arch="ARM64"
    fi
    if [ "$os" = "LINUX" ]; then
        if is_musl; then
            libc="_MUSL"
        else
            require_min_glibc
        fi
    fi
    PLATFORM_KEY="${os}_${arch}${libc}"
}

# is_interactive — is there a real terminal? (/dev/tty may exist yet be unopenable)
is_interactive() { ( : < /dev/tty > /dev/tty; ) 2>/dev/null; }

rc_file_for_shell() {
    case "$(basename "${SHELL:-}")" in
        zsh)  printf '%s\n' "$HOME/.zshrc" ;;
        bash) printf '%s\n' "$HOME/.bashrc" ;;
        *)    printf '%s\n' "" ;;
    esac
}

install_uv() {
    local url sha tarball
    url="$(manifest_get "UV_URL_$PLATFORM_KEY")"
    sha="$(manifest_get "UV_SHA256_$PLATFORM_KEY")"
    if [ -z "$url" ] || [ -z "$sha" ]; then
        die "no build available for your platform ($PLATFORM_KEY) — install with pip instead: pip install vastai"
    fi

    say "Downloading runtime..."
    tarball="$WORKDIR/uv.tar.gz"
    download "$url" "$tarball" progress
    verify_sha "$tarball" "$sha" "uv"

    mkdir -p "$WORKDIR/uv-extract"
    tar -xzf "$tarball" -C "$WORKDIR/uv-extract" \
        || die "could not unpack the runtime — tar+gzip required; install them or use pip: pip install vastai"
    # Locate the uv binary without depending on `find` (absent on minimal images
    # like amazonlinux:2023): the tarball is either uv-extract/uv or, more
    # commonly, uv-extract/<target-triple>/uv.
    local uv_bin="" cand
    for cand in "$WORKDIR"/uv-extract/uv "$WORKDIR"/uv-extract/*/uv; do
        [ -f "$cand" ] && { uv_bin="$cand"; break; }
    done
    [ -n "$uv_bin" ] || die "uv binary not found in downloaded archive"
    chmod +x "$uv_bin"
    # Nothing lands in $ROOT until the download has been verified.
    mkdir -p "$ROOT/bin"
    mv -f "$uv_bin" "$ROOT/bin/uv"
}

install_version() {
    local version="$1" python_pin="$2" wheel_url="${3:-}" wheel_sha="${4:-}"
    local envdir="$ROOT/current" newdir="$ROOT/.current.new"

    say "Installing vastai $version (Python $python_pin) → $ROOT"
    rm -rf "$newdir"
    export UV_PYTHON_INSTALL_DIR="$ROOT/python"
    export UV_PYTHON_PREFERENCE="only-managed"
    # Provision the managed CPython first — the slow, download-heavy step, so show
    # its progress at a TTY (quiet in CI). The venv build is then always quiet:
    # uv venv's own "Activate with: source .../.current.new/..." line is misleading
    # here — .current.new is renamed to current/ below, and vastai is a symlinked
    # CLI you run, never a venv you "activate".
    # ${arr[@]+...} guard: bash 3.2 (macOS default) treats an empty array as
    # unset under `set -u`, so a bare "${pyquiet[@]}" would abort the install.
    # --no-bin: the venv finds the interpreter via UV_PYTHON_INSTALL_DIR;
    # shims in ~/.local/bin would only add uv's misleading PATH warning.
    local pyquiet=(--quiet)
    [ -t 2 ] && pyquiet=()
    if ! "$ROOT/bin/uv" python install "$python_pin" --no-bin ${pyquiet[@]+"${pyquiet[@]}"}; then
        rm -rf "$newdir"
        die "could not provision the Python $python_pin runtime"
    fi
    # --relocatable: no hardcoded build path in shebangs (current/ is renamed into place).
    if ! "$ROOT/bin/uv" venv "$newdir" --python "$python_pin" --relocatable --quiet; then
        rm -rf "$newdir"
        die "could not set up the Python $python_pin runtime"
    fi
    # Latest installs the release wheel by URL, hash-verified against the
    # manifest — no PyPI index propagation window. A pin to any other
    # version falls back to PyPI (always long-published, so race-free).
    local spec="${VASTAI_PIP_SPEC:-vastai==$version}"
    if [ -z "${VASTAI_PIP_SPEC:-}" ] && [ -n "$wheel_url" ] && [ -n "$wheel_sha" ]; then
        spec="vastai @ ${wheel_url}#sha256=${wheel_sha}"
    fi
    local pipquiet=(--quiet)
    [ -t 2 ] && pipquiet=()
    if ! "$ROOT/bin/uv" pip install --python "$newdir/bin/python" ${pipquiet[@]+"${pipquiet[@]}"} "$spec"; then
        rm -rf "$newdir"
        die "could not install $spec (is the version correct?)"
    fi
    "$newdir/bin/vastai" --version >/dev/null \
        || { rm -rf "$newdir"; die "installed CLI failed its smoke test"; }

    # Swap built env in via renames; an interrupted build can't break the live env.
    rm -rf "$ROOT/.current.old"
    [ -d "$envdir" ] && mv "$envdir" "$ROOT/.current.old"
    mv "$newdir" "$envdir"
    rm -rf "$ROOT/.current.old"

    # Fixed-target symlinks (current/ path is constant); never retargeted on update.
    local name
    for name in vastai serve-vast-deployment register-python-argcomplete; do
        [ -e "$envdir/bin/$name" ] && link_swap "../current/bin/$name" "$ROOT/bin/$name"
    done
}

# generate_completions — precompute static completion scripts in $ROOT/share so
# the rc just sources a file (no register-python-argcomplete spawn per shell).
generate_completions() {
    local rpa="$ROOT/bin/register-python-argcomplete" sh out
    [ -x "$rpa" ] || return 0
    mkdir -p "$ROOT/share"
    for sh in bash zsh; do
        out="$ROOT/share/vastai-completion.$sh"
        if "$rpa" -s "$sh" vastai >"$out.tmp" 2>/dev/null && [ -s "$out.tmp" ]; then
            mv -f "$out.tmp" "$out"
        else
            rm -f "$out.tmp"
        fi
    done
}

# write_env_sh — $ROOT/env.sh, regenerated every install: PATH precedence + completion.
# The rc references it via one constant line, so rc files are append-only, never rewritten.
write_env_sh() {
    cat > "$ROOT/env.sh" <<EOF
# vastai shell setup — regenerated by the installer; do not edit.
case ":\$PATH:" in ":$LOCAL_BIN:"*) ;; *) export PATH="$LOCAL_BIN:\$PATH" ;; esac
[ -n "\${BASH_VERSION:-}" ] && [ -f "$ROOT/share/vastai-completion.bash" ] && . "$ROOT/share/vastai-completion.bash"
[ -n "\${ZSH_VERSION:-}" ] && [ -f "$ROOT/share/vastai-completion.zsh" ] && . "$ROOT/share/vastai-completion.zsh"
true
EOF
}

setup_path() {
    mkdir -p "$LOCAL_BIN"
    link_swap "$ROOT/bin/vastai" "$LOCAL_BIN/vastai"
    write_env_sh

    # Hint "Use it now" whenever this shell wouldn't run our vastai (off PATH or outranked, e.g. by a pip install).
    local existing
    existing="$(command -v vastai 2>/dev/null || true)"
    case "$existing" in
        "$LOCAL_BIN/vastai"|"$ROOT/bin/vastai") ;;
        *) NEEDS_PATH_HINT=1 ;;
    esac

    local rc_file line
    rc_file="$(rc_file_for_shell)"
    line="[ -f \"$ROOT/env.sh\" ] && . \"$ROOT/env.sh\"  # vastai shell setup"
    if [ -n "$rc_file" ] && [ -f "$rc_file" ] && grep -qxF "$line" "$rc_file"; then
        # RC_UPDATED means "rc guarantees precedence", not "written this run" — else re-runs warn spuriously.
        RC_UPDATED=1
        return 0
    fi
    # Default-on, no prompt — but never edit rc under --no-modify-path or without a TTY (CI/pipes).
    if [ -z "$NO_MODIFY_PATH" ] && [ -n "$rc_file" ] && is_interactive; then
        printf '\n%s\n' "$line" >> "$rc_file"
        RC_UPDATED=1
    else
        say "To finish setup, add this line to your shell rc file:"
        printf '\n%s\n\n' "$line"
    fi
}

check_pip_coexistence() {
    local existing
    existing="$(command -v vastai 2>/dev/null || true)"
    case "$existing" in
        ""|"$LOCAL_BIN/vastai"|"$ROOT/bin/vastai") return 0 ;;
    esac
    # The rc update already put ours first — resolved, nothing to say.
    # Warn only when precedence couldn't be guaranteed (no-modify-path,
    # non-interactive, unknown shell).
    [ -n "$RC_UPDATED" ] && return 0
    warn "another vastai is on your PATH at $existing."
    warn "put $LOCAL_BIN first in PATH so this one wins."
}

main() {
    for arg in "$@"; do
        case "$arg" in
            --no-modify-path) NO_MODIFY_PATH=1 ;;
            --version) die "pass a version with VASTAI_VERSION=x.y.z instead" ;;
            *) die "unknown option: $arg" ;;
        esac
    done

    need_cmd uname
    need_cmd tar
    need_cmd mktemp
    detect_platform
    WORKDIR="$(mktemp -d)"

    download "$BASE_URL/manifest.env" "$WORKDIR/manifest.env" \
        || die "could not fetch release manifest from $BASE_URL/manifest.env"
    local schema latest python_pin version
    schema="$(manifest_get SCHEMA)"
    [ "$schema" = "1" ] || die "manifest schema '$schema' not understood by this installer; get the latest from https://vast.ai/install.sh"
    latest="$(manifest_get LATEST)"
    python_pin="$(manifest_get PYTHON)"
    if [ -z "$latest" ] || [ -z "$python_pin" ]; then
        die "malformed release manifest"
    fi
    version="${VASTAI_VERSION:-$latest}"

    # The wheel URL/sha are truthful only for the version they describe
    # (LATEST) — used whenever that's what we're installing, pinned or not.
    local wheel_url="" wheel_sha=""
    if [ "$version" = "$latest" ]; then
        wheel_url="$(manifest_get WHEEL_URL)"
        wheel_sha="$(manifest_get WHEEL_SHA256)"
    fi

    install_uv
    install_version "$version" "$python_pin" "$wheel_url" "$wheel_sha"
    generate_completions
    setup_path
    check_pip_coexistence

    printf '\n'
    say "vastai $version installed to $ROOT"
    if [ -n "$RC_UPDATED" ] && [ -n "$NEEDS_PATH_HINT" ]; then
        say "  Use it now:   start a new shell, or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
    say "  Get started:  vastai set api-key YOUR_API_KEY   (https://cloud.vast.ai/manage-keys/?tab=api-keys)"
    say "  All commands: vastai --help"
    say "  Update later: vastai update"
    if [ -n "$RC_UPDATED" ]; then
        say "  Tab completion: start a new shell, then type 'vastai <TAB>'"
    fi
}

main "$@"
