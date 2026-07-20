"""Tests for vastai/cli/main.py — _emit_error's client/host 401 hint (CLN-3582)."""

import argparse
import io
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vastai.cli.main import _emit_error


def _args(*, raw=False, func=None):
    return argparse.Namespace(raw=raw, func=func)


def _host_command_func(command_name):
    """A stand-in for args.func: mysignature is the registered subparser."""
    sp = SimpleNamespace(host_only=True, command_name=command_name)
    func = lambda a: None  # noqa: E731
    func.mysignature = sp
    return func


def _client_command_func(command_name):
    sp = SimpleNamespace(host_only=False, command_name=command_name)
    func = lambda a: None  # noqa: E731
    func.mysignature = sp
    return func


class TestHostCommand401Hint:
    def test_known_command_gets_specific_hint(self):
        args = _args(func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        out = buf.getvalue()
        assert "'show machines' is a host-only command" in out
        assert "did you mean 'vastai show instances'?" in out
        assert "set role host" in out

    def test_unknown_command_gets_generic_hint(self):
        args = _args(func=_host_command_func("dump-logs"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        out = buf.getvalue()
        assert "'dump-logs' is a host-only command" in out
        assert "vastai --help" in out

    def test_host_role_does_not_get_the_hint(self):
        args = _args(func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="host"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        assert "host-only command" not in buf.getvalue()

    def test_undetected_role_also_gets_the_hint(self):
        # Client is the default: an unset role is treated the same as
        # 'client', not 'host' — so the hint still fires.
        args = _args(func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value=None):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        assert "host-only command" in buf.getvalue()

    def test_non_host_only_command_does_not_get_the_hint(self):
        args = _args(func=_client_command_func("show instances"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        assert "host-only command" not in buf.getvalue()

    def test_2fa_message_takes_precedence_over_the_hint(self):
        # Even for a host command in the client role, an explicit 2FA error
        # keeps its own (pre-existing) guidance rather than the new hint.
        args = _args(func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "Two Factor Authentication required")
        out = buf.getvalue()
        assert "tfa login" in out
        assert "host-only command" not in out

    def test_raw_mode_skips_the_hint_and_emits_json(self):
        args = _args(raw=True, func=_host_command_func("show machines"))
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        out = buf.getvalue()
        assert "host-only command" not in out
        assert '"error": true' in out

    def test_no_func_on_args_does_not_crash(self):
        # Defensive: args without a func attribute (shouldn't happen in
        # practice, but _emit_error must not blow up on missing state).
        args = argparse.Namespace(raw=False)
        buf = io.StringIO()
        with patch("vastai.cli.main.get_role", return_value="client"):
            with redirect_stderr(buf):
                _emit_error(args, 401, "no permission")
        assert "Failed with error 401" in buf.getvalue()
