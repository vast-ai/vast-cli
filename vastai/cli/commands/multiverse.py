"""`vastai multiverse` — launch the Legion Multiverse TUI.

Opens a Textual TUI that bootstraps Legion in-process (inside legion's own venv):
type English → translate → market dispatch → result, with a prediction-market
view over competing funcimpls. legion needs Python 3.12 and isn't installed in
vast-cli's env, so this launches `python -m multiverse` in legion's venv.
"""
import os
import sys
import subprocess

from vastai.cli.parser import argument
from vastai.cli.utils import get_parser as _get_parser

parser = _get_parser()


def _find_legion_home(override=None):
    """Locate the legion repo (must contain the `multiverse` package)."""
    candidates = [
        override,
        os.environ.get("LEGION_HOME"),
        os.path.expanduser("~/workspace/legion"),
        os.path.join(os.getcwd(), "legion"),
        os.path.join(os.path.dirname(os.getcwd().rstrip("/")), "legion"),
    ]
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "multiverse")):
            return os.path.abspath(c)
    return None


@parser.command(
    argument("--legion-home", type=str, default=None,
             help="Path to the legion repo (else $LEGION_HOME or ~/workspace/legion)"),
    argument("--local", action="store_true",
             help="Self-contained local mode: in-process node, local translate parsers, "
                  "in-process function registration (no remote parse endpoint or deploy)"),
    usage="vastai multiverse [--local] [--legion-home PATH]",
    help="Launch the Legion Multiverse TUI (English -> market dispatch -> result)",
)
def multiverse(args):
    """Launch the Multiverse TUI in legion's Python environment."""
    home = _find_legion_home(args.legion_home)
    if not home:
        print("Could not locate the legion repo (looked for a `multiverse/` package). "
              "Set --legion-home or $LEGION_HOME.", file=sys.stderr)
        return 1
    py = os.path.join(home, ".venv", "bin", "python")
    if not os.path.exists(py):
        print(f"No venv python at {py}; falling back to {sys.executable}.", file=sys.stderr)
        py = sys.executable
    cmd = [py, "-m", "multiverse"]
    if args.local:
        cmd.append("--local")
    try:
        # Inherit stdin/stdout/stderr so Textual drives the real terminal.
        return subprocess.run(cmd, cwd=home).returncode
    except KeyboardInterrupt:
        return 0
