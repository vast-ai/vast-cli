"""`vastai uninstall` — remove a managed (curl | bash installer) install.

pip installs aren't managed by the installer; for those this command only
prints the correct pip uninstall instructions and exits non-zero — it never
shells out to pip, matching `update`'s same-method discipline.
"""

import sys

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.cli.util import VERSION
from vastai.cli.selfupdate import (
    INSTALL_SH_HINT, is_managed_install, install_root, perform_uninstall,
)
from vastai.cli.utils import get_parser as _get_parser

parser = _get_parser()

PIP_UNINSTALL_HINT = "pip uninstall vastai"


@parser.command(
    argument("-y", "--yes", action="store_true", help="skip the confirmation prompt"),
    usage="vastai uninstall [-y]",
    help="Remove the managed CLI install",
    hidden=True,  # still under testing — remove once ready to announce
    epilog=deindent(f"""
        Removes a CLI installed with the managed installer
        ({INSTALL_SH_HINT}): the install root and its symlinks in
        ~/.local/bin. Config in ~/.config/vastai (your API key) is left
        untouched, so re-running the installer keeps you logged in.
        For pip installs, uninstall with: {PIP_UNINSTALL_HINT}
    """),
)
def uninstall(args):
    if not is_managed_install():
        print(
            "This CLI was not installed with the managed installer, so this "
            f"command can't remove it.\n  Installed via pip? Run: {PIP_UNINSTALL_HINT}",
            file=sys.stderr,
        )
        return 1

    root = install_root()
    if not args.yes:
        if not sys.stdin.isatty():
            print(
                "Refusing to uninstall without confirmation in a non-interactive "
                "shell. Re-run with --yes to skip the prompt.",
                file=sys.stderr,
            )
            return 1
        try:
            answer = input(f"Remove vastai {VERSION} from {root}? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1

    perform_uninstall()
    print(f"vastai {VERSION} uninstalled from {root}.")
    print("Config in ~/.config/vastai was left untouched.")
    return 0
