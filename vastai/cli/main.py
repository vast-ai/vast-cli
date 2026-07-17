"""CLI entry point for vastai."""
import sys
import os
import json
import requests

from vastai.cli.parser import apwrap, argument, MyWideHelpFormatter, set_completers
from vastai.cli.util import (
    APIKEY_FILE, TFAKEY_FILE, VERSION, server_url_default, api_key_guard,
    format_key_suffix,
)

try:
    JSONDecodeError = json.JSONDecodeError
except AttributeError:
    JSONDecodeError = ValueError


def _emit_error(args, status_code, message):
    """Emit a command error in the appropriate format.

    In ``--raw`` mode, prints a JSON error object to stderr so scripts can
    parse it; otherwise prints a human-readable line. Always goes to stderr
    so stdout stays clean for scripting consumers.
    """
    if getattr(args, "raw", False):
        payload = {"error": True, "status_code": status_code, "msg": message}
        print(json.dumps(payload), file=sys.stderr)
        return

    if status_code:
        print(f"Failed with error {status_code}: {message}", file=sys.stderr)
    else:
        print(message, file=sys.stderr)

    if status_code == 401:
        if "Two Factor Authentication" in message:
            print(
                "\nThis endpoint requires a 2FA session. Authenticate with the method you have set up:\n"
                "  vastai tfa login --method-type totp -c <CODE>\n"
                "  vastai tfa login --method-type sms   --secret <SECRET> -c <CODE>\n"
                "  vastai tfa login --method-type email --secret <SECRET> -c <CODE>\n"
                "  vastai tfa login --backup-code ABCD-EFGH-IJKL\n"
                "For SMS or email, first run 'vastai tfa send-sms' or 'vastai tfa send-email' to get <SECRET>.",
                file=sys.stderr,
            )
            return

        env = os.environ.get("VAST_API_KEY")
        file_key = None
        if os.path.exists(APIKEY_FILE):
            try:
                with open(APIKEY_FILE) as f:
                    file_key = f.read().strip()
            except OSError:
                pass

        if env and file_key:
            print(f"  Sent key from $VAST_API_KEY (ends in {format_key_suffix(env)}). Env var overrides the file.", file=sys.stderr)
            print(f"  Unset the VAST_API_KEY env var to use the saved key in {APIKEY_FILE} (ends in {format_key_suffix(file_key)}) instead.", file=sys.stderr)
        elif env:
            print(f"  Sent key from $VAST_API_KEY (ends in {format_key_suffix(env)}). Update the env var with a new key.", file=sys.stderr)
        elif file_key:
            print(f"  Sent key from {APIKEY_FILE} (ends in {format_key_suffix(file_key)}). Update with: vastai set api-key <KEY>", file=sys.stderr)


# Create the global parser instance
parser = apwrap(
    epilog="Use 'vastai COMMAND --help' for more info about a command. AI agent? See https://raw.githubusercontent.com/vast-ai/vast-cli/master/vastai/SKILL.md",
    formatter_class=MyWideHelpFormatter
)


