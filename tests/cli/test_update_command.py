"""Tests for the `vastai update` command and self-update machinery.

Coverage focuses on the core invariants: atomic swap safety, structural
managed-install detection, the pip-install refusal, exit-code contract, and
the nudge's silence guarantees (offline, throttled, suppressed).
"""

import os
import stat
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vastai.cli import selfupdate
from vastai.cli.selfupdate import (
    UpdateError, is_newer, version_key, is_managed_install, perform_update,
    wheel_spec,
)

MANIFEST = {
    "schema": 1,
    "channel": "stable",
    "latest": "1.3.0",
    "install": {"type": "pypi-wheel", "package": "vastai", "python": "3.12"},
}

WHEEL_URL = "https://github.com/vast-ai/vast-cli/releases/download/v1.3.0/vastai-1.3.0-py3-none-any.whl"
MANIFEST_WITH_WHEEL = {
    **MANIFEST,
    "install": {**MANIFEST["install"], "wheel_url": WHEEL_URL, "wheel_sha256": "cafe123"},
}


class TestWheelSpec:
    def test_latest_installs_the_hash_pinned_release_wheel(self):
        assert wheel_spec("1.3.0", MANIFEST_WITH_WHEEL) == f"vastai @ {WHEEL_URL}#sha256=cafe123"

    def test_pin_or_rollback_uses_the_pypi_version_pin(self):
        assert wheel_spec("1.2.0", MANIFEST_WITH_WHEEL) == "vastai==1.2.0"

    def test_manifest_without_wheel_url_falls_back(self):
        assert wheel_spec("1.3.0", MANIFEST) == "vastai==1.3.0"

    def test_wheel_url_without_sha_falls_back(self):
        manifest = {**MANIFEST, "install": {**MANIFEST["install"], "wheel_url": WHEEL_URL}}
        assert wheel_spec("1.3.0", manifest) == "vastai==1.3.0"


class TestVersionOrdering:
    @pytest.mark.parametrize("newer,older", [
        ("1.0.1", "1.0.0"),
        ("1.10.0", "1.9.9"),
        ("1.0.0", "1.0.0.dev3"),
        ("1.0.0", "1.0.0rc1"),
        ("1.0.0.post1", "1.0.0"),
        ("1.0.13", "0.5.0.post116+aba334f"),
    ])
    def test_ordering(self, newer, older):
        assert is_newer(newer, older)
        assert not is_newer(older, newer)

    @pytest.mark.parametrize("a,b", [("1.0.0+local", "1.0.0"), ("1.0", "1.0.0")])
    def test_equivalent_forms(self, a, b):
        assert version_key(a) == version_key(b)


@pytest.fixture
def install_root(tmp_path, monkeypatch):
    root = tmp_path / "vastai-root"
    (root / "bin").mkdir(parents=True)
    monkeypatch.setenv("VASTAI_INSTALL_DIR", str(root))
    return root


