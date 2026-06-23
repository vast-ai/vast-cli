#!/usr/bin/env python3
"""Generate the CLI release manifest (manifest.json + manifest.env).

To be run after a release is published to PyPI (release-CI wiring lands in a
follow-up PR; until then run manually or via scripts/dev-install.sh):

    python scripts/make_manifest.py --version 1.3.0 --wheel dist/vastai-1.3.0-*.whl --out dist-manifest/

manifest.json is consumed by the (future) `vastai update` and passive version
check; manifest.env is the flat key=value rendering consumed by install.sh
(no JSON parser required on a bare machine). Both get attached to the GitHub
Release, which the vast.ai redirects serve via releases/latest/download/.

stdlib only — must run on a bare CI python with no project deps installed.
"""

import argparse
import glob
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1

# The Python minor every managed install runs on (docs/install-design.md).
PYTHON_PIN = "3.12"

# Pinned uv release used to bootstrap installs. Bump deliberately; the
# installer and `vastai update` only ever see the artifacts listed here.
UV_VERSION = "0.11.21"
UV_BASE = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}"

# manifest platform key -> uv release target triple
UV_TARGETS = {
    "linux-x86_64":       "x86_64-unknown-linux-gnu",
    "linux-x86_64-musl":  "x86_64-unknown-linux-musl",
    "linux-aarch64":      "aarch64-unknown-linux-gnu",
    "linux-aarch64-musl": "aarch64-unknown-linux-musl",
    "darwin-arm64":       "aarch64-apple-darwin",
    "darwin-x86_64":      "x86_64-apple-darwin",
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_uv_sha(target: str) -> str:
    """uv publishes <asset>.sha256 files containing '<hex>  <filename>'."""
    url = f"{UV_BASE}/uv-{target}.tar.gz.sha256"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode().split()[0]


def build_manifest(version: str, wheel_sha: str, channel: str) -> dict:
    uv_artifacts = {
        key: {
            "url": f"{UV_BASE}/uv-{target}.tar.gz",
            "sha256": fetch_uv_sha(target),
        }
        for key, target in UV_TARGETS.items()
    }
    return {
        "schema": SCHEMA,
        "channel": channel,
        "latest": version,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "install": {
            "type": "pypi-wheel",
            "package": "vastai",
            "python": PYTHON_PIN,
            "wheel_sha256": wheel_sha,
            "uv": {
                "version": UV_VERSION,
                "artifacts": uv_artifacts,
            },
        },
    }


def render_env(manifest: dict) -> str:
    """Flat rendering for install.sh: KEY=VALUE, platform keys upper_snake."""
    install = manifest["install"]
    lines = [
        f"SCHEMA={manifest['schema']}",
        f"CHANNEL={manifest['channel']}",
        f"LATEST={manifest['latest']}",
        f"PYTHON={install['python']}",
        f"WHEEL_SHA256={install['wheel_sha256']}",
        f"UV_VERSION={install['uv']['version']}",
    ]
    for key, art in install["uv"]["artifacts"].items():
        env_key = key.upper().replace("-", "_")
        lines.append(f"UV_URL_{env_key}={art['url']}")
        lines.append(f"UV_SHA256_{env_key}={art['sha256']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True, help="CLI version being released (no leading v)")
    ap.add_argument("--wheel", required=True, help="path (or glob) to the published vastai wheel")
    ap.add_argument("--channel", default="stable")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    wheels = sorted(glob.glob(args.wheel))
    if len(wheels) != 1:
        print(f"error: --wheel {args.wheel!r} matched {len(wheels)} files, need exactly 1", file=sys.stderr)
        return 1

    manifest = build_manifest(args.version, sha256_file(Path(wheels[0])), args.channel)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "manifest.env").write_text(render_env(manifest))
    print(f"wrote {out / 'manifest.json'} and {out / 'manifest.env'} for vastai {args.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
