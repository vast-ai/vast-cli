#!/usr/bin/env bash
# Simulate the hosted https://vast.ai/install.sh end-to-end, locally.
#
#   scripts/dev-install.sh                       # install latest released version
#   scripts/dev-install.sh --from-source         # install a wheel built from this tree
#   VASTAI_VERSION=1.0.12 scripts/dev-install.sh # pin a version
#   scripts/dev-install.sh --no-modify-path      # other flags pass through
#
# Renders the same release manifest CI would publish (real uv checksums from
# GitHub), then runs scripts/install.sh against it via file:// — everything
# else is exactly the production path: installs to ~/.vastai, links
# ~/.local/bin/vastai, consent-gated PATH edit, real PyPI download.
#
# --from-source builds the working tree with poetry and installs that wheel
# through the same path, so unreleased features (e.g. `vastai update`) can be
# dogfooded. `vastai update` needs a manifest URL until vast.ai/cli is live:
#   python3 scripts/make_manifest.py --version X --wheel W --out DIR
#   python3 -m http.server 8901 --directory DIR &
#   VASTAI_MANIFEST_URL=http://127.0.0.1:8901/manifest.json vastai update --check
#
# Uninstall: rm -rf ~/.vastai ~/.local/bin/vastai

set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

from_source=""
passthrough=()
for arg in "$@"; do
    case "$arg" in
        --from-source) from_source=1 ;;
        *) passthrough+=("$arg") ;;
    esac
done

if [ -n "$from_source" ]; then
    echo "dev-install: building wheel from working tree..."
    rm -f "$repo"/dist/vastai-*.whl
    (cd "$repo" && poetry build --format wheel --quiet)
    wheel="$(find "$repo/dist" -name 'vastai-*.whl' -print -quit)"
    [ -n "$wheel" ] || { echo "dev-install: error: no wheel produced in dist/" >&2; exit 1; }
    # vastai-<version>-py3-none-any.whl
    version="$(basename "$wheel" | sed 's/^vastai-//; s/-py3-none-any\.whl$//')"
    export VASTAI_PIP_SPEC="$wheel"
else
    # Default to the latest released tag: that's what the hosted manifest will say.
    version="${VASTAI_VERSION:-$(git -C "$repo" describe --tags --abbrev=0 | sed 's/^v//')}"
    wheel="$tmp/dummy.whl"
    # install.sh never reads the wheel hash (uv verifies PyPI downloads itself),
    # so a dummy wheel is fine for manifest rendering here.
    touch "$wheel"
fi

python3 "$repo/scripts/make_manifest.py" \
    --version "$version" --wheel "$wheel" --out "$tmp" >/dev/null

echo "dev-install: simulating hosted installer for vastai $version (manifest in $tmp)"
VASTAI_CLI_BASE_URL="file://$tmp" VASTAI_VERSION="$version" \
    bash "$repo/scripts/install.sh" ${passthrough[0]+"${passthrough[@]}"}
