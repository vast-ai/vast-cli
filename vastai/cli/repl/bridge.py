"""Run one CLI line inside the REPL process.

The REPL reuses the exact parser and command functions that ``vastai ...``
uses, so ``show instances`` at the prompt behaves identically to
``vastai show instances`` — same auth, same output, same flags. The only
difference is control flow: a failing command ends the line, never the session.
"""
import json
import shlex
import sys

import requests

from vastai.cli.main import _emit_error

# Globals the session carries onto every line, so a bare `show instances`
# doesn't have to repeat --api-key/--url/--raw. A flag typed on the line wins.
SESSION_GLOBALS = (
    "api_key", "url", "retry", "explain", "curl", "raw", "full", "no_color",
)


def run_line(parser, line, session_args):
    """Parse and execute one command line. Returns the command's return value,
    or None if the line failed to parse or the command errored."""
    try:
        argv = shlex.split(line)
    except ValueError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return None
    if not argv:
        return None

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return None  # argparse already printed usage or an error

    apply_session_globals(parser, args, session_args)
    func = getattr(args, "func", None)
    if func is None:
        return None
    return _invoke(args, func)


def apply_session_globals(parser, args, session_args):
    """Carry the session's global flags onto one line's args.

    A global left at its parser default was not typed on this line, so the
    session's value applies; anything explicitly typed is left alone.
    """
    inner = getattr(parser, "parser", parser)
    for name in SESSION_GLOBALS:
        if not hasattr(args, name) or not hasattr(session_args, name):
            continue
        if getattr(args, name) == inner.get_default(name):
            setattr(args, name, getattr(session_args, name))


def _invoke(args, func):
    try:
        res = func(args)
    except SystemExit:
        # Commands (and --help) exit the process in one-shot mode; here that
        # just ends the line.
        return None
    except requests.exceptions.HTTPError as exc:
        _emit_http_error(args, exc)
        return None
    except ValueError as exc:
        _emit_error(args, 0, str(exc))
        return None
    except KeyboardInterrupt:
        print("^C", file=sys.stderr)
        return None
    except Exception as exc:  # a broken command must not kill the session
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    if getattr(args, "raw", False) and res is not None:
        _print_raw(res)
    return res


def _emit_http_error(args, exc):
    """Format an API error the same way the one-shot CLI's main loop does."""
    resp = exc.response
    status = getattr(resp, "status_code", 0)
    try:
        msg = resp.json().get("msg")
    except (ValueError, AttributeError):
        msg = "Please log in or sign up" if status == 401 else "(no detail message supplied)"
    _emit_error(args, status, msg)


def _print_raw(res):
    try:
        print(json.dumps(res, indent=1, sort_keys=True))
    except (TypeError, ValueError):
        print(json.dumps(res.json(), indent=1, sort_keys=True))
