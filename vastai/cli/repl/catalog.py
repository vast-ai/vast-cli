"""What the REPL knows about the CLI's command tree.

Commands are registered on one argparse parser as flat ``"verb object"``
subparser names ("show instances"). The catalog derives the two-stage view of
that — verbs, the objects each verb takes, bare commands, per-command options —
once at startup, so completion and command resolution stay dict lookups instead
of a walk over ~150 subparsers on every keystroke.
"""
import argparse
import difflib

from vastai.cli.parser import build_command_maps


def option_action(parser, token):
    """The action a flag token names on a parser: exact match, ``--flag=value``,
    or the unambiguous abbreviation argparse itself would accept."""
    options = parser._option_string_actions
    name = token.split("=", 1)[0]
    action = options.get(name)
    if action is not None:
        return action
    if name.startswith("--"):
        matches = {id(a): a for opt, a in options.items() if opt.startswith(name)}
        if len(matches) == 1:
            return next(iter(matches.values()))
    return None


class CommandCatalog:
    """Two-stage (verb -> object) index over a live ``apwrap`` parser."""

    def __init__(self, parser):
        self._parser = getattr(parser, "parser", parser)
        self.verbs, self.verb_objects, self.singles = build_command_maps(self._parser)
        self._choices = self._subparser_choices()
        # Hidden commands are left out of the maps above — they are gated from
        # discovery, not from use — but a line naming one must still resolve,
        # or the REPL would reject a command the one-shot CLI runs.
        self._runnable_verbs = {name.split(" ")[0] for name in self._choices if " " in name}
        self._flag_cache = {}
        self.first_words = sorted(self.verbs | self.singles)
        self.names = sorted(self.singles | {
            f"{verb} {obj}" for verb, objs in self.verb_objects.items() for obj in objs})

    def _subparser_choices(self):
        for action in self._parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action.choices
        return {}

    def objects(self, verb):
        """The objects registered for a verb, e.g. show -> instances, user, ..."""
        return sorted(self.verb_objects.get(verb, ()))

    def strip_options(self, tokens):
        """Drop the global options a line leads with (``--raw show user``), so
        what's left starts at the command name."""
        i = 0
        while i < len(tokens) and tokens[i].startswith("-") and tokens[i] != "-":
            token = tokens[i]
            action = option_action(self._parser, token)
            i += 1
            if action is not None and action.nargs != 0 and "=" not in token:
                i += 1  # the option's value
        return tokens[i:]

    def resolve(self, tokens):
        """The command name a tokenised line names, or None if it names none.

        Mirrors ``apwrap.parse_args``: a verb absorbs the next token as its
        object, but never a flag, so ``update --check`` stays the bare command.
        """
        if not tokens:
            return None
        if tokens[0] in self._runnable_verbs and len(tokens) > 1 and not tokens[1].startswith("-"):
            fused = f"{tokens[0]} {tokens[1]}"
            if fused in self._choices:
                return fused
            # `update bogus` is not the bare `update` command. Only a bare
            # command that takes an argument can legitimately own a second word.
            if not self.takes_positional(tokens[0]):
                return None
        return tokens[0] if tokens[0] in self._choices else None

    def suggest(self, tokens):
        """Close command names for a line that resolves to nothing — 'did you mean'."""
        if not tokens:
            return []
        head = tokens[0]
        if head in self.verbs:  # known verb, missing or misspelled object
            objs = self.objects(head)
            near = difflib.get_close_matches(tokens[1], objs, n=3, cutoff=0.5) if len(tokens) > 1 else []
            return [f"{head} {obj}" for obj in (near or objs)]
        return (difflib.get_close_matches(" ".join(tokens[:2]), self.names, n=3, cutoff=0.5)
                or difflib.get_close_matches(head, self.first_words, n=3, cutoff=0.5))

    def flags(self, name):
        """``{"--flag": action}`` for one command, cached after the first lookup.

        Long forms only: they are what completion offers. Use ``option`` to look
        up a token the user actually typed, which may be a short alias.
        """
        if name not in self._flag_cache:
            sub = self._choices.get(name)
            flags = {}
            if sub is not None:
                for action in sub._actions:
                    for opt in action.option_strings:
                        if opt.startswith("--"):
                            flags[opt] = action
            self._flag_cache[name] = flags
        return self._flag_cache[name]

    def option(self, name, token):
        """The action a flag token names on one command, short form included."""
        sub = self._choices.get(name)
        return option_action(sub, token) if sub is not None else None

    def global_option(self, token):
        """The action a flag token names among the global options."""
        return option_action(self._parser, token)

    def positionals(self, name):
        sub = self._choices.get(name)
        return [a for a in sub._actions if not a.option_strings] if sub is not None else []

    def takes_positional(self, name):
        return bool(self.positionals(name))

    def positional_completer(self, name, index=0):
        """The completer for a command's index-th positional, if it has one.

        ``apwrap._add_completer`` tags id/machine/ssh positionals with a
        completer function; that is what turns ``destroy instance <tab>`` into a
        list of live instance ids, and the second argument of
        ``update ssh-key <id> <tab>`` into local .pub paths instead.
        """
        positionals = self.positionals(name)
        if not positionals:
            return None
        if index >= len(positionals):
            # A trailing nargs='+'/'*' positional keeps accepting values.
            last = positionals[-1]
            return getattr(last, "completer", None) if last.nargs in ("+", "*") else None
        return getattr(positionals[index], "completer", None)
