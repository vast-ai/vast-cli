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
    """Parse and execute one command line, returning its exit status (0 when
    the line ran cleanly), so a piped script can fail the way a shell would."""
    try:
        argv = shlex.split(line)
    except ValueError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return 1
    if not argv:
        return 0

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return _status(exc.code)  # argparse already printed usage or an error

    apply_session_globals(parser, args, session_args, argv)
    func = getattr(args, "func", None)
    if func is None:
        return 0
    return _invoke(args, func, session_args)


def apply_session_globals(parser, args, session_args, argv=()):
    """Carry the session's global flags onto one line's args.

    Presence is read from the line itself rather than by comparing parsed
    values against defaults: an option typed with exactly its default value
    (``--retry 3`` while the session runs with ``--retry 10``) must still win.
    """
    inner = getattr(parser, "parser", parser)
    # Read the flags against the command's own parser (apwrap registers every
    # global on each subparser), so options like --args are known here.
    scope = getattr(getattr(args, "func", None), "mysignature", None) or inner
    typed = explicit_dests(scope, argv)
    for name in SESSION_GLOBALS:
        if name in typed or not hasattr(args, name) or not hasattr(session_args, name):
            continue
        setattr(args, name, getattr(session_args, name))


def explicit_dests(parser, argv):
    """The dests of the options a line actually names, in any form argparse
    accepts (``--flag``, ``--flag=value``, a short alias, an abbreviation).

    Stops where argparse stops treating words as this command's options: at
    ``--`` or at a REMAINDER option, so ``create instance --args --raw`` passes
    ``--raw`` to the container rather than counting it as a global.
    """
    dests = set()
    for token in argv:
        if token == "--":
            break
        if not token.startswith("-") or token == "-":
            continue
        action = option_action(parser, token)
        if action is None:
            continue
        if action.nargs == argparse.REMAINDER:
            break
        dests.add(action.dest)
    return dests


def _invoke(args, func, session_args=None):
    try:
        res = func(args)
    except SystemExit as exc:
        # Commands (and --help) exit the process in one-shot mode; here that
        # just ends the line, keeping whatever status they asked for.
        return _status(exc.code)
    except requests.exceptions.HTTPError as exc:
        outcome = _recover_expired_tfa_session(args, exc, session_args)
        if outcome == RETRY:
            return _invoke(args, func)  # retry once, as the one-shot CLI does
        if outcome != HANDLED:
            _emit_http_error(args, exc)
        return 1
    except ValueError as exc:
        cli_main._emit_error(args, 0, str(exc))
        return 1
    except KeyboardInterrupt:
        print("^C", file=sys.stderr)
        return 1
    except Exception as exc:  # a broken command must not kill the session
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "raw", False) and res is not None:
        _print_raw(res)
    # By CLI convention a command returns its exit code; a payload is a success.
    return res if isinstance(res, int) and not isinstance(res, bool) else 0


def _status(code):
    """An exit status from whatever SystemExit carried: None means success."""
    if code is None:
        return 0
    return code if isinstance(code, int) else 1


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
