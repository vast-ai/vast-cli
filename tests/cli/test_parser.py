"""Tests for vastai/cli/parser.py — apwrap, command registration, parse_args."""

import pytest
from vastai.cli.parser import (
    apwrap, argument, hidden_aliases, MyWideHelpFormatter,
    build_command_maps, two_stage_command_completions,
    is_hidden_command,
)


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


def _completion_parser():
    p = apwrap()

    @p.command(argument("--quiet", action="store_true"), help="show instances")
    def show__instances(args):
        pass

    @p.command(help="show env vars")
    def show__env_vars(args):
        pass

    @p.command(help="create an instance")
    def create__instance(args):
        pass

    @p.command(argument("--check", action="store_true"), help="self update")
    def update(args):
        pass

    return p


class TestBuildCommandMaps:
    def test_splits_verbs_objects_and_singles(self):
        verbs, verb_objs, singles = build_command_maps(_completion_parser().parser)
        assert {"show", "create"} <= verbs
        assert verb_objs["show"] == {"instances", "env-vars"}
        assert verb_objs["create"] == {"instance"}
        # bare command + the auto-registered "help" land in singles, not verbs
        assert "update" in singles and "update" not in verbs

    def test_hidden_command_excluded_from_completion(self):
        p = _completion_parser()

        @p.command(help="an unreleased thing", hidden=True)
        def show__unreleased(args):
            pass

        _, verb_objs, _ = build_command_maps(p.parser)
        assert verb_objs["show"] == {"instances", "env-vars"}


class TestIsHiddenCommand:
    """Unit tests for the unreleased/feature-flagged command gate."""

    def test_explicit_true_wins(self):
        assert is_hidden_command("show instances", explicit=True) is True

    def test_explicit_false_wins_over_registry(self):
        assert is_hidden_command("search network-volumes", explicit=False) is False

    def test_known_unreleased_command_is_hidden(self):
        assert is_hidden_command("search network-volumes") is True
        assert is_hidden_command("create network-volume") is True
        assert is_hidden_command("list network-volume") is True
        assert is_hidden_command("unlist network-volume") is True

    def test_unregistered_command_defaults_to_visible(self):
        assert is_hidden_command("show instances") is False


class TestCommandDecoratorHidden:
    def test_hidden_kwarg_is_stored_on_the_subparser(self):
        p = apwrap()

        @p.command(help="an unreleased thing", hidden=True)
        def do__unreleased(args):
            pass

        assert do__unreleased.mysignature.hidden is True

    def test_default_is_not_hidden(self):
        p = apwrap()

        @p.command(help="a normal thing")
        def show__thing(args):
            pass

        assert show__thing.mysignature.hidden is False

    def test_hidden_command_excluded_from_grouped_help(self):
        p = apwrap(epilog="epilogue text")

        @p.command(help="show instances")
        def show__instances(args):
            pass

        @p.command(help="an unreleased thing", hidden=True)
        def show__unreleased(args):
            pass

        help_text = p.parser.format_help()
        assert "show instances" in help_text
        assert "show unreleased" not in help_text


class TestFullCliHiddenCommands:
    """Sanity check against the real, fully-populated CLI parser."""

    def test_network_volume_commands_are_hidden_from_help(self, cli_parser):
        help_text = cli_parser.parser.format_help()
        assert "network-volume" not in help_text

    def test_network_volume_commands_still_parse_directly(self, cli_parser):
        args = cli_parser.parse_args(["search", "network-volumes"])
        assert callable(args.func)

    def test_update_and_uninstall_are_hidden_from_help(self, cli_parser):
        help_text = cli_parser.parser.format_help()
        assert "\nupdate " not in help_text
        assert "\nuninstall " not in help_text

    def test_update_and_uninstall_still_parse_directly(self, cli_parser):
        assert callable(cli_parser.parse_args(["update", "--check"]).func)
        assert callable(cli_parser.parse_args(["uninstall", "--yes"]).func)


class TestTwoStageCompletions:
    def setup_method(self):
        self.maps = build_command_maps(_completion_parser().parser)

    def _complete(self, comp_words, prefix):
        return two_stage_command_completions(comp_words, prefix, *self.maps)

    def test_first_word_offers_verbs_and_singles(self):
        cands, merged = self._complete(["vastai"], "")
        assert merged is None
        assert {"show", "create", "update"} <= set(cands)

    def test_first_word_narrows_by_prefix(self):
        cands, _ = self._complete(["vastai"], "sh")
        assert cands == ["show"]

    def test_object_stage_lists_only_that_verbs_objects(self):
        cands, merged = self._complete(["vastai", "show"], "")
        assert merged is None
        assert cands == ["env-vars", "instances"]  # sorted, no "create" leakage

    def test_object_stage_has_no_escaped_space(self):
        cands, _ = self._complete(["vastai", "show"], "")
        assert all(" " not in c and "\\" not in c for c in cands)

    def test_object_stage_narrows_by_prefix(self):
        cands, _ = self._complete(["vastai", "show"], "env")
        assert cands == ["env-vars"]

    def test_bare_command_delegates_not_object_stage(self):
        # "update" is a single command, not a verb -> delegate (no object list)
        cands, merged = self._complete(["vastai", "update"], "--")
        assert cands is None
        assert merged == ["vastai", "update"]

    def test_flag_stage_fuses_verb_object_into_one_token(self):
        cands, merged = self._complete(["vastai", "show", "instances"], "--")
        assert cands is None
        assert merged == ["vastai", "show instances"]

    def test_flag_stage_never_fuses_across_a_flag(self):
        cands, merged = self._complete(["vastai", "show", "--help"], "")
        assert cands is None
        assert merged == ["vastai", "show", "--help"]  # unchanged
