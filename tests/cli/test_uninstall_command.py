"""Tests for the `vastai uninstall` command and its removal machinery.

Mirrors tests/cli/test_update_command.py's fixtures/patterns: a fake
managed install root under tmp_path, argv-level tests via parse_argv, and
the same-method discipline (pip installs are refused, never shelled out to).
"""

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vastai.cli import selfupdate
from vastai.cli.selfupdate import perform_uninstall


@pytest.fixture
def install_root(tmp_path, monkeypatch):
    root = tmp_path / "vastai-root"
    (root / "bin").mkdir(parents=True)
    (root / "current" / "bin").mkdir(parents=True)
    monkeypatch.setenv("VASTAI_INSTALL_DIR", str(root))
    return root


@pytest.fixture
def local_bin(tmp_path, monkeypatch):
    bindir = tmp_path / "local-bin"
    bindir.mkdir()
    monkeypatch.setattr(selfupdate, "LOCAL_BIN", bindir)
    return bindir


def _link(local_bin, name, target):
    (local_bin / name).symlink_to(target)


class TestPerformUninstall:
    def test_removes_the_install_root(self, install_root, local_bin):
        (install_root / "current" / "bin" / "vastai").write_text("#!/bin/sh\n")
        perform_uninstall()
        assert not install_root.exists()

    def test_removes_managed_binary_symlinks(self, install_root, local_bin):
        _link(local_bin, "vastai", install_root / "bin" / "vastai")
        _link(local_bin, "serve-vast-deployment", install_root / "bin" / "serve-vast-deployment")
        perform_uninstall()
        assert not (local_bin / "vastai").exists()
        assert not (local_bin / "serve-vast-deployment").exists()

    def test_leaves_unmanaged_binaries_with_the_same_name_alone(self, install_root, local_bin, tmp_path):
        # a symlink named "vastai" pointing somewhere outside our root isn't ours to remove
        foreign = tmp_path / "foreign-vastai"
        foreign.write_text("#!/bin/sh\necho foreign\n")
        _link(local_bin, "vastai", foreign)
        perform_uninstall()
        assert (local_bin / "vastai").is_symlink()

    def test_missing_binaries_are_a_no_op(self, install_root, local_bin):
        # no symlinks ever created in local_bin — must not raise
        perform_uninstall()
        assert not install_root.exists()

    def test_returns_the_removed_root(self, install_root, local_bin):
        assert perform_uninstall() == install_root


class TestUninstallCommand:
    def test_pip_install_refused_with_hint(self, parse_argv, capsys):
        args = parse_argv(["uninstall", "--yes"])
        with patch("vastai.cli.commands.uninstall.is_managed_install", return_value=False):
            assert args.func(args) == 1
        assert "pip uninstall vastai" in capsys.readouterr().err

    def test_pip_install_never_calls_perform_uninstall(self, parse_argv):
        args = parse_argv(["uninstall", "--yes"])
        with patch("vastai.cli.commands.uninstall.is_managed_install", return_value=False), \
             patch("vastai.cli.commands.uninstall.perform_uninstall") as mock_uninstall:
            args.func(args)
        mock_uninstall.assert_not_called()

    def test_yes_flag_skips_confirmation(self, parse_argv, capsys, tmp_path):
        args = parse_argv(["uninstall", "--yes"])
        with patch("vastai.cli.commands.uninstall.is_managed_install", return_value=True), \
             patch("vastai.cli.commands.uninstall.install_root", return_value=tmp_path), \
             patch("vastai.cli.commands.uninstall.perform_uninstall") as mock_uninstall:
            assert args.func(args) == 0
        mock_uninstall.assert_called_once_with()
        assert "uninstalled" in capsys.readouterr().out

    def test_non_interactive_without_yes_refuses(self, parse_argv, capsys, tmp_path, monkeypatch):
        args = parse_argv(["uninstall"])
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: False))
        with patch("vastai.cli.commands.uninstall.is_managed_install", return_value=True), \
             patch("vastai.cli.commands.uninstall.install_root", return_value=tmp_path), \
             patch("vastai.cli.commands.uninstall.perform_uninstall") as mock_uninstall:
            assert args.func(args) == 1
        mock_uninstall.assert_not_called()
        assert "--yes" in capsys.readouterr().err

    def test_declining_the_prompt_aborts(self, parse_argv, capsys, tmp_path, monkeypatch):
        args = parse_argv(["uninstall"])
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
        with patch("vastai.cli.commands.uninstall.is_managed_install", return_value=True), \
             patch("vastai.cli.commands.uninstall.install_root", return_value=tmp_path), \
             patch("builtins.input", return_value="n"), \
             patch("vastai.cli.commands.uninstall.perform_uninstall") as mock_uninstall:
            assert args.func(args) == 1
        mock_uninstall.assert_not_called()
        assert "Aborted" in capsys.readouterr().out

    def test_confirming_the_prompt_proceeds(self, parse_argv, capsys, tmp_path, monkeypatch):
        args = parse_argv(["uninstall"])
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
        with patch("vastai.cli.commands.uninstall.is_managed_install", return_value=True), \
             patch("vastai.cli.commands.uninstall.install_root", return_value=tmp_path), \
             patch("builtins.input", return_value="y"), \
             patch("vastai.cli.commands.uninstall.perform_uninstall") as mock_uninstall:
            assert args.func(args) == 0
        mock_uninstall.assert_called_once_with()
        assert "uninstalled" in capsys.readouterr().out

    def test_eof_on_prompt_aborts_rather_than_raising(self, parse_argv, tmp_path, monkeypatch):
        args = parse_argv(["uninstall"])
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
        with patch("vastai.cli.commands.uninstall.is_managed_install", return_value=True), \
             patch("vastai.cli.commands.uninstall.install_root", return_value=tmp_path), \
             patch("builtins.input", side_effect=EOFError), \
             patch("vastai.cli.commands.uninstall.perform_uninstall") as mock_uninstall:
            assert args.func(args) == 1
        mock_uninstall.assert_not_called()
