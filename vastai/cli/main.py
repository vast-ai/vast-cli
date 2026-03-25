"""CLI entry point for vastai."""
import sys
import os
import json
import requests

from vastai.cli.parser import apwrap, argument, MyWideHelpFormatter, set_completers
from vastai.cli.util import (
    APIKEY_FILE, TFAKEY_FILE, VERSION, server_url_default,
    api_key_guard, should_check_for_update, is_pip_package, check_for_update
)

try:
    JSONDecodeError = json.JSONDecodeError
except AttributeError:
    JSONDecodeError = ValueError

# Create the global parser instance
parser = apwrap(
    epilog="Use 'vast COMMAND --help' for more info about a command",
    formatter_class=MyWideHelpFormatter
)


def main():
    # Import all command modules - the import itself triggers decorator
    # registrations on the global parser via _get_parser().
    from vastai.cli.commands import (  # noqa: F401
        instances, offers, machines, teams, keys, endpoints,
        billing, storage, auth, misc, deployments,
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
    parser.add_argument("--retry", help="Retry limit", default=3)
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

    # API key resolution
    if args.api_key is api_key_guard:
        key_file = TFAKEY_FILE if os.path.exists(TFAKEY_FILE) else APIKEY_FILE
        if os.path.exists(key_file):
            with open(key_file, "r") as reader:
                args.api_key = reader.read().strip()
        else:
            args.api_key = None

    # Version update check
    if not args.raw and should_check_for_update:
        try:
            if is_pip_package():
                check_for_update()
        except Exception as e:
            print(f"Error checking for update: {e}")

    # Execute command with error handling
    while True:
        try:
            res = args.func(args)
            if args.raw and res is not None:
                try:
                    print(json.dumps(res, indent=1, sort_keys=True))
                except:
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

            # 2FA Session Key Expired
            if e.response.status_code == 401 and errmsg == "Invalid user key":
                if os.path.exists(TFAKEY_FILE):
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

            print(f"Failed with error {e.response.status_code}: {errmsg}")
            break

        except ValueError as e:
            print(e)
            break


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
