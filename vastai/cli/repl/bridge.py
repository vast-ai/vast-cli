"""Run one CLI line inside the REPL process.

The REPL reuses the exact parser and command functions that ``vastai ...``
uses, so ``show instances`` at the prompt behaves identically to
``vastai show instances`` — same auth, same output, same flags. The only
difference is control flow: a failing command ends the line, never the session.
"""
import argparse
import json
import os
import shlex
import sys

import requests

from vastai.cli import main as cli_main
from vastai.cli.repl.catalog import option_action

# Globals the session carries onto every line, so a bare `show instances`
# doesn't have to repeat --api-key/--url/--raw. A flag typed on the line wins.
SESSION_GLOBALS = (
    "api_key", "url", "retry", "explain", "curl", "raw", "full", "no_color",
)

# Outcomes of an expired-2FA-session recovery attempt.
RETRY = "retry"      # a fresh key was loaded; run the command again
HANDLED = "handled"  # the expiry was reported; don't report it twice


def run_line(parser, line, session_args):
    """Parse and execute one command line. Returns the command's return value,
    or None if the line failed to parse or the command errored."""
    try:
        argv = tokenize(line)
    except ValueError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return None
    if not argv:
        return None

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return None  # argparse already printed usage or an error

    apply_session_globals(parser, args, session_args, argv)
    func = getattr(args, "func", None)
    if func is None:
        return None
    return _invoke(args, func, session_args)


def tokenize(line):
    """Split a line into argv the way a shell would.

    POSIX rules everywhere except Windows, where a backslash is a path
    separator rather than an escape: POSIX splitting would quietly turn
    ``--onstart C:\\tmp\\go.sh`` into ``C:tmpgo.sh``.
    """
    if os.name != "nt":
        return shlex.split(line)
    lexer = shlex.shlex(line, posix=False)
    lexer.whitespace_split = True
    return [_unquote(token) for token in lexer]


def _unquote(token):
    if len(token) > 1 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def apply_session_globals(parser, args, session_args, argv=()):
    """Carry the session's global flags onto one line's args.

    Presence is read from the line itself rather than by comparing parsed
    values against defaults: an option typed with exactly its default value
    (``--retry 3`` while the session runs with ``--retry 10``) must still win.
    """
    inner = getattr(parser, "parser", parser)
    sub = getattr(getattr(args, "func", None), "mysignature", None)
    typed = explicit_dests(inner, sub, argv)
    for name in SESSION_GLOBALS:
        if name in typed or not hasattr(args, name) or not hasattr(session_args, name):
            continue
        setattr(args, name, getattr(session_args, name))


def explicit_dests(root, sub, argv):
    """The dests of the options a line actually names, in any form argparse
    accepts (``--flag``, ``--flag=value``, a short alias, an abbreviation).

    Each option is read against the parser argparse itself would use: the root
    parser before the command name, the command's own parser after it. An
    abbreviation can be unambiguous in one and ambiguous in the other — ``--c``
    is ``--curl`` up front, but could be ``--cols`` on ``show instances``.

    Scanning stops where argparse stops treating words as options: at ``--`` or
    at a REMAINDER option, so ``create instance --args --raw`` passes ``--raw``
    to the container rather than counting it as a global.
    """
    dests = set()
    parser, skip = root, 0
    for token in argv:
        if skip:
            skip -= 1
            continue
        if token == "--":
            break
        if not token.startswith("-") or token == "-":
            parser = sub or root  # past the command name from here on
            continue
        action = option_action(parser, token)
        if action is None:
            continue
        if action.nargs == argparse.REMAINDER:
            break
        dests.add(action.dest)
        if parser is root and action.nargs != 0 and "=" not in token:
            skip = 1  # its value is not the command name
    return dests


def _invoke(args, func, session_args=None):
    try:
        res = func(args)
    except SystemExit:
        # Commands (and --help) exit the process in one-shot mode; here that
        # just ends the line.
        return None
    except requests.exceptions.HTTPError as exc:
        outcome = _recover_expired_tfa_session(args, exc, session_args)
        if outcome == RETRY:
            return _invoke(args, func)  # retry once, as the one-shot CLI does
        if outcome != HANDLED:
            _emit_http_error(args, exc)
        return None
    except ValueError as exc:
        cli_main._emit_error(args, 0, str(exc))
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


def _recover_expired_tfa_session(args, exc, session_args):
    """Fall back to the saved API key when a 2FA session expires, as
    ``main.run_command`` does — and keep the new key on the session, so the
    rest of the REPL's lines work too rather than failing one by one.

    Returns RETRY, HANDLED (reported, nothing left to say) or None (not a 2FA
    expiry, so the caller reports it).
    """
    status, msg = _error_detail(exc)
    if not cli_main._is_tfa_session_expired(status, msg):
        return None
    if not os.path.exists(cli_main.TFAKEY_FILE):
        return None

    print(f"Failed with error {status}: Your 2FA session has expired.")
    os.remove(cli_main.TFAKEY_FILE)
    if not os.path.exists(cli_main.APIKEY_FILE):
        print("Run `vastai tfa login` to start a new 2FA session and try again.")
        return HANDLED

    with open(cli_main.APIKEY_FILE, "r") as reader:
        key = reader.read().strip()
    args.api_key = key
    if session_args is not None:
        session_args.api_key = key
    print(f"Trying again with your normal API Key from {cli_main.APIKEY_FILE}...")
    print("To start a new 2FA session, run: vastai tfa login")
    return RETRY


def _error_detail(exc):
    """(status, message) from an API error, however malformed the response."""
    resp = exc.response
    status = getattr(resp, "status_code", 0)
    try:
        msg = resp.json().get("msg")
    except (ValueError, AttributeError):
        msg = None
    if not isinstance(msg, str):
        # A body that is valid JSON but carries no "msg" would otherwise hand
        # None to _emit_error, which tests it with `in` and raises TypeError.
        msg = "Please log in or sign up" if status == 401 else "(no detail message supplied)"
    return status, msg


def _emit_http_error(args, exc):
    """Format an API error the same way the one-shot CLI's main loop does."""
    status, msg = _error_detail(exc)
    cli_main._emit_error(args, status, msg)


def _print_raw(res):
    try:
        print(json.dumps(res, indent=1, sort_keys=True))
    except (TypeError, ValueError):
        print(json.dumps(res.json(), indent=1, sort_keys=True))
