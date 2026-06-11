"""Self-update engine for the managed (curl | bash) CLI install.

Layout (docs/install-design.md): everything under $VASTAI_INSTALL_DIR
(default ~/.vastai) — a single active venv at env/, with bin/vastai a fixed
symlink into it, and install-receipt.json recording how the CLI was installed.
Updating rebuilds env/ in place (build temp → verify → swap); there is no
version retention. No receipt means pip owns the install and we never touch it.

The passive nudge is throttled to one manifest GET and one notice per 24h,
capped at 1s, and swallows every failure — the CLI must never get slower or
noisier because the manifest endpoint is unreachable.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from vastai.cli.util import DIRS, VERSION

DEFAULT_MANIFEST_URL = "https://vast.ai/cli/manifest.json"
INSTALL_SH_HINT = "curl -fsSL https://vast.ai/install.sh | bash"
PIP_UPGRADE_HINT = "pip install --upgrade vastai"

UPDATE_CHECK_FILE = os.path.join(DIRS['temp'], "update_check.json")
CHECK_INTERVAL_S = 24 * 60 * 60
NUDGE_TIMEOUT_S = 1.0

# Console scripts shipped in the wheel; each gets a swapped symlink in bin/.
MANAGED_BINARIES = ("vastai", "serve-vast-deployment", "register-python-argcomplete")


class UpdateError(Exception):
    """A self-update step failed; the current install is untouched."""


# ---------------------------------------------------------------------------
# Receipt / manifest / versions
# ---------------------------------------------------------------------------

def install_root() -> Path:
    return Path(os.environ.get("VASTAI_INSTALL_DIR") or Path.home() / ".vastai")


def read_receipt():
    """Install receipt dict, or None for non-managed (pip) installs."""
    try:
        with open(install_root() / "install-receipt.json") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def write_receipt(receipt: dict) -> None:
    path = install_root() / "install-receipt.json"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def fetch_manifest(timeout: float = 10.0) -> dict:
    url = os.environ.get("VASTAI_MANIFEST_URL") or DEFAULT_MANIFEST_URL
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        raise UpdateError(f"Could not fetch release manifest from {url}: {e}")
    if not isinstance(data, dict) or "latest" not in data:
        raise UpdateError(f"Malformed release manifest at {url}")
    if data.get("schema") != 1:
        raise UpdateError(
            f"Release manifest schema {data.get('schema')!r} is not supported "
            f"by this CLI version.\nRe-run the installer: {INSTALL_SH_HINT}"
        )
    return data


def version_key(v: str):
    """Sort key tolerant of dev/rc (below release), post (above), +local (ignored)."""
    v = (v or "").strip().lstrip("v").split("+", 1)[0]
    nums, extra = [], 0
    for part in v.split("."):
        if part.isdigit():
            nums.append(int(part))
            continue
        m = re.match(r"\d+", part)
        if m:
            nums.append(int(m.group()))
        extra = 1 if part.startswith("post") else -1
        break
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums), extra


def is_newer(candidate: str, current: str) -> bool:
    return version_key(candidate) > version_key(current)


# ---------------------------------------------------------------------------
# Passive nudge
# ---------------------------------------------------------------------------

def _load_check_state() -> dict:
    try:
        with open(UPDATE_CHECK_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_check_state(state: dict) -> None:
    try:
        with open(UPDATE_CHECK_FILE, "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def _stderr_is_tty() -> bool:
    try:
        return sys.stderr.isatty()
    except Exception:
        return False


def maybe_notify_update(args=None) -> None:
    """Post-command, best-effort upgrade nudge. Must never raise or block."""
    try:
        _maybe_notify_update(args)
    except Exception:
        pass


def _maybe_notify_update(args) -> None:
    suppressed = (
        os.environ.get("VASTAI_NO_UPDATE_CHECK")
        or os.environ.get("CI")
        or getattr(args, "raw", False)
        or not _stderr_is_tty()
        # the updater itself doesn't need a nudge
        or getattr(getattr(args, "func", None), "__module__", "") == "vastai.cli.commands.update"
    )
    if suppressed:
        return

    now = time.time()
    state = _load_check_state()
    if now - state.get("checked_at", 0) > CHECK_INTERVAL_S:
        state["checked_at"] = now  # stamped even on failure, so errors back off too
        try:
            state["latest"] = fetch_manifest(timeout=NUDGE_TIMEOUT_S).get("latest")
        except UpdateError:
            pass
        _save_check_state(state)

    latest = state.get("latest")
    if not latest or not is_newer(latest, VERSION):
        return
    if now - state.get("notified_at", 0) <= CHECK_INTERVAL_S:
        return

    receipt = read_receipt()
    hint = "vastai update" if receipt and receipt.get("method") == "installer" else PIP_UPGRADE_HINT
    arrow = "↑" if "utf" in (sys.stderr.encoding or "").lower() else "*"
    print(
        f"{arrow} vastai {latest} is available (you have {VERSION}). Run `{hint}`.",
        file=sys.stderr,
    )
    state["notified_at"] = now
    _save_check_state(state)


# ---------------------------------------------------------------------------
# Update / rollback (managed installs only)
# ---------------------------------------------------------------------------

def _run(cmd, *, env=None):
    cmd = [str(c) for c in cmd]
    try:
        return subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise UpdateError(f"Required tool not found: {cmd[0]}")
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or "").strip()
        raise UpdateError(f"Command failed ({' '.join(cmd)})" + (f":\n{detail}" if detail else ""))


def _link_binaries(root: Path) -> None:
    """Point bin/<name> at the fixed env/bin/<name> for each shipped console
    script. The target path is constant across updates (always ``env/``), so
    this is not symlink *retargeting* — just (re)creating stable links."""
    for name in MANAGED_BINARIES:
        if not (root / "env" / "bin" / name).exists():
            continue
        link, tmp = root / "bin" / name, root / "bin" / f".{name}.tmp"
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        os.symlink(Path("..") / "env" / "bin" / name, tmp)
        os.replace(tmp, link)


def perform_update(target: str, manifest: dict, *, receipt: dict) -> None:
    """Install ``target`` into a fresh env, verify it, then swap it in.

    Single active install (the deno model): the new env is built in a temp dir
    and only swapped over the live one after it verifies, so an interrupted
    update can never leave a half-written or broken ``vastai``. There is no
    version retention — a re-pin or rollback is just ``update --version X``,
    which reinstalls. Wheel integrity is delegated to uv (TLS + PyPI hashes);
    we additionally confirm the installed version matches ``target``.
    """
    root = install_root()
    uv = root / "bin" / "uv"
    if not uv.exists():
        raise UpdateError(f"Bootstrap tool missing at {uv}.\nRe-run the installer: {INSTALL_SH_HINT}")

    python_pin = (manifest.get("install") or {}).get("python") or "3.12"
    env_dir, new_dir, old_dir = root / "env", root / ".env.new", root / ".env.old"
    shutil.rmtree(new_dir, ignore_errors=True)

    uv_env = dict(os.environ,
                  UV_PYTHON_INSTALL_DIR=str(root / "python"),
                  UV_PYTHON_PREFERENCE="only-managed")
    try:
        # --relocatable: entry-point shebangs must not hardcode the build path,
        # so the venv still works after .env.new is renamed into place.
        _run([uv, "venv", new_dir, "--python", python_pin, "--relocatable", "--quiet"], env=uv_env)
        _run([uv, "pip", "install", "--python", new_dir / "bin" / "python",
              "--quiet", f"vastai=={target}"], env=uv_env)
        installed = (_run([new_dir / "bin" / "vastai", "--version"]).stdout or "").strip()
        if target not in installed:
            raise UpdateError(
                f"Verification failed: new install reports version {installed!r}, expected {target}"
            )
    except UpdateError:
        shutil.rmtree(new_dir, ignore_errors=True)
        raise

    # Swap: the live env is only ever touched by these two renames (~instant);
    # a crash mid-build dirties .env.new, never the running install.
    shutil.rmtree(old_dir, ignore_errors=True)
    if env_dir.exists():
        os.replace(env_dir, old_dir)
    os.replace(new_dir, env_dir)
    _link_binaries(root)
    shutil.rmtree(old_dir, ignore_errors=True)

    receipt = dict(receipt)
    receipt.update(
        version=target,
        previous_version=receipt.get("version"),
        installed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    write_receipt(receipt)