def main():
    # Import all command modules - the import itself triggers decorator
    # registrations on the global parser via _get_parser().
    from vastai.cli.commands import (  # noqa: F401
        instances, offers, machines, teams, keys, endpoints,
        billing, storage, auth, misc, deployments, metrics,
        benchmarks,
        price_increase,
        update,
        # clusters,  # cluster/overlay commands disabled for now
    )

    # Wire up tab completers now that command modules are loaded
    set_completers(
        instance_machine_fn=lambda **kw: instances.show__instances(
            type('Args', (), {'api_key': os.getenv('VAST_API_KEY'), 'url': server_url_default,
                              'retry': 3, 'explain': False, 'curl': False,
                              'quiet': False, 'raw': False})(),
            {'internal': True, 'field': 'machine_id'}),
        instance_fn=lambda **kw: instances.show__instances(
            type('Args', (), {'api_key': os.getenv('VAST_API_KEY'), 'url': server_url_default,
                              'retry': 3, 'explain': False, 'curl': False,
                              'quiet': False, 'raw': False})(),
            {'internal': True, 'field': 'id'}),
    )

    # Add global arguments
    parser.add_argument("--url", help="Server REST API URL", default=server_url_default)
    parser.add_argument("--retry", help="Retry limit", type=int, default=3)
    parser.add_argument("--explain", action="store_true", help="Output verbose explanation of mapping of CLI calls to HTTPS API endpoints")
    parser.add_argument("--raw", action="store_true", help="Output machine-readable json")
    parser.add_argument("--full", action="store_true", help="Print full results instead of paging with `less` for commands that support it")
    parser.add_argument("--curl", action="store_true", help="Show a curl equivalency to the call")
    parser.add_argument("--api-key", help="API Key to use. defaults to using the one stored in {}".format(APIKEY_FILE), type=str, required=False, default=os.getenv("VAST_API_KEY", api_key_guard))
    parser.add_argument("--version", help="Show CLI version", action="version", version=VERSION)
    parser.add_argument("--no-color", action="store_true", help="Disable colored output for commands that support it")

    # Tab completion
    try:
        import argcomplete
        import argparse

        from typing import List, Optional
        from vastai.cli.parser import build_command_maps, two_stage_command_completions
        class MyAutocomplete(argcomplete.CompletionFinder):
            # Two-stage (verb -> object) completion over the flat "verb object"
            # subparser names. Logic in parser.py (pure + unit-tested).
            def _command_maps(self):
                cached = getattr(self, "_cmd_maps", None)
                if cached is None:
                    cached = self._cmd_maps = build_command_maps(self._parser)
                return cached

            def _get_completions(self, comp_words, cword_prefix, cword_prequote, last_wordbreak_pos):
                verbs, verb_objs, singles = self._command_maps()
                cands, merged = two_stage_command_completions(
                    comp_words, cword_prefix, verbs, verb_objs, singles)
                if cands is not None:
                    return cands
                return super()._get_completions(merged, cword_prefix, cword_prequote, last_wordbreak_pos)

            def quote_completions(self, completions: List[str], cword_prequote: str, last_wordbreak_pos: Optional[int]) -> List[str]:
                pre = super().quote_completions(completions, cword_prequote, last_wordbreak_pos)
                return sorted(pre, key=lambda x: x.startswith('-'))

        myautocc = MyAutocomplete()
        myautocc(parser.parser)
    except ImportError:
        pass

    args = parser.parse_args()

    # Passive upgrade nudge: best-effort, ≤1 manifest GET + ≤1 stderr line per
    # 24h, silent when offline/piped/CI. Never raises. Opt out with
    # VASTAI_NO_UPDATE_CHECK=1. Runs first so it's visible before any command
    # output, not buried after it. See selfupdate.py and §7.
    from vastai.cli.selfupdate import notify_update
    notify_update(args)

    # API key resolution
    if args.api_key is api_key_guard:
        key_file = TFAKEY_FILE if os.path.exists(TFAKEY_FILE) else APIKEY_FILE
        if os.path.exists(key_file):
            with open(key_file, "r") as reader:
                args.api_key = reader.read().strip()
        else:
            args.api_key = None

    # Execute command with error handling
    while True:
        try:
            res = args.func(args)

            if args.raw and res is not None:
                try:
                    print(json.dumps(res, indent=1, sort_keys=True))
                except (TypeError, ValueError):
                    print(json.dumps(res.json(), indent=1, sort_keys=True))
                sys.exit(0)
            sys.exit(res)

        except requests.exceptions.HTTPError as e:
            try:
                errmsg = e.response.json().get("msg")
            except JSONDecodeError:
                if e.response.status_code == 401:
                    errmsg = "Please log in or sign up"
                else:
                    errmsg = "(no detail message supplied)"

            # 2FA session key expired -> retry with long-lived API key
            if (e.response.status_code == 401 and errmsg == "Invalid user key"
                    and os.path.exists(TFAKEY_FILE)):
                print(f"Failed with error {e.response.status_code}: Your 2FA session has expired.")
                os.remove(TFAKEY_FILE)
                if os.path.exists(APIKEY_FILE):
                    with open(APIKEY_FILE, "r") as reader:
                        args.api_key = reader.read().strip()
                        print(f"Trying again with your normal API Key from {APIKEY_FILE}...")
                        continue
                else:
                    print("Please log in using the `tfa login` command and try again.")
                    break

            _emit_error(args, e.response.status_code, errmsg)
            break

        except ValueError as e:
            _emit_error(args, 0, str(e))
            break


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
