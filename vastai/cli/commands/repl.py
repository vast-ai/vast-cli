"""`vastai repl` — an interactive shell over the CLI's own commands."""
from vastai.cli.display import deindent
from vastai.cli.utils import get_parser as _get_parser

parser = _get_parser()


@parser.command(
    usage="vastai repl",
    help="Start an interactive vastai shell",
    epilog=deindent("""
        Runs vastai commands from one long-lived prompt, with Tab completion
        over commands, flags and your live instance ids:

            vast> show instances
            vast> destroy instance <tab>

        Commands behave exactly as they do from the shell — same auth, same
        flags, same output. `:help` lists the REPL's own meta-commands.
    """),
)
def repl(args):
    from vastai.cli.repl.session import run_repl
    return run_repl(args)
