"""What the REPL knows about the CLI's command tree.

Commands are registered on one argparse parser as flat ``"verb object"``
subparser names ("show instances"). The catalog derives the two-stage view of
that — verbs, the objects each verb takes, bare commands, per-command flags —
once at startup, so completion and command resolution stay dict lookups instead
of a walk over ~150 subparsers on every keystroke.
"""
import argparse
import difflib

from vastai.cli.parser import build_command_maps


class CommandCatalog:
    """Two-stage (verb -> object) index over a live ``apwrap`` parser."""

    def __init__(self, parser):
        self._parser = getattr(parser, "parser", parser)
        self.verbs, self.verb_objects, self.singles = build_command_maps(self._parser)
        self._choices = self._subparser_choices()
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

    def resolve(self, tokens):
        """The command name a tokenised line names, or None if it names none.

        Mirrors ``apwrap.parse_args``: a verb absorbs the next token as its
        object, but never a flag, so ``update --check`` stays the bare command.
        """
        if not tokens:
            return None
        if tokens[0] in self.verbs and len(tokens) > 1 and not tokens[1].startswith("-"):
            fused = f"{tokens[0]} {tokens[1]}"
            if fused in self._choices:
                return fused
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
        """``{"--flag": action}`` for one command, cached after the first lookup."""
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

    def value_completer(self, name):
        """The completer attached to a command's first completable positional.

        ``apwrap._add_completer`` tags id/machine/ssh positionals with a
        completer function; that is what turns ``destroy instance <tab>`` into a
        list of live instance ids.
        """
        sub = self._choices.get(name)
        if sub is None:
            return None
        for action in sub._actions:
            if not action.option_strings and getattr(action, "completer", None):
                return action.completer
        return None
