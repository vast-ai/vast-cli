#!/usr/bin/env bash
# Vast.ai CLI installer.
#
#   curl -fsSL https://vast.ai/install.sh | bash
#
# Installs a self-contained vastai CLI into ~/.vastai (no Python required on
# the machine, no sudo, nothing outside ~/.vastai and ~/.local/bin is touched
# except an optional, consent-gated PATH line in your shell rc).
# Design: install-design.md in https://github.com/vast-ai/vast-cli
#
# Options (env vars, or flags after `bash -s --`):
#   VASTAI_VERSION=1.2.3       install a specific version (default: latest)
#   VASTAI_INSTALL_DIR=DIR     install root (default: ~/.vastai)
#   VASTAI_CLI_BASE_URL=URL    manifest base (default: https://vast.ai/cli)
#   VASTAI_NO_MODIFY_PATH=1    never edit shell rc files  (flag: --no-modify-path)
#   VASTAI_PIP_SPEC=...        what to install instead of vastai==VERSION
#                              (dev/CI only: e.g. a local wheel path)
#
# Uninstall:  rm -rf ~/.vastai ~/.local/bin/vastai

set -euo pipefail

BASE_URL="${VASTAI_CLI_BASE_URL:-https://vast.ai/cli}"
ROOT="${VASTAI_INSTALL_DIR:-$HOME/.vastai}"
LOCAL_BIN="$HOME/.local/bin"
NO_MODIFY_PATH="${VASTAI_NO_MODIFY_PATH:-}"
WORKDIR=""

say()  { printf 'vastai-install: %s\n' "$*"; }
warn() { printf 'vastai-install: warning: %s\n' "$*" >&2; }
die()  { printf 'vastai-install: error: %s\n' "$*" >&2; exit 1; }

cleanup() { [ -n "$WORKDIR" ] && rm -rf "$WORKDIR"; }
trap cleanup EXIT

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

# download URL DEST
download() {
    if command -v curl >/dev/null 2>&1; then
        case "$1" in
            https://*) curl --proto '=https' --tlsv1.2 -fsSL --retry 3 -o "$2" "$1" ;;
            *)         curl -fsSL --retry 3 -o "$2" "$1" ;;
        esac
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$2" "$1"
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
    if [ "$os" = "LINUX" ] && command -v ldd >/dev/null 2>&1 \
        && ldd --version 2>&1 | grep -qi musl; then
        libc="_MUSL"
    fi
    PLATFORM_KEY="${os}_${arch}${libc}"
}

# is_interactive — can we prompt? (/dev/tty may exist yet be unopenable)
is_interactive() { ( : < /dev/tty > /dev/tty; ) 2>/dev/null; }

# ask_yn PROMPT — returns 0 on yes
ask_yn() {
    local reply
    printf '%s [y/N] ' "$1" > /dev/tty
    read -r reply < /dev/tty || reply=""
    case "$reply" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

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

    say "Downloading runtime bootstrap..."
    tarball="$WORKDIR/uv.tar.gz"
    download "$url" "$tarball"
    verify_sha "$tarball" "$sha" "uv"

    mkdir -p "$WORKDIR/uv-extract"
    tar -xzf "$tarball" -C "$WORKDIR/uv-extract"
    local uv_bin
    uv_bin="$(find "$WORKDIR/uv-extract" -type f -name uv | head -n 1)"
    [ -n "$uv_bin" ] || die "uv binary not found in downloaded archive"
    chmod +x "$uv_bin"
    # Nothing lands in $ROOT until the download has been verified.
    mkdir -p "$ROOT/bin"
    mv -f "$uv_bin" "$ROOT/bin/uv"
}

