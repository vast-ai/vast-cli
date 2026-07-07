#!/usr/bin/env python3
"""Attach installer assets to the GitHub Release for a Vast CLI release.

Runs in CI on a vX.Y.Z tag push (python-publish.yml), right after
`poetry publish --build` — so dist/ holds the exact bytes PyPI serves.
The deterministic core (manifest rendering) lives in make_manifest.py;
this wraps it with the Release steps (docs/install-design.md §13).

    python scripts/publish_release.py 1.0.14            # hash dist/ wheel → manifest → attach
    python scripts/publish_release.py 1.0.14 --dry-run  # print every action, touch nothing

The Release is created as a draft and published only once fully populated:
releases/latest ignores drafts, so installers never see a manifest whose
wheel isn't fetchable. Post-publish verification is the separate
verify_release_assets job; the manual break-glass runbook is in the docs.

stdlib only — must run on a bare CI python with no project deps installed.
Requires `gh` on PATH.
"""

import argparse
import glob
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
MAKE_MANIFEST = REPO_ROOT / "scripts" / "make_manifest.py"
PACKAGE = "vastai"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+([.\-+].+)?$")


class ReleaseError(Exception):
    pass


def log(msg):
    print(f"publish-release: {msg}", flush=True)


def run(cmd, *, dry, capture=False):
    """Run a command (or just print it under --dry-run)."""
    printable = " ".join(str(c) for c in cmd)
    if dry:
        log(f"[dry-run] {printable}")
        return None
    log(f"$ {printable}")
    try:
        return subprocess.run(
            [str(c) for c in cmd], check=True,
            capture_output=capture, text=True,
        )
    except FileNotFoundError:
        raise ReleaseError(f"required tool not found: {cmd[0]}")
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or "").strip() if capture else ""
        raise ReleaseError(f"command failed: {printable}" + (f"\n{detail}" if detail else ""))


def resolve_wheel(version, *, dry):
    """The wheel poetry just built/published, in dist/ — hash those exact bytes."""
    matches = sorted(glob.glob(str(REPO_ROOT / "dist" / f"{PACKAGE}-{version}-*.whl")))
    if matches:
        return matches[0]
    if dry:
        log(f"[dry-run] would hash dist/{PACKAGE}-{version}-*.whl")
        return f"dist/{PACKAGE}-{version}-<built>.whl"
    raise ReleaseError(f"no dist/{PACKAGE}-{version}-*.whl (run poetry publish --build first)")


def render_manifest(version, wheel, outdir, *, dry):
    run([sys.executable, MAKE_MANIFEST, "--version", version,
         "--wheel", wheel, "--out", outdir], dry=dry, capture=True)


def attach_release(tag, manifest_dir, wheel, *, dry):
    """Create the Release as a draft, upload all assets, then publish it.

    releases/latest ignores drafts, so installers never see a manifest whose
    wheel isn't fetchable, nor a half-populated latest release.
    """
    if dry:
        exists = False  # skip the gh probe: dry-run needs neither gh nor auth
    else:
        try:
            exists = subprocess.run(["gh", "release", "view", tag],
                                    capture_output=True, text=True).returncode == 0
        except FileNotFoundError:
            raise ReleaseError("required tool not found: gh")
    if not exists:
        run(["gh", "release", "create", tag, "--draft", "--title", tag,
             "--notes", f"{PACKAGE} {tag.lstrip('v')}", "--generate-notes"], dry=dry)
    else:
        log(f"release {tag} exists — updating assets")
    run(["gh", "release", "upload", tag, "--clobber",
         str(wheel),
         str(Path(manifest_dir) / "manifest.json"),
         str(Path(manifest_dir) / "manifest.env"),
         str(INSTALL_SH)], dry=dry)
    # No-op if already published (re-run); flips a fresh draft live.
    run(["gh", "release", "edit", tag, "--draft=false"], dry=dry)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version", help="release version, no leading v (e.g. 1.0.14)")
    ap.add_argument("--dry-run", action="store_true", help="print every action, change nothing")
    args = ap.parse_args()

    version, dry = args.version, args.dry_run
    tag = f"v{version}"
    if not VERSION_RE.match(version):
        ap.error(f"version {version!r} is not X.Y.Z[suffix]")

    try:
        wheel = resolve_wheel(version, dry=dry)
        log(f"hashing wheel: {wheel}")
        with tempfile.TemporaryDirectory() as workdir:
            render_manifest(version, wheel, workdir, dry=dry)
            attach_release(tag, workdir, wheel, dry=dry)
        log(f"done — {tag} assets attached" + (" (dry-run, nothing changed)" if dry else ""))
        return 0
    except ReleaseError as e:
        print(f"publish-release: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
