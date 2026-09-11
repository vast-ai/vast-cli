"""Tests for the `vastai repl` interactive shell (vastai/cli/repl/)."""

import argparse
from unittest.mock import MagicMock

import pytest
from requests.exceptions import HTTPError

from vastai.cli import parser as parser_mod
from vastai.cli.parser import apwrap, argument, set_completers
from vastai.cli.repl.bridge import apply_session_globals, run_line
from vastai.cli.repl.catalog import CommandCatalog
from vastai.cli.repl.completion import LiveValues, ReplCompleter
from vastai.cli.repl.session import Repl


@pytest.fixture
def cli(calls):
    """A miniature stand-in for the real CLI parser: two-word commands, a bare
    command that also acts as a verb, and the global options main() adds."""
    p = apwrap()

    @p.command(argument("id"), argument("--force", action="store_true"), help="destroy an instance")
    def destroy__instance(args):
        calls.append(args)
        return {"destroyed": args.id}

    @p.command(help="show instances")
    def show__instances(args):
        calls.append(args)
        return [{"id": 1}]

    @p.command(help="show the user")
    def show__user(args):
        calls.append(args)

    @p.command(argument("--status", choices=["running", "stopped"]), help="update an instance")
    def update__instance(args):
        calls.append(args)

    @p.command(argument("--check", action="store_true"), help="update the CLI")
    def update(args):
        calls.append(args)

    # Mirrors main(): globals go on the root parser and, suppressed, on every
    # subparser, so a flag works before or after the command name.
    p.add_argument("--url", default="https://console.vast.ai")
    p.add_argument("--retry", type=int, default=3)
    p.add_argument("--raw", action="store_true")
    p.add_argument("--explain", action="store_true")
    p.add_argument("--curl", action="store_true")
    p.add_argument("--full", action="store_true")
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--api-key", default=None)
    return p


@pytest.fixture
def calls():
    """Args namespaces the fixture commands were invoked with."""
    return []


@pytest.fixture
def catalog(cli):
    return CommandCatalog(cli)


@pytest.fixture
def session():
    """A resolved session namespace, as `vastai repl` itself was parsed into."""
    return argparse.Namespace(
        api_key="session-key", url="https://console.vast.ai", retry=3,
        raw=False, explain=False, curl=False, full=False, no_color=False,
    )


@pytest.fixture
def instance_ids():
    """Stub the parser's live-id completers; restore the real ones afterwards."""
    saved = (parser_mod._complete_instance, parser_mod._complete_instance_machine)
    set_completers(instance_fn=lambda **kw: ["100", "101", "220"],
                   instance_machine_fn=lambda **kw: ["900"])
    yield
    parser_mod._complete_instance, parser_mod._complete_instance_machine = saved


class TestCommandCatalog:
    def test_lists_verbs_and_bare_commands(self, catalog):
        assert {"show", "destroy", "update"} <= set(catalog.first_words)

    def test_objects_of_a_verb(self, catalog):
        assert catalog.objects("show") == ["instances", "user"]

    def test_resolves_verb_and_object(self, catalog):
        assert catalog.resolve(["show", "instances"]) == "show instances"

    def test_resolves_bare_command(self, catalog):
        assert catalog.resolve(["update", "--check"]) == "update"

    def test_verb_never_absorbs_a_flag(self, catalog):
        """`update` is both a verb and a bare command, mirroring the real CLI."""
        assert catalog.resolve(["update", "instance"]) == "update instance"
        assert catalog.resolve(["update", "--status", "running"]) == "update"

    def test_bare_verb_resolves_to_nothing(self, catalog):
        assert catalog.resolve(["show"]) is None

    def test_unknown_resolves_to_nothing(self, catalog):
        assert catalog.resolve(["shwo", "instances"]) is None
        assert catalog.resolve([]) is None

    def test_suggests_objects_for_a_misspelled_one(self, catalog):
        assert catalog.suggest(["show", "instanes"]) == ["show instances"]

    def test_suggests_every_object_for_a_bare_verb(self, catalog):
        assert catalog.suggest(["show"]) == ["show instances", "show user"]

    def test_suggests_near_misses_for_a_misspelled_verb(self, catalog):
        assert "show instances" in catalog.suggest(["shwo", "instances"])

    def test_flags_include_command_and_global_options(self, catalog):
        flags = catalog.flags("destroy instance")
        assert "--force" in flags and "--raw" in flags

    def test_flags_are_cached(self, catalog):
        assert catalog.flags("show user") is catalog.flags("show user")

    def test_value_completer_found_for_id_positional(self, catalog):
        assert catalog.value_completer("destroy instance") is not None

    def test_no_value_completer_without_a_positional(self, catalog):
        assert catalog.value_completer("show instances") is None


