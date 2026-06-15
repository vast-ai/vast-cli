#!/usr/bin/env python3
"""Publish a Vast CLI release: tag → manifest → attach Release assets → verify.

One orchestrator for both humans and CI (docs/install-design.md §13). The
deterministic core (manifest rendering) lives in make_manifest.py; this wraps
it with the release steps and the guardrails the manual runbook can't enforce
by itself.

    # local (manual window): tag, wait for PyPI, build+attach manifest, verify
    python scripts/publish_release.py 1.0.14

    # CI (on tag push): tag already pushed, wheel already in dist/
    python scripts/publish_release.py 1.0.14 --ci

    # see every action without doing anything
    python scripts/publish_release.py 1.0.14 --dry-run

Local vs --ci differ only in: who pushes the tag (you / the trigger), where the
wheel comes from (PyPI poll / dist/), and gh auth (your creds / GITHUB_TOKEN).

stdlib only — must run on a bare CI python with no project deps installed.
Requires `git`, `gh`, and `pip` on PATH; `bash` for the verify step.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
MAKE_MANIFEST = REPO_ROOT / "scripts" / "make_manifest.py"
PACKAGE = "vastai"
RELEASE_BASE_URL = "https://github.com/vast-ai/vast-cli/releases/latest/download"
PYPI_POLL_TIMEOUT_S = 15 * 60
PYPI_POLL_INTERVAL_S = 15

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+([.\-+].+)?$")


class ReleaseError(Exception):
    pass


def log(msg):
    print(f"publish-release: {msg}", flush=True)


def run(cmd, *, dry, capture=False, check=True, env=None):
    """Run a command (or just print it under --dry-run)."""
    printable = " ".join(str(c) for c in cmd)
    if dry:
        log(f"[dry-run] {printable}")
        return None
    log(f"$ {printable}")
    try:
        return subprocess.run(
            [str(c) for c in cmd], check=check, env=env,
            capture_output=capture, text=True,
        )
    except FileNotFoundError:
        raise ReleaseError(f"required tool not found: {cmd[0]}")
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or "").strip() if capture else ""
        raise ReleaseError(f"command failed: {printable}" + (f"\n{detail}" if detail else ""))


def confirm(prompt, *, assume_yes, dry):
    if assume_yes or dry:
        return True
    if not sys.stdin.isatty():
        raise ReleaseError(f"{prompt} (no TTY; pass --yes to proceed non-interactively)")
    return input(f"{prompt} [y/N] ").strip().lower() in ("y", "yes")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def check_clean_tree(dry):
    out = run(["git", "status", "--porcelain"], dry=False, capture=True)
    if out.stdout.strip():
        if dry:
            log("[dry-run] working tree is dirty (would abort in a real run)")
        else:
            raise ReleaseError("working tree is dirty — commit or stash before releasing")


def tag_exists(tag):
    local = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
                           capture_output=True, text=True)
    if local.returncode == 0:
        return True
    remote = subprocess.run(["git", "ls-remote", "--tags", "origin", tag],
                            capture_output=True, text=True)
    return bool(remote.stdout.strip())


def ensure_tag_pushed(tag, *, assume_yes, dry):
    """Create + push the tag (triggers the PyPI publish workflow). Idempotent."""
    if tag_exists(tag):
        log(f"{tag} already exists — skipping tag/push (re-run or CI trigger)")
        return
    if not confirm(f"Tag and push {tag}? This triggers the PyPI publish.",
                   assume_yes=assume_yes, dry=dry):
        raise ReleaseError("aborted before tagging")
    run(["git", "tag", tag], dry=dry)
    run(["git", "push", "origin", tag], dry=dry)


def wait_for_pypi(version, dry):
    """Poll PyPI until the version is downloadable."""
    url = f"https://pypi.org/pypi/{PACKAGE}/{version}/json"
    if dry:
        log(f"[dry-run] poll {url} until available")
        return
    log(f"waiting for {PACKAGE}=={version} on PyPI ...")
    start = time.monotonic()
    while True:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                if r.status == 200:
                    log(f"{PACKAGE}=={version} is live on PyPI")
                    return
        except Exception:
            pass
        if time.monotonic() - start > PYPI_POLL_TIMEOUT_S:
            raise ReleaseError(f"timed out waiting for {PACKAGE}=={version} on PyPI")
        time.sleep(PYPI_POLL_INTERVAL_S)


def resolve_wheel(version, workdir, *, ci, dry):
    """Return the path to the wheel to hash.

    --ci: the wheel poetry just built/published is in dist/ — hash those exact
    bytes. Local: download the published wheel from PyPI.
    """
    if ci:
        matches = sorted(glob.glob(str(REPO_ROOT / "dist" / f"{PACKAGE}-{version}-*.whl")))
        if matches:
            return matches[0]
        if dry:
            log(f"[dry-run] would hash dist/{PACKAGE}-{version}-*.whl")
            return f"dist/{PACKAGE}-{version}-<built>.whl"
        raise ReleaseError(f"--ci: no dist/{PACKAGE}-{version}-*.whl (run poetry publish --build first)")
    if dry:
        log(f"[dry-run] pip download {PACKAGE}=={version} into {workdir}")
        return str(Path(workdir) / f"{PACKAGE}-{version}-py3-none-any.whl")
    run(["pip", "download", f"{PACKAGE}=={version}", "--no-deps", "-d", workdir],
        dry=False, capture=True)
    matches = sorted(glob.glob(str(Path(workdir) / f"{PACKAGE}-{version}-*.whl")))
    if not matches:
        raise ReleaseError(f"could not download {PACKAGE}=={version} wheel from PyPI")
    return matches[0]


def render_manifest(version, wheel, outdir, *, dry):
    run([sys.executable, MAKE_MANIFEST, "--version", version,
         "--wheel", wheel, "--out", outdir], dry=dry, capture=True)


def attach_release(tag, manifest_dir, *, dry):
    """Create the Release (if missing) and upload the three assets."""
    if dry:
        log(f"[dry-run] gh release create/view {tag}; "
            f"gh release upload {tag} --clobber manifest.json manifest.env install.sh")
        return
    exists = subprocess.run(["gh", "release", "view", tag],
                            capture_output=True, text=True).returncode == 0
    if not exists:
        run(["gh", "release", "create", tag, "--title", tag,
             "--notes", f"{PACKAGE} {tag.lstrip('v')}"], dry=dry)
    else:
        log(f"release {tag} exists — updating assets")
    run(["gh", "release", "upload", tag, "--clobber",
         str(Path(manifest_dir) / "manifest.json"),
         str(Path(manifest_dir) / "manifest.env"),
         str(INSTALL_SH)], dry=dry)


def verify_install(version, *, dry):
    """Install from the just-published Release URL into a throwaway root."""
    if dry:
        log(f"[dry-run] install from {RELEASE_BASE_URL} and check --version == {version}")
        return
    with tempfile.TemporaryDirectory() as root:
        env = dict(os.environ,
                   VASTAI_CLI_BASE_URL=RELEASE_BASE_URL,
                   VASTAI_INSTALL_DIR=root,
                   VASTAI_NO_MODIFY_PATH="1")
        run(["bash", str(INSTALL_SH)], dry=False, env=env, capture=True)
        out = run([str(Path(root) / "bin" / "vastai"), "--version"], dry=False, capture=True)
        got = (out.stdout or "").strip()
        if version not in got:
            raise ReleaseError(f"verify failed: installed CLI reports {got!r}, expected {version}")
        log(f"verified: a fresh install from the Release reports {got}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version", help="release version, no leading v (e.g. 1.0.14)")
    ap.add_argument("--ci", action="store_true",
                    help="CI mode: tag already pushed, hash the wheel in dist/ (no PyPI poll)")
    ap.add_argument("--dry-run", action="store_true", help="print every action, change nothing")
    ap.add_argument("--yes", action="store_true", help="skip confirmation prompts")
    ap.add_argument("--skip-verify", action="store_true",
                    help="skip the post-publish install check (CI runs it as a separate matrix job)")
    args = ap.parse_args()

    version, dry, ci = args.version, args.dry_run, args.ci
    tag = f"v{version}"
    if not VERSION_RE.match(version):
        ap.error(f"version {version!r} is not X.Y.Z[suffix]")

    try:
        if ci:
            log(f"CI release for {tag} (tag already pushed; wheel from dist/)")
        else:
            check_clean_tree(dry)
            ensure_tag_pushed(tag, assume_yes=args.yes, dry=dry)
            wait_for_pypi(version, dry)

        with tempfile.TemporaryDirectory() as workdir:
            wheel = resolve_wheel(version, workdir, ci=ci, dry=dry)
            log(f"hashing wheel: {wheel}")
            render_manifest(version, wheel, workdir, dry=dry)
            if not confirm(f"Attach manifest + install.sh to GitHub Release {tag}?",
                           assume_yes=args.yes or ci, dry=dry):
                raise ReleaseError("aborted before publishing the Release")
            attach_release(tag, workdir, dry=dry)

        if args.skip_verify:
            log("skipping verify (--skip-verify)")
        else:
            verify_install(version, dry=dry)

        log(f"done — {tag} published" + (" (dry-run, nothing changed)" if dry else ""))
        return 0
    except ReleaseError as e:
        print(f"publish-release: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