def _seed_env(root, version):
    """Create a live env/ with a runnable vastai (a prior install to replace)."""
    bindir = root / "env" / "bin"
    bindir.mkdir(parents=True)
    exe = bindir / "vastai"
    exe.write_text(f"#!/bin/sh\necho '{version}'\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)


class TestIsManagedInstall:
    def test_true_when_running_from_env_next_to_uv(self, install_root, monkeypatch):
        (install_root / "env").mkdir()
        (install_root / "bin" / "uv").write_text("")
        monkeypatch.setattr(sys, "prefix", str(install_root / "env"))
        assert is_managed_install() is True

    def test_false_for_pip_install(self, install_root, monkeypatch):
        # interpreter runs from somewhere else (a pip/venv install)
        monkeypatch.setattr(sys, "prefix", str(install_root.parent / "some-venv"))
        assert is_managed_install() is False

    def test_false_when_uv_missing(self, install_root, monkeypatch):
        (install_root / "env").mkdir()  # env present but no bin/uv
        monkeypatch.setattr(sys, "prefix", str(install_root / "env"))
        assert is_managed_install() is False


# Fake uv: `uv venv DIR ...` and `uv pip install --python PY ... vastai==VER`
FAKE_UV = """#!/bin/sh
set -e
if [ "$1" = "venv" ]; then
    mkdir -p "$2/bin"; touch "$2/bin/python"; chmod +x "$2/bin/python"
elif [ "$1" = "pip" ]; then
    py="" prev="" last=""
    for a in "$@"; do
        [ "$prev" = "--python" ] && py="$a"
        prev="$a"; last="$a"
    done
    bindir="$(dirname "$py")"
    printf '#!/bin/sh\\necho "%s"\\n' "${last#vastai==}" > "$bindir/vastai"
    chmod +x "$bindir/vastai"
fi
"""


@pytest.fixture
def fake_uv(install_root):
    uv = install_root / "bin" / "uv"
    uv.write_text(FAKE_UV)
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
    return uv


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="managed install is POSIX-only (the installer does not support Windows); "
           "these tests execute shell-script fakes",
)
class TestPerformUpdate:
    def test_success_swaps_in_new_env(self, install_root, fake_uv):
        _seed_env(install_root, "1.2.3")
        perform_update("1.3.0", MANIFEST)

        # single fixed env, symlink points into it, new version live, no retention
        assert "env/bin/vastai" in os.readlink(str(install_root / "bin" / "vastai"))
        assert (install_root / "env" / "bin" / "vastai").exists()
        assert "1.3.0" in (install_root / "env" / "bin" / "vastai").read_text()
        assert not (install_root / ".env.new").exists()
        assert not (install_root / "versions").exists()

    def test_build_failure_surfaces_real_error_not_a_fabricated_one(self, install_root):
        # A uv that "succeeds" but never builds the env: the verify step then
        # runs a non-existent .env.new/bin/vastai. The error must name the real
        # missing path, not relabel it the misleading "Required tool not found".
        _seed_env(install_root, "1.2.3")
        uv = install_root / "bin" / "uv"
        uv.write_text("#!/bin/sh\nexit 0\n")  # does nothing — no venv, no install
        uv.chmod(uv.stat().st_mode | stat.S_IXUSR)

        with pytest.raises(UpdateError) as exc:
            perform_update("1.3.0", MANIFEST)
        msg = str(exc.value)
        assert "Required tool not found" not in msg
        assert ".env.new/bin/vastai" in msg

    def test_failure_leaves_current_install_untouched(self, install_root):
        _seed_env(install_root, "1.2.3")  # live install that must survive
        before = (install_root / "env" / "bin" / "vastai").read_text()
        uv = install_root / "bin" / "uv"
        uv.write_text("#!/bin/sh\nexit 1\n")
        uv.chmod(uv.stat().st_mode | stat.S_IXUSR)

        with pytest.raises(UpdateError):
            perform_update("1.3.0", MANIFEST)

        assert (install_root / "env" / "bin" / "vastai").read_text() == before
        assert not (install_root / ".env.new").exists()


class TestUpdateCommand:
    """Argv-level tests: these also pin the parser verb-merge fix
    (`update` collides with the `update instance` verb)."""

    def test_check_stale_exits_10(self, parse_argv, capsys):
        args = parse_argv(["update", "--check"])
        with patch("vastai.cli.commands.update.fetch_manifest", return_value=MANIFEST), \
             patch("vastai.cli.commands.update.VERSION", "1.2.0"):
            assert args.func(args) == 10
        assert "Update available: 1.3.0" in capsys.readouterr().out

    def test_pip_install_refused_with_hint(self, parse_argv, capsys):
        # not a managed install (interpreter isn't under ~/.vastai/env)
        args = parse_argv(["update"])
        with patch("vastai.cli.commands.update.is_managed_install", return_value=False):
            assert args.func(args) == 1
        assert "pip install --upgrade vastai" in capsys.readouterr().err

    def test_up_to_date_reports_latest_version(self, parse_argv, capsys):
        # already on the latest: don't update, but surface what latest is
        args = parse_argv(["update"])
        with patch("vastai.cli.commands.update.is_managed_install", return_value=True), \
             patch("vastai.cli.commands.update.fetch_manifest", return_value=MANIFEST), \
             patch("vastai.cli.commands.update.VERSION", "1.3.0"):
            assert args.func(args) == 0
        out = capsys.readouterr().out
        assert "up to date" in out and "1.3.0" in out

    def test_pinned_version_already_installed_reports_latest(self, parse_argv, capsys):
        # pinned to the version already running: note it, plus what latest is
        args = parse_argv(["update", "--version", "1.2.0"])
        with patch("vastai.cli.commands.update.is_managed_install", return_value=True), \
             patch("vastai.cli.commands.update.fetch_manifest", return_value=MANIFEST), \
             patch("vastai.cli.commands.update.VERSION", "1.2.0"):
            assert args.func(args) == 0
        out = capsys.readouterr().out
        assert "already installed" in out and "latest available: 1.3.0" in out

    def test_version_flag_targets_specific_version(self, parse_argv):
        args = parse_argv(["update", "--version", "1.2.9"])
        with patch("vastai.cli.commands.update.is_managed_install", return_value=True), \
             patch("vastai.cli.commands.update.fetch_manifest", return_value=MANIFEST), \
             patch("vastai.cli.commands.update.perform_update") as mock_update:
            assert args.func(args) == 0
        mock_update.assert_called_once_with("1.2.9", MANIFEST)


