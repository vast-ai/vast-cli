"""Tests for vastai/cli/parser.py — apwrap, command registration, parse_args."""

import argparse

import pytest
from vastai.cli.parser import (
    apwrap, argument, hidden_aliases, MyWideHelpFormatter,
    build_command_maps, two_stage_command_completions,
    is_host_only_command,
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


def _completion_parser_with_host_cmd():
    p = _completion_parser()

    @p.command(help="show host machines", host_only=True)
    def show__machines(args):
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

    def test_no_role_defaults_to_client_completions(self):
        # Client is the default: an unset role (no role= passed) hides
        # host-only commands from completion too, not just 'client'.
        _, verb_objs, _ = build_command_maps(_completion_parser_with_host_cmd().parser)
        assert verb_objs["show"] == {"instances", "env-vars"}

    def test_host_role_completes_host_commands(self):
        _, verb_objs, _ = build_command_maps(
            _completion_parser_with_host_cmd().parser, role="host"
        )
        assert verb_objs["show"] == {"instances", "env-vars", "machines"}

    def test_client_role_hides_host_commands_from_completion(self):
        _, verb_objs, _ = build_command_maps(
            _completion_parser_with_host_cmd().parser, role="client"
        )
        assert verb_objs["show"] == {"instances", "env-vars"}


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


class TestIsHostOnlyCommand:
    """Unit tests for the host-only/not classification (CLN-3582)."""

    def test_explicit_true_wins_over_everything(self):
        assert is_host_only_command(
            "search offers", "vastai.cli.commands.machines", explicit=True
        ) is True

    def test_explicit_false_wins_over_everything(self):
        assert is_host_only_command(
            "show earnings", "vastai.cli.commands.machines", explicit=False
        ) is False

    def test_command_override_wins_over_module_default(self):
        # 'reports' is flagged host-only despite misc.py being client-facing.
        assert is_host_only_command("reports", "vastai.cli.commands.misc") is True

    def test_falls_back_to_module_default(self):
        assert is_host_only_command(
            "show instances", "vastai.cli.commands.instances"
        ) is False
        assert is_host_only_command(
            "show machines", "vastai.cli.commands.machines"
        ) is True

    def test_unmapped_module_and_command_defaults_to_visible(self):
        # No raise, no "unresolved" state: an unmapped module/command is
        # simply not host-only, so it's never hidden by mistake.
        assert is_host_only_command("do stuff", "some.made.up.module") is False


class TestCommandDecoratorHostOnly:
    def test_unmapped_module_defaults_to_not_host_only(self):
        # This test file's module isn't in HOST_ONLY_MODULES — the command
        # is simply visible, not left in some unresolved state.
        p = apwrap()

        @p.command(help="show items")
        def show__items(args):
            pass

        assert show__items.mysignature.host_only is False

    def test_explicit_host_only_kwarg_is_honored(self):
        p = apwrap()

        @p.command(help="a host-only test command", host_only=True)
        def do__hostthing(args):
            pass

        assert do__hostthing.mysignature.host_only is True

    def test_host_only_auto_prefixes_help_text(self):
        p = apwrap()

        @p.command(help="do a host thing", host_only=True)
        def do__hostthing(args):
            pass

        assert do__hostthing.mysignature_help == "do a host thing"  # stored unprefixed
        # The rendered help (shown in --help output) carries the [Host] marker.
        choices_actions = p.subparsers()._choices_actions
        rendered = next(c.help for c in choices_actions if c.dest == "do hostthing")
        assert rendered == "[Host] do a host thing"

    def test_non_host_only_does_not_get_host_prefix(self):
        p = apwrap()

        @p.command(help="a client thing", host_only=False)
        def show__clientthing(args):
            pass

        choices_actions = p.subparsers()._choices_actions
        rendered = {c.dest: c.help for c in choices_actions}
        assert rendered["show clientthing"] == "a client thing"


class TestFullCliHostOnlyCoverage:
    """Sanity check against the real, fully-populated CLI parser."""

    def _all_choices_actions(self, cli_parser):
        for a in cli_parser.parser._actions:
            if isinstance(a, argparse._SubParsersAction):
                return a
        raise AssertionError("no subparsers action found")

    def test_client_view_excludes_known_host_only_commands(self, cli_parser):
        sub_action = self._all_choices_actions(cli_parser)
        host_only = {
            pseudo.dest
            for pseudo in sub_action._choices_actions
            if getattr(sub_action.choices.get(pseudo.dest), "host_only", False)
        }
        assert {"show machines", "list machine", "set min-bid"} <= host_only
        assert "show instances" not in host_only


class TestGroupedHelpRoleFiltering:
    """--help output hides host-only commands for the client role (CLN-3582)."""

    def _parser_with_host_and_client_cmds(self):
        p = apwrap(epilog="epilogue text")

        @p.command(help="show instances", host_only=False)
        def show__instances(args):
            pass

        @p.command(help="show host machines", host_only=True)
        def show__machines(args):
            pass

        return p

    def test_unset_role_defaults_to_client_view(self, monkeypatch):
        # Client is the default: an unset role hides host-only commands too,
        # not just an explicit 'client' — see test below for that case.
        monkeypatch.setattr("vastai.cli.parser.get_role", lambda: None)
        help_text = self._parser_with_host_and_client_cmds().parser.format_help()
        assert "show instances" in help_text
        assert "show machines" not in help_text
        assert "set role host" in help_text

    def test_host_role_shows_everything(self, monkeypatch):
        monkeypatch.setattr("vastai.cli.parser.get_role", lambda: "host")
        help_text = self._parser_with_host_and_client_cmds().parser.format_help()
        assert "show instances" in help_text
        assert "show machines" in help_text
        assert "set role host" not in help_text

    def test_client_role_hides_host_commands_and_shows_footer(self, monkeypatch):
        monkeypatch.setattr("vastai.cli.parser.get_role", lambda: "client")
        help_text = self._parser_with_host_and_client_cmds().parser.format_help()
        assert "show instances" in help_text
        assert "show machines" not in help_text
        assert "set role host" in help_text

    def test_client_role_with_no_host_commands_shows_no_footer(self, monkeypatch):
        monkeypatch.setattr("vastai.cli.parser.get_role", lambda: "client")
        p = apwrap(epilog="epilogue text")

        @p.command(help="show instances", host_only=False)
        def show__instances(args):
            pass

        help_text = p.parser.format_help()
        assert "set role host" not in help_text