class TestLiveValues:
    def test_filters_by_prefix(self):
        values = LiveValues(clock=lambda: 0.0)
        assert values.matching(lambda prefix: ["100", "101", "220"], "10") == ["100", "101"]

    def test_fetches_once_within_the_ttl(self):
        completer = MagicMock(return_value=["100"])
        values = LiveValues(ttl=30, clock=lambda: 0.0)
        values.matching(completer, "")
        values.matching(completer, "1")
        assert completer.call_count == 1

    def test_refetches_after_the_ttl(self):
        now = [0.0]
        completer = MagicMock(return_value=["100"])
        values = LiveValues(ttl=30, clock=lambda: now[0])
        values.matching(completer, "")
        now[0] = 31.0
        values.matching(completer, "")
        assert completer.call_count == 2

    def test_a_failing_completer_yields_nothing_and_is_not_retried(self):
        completer = MagicMock(side_effect=RuntimeError("api down"))
        values = LiveValues(ttl=30, clock=lambda: 0.0)
        assert values.matching(completer, "") == []
        values.matching(completer, "")
        assert completer.call_count == 1


class TestCompletion:
    def _completer(self, catalog):
        return ReplCompleter(catalog, meta_commands=[":help", ":set", ":history"],
                             meta_arguments={":set": lambda typed: ["on", "off"] if typed else ["raw"]})

    def test_completes_the_first_word(self, catalog):
        assert self._completer(catalog).suggestions("sh") == ["show"]

    def test_completes_objects_after_a_verb(self, catalog):
        assert self._completer(catalog).suggestions("show ") == ["instances", "user"]

    def test_completes_a_partial_object(self, catalog):
        assert self._completer(catalog).suggestions("show inst") == ["instances"]

    def test_completes_flags_of_the_resolved_command(self, catalog):
        assert self._completer(catalog).suggestions("destroy instance 5 --f") == ["--force", "--full"]

    def test_completes_global_flags_too(self, catalog):
        assert "--raw" in self._completer(catalog).suggestions("show instances --r")

    def test_completes_flags_of_a_bare_command(self, catalog):
        assert self._completer(catalog).suggestions("update --c") == ["--check", "--curl"]

    def test_completes_a_flags_choices(self, catalog):
        assert self._completer(catalog).suggestions("update instance --status ") == ["running", "stopped"]

    def test_completes_live_ids_for_a_positional(self, catalog, instance_ids):
        assert self._completer(catalog).suggestions("destroy instance 1") == ["100", "101"]

    def test_a_valueless_flag_does_not_swallow_the_positional(self, catalog, instance_ids):
        assert self._completer(catalog).suggestions("destroy instance --force 1") == ["100", "101"]

    def test_completes_nothing_for_an_unknown_command(self, catalog):
        assert self._completer(catalog).suggestions("nonsense ") == []

    def test_completes_nothing_inside_a_shell_escape(self, catalog):
        assert self._completer(catalog).suggestions("!ls ") == []

    def test_completes_meta_commands(self, catalog):
        assert self._completer(catalog).suggestions(":h") == [":help", ":history"]

    def test_completes_meta_arguments(self, catalog):
        assert self._completer(catalog).suggestions(":set ") == ["raw"]
        assert self._completer(catalog).suggestions(":set raw ") == ["off", "on"]

    def test_readline_protocol_returns_one_match_per_state(self, catalog):
        completer = self._completer(catalog)
        completer.matches = []
        assert completer.complete("sh", 0) == "show"
        assert completer.complete("sh", 1) is None


class TestSessionGlobals:
    def test_session_values_apply_to_a_bare_line(self, cli, session):
        session.raw = True
        args = cli.parse_args(["show", "instances"])
        apply_session_globals(cli, args, session)
        assert args.raw is True
        assert args.api_key == "session-key"

    def test_a_flag_typed_on_the_line_wins(self, cli, session):
        args = cli.parse_args(["show", "instances", "--url", "https://other"])
        apply_session_globals(cli, args, session)
        assert args.url == "https://other"


