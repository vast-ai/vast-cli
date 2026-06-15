"""Tests for the (dormant) `vastai update` command and self-update machinery.

The command is not registered in vastai.cli.main yet; tests/conftest.py
imports it onto the test parser. Coverage focuses on the core invariants:
atomic swap/rollback safety, the pip-install refusal, exit-code contract,
and the nudge's silence guarantees (offline, throttled, suppressed).
"""

import os
import stat
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vastai.cli import selfupdate
from vastai.cli.selfupdate import (
    UpdateError, is_newer, version_key, read_receipt, write_receipt,
    perform_update,
)

MANIFEST = {
    "schema": 1,
    "channel": "stable",
    "latest": "1.3.0",
    "install": {"type": "pypi-wheel", "package": "vastai", "python": "3.12"},
}


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


@pytest.fixture
def managed_receipt(install_root):
    receipt = {"method": "installer", "version": "1.2.3", "previous_version": None}
    write_receipt(receipt)
    return receipt


def _seed_env(root, version):
    """Create a live env/ with a runnable vastai (a prior install to replace)."""
    bindir = root / "env" / "bin"
    bindir.mkdir(parents=True)
    exe = bindir / "vastai"
    exe.write_text(f"#!/bin/sh\necho '{version}'\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)


def test_receipt_never_raises(install_root):
    assert read_receipt() is None  # missing
    (install_root / "install-receipt.json").write_text("{not json")
    assert read_receipt() is None  # corrupt
    write_receipt({"method": "installer", "version": "1.0.0"})
    assert read_receipt() == {"method": "installer", "version": "1.0.0"}


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
    def test_success_swaps_in_new_env(self, install_root, managed_receipt, fake_uv):
        _seed_env(install_root, "1.2.3")
        perform_update("1.3.0", MANIFEST, receipt=managed_receipt)

        # single fixed env, symlink points into it, no version retention
        assert "env/bin/vastai" in os.readlink(str(install_root / "bin" / "vastai"))
        assert (install_root / "env" / "bin" / "vastai").exists()
        assert not (install_root / ".env.new").exists()
        assert not (install_root / "versions").exists()
        receipt = read_receipt()
        assert receipt["version"] == "1.3.0"
        assert receipt["previous_version"] == "1.2.3"

    def test_failure_leaves_current_install_untouched(
        self, install_root, managed_receipt
    ):
        _seed_env(install_root, "1.2.3")  # live install that must survive
        before = (install_root / "env" / "bin" / "vastai").read_text()
        uv = install_root / "bin" / "uv"
        uv.write_text("#!/bin/sh\nexit 1\n")
        uv.chmod(uv.stat().st_mode | stat.S_IXUSR)

        with pytest.raises(UpdateError):
            perform_update("1.3.0", MANIFEST, receipt=managed_receipt)

        assert (install_root / "env" / "bin" / "vastai").read_text() == before
        assert not (install_root / ".env.new").exists()
        assert read_receipt()["version"] == "1.2.3"


class TestUpdateCommand:
    """Argv-level tests: these also pin the parser verb-merge fix
    (`update` collides with the `update instance` verb)."""

    def test_check_stale_exits_10(self, parse_argv, capsys):
        args = parse_argv(["update", "--check"])
        with patch("vastai.cli.commands.update.fetch_manifest", return_value=MANIFEST), \
             patch("vastai.cli.commands.update.VERSION", "1.2.0"):
            assert args.func(args) == 10
        assert "Update available: 1.3.0" in capsys.readouterr().out

    def test_pip_install_refused_with_hint(self, parse_argv, capsys, install_root):
        args = parse_argv(["update"])  # no receipt under install_root
        assert args.func(args) == 1
        assert "pip install --upgrade vastai" in capsys.readouterr().err

    def test_version_flag_targets_specific_version(self, parse_argv, managed_receipt):
        args = parse_argv(["update", "--version", "1.2.9"])
        with patch("vastai.cli.commands.update.fetch_manifest", return_value=MANIFEST), \
             patch("vastai.cli.commands.update.perform_update") as mock_update:
            assert args.func(args) == 0
        mock_update.assert_called_once_with("1.2.9", MANIFEST, receipt=managed_receipt)


@pytest.fixture
def nudge_env(tmp_path, monkeypatch):
    """Environment where the nudge is allowed to fire: tty stderr, no CI,
    empty install root (not the developer's real ~/.vastai)."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("VASTAI_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setenv("VASTAI_INSTALL_DIR", str(tmp_path / "no-receipt-root"))
    monkeypatch.setattr(selfupdate, "UPDATE_CHECK_FILE", str(tmp_path / "check.json"))
    monkeypatch.setattr(selfupdate, "VERSION", "1.0.0")
    monkeypatch.setattr(selfupdate, "_stderr_is_tty", lambda: True)
    return SimpleNamespace(raw=False)


class TestNudge:
    def test_fires_when_stale_with_method_aware_hint(self, nudge_env, capsys):
        with patch.object(selfupdate, "fetch_manifest", return_value=MANIFEST):
            selfupdate.maybe_notify_update(nudge_env)
        err = capsys.readouterr().err
        assert "1.3.0 is available" in err
        assert "pip install --upgrade vastai" in err  # no receipt -> pip hint

    def test_silent_on_fetch_failure(self, nudge_env, capsys):
        with patch.object(selfupdate, "fetch_manifest", side_effect=UpdateError("down")):
            selfupdate.maybe_notify_update(nudge_env)
        assert capsys.readouterr().err == ""

    def test_one_check_and_one_notice_per_24h(self, nudge_env, capsys):
        with patch.object(selfupdate, "fetch_manifest", return_value=MANIFEST) as f:
            selfupdate.maybe_notify_update(nudge_env)
            selfupdate.maybe_notify_update(nudge_env)
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
            selfupdate.maybe_notify_update(nudge_env)
        assert f.call_count == 0
        assert capsys.readouterr().err == ""

    def test_never_raises(self, nudge_env):
        with patch.object(selfupdate, "_load_check_state", side_effect=RuntimeError("boom")):
            selfupdate.maybe_notify_update(nudge_env)  # must not raise
