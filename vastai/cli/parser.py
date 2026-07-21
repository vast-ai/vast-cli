"""
Argument parser infrastructure for the Vast.ai CLI.

Extracted from vast.py - contains the core parser wrapper classes
that handle command registration, argument parsing, and tab completion.
"""

from __future__ import unicode_literals, print_function

import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Tab-completion helpers
#
# These reference show__instances which lives in the CLI commands layer.
# We keep them as lazy references (initially None) so this module can be
# imported without pulling in the whole command tree.  The CLI entry-point
# populates them once everything is wired up.
# ---------------------------------------------------------------------------

# Populated later by the CLI entry point
_complete_instance_machine = None
_complete_instance = None

def complete_instance_machine(prefix=None, action=None, parser=None, parsed_args=None):
    if _complete_instance_machine is not None:
        return _complete_instance_machine(prefix=prefix, action=action, parser=parser, parsed_args=parsed_args)
    return []

def complete_instance(prefix=None, action=None, parser=None, parsed_args=None):
    if _complete_instance is not None:
        return _complete_instance(prefix=prefix, action=action, parser=parser, parsed_args=parsed_args)
    return []

def complete_sshkeys(prefix=None, action=None, parser=None, parsed_args=None):
    return [str(m) for m in Path.home().joinpath('.ssh').glob('*.pub')]


# ---------------------------------------------------------------------------
# Two-stage (verb -> object) command-name completion
#
# Pure, unit-testable helpers that turn the flat "verb object" subparser names
# into staged completion. The argcomplete adapter in cli/main.py calls them.
# ---------------------------------------------------------------------------

def build_command_maps(parser):
    """Derive (verbs, verb_objs, singles) from a parser's subparser names.

    Commands flagged hidden (see ``is_hidden_command``) are left out of
    completion — unreleased/feature-flagged functionality, still fully
    runnable if typed directly.
    """
    names = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sp in action.choices.items():
                if getattr(sp, 'hidden', False):
                    continue
                names.append(name)
            break
    verbs, verb_objs, singles = set(), {}, set()
    for name in names:
        verb, sep, obj = name.partition(" ")
        if sep:
            verbs.add(verb)
            verb_objs.setdefault(verb, set()).add(obj)
        else:
            singles.add(verb)
    return verbs, verb_objs, singles


def two_stage_command_completions(comp_words, cword_prefix, verbs, verb_objs, singles):
    """Stage command-name completion. Returns (candidates, merged): candidates is
    the verb/object list, or None to delegate flag completion using merged."""
    n = len(comp_words)
    if n == 1:  # completing the verb / bare command
        return sorted(c for c in (verbs | singles) if c.startswith(cword_prefix)), None
    if n == 2 and comp_words[1] in verbs:  # completing the object for a verb
        objs = verb_objs.get(comp_words[1], set())
        return sorted(o for o in objs if o.startswith(cword_prefix)), None
    # Past the command name: fuse "verb object" so the right subparser is found.
    # Never fuse across a flag, mirroring apwrap.parse_args.
    merged = comp_words
    if n >= 3 and comp_words[1] in verbs and not comp_words[2].startswith("-"):
        merged = [comp_words[0], comp_words[1] + " " + comp_words[2]] + list(comp_words[3:])
    return None, merged


def set_completers(instance_machine_fn=None, instance_fn=None):
    """
    Wire up the tab-completion functions.  Called once from the CLI
    entry-point after all command modules have been loaded.
    """
    global _complete_instance_machine, _complete_instance
    if instance_machine_fn is not None:
        _complete_instance_machine = instance_machine_fn
    if instance_fn is not None:
        _complete_instance = instance_fn


# ---------------------------------------------------------------------------
# Argument wrapper
# ---------------------------------------------------------------------------

class argument(object):
    """Thin wrapper that stores positional and keyword args for later
    application to an argparse subparser."""
    def __init__(self, *args, mutex_group=None, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.mutex_group = mutex_group  # Name of the mutually exclusive group this arg belongs to


class hidden_aliases(object):
    """A list-like that is falsy so argparse won't display aliases in help."""
    def __init__(self, l):
        self.l = l

    def __iter__(self):
        return iter(self.l)

    def __bool__(self):
        return False

    def __nonzero__(self):
        return False

    def append(self, x):
        self.l.append(x)


class MyWideHelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, width=128, max_help_position=50, indent_increment=1)