class TestRunLine:
    def test_runs_the_command_with_session_globals(self, cli, session, calls):
        assert run_line(cli, "destroy instance 7 --force", session) == {"destroyed": "7"}
        assert calls[0].force is True
        assert calls[0].api_key == "session-key"

    def test_quoted_arguments_are_split_like_a_shell(self, cli, session, calls):
        run_line(cli, "destroy instance 'a b'", session)
        assert calls[0].id == "a b"

    def test_unbalanced_quotes_report_a_parse_error(self, cli, session, calls, capsys):
        assert run_line(cli, "destroy instance 'oops", session) is None
        assert "parse error" in capsys.readouterr().err
        assert calls == []

    def test_a_usage_error_does_not_end_the_session(self, cli, session, calls):
        assert run_line(cli, "destroy instance", session) is None
        assert calls == []

    def test_raw_prints_the_result_as_json(self, cli, session, capsys):
        session.raw = True
        run_line(cli, "show instances", session)
        assert '"id": 1' in capsys.readouterr().out

    def test_an_api_error_is_reported_not_raised(self, cli, session, capsys):
        response = MagicMock(status_code=403)
        response.json.return_value = {"msg": "forbidden"}
        cli.subparsers_.choices["show user"].set_defaults(
            func=MagicMock(side_effect=HTTPError(response=response)))
        assert run_line(cli, "show user", session) is None
        assert "Failed with error 403: forbidden" in capsys.readouterr().err

    def test_an_unexpected_error_is_reported_not_raised(self, cli, session, capsys):
        cli.subparsers_.choices["show user"].set_defaults(
            func=MagicMock(side_effect=RuntimeError("boom")))
        assert run_line(cli, "show user", session) is None
        assert "RuntimeError: boom" in capsys.readouterr().err


class TestReplLoop:
    def test_blank_lines_are_ignored(self, cli, session, calls):
        repl = Repl(cli, session)
        assert repl.handle("   ") is True
        assert calls == []

    @pytest.mark.parametrize("word", ["exit", "quit", "q", ":quit"])
    def test_exit_words_end_the_session(self, cli, session, word):
        assert Repl(cli, session).handle(word) is False

    def test_a_command_runs(self, cli, session, calls):
        assert Repl(cli, session).handle("show instances") is True
        assert len(calls) == 1

    def test_an_unknown_command_suggests_near_misses(self, cli, session, calls, capsys):
        Repl(cli, session).handle("shwo instances")
        err = capsys.readouterr().err
        assert "unknown command: shwo instances" in err
        assert "show instances" in err
        assert calls == []

    def test_a_bare_verb_lists_its_objects(self, cli, session, capsys):
        Repl(cli, session).handle("show")
        assert "show takes an object: instances, user" in capsys.readouterr().err

    def test_nested_repl_is_refused(self, cli, session, capsys):
        Repl(cli, session).handle("repl")
        assert "Already in the REPL" in capsys.readouterr().out

    def test_set_toggles_a_session_flag(self, cli, session):
        repl = Repl(cli, session)
        repl.handle(":set raw")
        assert repl.args.raw is True
        repl.handle(":set raw off")
        assert repl.args.raw is False

    def test_set_does_not_mutate_the_callers_args(self, cli, session):
        repl = Repl(cli, session)
        repl.handle(":set explain on")
        assert repl.args.explain is True
        assert session.explain is False

    def test_set_rejects_an_unknown_flag(self, cli, session, capsys):
        Repl(cli, session).handle(":set nonsense on")
        assert "unknown flag 'nonsense'" in capsys.readouterr().out

    def test_set_without_arguments_lists_the_flags(self, cli, session, capsys):
        Repl(cli, session).handle(":set")
        assert "raw: off" in capsys.readouterr().out

    def test_an_unknown_meta_command_is_reported(self, cli, session, capsys):
        Repl(cli, session).handle(":nope")
        assert "unknown meta-command ':nope'" in capsys.readouterr().out

    def test_the_prompt_shows_active_flags(self, cli, session):
        repl = Repl(cli, session)
        assert repl.prompt() == "vast> "
        repl.handle(":set raw on")
        assert repl.prompt() == "vast[raw]> "

    def test_piped_input_runs_every_line(self, cli, session, calls):
        Repl(cli, session).run_script(["show instances\n", "show user\n"])
        assert len(calls) == 2

    def test_piped_input_stops_at_an_exit_word(self, cli, session, calls):
        Repl(cli, session).run_script(["show instances\n", "exit\n", "show user\n"])
        assert len(calls) == 1
