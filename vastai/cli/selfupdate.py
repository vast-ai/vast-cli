"""Self-update engine for the managed (curl | bash) CLI install.

Layout (docs/install-design.md, XDG Base Directory Specification): the
install root defaults to $XDG_DATA_HOME/vastai (~/.local/share/vastai),
override with $VASTAI_INSTALL_DIR — a single active venv at current/, with
bin/vastai a fixed symlink into it. Updating rebuilds current/ in place
(build temp → verify → swap); there is no version retention.

"Managed install?" is detected structurally (``is_managed_install``): a managed
CLI runs from <root>/current with a sibling <root>/bin/uv. That's ground
truth — no on-disk marker to drift or hand-copy. pip installs fail the check
and the updater never touches them.

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
from pathlib import Path

import requests

from vastai.cli.util import DATA_HOME, DIRS, VERSION

DEFAULT_MANIFEST_URL = "https://vast.ai/cli/manifest.json"
INSTALL_SH_HINT = "curl -fsSL https://vast.ai/install.sh | bash"
PIP_UPGRADE_HINT = "pip install --upgrade vastai"

# Oldest version whose bundled selfupdate.py understands this layout
# (<root>/current + <root>/bin/uv, XDG-based root). Versions before this pin
# assumed ~/.vastai/env and would install fine but then see themselves as unmanaged,
# permanently losing self-update until the install is rebuilt from scratch.
MIN_DOWNGRADE_VERSION = "1.4.0"

UPDATE_CHECK_FILE = os.path.join(DIRS['state'], "update_check.json")
CHECK_INTERVAL_S = 24 * 60 * 60
NUDGE_TIMEOUT_S = 1.0

# Console scripts shipped in the wheel; each gets a swapped symlink in bin/.
MANAGED_BINARIES = ("vastai", "serve-vast-deployment", "register-python-argcomplete")


class UpdateError(Exception):
    """A self-update step failed; the current install is untouched."""


# ---------------------------------------------------------------------------
# Install detection / manifest / versions
# ---------------------------------------------------------------------------

def install_root() -> Path:
    """Where the managed install lives.

    Prefers ground truth from where this interpreter is actually running: if
    we're already inside a managed install (``<root>/current`` next to
    ``<root>/bin/uv``), that's authoritative and immune to
    $VASTAI_INSTALL_DIR/$XDG_DATA_HOME differing between install time and
    now — e.g. a custom install dir that isn't set in the current shell would
    otherwise make a real managed install look unmanaged. Only when we're
    *not* currently running from one (a pip install checking
    ``is_managed_install``) do we fall back to computing where a managed
    install would live.
    """
    prefix = Path(sys.prefix).resolve()
    if prefix.name == "current" and (prefix.parent / "bin" / "uv").exists():
        return prefix.parent
    if os.environ.get("VASTAI_INSTALL_DIR"):
        return Path(os.environ["VASTAI_INSTALL_DIR"]).expanduser()
    return Path(DATA_HOME) / "vastai"


def is_managed_install() -> bool:
    """True iff this CLI was installed by the managed installer.

    Detected from where the interpreter actually runs: a managed CLI lives in
    ``<root>/current`` next to ``<root>/bin/uv``. Ground truth, no marker file.
    pip installs run from elsewhere and fail the check.
    """
    try:
        root = install_root()
        return (
            Path(sys.prefix).resolve() == (root / "current").resolve()
            and (root / "bin" / "uv").exists()
        )
    except Exception:
        return False


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


def notify_update(args=None) -> None:
    """Post-command, best-effort upgrade nudge. Must never raise or block."""
    try:
        _notify_update(args)
    except Exception:
        pass


def _notify_update(args) -> None:
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

    hint = "vastai update" if is_managed_install() else PIP_UPGRADE_HINT
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
    except subprocess.CalledProcessError as e:
        # Surface the tool's own stderr — that's the real error (e.g. uv's
        # resolution failure), not a category we invent.
        detail = (e.stderr or e.stdout or "").strip()
        raise UpdateError(f"Command failed: {' '.join(cmd)}" + (f"\n{detail}" if detail else ""))
    except OSError as e:
        # Carry the actual OSError through (wrong path, missing binary, …)
        # rather than relabeling everything "Required tool not found".
        raise UpdateError(f"Could not run {' '.join(cmd)}: {e}")


def _prune_uv_cache(uv: Path, env: dict) -> None:
    """Best-effort prune of uv's cache after a successful swap.

    Each update hardlinks the new env out of the cache, so the cache
    accumulates every version's wheels forever unless pruned. Prune (not
    clean): the cache is the user-global one, shared with any other uv on
    the machine. The update already succeeded — never fail because of this.
    """
    try:
        _run([uv, "cache", "prune", "--quiet"], env=env)
    except UpdateError:
        pass


def _link_binaries(root: Path) -> None:
    """Point bin/<name> at the fixed current/bin/<name> for each shipped
    console script. The target path is constant across updates (always
    ``current/``), so this is not symlink *retargeting* — just (re)creating
    stable links."""
    for name in MANAGED_BINARIES:
        if not (root / "current" / "bin" / name).exists():
            continue
        link, tmp = root / "bin" / name, root / "bin" / f".{name}.tmp"
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        os.symlink(Path("..") / "current" / "bin" / name, tmp)
        os.replace(tmp, link)


def wheel_spec(target: str, manifest: dict) -> str:
    """Requirement spec that installs ``target``.

    Latest installs the manifest's release wheel: hash-pinned bytes straight
    from the GitHub Release, no PyPI propagation window. Other targets are
    pins/rollbacks to long-published versions, where the PyPI pin is
    race-free and covers releases that predate wheel_url.
    """
    install = manifest.get("install") or {}
    url, sha = install.get("wheel_url"), install.get("wheel_sha256")
    if target == manifest.get("latest") and url and sha:
        return f"vastai @ {url}#sha256={sha}"
    return f"vastai=={target}"


def perform_update(target: str, manifest: dict) -> None:
    """Install ``target`` into a fresh env, verify it, then swap it in.

    Single active install (the deno model): the new env is built in a temp dir
    and only swapped over the live one after it verifies, so an interrupted
    update can never leave a half-written or broken ``vastai``. There is no
    version retention — a re-pin or rollback is just ``update --version X``,
    which reinstalls. Wheel integrity comes from ``wheel_spec``; we
    additionally confirm the installed version matches ``target``.
    """
    if version_key(target) < version_key(MIN_DOWNGRADE_VERSION):
        raise UpdateError(
            f"Can't roll back to {target}: versions before {MIN_DOWNGRADE_VERSION} "
            "don't recognize this install's layout and would lose the ability "
            f"to self-update. The oldest version you can roll back to is {MIN_DOWNGRADE_VERSION}."
        )
    root = install_root()
    uv = root / "bin" / "uv"
    if not uv.exists():
        raise UpdateError(f"Bootstrap tool missing at {uv}.\nRe-run the installer: {INSTALL_SH_HINT}")

    python_pin = (manifest.get("install") or {}).get("python") or "3.12"
    env_dir, new_dir, old_dir = root / "current", root / ".current.new", root / ".current.old"
    shutil.rmtree(new_dir, ignore_errors=True)

    uv_env = dict(os.environ,
                  UV_PYTHON_INSTALL_DIR=str(root / "python"),
                  UV_PYTHON_PREFERENCE="only-managed")
    try:
        # --relocatable: shebangs must not hardcode the build path (env is renamed into place).
        _run([uv, "venv", new_dir, "--python", python_pin, "--relocatable", "--quiet"], env=uv_env)
        _run([uv, "pip", "install", "--python", new_dir / "bin" / "python",
              "--quiet", wheel_spec(target, manifest)], env=uv_env)
        installed = (_run([new_dir / "bin" / "vastai", "--version"]).stdout or "").strip()
        if target not in installed:
            raise UpdateError(
                f"Verification failed: new install reports version {installed!r}, expected {target}"
            )
    except UpdateError:
        shutil.rmtree(new_dir, ignore_errors=True)
        raise

    # Swap via two renames (~instant); a crash mid-build only dirties .current.new.
    shutil.rmtree(old_dir, ignore_errors=True)
    if env_dir.exists():
        os.replace(env_dir, old_dir)
    os.replace(new_dir, env_dir)
    _link_binaries(root)
    shutil.rmtree(old_dir, ignore_errors=True)
    _prune_uv_cache(uv, uv_env)