COMMAND_GROUPS = {
    'vastai.cli.commands.offers':       'Search',
    'vastai.cli.commands.instances':    'Instances',
    'vastai.cli.commands.benchmarks':   'Instances',
    'vastai.cli.commands.machines':     'Host machines',
    'vastai.cli.commands.teams':        'Teams',
    'vastai.cli.commands.keys':         'Auth & keys',
    'vastai.cli.commands.auth':         'Auth & keys',
    'vastai.cli.commands.billing':      'Billing & account',
    'vastai.cli.commands.endpoints':    'Serverless',
    'vastai.cli.commands.deployments':  'Serverless',
    'vastai.cli.commands.metrics':      'Metrics',
    'vastai.cli.commands.storage':      'Storage volumes',
    'vastai.cli.commands.misc':         'Other',
    'vastai.cli.commands.update':       'Other',
}

# Some misc.py commands belong with their target resource section, not Other.
COMMAND_OVERRIDES = {
    'execute':       'Instances',
    'logs':          'Instances',
    'ssh-url':       'Instances',
    'scp-url':       'Instances',
    'take snapshot': 'Instances',
    'reports':       'Host machines',
}

GROUP_ORDER = [
    'Search', 'Instances', 'Host machines', 'Teams', 'Auth & keys',
    'Billing & account', 'Serverless', 'Metrics', 'Storage volumes', 'Other',
]

# ---------------------------------------------------------------------------
# Unreleased/feature-flagged commands
#
# Hidden from --help and tab completion regardless of anything else — a
# discoverability gate, not an access gate: the command still runs if typed
# directly, so internal testing keeps working. Remove an entry once the
# feature is ready to announce.
# ---------------------------------------------------------------------------

HIDDEN_COMMANDS = {
    'search network-volumes',  # network volumes are not yet released
    'create network-volume',
    'list network-volume',
    'unlist network-volume',
}


def is_hidden_command(name, explicit=None):
    """Whether a registered command should be hidden from --help/completion.

    Priority: explicit ``hidden=`` kwarg on the decorator > ``HIDDEN_COMMANDS``.
    Defaults to ``False`` (visible).
    """
    if explicit is not None:
        return bool(explicit)
    return name in HIDDEN_COMMANDS


class GroupedArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that renders subcommands grouped by registering module."""

    def format_help(self):
        sub_action = self._subparsers_action()
        if sub_action is None or not sub_action.choices:
            return super().format_help()

        formatter = self._get_formatter()
        formatter.add_usage(self.usage, self._actions, self._mutually_exclusive_groups)
        formatter.add_text(self.description)

        # Skip the subparsers action; we render commands grouped below.
        for action_group in self._action_groups:
            non_sub_actions = [
                a for a in action_group._group_actions
                if not isinstance(a, argparse._SubParsersAction)
            ]
            if not non_sub_actions:
                continue
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(non_sub_actions)
            formatter.end_section()

        self._add_grouped_commands(formatter, sub_action)
        formatter.add_text(self.epilog)
        return formatter.format_help()

    def _subparsers_action(self):
        for a in self._actions:
            if isinstance(a, argparse._SubParsersAction):
                return a
        return None

    def _add_grouped_commands(self, formatter, sub_action):
        grouped = {}
        for pseudo in sub_action._choices_actions:
            sp = sub_action.choices.get(pseudo.dest)
            if sp is None:
                continue
            if getattr(sp, 'hidden', False):
                continue
            label = COMMAND_OVERRIDES.get(pseudo.dest)
            if label is None:
                func = sp.get_default('func')
                module = getattr(func, '__module__', None)
                label = COMMAND_GROUPS.get(module, 'Other')
            grouped.setdefault(label, []).append(pseudo)

        seen = set()
        for label in GROUP_ORDER:
            if label in grouped:
                formatter.start_section(label)
                formatter.add_arguments(grouped[label])
                formatter.end_section()
                seen.add(label)
        for label, actions in grouped.items():
            if label in seen:
                continue
            formatter.start_section(label)
            formatter.add_arguments(actions)
            formatter.end_section()


# ---------------------------------------------------------------------------
# Main parser wrapper
# ---------------------------------------------------------------------------

class apwrap(object):
    """Wraps :class:`argparse.ArgumentParser` with convenience methods for
    two-word command registration (``verb object``) and tab-completion."""

    def __init__(self, *args, **kwargs):
        if "formatter_class" not in kwargs:
            kwargs["formatter_class"] = MyWideHelpFormatter
        self.parser = GroupedArgumentParser(*args, **kwargs)
        self.parser.set_defaults(func=self.fail_with_help)
        self.subparsers_ = None
        self.subparser_objs = []
        self.added_help_cmd = False
        self.post_setup = []
        self.verbs = set()
        self.objs = set()

    def fail_with_help(self, *a, **kw):
        self.parser.print_help(sys.stderr)
        raise SystemExit

    def add_argument(self, *a, **kw):
        if not kw.get("parent_only"):
            for x in self.subparser_objs:
                try:
                    # Create a global options group for better visual separation
                    if not hasattr(x, '_global_options_group'):
                        x._global_options_group = x.add_argument_group('Global options (available for all commands)')
                    # Use SUPPRESS as default for subparsers so they don't overwrite
                    # values already set by the main parser when the argument is placed
                    # before the subcommand (e.g., `vastai --url <url> get wrkgrp-logs`)
                    subparser_kw = kw.copy()
                    subparser_kw['default'] = argparse.SUPPRESS
                    x._global_options_group.add_argument(*a, **subparser_kw)
                except argparse.ArgumentError:
                    # duplicate - or maybe other things, hopefully not
                    pass
        return self.parser.add_argument(*a, **kw)

    def subparsers(self, *a, **kw):
        if self.subparsers_ is None:
            kw["metavar"] = "command"
            kw["help"] = "command to run. one of:"
            self.subparsers_ = self.parser.add_subparsers(*a, **kw)
        return self.subparsers_

    def get_name(self, verb, obj):
        if obj:
            self.verbs.add(verb)
            self.objs.add(obj)
            name = verb + ' ' + obj
        else:
            self.objs.add(verb)
            name = verb
        return name

    def command(self, *arguments, aliases=(), help=None, hidden=None, **kwargs):
        help_ = help
        if not self.added_help_cmd:
            self.added_help_cmd = True

            @self.command(argument("subcommand", default=None, nargs="?"), help="print this help message")
            def help(*a, **kw):
                self.fail_with_help()

        def inner(func):
            dashed_name = func.__name__.replace("_", "-")
            verb, _, obj = dashed_name.partition("--")
            name = self.get_name(verb, obj)
            aliases_transformed = [] if aliases else hidden_aliases([])
            for x in aliases:
                verb, _, obj = x.partition(" ")
                aliases_transformed.append(self.get_name(verb, obj))
            if "formatter_class" not in kwargs:
                kwargs["formatter_class"] = MyWideHelpFormatter

            sp = self.subparsers().add_parser(name, aliases=aliases_transformed, help=help_, **kwargs)
            sp.hidden = is_hidden_command(name, explicit=hidden)

            # TODO: Sometimes the parser.command has a help parameter. Ideally
            # I'd extract this during the sdk phase but for the life of me
            # I can't find it.
            setattr(func, "mysignature", sp)
            setattr(func, "mysignature_help", help_)

            self.subparser_objs.append(sp)

            self._process_arguments_with_groups(sp, arguments)

            sp.set_defaults(func=func)
            return func

        if len(arguments) == 1 and type(arguments[0]) != argument:
            func = arguments[0]
            arguments = []
            return inner(func)
        return inner

    def parse_args(self, argv=None, *a, **kw):
        if argv is None:
            argv = sys.argv[1:]
        argv_ = []
        for x in argv:
            # Merge "verb object" into one command token, but never swallow a
            # flag: a verb that is also a bare command (e.g. `update`) must
            # accept options (`vastai update --check`).
            if argv_ and argv_[-1] in self.verbs and not x.startswith("-"):
                argv_[-1] += " " + x
            else:
                argv_.append(x)
        args = self.parser.parse_args(argv_, *a, **kw)
        for func in self.post_setup:
            func(args)
        return args

    def _process_arguments_with_groups(self, parser_obj, arguments):
        """Process arguments and handle mutually exclusive groups"""
        mutex_groups_to_required = {}
        arg_to_group = {}

        # Determine if any mutex groups are required
        for arg in arguments:
            key = arg.args[0]
            if arg.mutex_group:
                is_required = arg.kwargs.pop('required', False)
                group_name = arg.mutex_group
                arg_to_group[key] = group_name
                if mutex_groups_to_required.get(group_name):
                    continue  # if marked as required then it stays required
                else:
                    mutex_groups_to_required[group_name] = is_required

        name_to_group_parser = {}  # Create mutually exclusive group parsers
        for group_name, is_required in mutex_groups_to_required.items():
            mutex_group = parser_obj.add_mutually_exclusive_group(required=is_required)
            name_to_group_parser[group_name] = mutex_group

        for arg in arguments:  # Add args via the appropriate parser
            key = arg.args[0]
            if arg_to_group.get(key):
                group_parser = name_to_group_parser[arg_to_group[key]]
                tsp = group_parser.add_argument(*arg.args, **arg.kwargs)
            else:
                tsp = parser_obj.add_argument(*arg.args, **arg.kwargs)
            self._add_completer(tsp, arg)


    def _add_completer(self, tsp, arg):
        """Helper function to add completers based on argument names"""
        myCompleter = None
        comparator = arg.args[0].lower()
        if comparator.startswith('machine'):
            myCompleter = complete_instance_machine
        elif comparator.startswith('id') or comparator.endswith('id'):
            myCompleter = complete_instance
        elif comparator.startswith('ssh'):
            myCompleter = complete_sshkeys

        if myCompleter:
            setattr(tsp, 'completer', myCompleter)
