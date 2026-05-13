"""CLI entry point for vastai."""
import sys
import os
import json
import requests

from vastai.cli.parser import apwrap, argument, MyWideHelpFormatter, set_completers
from vastai.cli.util import (
    APIKEY_FILE, TFAKEY_FILE, VERSION, server_url_default, api_key_guard,
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
    else:
        if status_code:
            print(f"Failed with error {status_code}: {message}", file=sys.stderr)
        else:
            print(message, file=sys.stderr)


def _gather_key_sources(cli_flag_value):
    """Return all configured API key sources in precedence order.

    Each entry is ``(source_label, key_value)``. The first entry is the one
    the CLI will actually use; remaining entries exist for diagnostics so a
    401 message can tell the user which other keys are configured.
    """
    sources = []
    if cli_flag_value is not api_key_guard:
        sources.append(("--api-key flag", cli_flag_value))
    env = os.getenv("VAST_API_KEY")
    if env:
        sources.append(("VAST_API_KEY env var", env))
    if os.path.exists(TFAKEY_FILE):
        try:
            with open(TFAKEY_FILE) as f:
                sources.append((f"TFA session file ({TFAKEY_FILE})", f.read().strip()))
        except OSError:
            pass
    if os.path.exists(APIKEY_FILE):
        try:
            with open(APIKEY_FILE) as f:
                sources.append((f"API key file ({APIKEY_FILE})", f.read().strip()))
        except OSError:
            pass
    return sources


def _format_key_diagnostic(used_source, used_key, all_sources):
    def last4(k):
        return f"...{k[-4:]}" if k and len(k) >= 4 else "(empty)"
    lines = [f"  Used key from: {used_source} (ends in {last4(used_key)})"]
    others = [(s, k) for s, k in all_sources if s != used_source]
    if others:
        lines.append("  Also configured:")
        for s, k in others:
            lines.append(f"    - {s} (ends in {last4(k)})")
        lines.append("  Tip: env var beats file. Unset VAST_API_KEY or pass --api-key to use a different key.")
    return "\n".join(lines)


# Create the global parser instance
parser = apwrap(
    epilog="Use 'vast COMMAND --help' for more info about a command. AI agent? See https://raw.githubusercontent.com/vast-ai/vast-cli/master/vastai/SKILL.md",
    formatter_class=MyWideHelpFormatter
)


def main():
    # Import all command modules - the import itself triggers decorator
    # registrations on the global parser via _get_parser().
    from vastai.cli.commands import (  # noqa: F401
        instances, offers, machines, teams, keys, endpoints,
        billing, storage, auth, misc, deployments, metrics,
        benchmarks,
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
    parser.add_argument("--api-key", help="API key to use. If unset, falls back to $VAST_API_KEY, then {}".format(APIKEY_FILE), type=str, required=False, default=api_key_guard)
    parser.add_argument("--version", help="Show CLI version", action="version", version=VERSION)
    parser.add_argument("--no-color", action="store_true", help="Disable colored output for commands that support it")

    # Tab completion
    try:
        import argcomplete

        from typing import List, Optional
        class MyAutocomplete(argcomplete.CompletionFinder):
            def quote_completions(self, completions: List[str], cword_prequote: str, last_wordbreak_pos: Optional[int]) -> List[str]:
                pre = super().quote_completions(completions, cword_prequote, last_wordbreak_pos)
                return sorted(pre, key=lambda x: x.startswith('-'))

        myautocc = MyAutocomplete()
        myautocc(parser.parser)
    except ImportError:
        pass

    args = parser.parse_args()

    # API key resolution. Precedence (highest first): --api-key flag,
    # $VAST_API_KEY, TFA session file, API key file. The source label is
    # kept around so a 401 can tell the user which key was rejected.
    original_cli_flag = args.api_key
    key_sources = _gather_key_sources(original_cli_flag)
    if key_sources:
        key_source, args.api_key = key_sources[0]
    else:
        key_source = None
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

            if e.response.status_code == 401 and errmsg == "Invalid user key":
                # TFA session rejected -> assume expiry, retry with long-lived key.
                if key_source and key_source.startswith("TFA session file"):
                    print(f"Failed with error {e.response.status_code}: Your 2FA session has expired.")
                    try:
                        os.remove(TFAKEY_FILE)
                    except OSError:
                        pass
                    if os.path.exists(APIKEY_FILE):
                        with open(APIKEY_FILE, "r") as reader:
                            args.api_key = reader.read().strip()
                        key_source = f"API key file ({APIKEY_FILE})"
                        key_sources = _gather_key_sources(original_cli_flag)
                        print(f"Trying again with your normal API Key from {APIKEY_FILE}...")
                        continue
                    else:
                        print("Please log in using the `tfa login` command and try again.")
                        break

                _emit_error(args, e.response.status_code, errmsg)
                if key_source and not getattr(args, "raw", False):
                    print(_format_key_diagnostic(key_source, args.api_key, key_sources), file=sys.stderr)
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
