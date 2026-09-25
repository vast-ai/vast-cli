"""The `vastai repl` loop: the same CLI, one live process.

    vast> show instances
    vast> search offers 'gpu_name=RTX_4090 num_gpus=1' -o dph
    vast> destroy instance <tab>      # completes from your live instances

Every line is handed to the same parser `vastai` uses, so behaviour is
identical to the one-shot CLI — only faster, because the interpreter and the
command tree load once. Type `help` for the commands, `clear` to clear the
screen, `exit` or Ctrl-D to leave.
"""
import copy
import os
import shutil
import sys
import textwrap

from vastai.cli.repl.bridge import run_line
from vastai.cli.repl.catalog import CommandCatalog
from vastai.cli.repl.completion import ReplCompleter
from vastai.cli.util import APIKEY_FILE, TFAKEY_FILE

PROMPT = "vast> "
EXIT_WORDS = ("exit", "quit", "q")
CLEAR_WORDS = ("clear", "cls")
CLEAR_SCREEN = "\033[H\033[2J\033[3J"  # cursor home, clear screen, clear scrollback


class Repl:
    def __init__(self, parser, session_args, stdout=None):
        self.parser = parser
        # A copy: the session's own state is not the caller's.
        self.args = copy.copy(session_args)
        self.out = stdout or sys.stdout
        self._stored_key = _stored_api_key()
        # Whether this session's key came from the config file. A key from
        # $VAST_API_KEY or --api-key outranks the file (the CLI says so, and
        # `set api-key` warns about it), so it must not be replaced by one.
        self._from_disk = getattr(session_args, "api_key", None) in (None, self._stored_key)
        self.catalog = CommandCatalog(parser)
        self.completer = ReplCompleter(self.catalog)

    # -- one line ----------------------------------------------------------
    def handle(self, line):
        """Run one input line. Returns False when the session should end."""
        s = line.strip()
        if not s:
            return True
        if s in EXIT_WORDS:
            return False
        if s in CLEAR_WORDS:
            self._clear_screen()
            return True

        # Leading global flags (`--raw show user`) are the parser's business,
        # not part of the command name.
        tokens = self.catalog.strip_options(s.split())
        if tokens and tokens[0] == "repl":
            self._print("Already in the REPL. Use exit or Ctrl-D to leave.")
            return True
        # Resolve first so a typo gets a short 'did you mean' instead of
        # argparse dumping all ~150 command names. A line that is only flags
        # (`--version`) names no command and goes straight to the parser.
        if tokens and self.catalog.resolve(tokens) is None:
            self._unknown(tokens)
            return True
        run_line(self.parser, s, self.args)
        self._refresh_credentials()
        return True

    def _unknown(self, tokens):
        """Report an unrecognised line. argparse would answer with all ~150
        command names; a verb's own objects, or a few near misses, is the
        answer worth reading."""
        if len(tokens) == 1 and tokens[0] in self.catalog.verbs:
            self._print_wrapped(f"{tokens[0]} takes an object: ",
                                self.catalog.objects(tokens[0]))
            return
        print(f"unknown command: {' '.join(tokens[:2])}", file=sys.stderr)
        suggestions = self.catalog.suggest(tokens)[:6]
        if suggestions:
            self._print_wrapped("did you mean: ", suggestions)
        print("(help lists every command)", file=sys.stderr)

    def _print_wrapped(self, lead, items):
        width = shutil.get_terminal_size(fallback=(80, 24)).columns
        print(textwrap.fill(", ".join(items), width=max(40, width),
                            initial_indent=lead, subsequent_indent=" " * len(lead)),
              file=sys.stderr)

    def _clear_screen(self):
        # Legacy Windows consoles don't honour ANSI escapes; cls always works there.
        if os.name == "nt":
            os.system("cls")
        else:
            self.out.write(CLEAR_SCREEN)
            self.out.flush()

    def _print(self, text):
        print(text, file=self.out)

    def _refresh_credentials(self):
        """Pick up a key written mid-session by `set api-key` or `tfa login`.

        Those commands write the config file but not our namespace, so without
        this the session would keep sending the key it started with — often
        none at all, leaving every later line to fail on auth. Only a session
        that took its key from the file follows the file; one running on
        $VAST_API_KEY or --api-key keeps what it was given, as the one-shot CLI
        would. A key that disappears is dropped rather than reused: an expired
        2FA session with no fallback should report "no API key", not repeat the
        same failure on every line.
        """
        if not self._from_disk:
            return
        key = _stored_api_key()
        if key == self._stored_key:
            return
        self.args.api_key = key
        self._stored_key = key
        self.completer.values.clear()  # ids belong to the old account

    # -- the loop ----------------------------------------------------------
    def run(self):
        self._setup_terminal()
        while True:
            try:
                line = input(PROMPT)
            except KeyboardInterrupt:
                self._print("^C")
                continue
            except EOFError:
                self._print("")
                break
            if not self.handle(line):
                break

    def _setup_terminal(self):
        """Wire completion. History lives in readline for the session only —
        persisting it would put whatever was typed, credentials included, in
        plain text on disk, which wants a redaction design of its own."""
        self._wire_live_completions()
        self.completer.install()

    def _wire_live_completions(self):
        """Point the parser's id completers at this session.

        The one-shot CLI wires these for argcomplete using only $VAST_API_KEY;
        rebinding them here means `destroy instance <tab>` works for a key that
        came from the config file or from `--api-key` on the repl command.
        """
        from vastai.cli.commands import instances
        from vastai.cli.parser import set_completers

        def ids(field):
            return lambda **kw: instances.show__instances(
                self._completion_args(), {"internal": True, "field": field})

        set_completers(instance_machine_fn=ids("machine_id"), instance_fn=ids("id"))

    def _completion_args(self):
        """Args for completion's own API calls: this session's auth, endpoint
        and retries, with the output modes off. `--curl` in particular makes
        the client print a curl command and exit, which would otherwise land in
        the middle of the prompt on every Tab press.
        """
        args = copy.copy(self.args)
        for flag in ("explain", "curl", "raw", "full"):
            setattr(args, flag, False)
        args.retry = 1  # a Tab press must not queue minutes of retries
        return args


def _stored_api_key():
    """The key on disk right now, resolved as the one-shot CLI resolves it."""
    path = TFAKEY_FILE if os.path.exists(TFAKEY_FILE) else APIKEY_FILE
    try:
        with open(path, "r") as reader:
            return reader.read().strip() or None
    except OSError:
        return None


def run_repl(args):
    from vastai.cli.main import parser
    Repl(parser, args).run()
