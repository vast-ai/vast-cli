"""Tab completion for the REPL.

Inside our own readline loop the completer sees the whole line, so completion
can be staged the way the command tree actually is:

    sh<tab>                    -> show, search, set, ssh-url, ...   (verbs)
    show <tab>                 -> instances, user, invoices, ...    (objects)
    show instances --<tab>     -> --raw, --quiet, ...               (flags)
    destroy instance <tab>     -> live instance ids                 (values)
    :set <tab>                 -> raw, explain, ...                 (meta)

It is also the fast path: `vastai` under argcomplete forks a fresh interpreter
per Tab press, while here the parser is already in memory and ids are cached,
so completion is a dict lookup.
"""
import time

from vastai.cli.repl.catalog import CommandCatalog

VALUE_CACHE_TTL = 30.0  # seconds a fetched id list stays warm


class LiveValues:
    """Cache over the id completers the parser attaches to positionals.

    Each lookup would otherwise be an API round trip on a keystroke, so the
    full list is fetched once per completer and filtered locally. Failures are
    cached too — a down API or a missing key must not hang every Tab press.
    """

    def __init__(self, ttl=VALUE_CACHE_TTL, clock=time.monotonic):
        self._ttl = ttl
        self._clock = clock
        self._cache = {}

    def matching(self, completer, prefix):
        now = self._clock()
        cached = self._cache.get(completer)
        if cached is None or now - cached[0] > self._ttl:
            try:
                values = [str(v) for v in (completer(prefix="") or [])]
            except Exception:
                values = []
            cached = (now, values)
            self._cache[completer] = cached
        return [v for v in cached[1] if v.startswith(prefix)]


class ReplCompleter:
    """A readline completer over the live command tree.

    ``suggestions`` is the whole of the logic and is pure with respect to
    readline (it takes the line, not the terminal state); ``complete`` is just
    the readline protocol adapter around it.
    """

    def __init__(self, catalog, meta_commands=(), meta_arguments=None, values=None):
        self.catalog = catalog if isinstance(catalog, CommandCatalog) else CommandCatalog(catalog)
        self.meta_commands = sorted(meta_commands)
        self.meta_arguments = meta_arguments or {}
        self.values = values if values is not None else LiveValues()
        self.matches = []

    # -- readline protocol -------------------------------------------------
    def complete(self, text, state):
        if state == 0:
            try:
                import readline
                buf = readline.get_line_buffer()[: readline.get_endidx()]
            except Exception:
                buf = text
            try:
                self.matches = self.suggestions(buf, text)
            except Exception:
                self.matches = []  # a broken completion must never break typing
        try:
            return self.matches[state]
        except IndexError:
            return None

    def install(self):
        """Bind this completer to readline. No-op where readline is missing."""
        try:
            import readline
        except ImportError:
            return False
        readline.set_completer(self.complete)
        # Split on whitespace only, so the completer sees ':set' and '--flag'
        # as single tokens and decides for itself what they mean.
        readline.set_completer_delims(" \t\n")
        if "libedit" in (getattr(readline, "__doc__", "") or ""):
            readline.parse_and_bind("bind ^I rl_complete")  # macOS libedit
        else:
            readline.parse_and_bind("tab: complete")
        return True

    # -- the actual logic --------------------------------------------------
    def suggestions(self, buf, text=None):
        """Candidates for the token being typed at the end of ``buf``."""
        if text is None:
            text = "" if (not buf or buf[-1].isspace()) else buf.split()[-1]
        stripped = buf.lstrip()
        if stripped.startswith("!"):
            return []  # shell escape: the shell's business, not ours
        if stripped.startswith(":"):
            return self._meta(stripped, text)

        tokens = stripped.split()
        typed = tokens if (not stripped or buf[-1:].isspace()) else tokens[:-1]

        if not typed:
            return self._starting_with(self.catalog.first_words, text)

        if len(typed) == 1 and typed[0] in self.catalog.verbs and not text.startswith("-"):
            return self._starting_with(self.catalog.objects(typed[0]), text)

        name = self.catalog.resolve(typed)
        if name is None:
            return []
        if text.startswith("-"):
            return self._starting_with(self.catalog.flags(name), text)
        return self._values(name, typed, text)

    def _values(self, name, typed, text):
        """Complete an argument value: a flag's choices, else live ids."""
        flag = self.catalog.flags(name).get(typed[-1])
        if flag is not None and flag.nargs != 0:  # a flag still awaiting its value
            if flag.choices:
                return self._starting_with([str(c) for c in flag.choices], text)
            return self._live(getattr(flag, "completer", None), text)
        return self._live(self.catalog.value_completer(name), text)

    def _live(self, completer, text):
        return self.values.matching(completer, text) if completer else []

    def _meta(self, stripped, text):
        words = stripped.split()
        if len(words) == 1 and not stripped[-1].isspace():
            return self._starting_with(self.meta_commands, text)
        options = self.meta_arguments.get(words[0], ())
        if callable(options):
            options = options(words[1:])
        return self._starting_with(options, text)

    @staticmethod
    def _starting_with(candidates, text):
        return sorted(c for c in candidates if c.startswith(text))
