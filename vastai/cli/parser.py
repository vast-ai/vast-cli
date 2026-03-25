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


# ---------------------------------------------------------------------------
# Help formatter
# ---------------------------------------------------------------------------

class MyWideHelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, width=128, max_help_position=50, indent_increment=1)


# ---------------------------------------------------------------------------
# Main parser wrapper
# ---------------------------------------------------------------------------

class apwrap(object):
    """Wraps :class:`argparse.ArgumentParser` with convenience methods for
    two-word command registration (``verb object``) and tab-completion."""

    def __init__(self, *args, **kwargs):
        if "formatter_class" not in kwargs:
            kwargs["formatter_class"] = MyWideHelpFormatter
        self.parser = argparse.ArgumentParser(*args, **kwargs)
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

    def command(self, *arguments, aliases=(), help=None, **kwargs):
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
            if argv_ and argv_[-1] in self.verbs:
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
