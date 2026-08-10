"""`vastai update` — self-update for managed (curl | bash installer) installs.

pip installs aren't managed by the installer; for those this command only
prints the correct pip upgrade instructions and exits non-zero — it never
shells out to pip, since the CLI cannot know which pip/venv owns its
environment.
"""

import sys

from vastai.cli.parser import argument
from vastai.cli.display import deindent
from vastai.cli.util import VERSION
from vastai.cli.selfupdate import (
    INSTALL_SH_HINT, PIP_UPGRADE_HINT, UpdateError,
    fetch_manifest, is_managed_install, is_newer, perform_update,
)
from vastai.cli.utils import get_parser as _get_parser

parser = _get_parser()

EXIT_STALE = 10  # `update --check` exit code when a newer version exists


@parser.command(
    argument("--check", action="store_true", help="only check for a newer version; exit 0 if current, 10 if an update is available"),
    argument("--version", dest="target_version", metavar="VERSION", help="install a specific version instead of the latest (also how you pin or roll back)"),
    usage="vastai update [--check | --version VERSION]",
    help="Update the CLI to the latest version",
    epilog=deindent("""
        Updates a CLI installed with the managed installer
        (curl -fsSL https://vast.ai/install.sh | bash). The new version is
        installed into a fresh environment and verified before it is swapped
        in, so an interrupted update never leaves a broken CLI. To roll back a
        bad release, pin the previous one: vastai update --version 1.2.3
        For pip installs, update with: pip install --upgrade vastai
    """),
)
def update(args):
    try:
        if args.check:
            latest = fetch_manifest()["latest"]
            if is_newer(latest, VERSION):
                print(f"Update available: {latest} (you have {VERSION})")
                return EXIT_STALE
            print(f"vastai {VERSION} is up to date (latest: {latest})")
            return 0

        if not is_managed_install():
            print(
                "This CLI was not installed with the managed installer, so it "
                f"cannot self-update.\n  Installed via pip? Run: {PIP_UPGRADE_HINT}\n"
                f"  Or switch to the managed install: {INSTALL_SH_HINT}",
                file=sys.stderr,
            )
            return 1

        manifest = fetch_manifest()
        target = args.target_version or manifest["latest"]
        current = VERSION
        if target == current:
            latest = manifest["latest"]
            if args.target_version:
                print(f"vastai {current} is already installed (latest available: {latest}).")
            else:
                print(f"vastai {current} is up to date (latest: {latest}).")
            return 0
        print(f"Updating vastai {current} -> {target} ...")
        perform_update(target, manifest)
        print(f"Done. vastai is now {target}.")
        return 0

    except UpdateError as e:
        print(str(e), file=sys.stderr)
        if not args.check:
            print("The current install was left untouched.", file=sys.stderr)
        return 1
