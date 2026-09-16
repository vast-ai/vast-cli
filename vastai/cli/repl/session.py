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
from vastai.cli.util import APIKEY_FILE, DIRS, TFAKEY_FILE

HISTORY_FILE = os.path.join(DIRS["state"], "repl_history")
HISTORY_LENGTH = 1000

# Global flags that persist for the session; `:set <flag>` toggles one.
SESSION_FLAGS = ("raw", "explain", "curl", "full", "no_color")

EXIT_WORDS = ("exit", "quit", "q")

ON_VALUES = ("on", "true", "yes", "1")
OFF_VALUES = ("off", "false", "no", "0")

# Lines that carry a credential. They run normally but are kept out of the
# history file, which is plain text on disk and readable via `:history`.
# `tfa ` covers the whole family: login, auth-new, delete and regen-codes all
# take one-time codes or backup codes, and a new subcommand would too. These
# also catch a credential passed through a `!` shell escape, where there is no
# vastai command for us to resolve.
SECRET_COMMANDS = ("set api-key", "tfa ")

# Options whose value is a credential, matched by dest so that every spelling
# argparse accepts is covered — `--api-key`, `--api-key=...`, `-s`, and the
# abbreviations argparse resolves, such as `--api`.
SECRET_DESTS = frozenset({"api_key", "secret", "backup_code", "code"})

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
        self.failures = 0
        self._stored_key = _stored_api_key()
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
            self.failures += 1
            return True
        if run_line(self.parser, s, self.args):
            self.failures += 1
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

    def _shell(self, command):
        if command:
            sys.stdout.flush()  # our output precedes the child's, not the reverse
            if subprocess.call(command, shell=True):
                self.failures += 1  # `!false` fails the script, as in a shell
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
            self.failures += 1
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
            self.failures += 1
            return
        if len(parts) > 1:
            if parts[1].lower() in ON_VALUES:
                value = True
            elif parts[1].lower() in OFF_VALUES:
                value = False
            else:  # never let a typo silently turn a flag off
                self._print(f"expected on or off, not '{parts[1]}'")
                self.failures += 1
                return
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

    def _is_secret(self, line):
        """Whether a line carries a credential that must not be written to disk."""
        lowered = line.lower()
        if any(fragment in lowered for fragment in SECRET_COMMANDS):
            return True
        tokens = line.split()
        name = self.catalog.resolve(self.catalog.strip_options(tokens))
        for token in tokens:
            if not token.startswith("-") or token == "-":
                continue
            action = (self.catalog.option(name, token) if name else None) \
                or self.catalog.global_option(token)
            if action is not None and action.dest in SECRET_DESTS:
                return True
        return False

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

    def _refresh_credentials(self):
        """Pick up a key written mid-session by `set api-key` or `tfa login`.

        Those commands write the config file but not our namespace, so without
        this the session would keep sending the key it started with — often
        none at all, leaving every later line to fail on auth.
        """
        key = _stored_api_key()
        if key == self._stored_key:
            return
        if key is not None:
            self.args.api_key = key
        elif self.args.api_key == self._stored_key:
            # The key we were using was just removed (an expired 2FA session
            # with nothing to fall back to). Keep using it and every line would
            # fail the same way; dropping it gets the real "no API key" advice.
            self.args.api_key = None
        self._stored_key = key
        self.completer.values.clear()  # ids belong to the old account

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
            if self._is_secret(line):
                _forget_last_history_entry()  # a key must not reach the disk
            if not self.handle(line):
                break
        _save_history()
        return 0

    def run_script(self, stream):
        """Non-interactive input (a pipe or a heredoc): run each line, no
        prompt. Returns nonzero if any line failed, so CI can see it."""
        for line in stream:
            keep_going = self.handle(line)
            sys.stdout.flush()
            if not keep_going:
                break
        return 1 if self.failures else 0

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
                self._completion_args(), {"internal": True, "field": field})

        set_completers(instance_machine_fn=ids("machine_id"), instance_fn=ids("id"))


def _dashed(flag):
    return flag.replace("_", "-")


def _forget_last_history_entry():
    try:
        import readline
        length = readline.get_current_history_length()
        if length:
            readline.remove_history_item(length - 1)
    except (ImportError, ValueError):
        pass


def _stored_api_key():
    """The key on disk right now, resolved as the one-shot CLI resolves it."""
    path = TFAKEY_FILE if os.path.exists(TFAKEY_FILE) else APIKEY_FILE
    try:
        with open(path, "r") as reader:
            return reader.read().strip() or None
    except OSError:
        return None


def _save_history():
    try:
        import readline
        readline.write_history_file(HISTORY_FILE)
    except (ImportError, OSError):
        pass


def run_repl(args):
    from vastai.cli.main import parser
    # A clean session returns None, not 0: main.run_command prints any non-None
    # result under --raw, and an exit code is not command output.
    return Repl(parser, args).run() or None
