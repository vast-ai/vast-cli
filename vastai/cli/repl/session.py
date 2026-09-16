"""The `vastai repl` loop: the same CLI, one live process.

    vast> show instances
    vast> search offers 'gpu_name=RTX_4090 num_gpus=1' -o dph
    vast> destroy instance <tab>      # completes from your live instances
    vast> :set raw on                 # global flags, for the whole session
    vast> !grep 4090 offers.txt       # shell escape

Anything that isn't a `:meta` command or a `!shell` escape is handed to the
same parser `vastai` uses, so behaviour is identical to the one-shot CLI.
"""
import copy
import os
import shutil
import subprocess
import sys
import textwrap

from vastai.cli.repl.bridge import run_line
from vastai.cli.repl.catalog import CommandCatalog
from vastai.cli.repl.completion import ReplCompleter
from vastai.cli.util import DIRS

HISTORY_FILE = os.path.join(DIRS["state"], "repl_history")
HISTORY_LENGTH = 1000

# Global flags that persist for the session; `:set <flag>` toggles one.
SESSION_FLAGS = ("raw", "explain", "curl", "full", "no_color")

EXIT_WORDS = ("exit", "quit", "q")

META_COMMANDS = (":help", ":set", ":history", ":clear", ":quit")

BANNER = """\
vastai REPL — every vastai command, without the startup cost.
  Tab completes commands, flags and live instance ids.
  help for commands, :help for REPL meta-commands, exit or Ctrl-D to leave."""

META_HELP = """\
REPL meta-commands:
  :help                  this message
  :set                   show the session's global flags
  :set <flag> [on|off]   set one (raw, explain, curl, full, no-color); no value toggles
  :history [N]           last N lines (default 20)
  :clear                 clear the screen
  :quit                  leave (so do exit, quit, q and Ctrl-D)
  !<command>             run a shell command
Everything else is a vastai command — run `help` for the full list, or
`<command> --help` for one command. Global flags typed on a line
(`show instances --raw`) apply to that line only."""


class Repl:
    def __init__(self, parser, session_args, stdout=None):
        self.parser = parser
        # A copy: `:set raw on` is the session's business, not the caller's.
        self.args = copy.copy(session_args)
        self.out = stdout or sys.stdout
        self.catalog = CommandCatalog(parser)
        self.completer = ReplCompleter(
            self.catalog,
            meta_commands=META_COMMANDS,
            meta_arguments={":set": self._set_completions},
        )

    # -- one line ----------------------------------------------------------
    def handle(self, line):
        """Run one input line. Returns False when the session should end."""
        s = line.strip()
        if not s:
            return True
        if s in EXIT_WORDS:
            return False
        if s.startswith("!"):
            return self._shell(s[1:].strip())
        if s.startswith(":"):
            return self._meta(s)

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

    def _shell(self, command):
        if command:
            sys.stdout.flush()  # our output precedes the child's, not the reverse
            subprocess.call(command, shell=True)
        return True

    # -- meta commands -----------------------------------------------------
    def _meta(self, s):
        word, _, rest = s.partition(" ")
        rest = rest.strip()
        if word in (":quit", ":exit", ":q"):
            return False
        if word in (":help", ":h", ":?"):
            self._print(META_HELP)
        elif word == ":set":
            self._set(rest)
        elif word == ":history":
            self._history(rest)
        elif word == ":clear":
            self._clear()
        else:
            self._print(f"unknown meta-command '{word}' (try :help)")
        return True

    def _set(self, rest):
        parts = rest.split()
        if not parts:
            self._print("  " + "\n  ".join(
                f"{_dashed(f)}: {'on' if getattr(self.args, f, False) else 'off'}"
                for f in SESSION_FLAGS))
            return
        flag = parts[0].replace("-", "_")
        if flag not in SESSION_FLAGS:
            self._print(f"unknown flag '{parts[0]}' (one of: "
                        f"{', '.join(_dashed(f) for f in SESSION_FLAGS)})")
            return
        if len(parts) > 1:
            value = parts[1].lower() in ("on", "true", "yes", "1")
        else:
            value = not getattr(self.args, flag, False)
        setattr(self.args, flag, value)
        self._print(f"{_dashed(flag)}: {'on' if value else 'off'}")

    def _set_completions(self, typed):
        """Completions after `:set` — a flag name, then on/off."""
        if not typed:
            return [_dashed(f) for f in SESSION_FLAGS]
        return ["on", "off"]

    def _history(self, rest):
        try:
            import readline
        except ImportError:
            self._print("history is unavailable (no readline on this platform)")
            return
        count = int(rest) if rest.isdigit() else 20
        total = readline.get_current_history_length()
        for i in range(max(1, total - count + 1), total + 1):
            self._print(f"{i:5}  {readline.get_history_item(i)}")

    def _clear(self):
        subprocess.call("cls" if os.name == "nt" else "clear", shell=True)

    def _print(self, text):
        print(text, file=self.out)

    # -- the loop ----------------------------------------------------------
    def prompt(self):
        on = [_dashed(f) for f in SESSION_FLAGS if getattr(self.args, f, False)]
        return f"vast[{','.join(on)}]> " if on else "vast> "

    def run(self):
        if not sys.stdin.isatty():
            return self.run_script(sys.stdin)
        self._setup_terminal()
        self._print(BANNER)
        while True:
            try:
                line = input(self.prompt())
            except KeyboardInterrupt:
                self._print("^C")
                continue
            except EOFError:
                self._print("")
                break
            if not self.handle(line):
                break
        _save_history()
        return 0

    def run_script(self, stream):
        """Non-interactive input (a pipe or a heredoc): run each line, no prompt."""
        for line in stream:
            keep_going = self.handle(line)
            sys.stdout.flush()
            if not keep_going:
                break
        return 0

    def _setup_terminal(self):
        self._wire_live_completions()
        if not self.completer.install():
            return
        import readline
        readline.set_history_length(HISTORY_LENGTH)
        try:
            readline.read_history_file(HISTORY_FILE)
        except OSError:
            pass

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
                self.args, {"internal": True, "field": field})

        set_completers(instance_machine_fn=ids("machine_id"), instance_fn=ids("id"))


def _dashed(flag):
    return flag.replace("_", "-")


def _save_history():
    try:
        import readline
        readline.write_history_file(HISTORY_FILE)
    except (ImportError, OSError):
        pass


def run_repl(args):
    from vastai.cli.main import parser
    Repl(parser, args).run()