@pytest.fixture
def nudge_env(tmp_path, monkeypatch):
    """Environment where the nudge is allowed to fire: tty stderr, no CI,
    not a managed install (so the hint defaults to pip)."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("VASTAI_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setenv("VASTAI_INSTALL_DIR", str(tmp_path / "root"))
    monkeypatch.setattr(selfupdate, "UPDATE_CHECK_FILE", str(tmp_path / "check.json"))
    monkeypatch.setattr(selfupdate, "VERSION", "1.0.0")
    monkeypatch.setattr(selfupdate, "_stderr_is_tty", lambda: True)
    return SimpleNamespace(raw=False)


class TestNudge:
    def test_fires_when_stale_with_pip_hint_for_pip_install(self, nudge_env, capsys):
        # not a managed install (real interpreter prefix) -> pip hint
        with patch.object(selfupdate, "fetch_manifest", return_value=MANIFEST):
            selfupdate.notify_update(nudge_env)
        err = capsys.readouterr().err
        assert "1.3.0 is available" in err
        assert "pip install --upgrade vastai" in err

    def test_managed_install_gets_vastai_update_hint(self, nudge_env, capsys):
        with patch.object(selfupdate, "fetch_manifest", return_value=MANIFEST), \
             patch.object(selfupdate, "is_managed_install", return_value=True):
            selfupdate.notify_update(nudge_env)
        assert "Run `vastai update`" in capsys.readouterr().err

    def test_silent_on_fetch_failure(self, nudge_env, capsys):
        with patch.object(selfupdate, "fetch_manifest", side_effect=UpdateError("down")):
            selfupdate.notify_update(nudge_env)
        assert capsys.readouterr().err == ""

    def test_one_check_and_one_notice_per_24h(self, nudge_env, capsys):
        with patch.object(selfupdate, "fetch_manifest", return_value=MANIFEST) as f:
            selfupdate.notify_update(nudge_env)
            selfupdate.notify_update(nudge_env)
        assert f.call_count == 1
        assert capsys.readouterr().err.count("is available") == 1

    @pytest.mark.parametrize("mute", [
        lambda mp, args: mp.setenv("CI", "1"),
        lambda mp, args: mp.setenv("VASTAI_NO_UPDATE_CHECK", "1"),
        lambda mp, args: setattr(args, "raw", True),
        lambda mp, args: mp.setattr(selfupdate, "_stderr_is_tty", lambda: False),
    ], ids=["ci-env", "opt-out-env", "raw-mode", "no-tty"])
    def test_suppressed_makes_no_network_call(self, nudge_env, monkeypatch, capsys, mute):
        mute(monkeypatch, nudge_env)
        with patch.object(selfupdate, "fetch_manifest", return_value=MANIFEST) as f:
            selfupdate.notify_update(nudge_env)
        assert f.call_count == 0
        assert capsys.readouterr().err == ""

    def test_never_raises(self, nudge_env):
        with patch.object(selfupdate, "_load_check_state", side_effect=RuntimeError("boom")):
            selfupdate.notify_update(nudge_env)  # must not raise