install_version() {
    local version="$1" python_pin="$2" envdir="$ROOT/env" newdir="$ROOT/.env.new"

    say "Installing vastai $version (Python $python_pin, isolated in $ROOT)..."
    rm -rf "$newdir"
    export UV_PYTHON_INSTALL_DIR="$ROOT/python"
    export UV_PYTHON_PREFERENCE="only-managed"
    # --relocatable: shebangs must not hardcode the build path (env is renamed into place).
    if ! "$ROOT/bin/uv" venv "$newdir" --python "$python_pin" --relocatable --quiet; then
        rm -rf "$newdir"
        die "could not set up the Python $python_pin runtime"
    fi
    local spec="${VASTAI_PIP_SPEC:-vastai==$version}"
    if ! "$ROOT/bin/uv" pip install --python "$newdir/bin/python" --quiet "$spec"; then
        rm -rf "$newdir"
        die "could not install $spec (is the version correct?)"
    fi
    "$newdir/bin/vastai" --version >/dev/null \
        || { rm -rf "$newdir"; die "installed CLI failed its smoke test"; }

    # Swap built env in via renames; an interrupted build can't break the live env.
    rm -rf "$ROOT/.env.old"
    [ -d "$envdir" ] && mv "$envdir" "$ROOT/.env.old"
    mv "$newdir" "$envdir"
    rm -rf "$ROOT/.env.old"

    # Fixed-target symlinks (env/ path is constant); never retargeted on update.
    local name
    for name in vastai serve-vast-deployment register-python-argcomplete; do
        [ -e "$envdir/bin/$name" ] && link_swap "../env/bin/$name" "$ROOT/bin/$name"
    done
}

# state.json — advisory install info for `vastai update` (channel + coordination
# context). NOT used for managed-install detection (that's structural). A fresh
# install always starts on the stable channel; switch with `vastai update --channel`.
write_state() {
    local version="$1"
    cat > "$ROOT/state.json" <<EOF
{
  "schema": 1,
  "channel": "stable",
  "version": "$version",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
}

setup_path() {
    mkdir -p "$LOCAL_BIN"
    link_swap "$ROOT/bin/vastai" "$LOCAL_BIN/vastai"

    case ":$PATH:" in
        *":$LOCAL_BIN:"*) PATH_OK=1 ;;
        *) PATH_OK="" ;;
    esac
    [ -n "$PATH_OK" ] && return 0

    local rc_file marker block
    rc_file="$(rc_file_for_shell)"
    marker="# >>> vastai installer >>>"
    block="$marker
export PATH=\"\$HOME/.local/bin:\$PATH\"
eval \"\$('$ROOT/bin/register-python-argcomplete' vastai 2>/dev/null)\" 2>/dev/null || true
# <<< vastai installer <<<"

    if [ -n "$rc_file" ] && [ -f "$rc_file" ] && grep -qF "$marker" "$rc_file"; then
        return 0  # already configured; takes effect in new shells
    fi

    if [ -z "$NO_MODIFY_PATH" ] && [ -n "$rc_file" ] && is_interactive \
        && ask_yn "Add $LOCAL_BIN to PATH and enable tab completion in $rc_file?"; then
        printf '\n%s\n' "$block" >> "$rc_file"
        say "Updated $rc_file (takes effect in new shells)."
    else
        say "To finish setup, add this to your shell rc file:"
        printf '\n%s\n\n' "$block"
    fi
}

check_pip_coexistence() {
    local existing
    existing="$(command -v vastai 2>/dev/null || true)"
    case "$existing" in
        ""|"$LOCAL_BIN/vastai"|"$ROOT/bin/vastai") return 0 ;;
    esac
    warn "another vastai is on your PATH at $existing (likely a pip install)."
    warn "whichever comes first in PATH wins; remove the old one with: pip uninstall vastai"
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

    install_uv
    install_version "$version" "$python_pin"
    write_state "$version"
    setup_path
    check_pip_coexistence

    say ""
    say "vastai $version installed to $ROOT"
    say "  Get started:  vastai set api-key YOUR_API_KEY   (https://cloud.vast.ai/manage-keys/)"
    say "  Update later: vastai update"
}

main "$@"
