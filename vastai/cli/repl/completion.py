"""Tab completion for the REPL.

Inside our own readline loop the completer sees the whole line, so completion
can be staged the way the command tree actually is:

    sh<tab>                    -> show, search, set, ssh-url, ...   (verbs)
    show <tab>                 -> instances, user, invoices, ...    (objects)
    show instances --<tab>     -> --raw, --quiet, ...               (flags)
    destroy instance <tab>     -> live instance ids                 (values)

It is also the fast path: `vastai` under argcomplete forks a fresh interpreter
per Tab press, while here the parser is already in memory and ids are cached,
so completion is a dict lookup.
"""
import argparse
import threading
import time

from vastai.cli.repl.catalog import CommandCatalog

VALUE_CACHE_TTL = 30.0    # seconds a fetched id list stays warm
COMPLETION_BUDGET = 2.0   # seconds a Tab press will wait for that fetch


class LiveValues:
    """Cache over the id completers the parser attaches to positionals.

    Each lookup would otherwise be an API round trip on a keystroke, so the
    full list is fetched once per completer and filtered locally. Failures are
    cached too — a down API or a missing key must not hang every Tab press.
    """

    def __init__(self, ttl=VALUE_CACHE_TTL, clock=time.monotonic,
                 budget=COMPLETION_BUDGET):
        self._ttl = ttl
        self._clock = clock
        self._budget = budget
        self._cache = {}
        self._pending = set()
        self._generation = 0

    def clear(self):
        """Forget every cached list — called when the session's credentials
        change, so Tab can't offer the previous account's ids."""
        self._cache.clear()
        self._pending.clear()
        self._generation += 1  # discard whatever is still in flight

    def matching(self, completer, prefix):
        cached = self._cache.get(completer)
        if cached is None or self._clock() - cached[0] > self._ttl:
            self._fetch(completer)
            cached = self._cache.get(completer)
            if cached is None:
                return []  # still in flight; a later Tab press will have it
        return [v for v in cached[1] if v.startswith(prefix)]

    def _fetch(self, completer):
        """Fetch in a worker, and wait only a moment for it.

        The API client allows 120s per request and retries, so fetching on the
        input thread would let one Tab press freeze the prompt for minutes
        against an unreachable endpoint. Whatever the worker eventually returns
        lands in the cache for the next press.
        """
        if completer in self._pending:
            return
        self._pending.add(completer)
        generation = self._generation

        def work():
            try:
                values = [str(v) for v in (completer(prefix="") or [])]
            except Exception:
                values = []
            if generation != self._generation:
                return  # the account changed while we were fetching
            self._cache[completer] = (self._clock(), values)
            self._pending.discard(completer)

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(self._budget)


class ReplCompleter:
    """A readline completer over the live command tree.

    ``suggestions`` is the whole of the logic and is pure with respect to
    readline (it takes the line, not the terminal state); ``complete`` is just
    the readline protocol adapter around it.
    """

    def __init__(self, catalog, values=None):
        self.catalog = catalog if isinstance(catalog, CommandCatalog) else CommandCatalog(catalog)
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
        # Split on whitespace only, so the completer sees '--flag' and
        # '--flag=value' as single tokens and decides what they mean.
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
        tokens = stripped.split()
        typed = tokens if (not stripped or buf[-1:].isspace()) else tokens[:-1]
        typed = self.catalog.strip_options(typed)  # `--raw show <tab>` completes too

        if not typed:
            return self._starting_with(self.catalog.first_words, text)

        if len(typed) == 1 and typed[0] in self.catalog.verbs and not text.startswith("-"):
            return self._starting_with(self.catalog.objects(typed[0]), text)

        name = self.catalog.resolve(typed)
        if name is None:
            return []
        if text.startswith("-"):
            return self._starting_with(self.catalog.flags(name), text)
        return self._values(name, typed[len(name.split()):], text)

    def _values(self, name, args, text):
        """Complete an argument value: the choices or ids of whichever option or
        positional the cursor sits on."""
        option, index = self._position(name, args)
        if option is not None:
            if option.choices:
                return self._starting_with([str(c) for c in option.choices], text)
            return self._live(getattr(option, "completer", None), text)
        return self._live(self.catalog.positional_completer(name, index), text)

    def _position(self, name, args):
        """Walk a command's arguments as argparse would.

        Returns the option still awaiting values (the cursor is typing one of
        them) and the index of the positional being typed — so a second
        positional gets its own completer, and a multi-value option keeps
        offering its choices.
        """
        option, index, i = None, 0, 0
        while i < len(args):
            token = args[i]
            i += 1
            if token.startswith("-") and token != "-":
                option = None
                action = self.catalog.option(name, token)
                if action is None or action.nargs == 0 or "=" in token:
                    continue
                taken = 0
                while (i < len(args) and _accepts_more(action, taken)
                       and not args[i].startswith("-")):
                    taken += 1
                    i += 1
                if _accepts_more(action, taken):
                    option = action  # still hungry: the cursor's word is its value
                continue
            option = None
            index += 1
        return option, index

    def _live(self, completer, text):
        return self.values.matching(completer, text) if completer else []

    @staticmethod
    def _starting_with(candidates, text):
        return sorted(c for c in candidates if c.startswith(text))


def _accepts_more(action, taken):
    """Whether an option can still absorb another value after `taken` of them."""
    nargs = action.nargs
    if nargs in ("+", "*", argparse.REMAINDER):
        return True
    if nargs == "?":
        return taken < 1
    if isinstance(nargs, int):
        return taken < nargs
    return taken < 1  # nargs None: exactly one value
