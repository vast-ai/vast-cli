#!/usr/bin/env bash
# Smoke-test scripts/install.sh across an OS matrix in throwaway containers.
# Mirrors .github/workflows/installer-ci.yml os-matrix (minus macOS, which needs
# a real runner). Runs THIS checkout's install.sh against the live release
# manifest, then confirms the installed CLI runs.
#
#   scripts/tests/test-install-matrix.sh              # all linux variants
#   scripts/tests/test-install-matrix.sh alpine       # one variant
#   TTY=1 scripts/tests/test-install-matrix.sh debian # interactive (test PATH/completion prompt)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BASE="https://github.com/vast-ai/vast-cli/releases/latest/download"

# name|image|prep  (tar + coreutils sha256sum/mktemp/uname assumed present in
# every base image; prep only needs to ensure curl is installed)
MATRIX=(
  # --- musl ---
  "alpine|alpine:latest|apk add --no-cache bash curl"
  # --- Debian / Ubuntu (glibc) ---
  "debian-slim|debian:stable-slim|apt-get update -qq && apt-get install -y -qq curl ca-certificates"
  "debian12|debian:12-slim|apt-get update -qq && apt-get install -y -qq curl ca-certificates"
  "ubuntu2004|ubuntu:20.04|apt-get update -qq && apt-get install -y -qq curl ca-certificates"  # glibc floor (2.31)
  "ubuntu2204|ubuntu:22.04|apt-get update -qq && apt-get install -y -qq curl ca-certificates"
  "ubuntu2404|ubuntu:24.04|apt-get update -qq && apt-get install -y -qq curl ca-certificates"
  # --- RHEL family (glibc) --- curl-minimal/ca-certs preinstalled; add curl only if absent
  "fedora|fedora:latest|command -v curl >/dev/null 2>&1 || dnf install -y -q curl"
  "rocky9|rockylinux:9|command -v curl >/dev/null 2>&1 || dnf install -y -q curl"
  "alma9|almalinux:9|command -v curl >/dev/null 2>&1 || dnf install -y -q curl"
  "amazonlinux2023|amazonlinux:2023|dnf install -y -q tar gzip"  # minimal image lacks tar+gzip (the unpacker)
  # --- rolling / other ---
  "arch|archlinux:latest|pacman -Sy --noconfirm --needed curl"
  "opensuse-leap|opensuse/leap:latest|zypper -n install curl"
)

SELECT="${1:-}"
DOCKER_FLAGS=(--rm)
[ -n "${TTY:-}" ] && DOCKER_FLAGS+=(-it)

pass=0 fail=0
for row in "${MATRIX[@]}"; do
  IFS='|' read -r name image prep <<<"$row"
  [ -n "$SELECT" ] && [ "$SELECT" != "$name" ] && continue
  echo "==================== $name ($image) ===================="
  if docker run "${DOCKER_FLAGS[@]}" -v "$REPO:/repo" -w /repo \
      -e VASTAI_CLI_BASE_URL="$BASE" -e VASTAI_NO_MODIFY_PATH="${TTY:+}${TTY:-1}" \
      "$image" sh -c "$prep
        bash scripts/install.sh
        \"\$HOME/.vastai/bin/vastai\" --version"; then
    echo "PASS $name"; pass=$((pass+1))
  else
    echo "FAIL $name"; fail=$((fail+1))
  fi
done
echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
