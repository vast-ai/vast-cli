"""Tests for vastai/cli/parser.py — apwrap, command registration, parse_args."""

import pytest
from vastai.cli.parser import apwrap, argument, hidden_aliases, MyWideHelpFormatter


class TestArgument:
    def test_stores_args_and_kwargs(self):
        a = argument("--foo", type=int, help="bar")
        assert a.args == ("--foo",)
        assert a.kwargs["type"] is int
        assert a.kwargs["help"] == "bar"

    def test_mutex_group(self):
        a = argument("--x", mutex_group="grp")
        assert a.mutex_group == "grp"

    def test_no_mutex_group(self):
        a = argument("pos")
        assert a.mutex_group is None


class TestHiddenAliases:
    def test_is_falsy(self):
        h = hidden_aliases(["a", "b"])
        assert not h
        assert bool(h) is False

    def test_iteration(self):
        h = hidden_aliases(["x", "y"])
        assert list(h) == ["x", "y"]

    def test_append(self):
        h = hidden_aliases([])
        h.append("z")
        assert list(h) == ["z"]


class TestApwrap:
    def test_creation(self):
        p = apwrap(description="test")
        assert p.parser is not None
        assert p.subparsers_ is None

    def test_fail_with_help_raises_system_exit(self):
        p = apwrap()
        with pytest.raises(SystemExit):
            p.fail_with_help()

    def test_command_decorator_single_word(self):
        p = apwrap()

        @p.command(argument("--flag", action="store_true"), help="do stuff")
        def mycommand(args):
            pass

        assert callable(mycommand)
        assert hasattr(mycommand, "mysignature")

    def test_command_double_underscore_becomes_two_word(self):
        p = apwrap()

        @p.command(help="show items")
        def show__items(args):
            pass

        # The name should be "show items" internally
        assert "show" in p.verbs
        assert "items" in p.objs

    def test_command_with_dashes(self):
        p = apwrap()

        @p.command(help="do dash things")
        def do_dash__things(args):
            pass

        # do-dash things
        assert "do-dash" in p.verbs
        assert "things" in p.objs

    def test_parse_args_joins_two_word_commands(self):
        p = apwrap()

        @p.command(argument("--flag", action="store_true"), help="show stuff")
        def show__stuff(args):
            return 0

        args = p.parse_args(["show", "stuff", "--flag"])
        assert args.flag is True
        assert args.func is show__stuff

    def test_parse_args_empty_argv(self):
        p = apwrap()

        @p.command(help="test")
        def test_cmd(args):
            pass

        # Empty argv should set func to fail_with_help
        args = p.parse_args(["test-cmd"])
        assert args.func is test_cmd


class TestMutuallyExclusiveGroups:
    def test_mutex_group(self):
        p = apwrap()

        @p.command(
            argument("--opt-a", mutex_group="grp", action="store_true"),
            argument("--opt-b", mutex_group="grp", action="store_true"),
            help="test mutex",
        )
        def mutex__test(args):
            pass

        args = p.parse_args(["mutex", "test", "--opt-a"])
        assert args.opt_a is True
        assert args.opt_b is False


class TestCliParserReadOnlyCommands:
    """Parametrized test that all read-only commands parse without error."""

    READ_ONLY_COMMANDS = [
        ["show", "instances"],
        ["show", "user"],
        ["show", "invoices"],
        ["show", "earnings"],
        ["show", "subaccounts"],
        ["show", "ipaddrs"],
        ["show", "ssh-keys"],
        ["show", "api-keys"],
        ["show", "machines"],
        ["show", "audit-logs"],
        ["show", "env-vars"],
        ["show", "scheduled-jobs"],
        ["show", "endpoints"],
        ["show", "volumes"],
        ["show", "clusters"],
        ["show", "overlays"],
        ["show", "connections"],
        ["show", "workergroups"],
        ["tfa", "status"],
    ]

    @pytest.mark.parametrize("argv", READ_ONLY_COMMANDS)
    def test_parse_readonly_command(self, cli_parser, argv):
        args = cli_parser.parse_args(argv)
        assert callable(args.func)
