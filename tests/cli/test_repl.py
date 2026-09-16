"""Tests for the `vastai repl` interactive shell (vastai/cli/repl/)."""

import argparse
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from vastai.cli import parser as parser_mod
from vastai.cli.parser import apwrap, argument, set_completers
from vastai.cli.repl.bridge import apply_session_globals, run_line
from vastai.cli.repl.catalog import CommandCatalog
from vastai.cli.repl.completion import LiveValues, ReplCompleter
from vastai.cli.repl.session import Repl, _is_secret


@pytest.fixture
def cli(calls):
    """A miniature stand-in for the real CLI parser: two-word commands, a bare
    command that also acts as a verb, and the global options main() adds."""
    p = apwrap()

    @p.command(argument("id"), argument("--force", action="store_true"), help="destroy an instance")
    def destroy__instance(args):
        calls.append(args)
        return {"destroyed": args.id}

    @p.command(argument("--verification", nargs="+", choices=["verified", "unverified"]),
               argument("-g", "--gpu-name", choices=["RTX_4090", "H100"]),
               help="show instances")
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

    @p.command(argument("id"), argument("ssh_key"), help="update an ssh key")
    def update__ssh_key(args):
        calls.append(args)

    @p.command(argument("--args", nargs=argparse.REMAINDER), help="run a container")
    def run__container(args):
        calls.append(args)

    @p.command(argument("text"), help="a bare command that takes an argument")
    def label(args):
        calls.append(args)

    @p.command(argument("id"), help="label an instance")
    def label__instance(args):
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

    def test_an_unknown_object_does_not_fall_back_to_the_bare_verb(self, catalog):
        """`update bogus` must not resolve to `update`, or argparse answers a
        typo by printing all ~150 command names."""
        assert catalog.resolve(["update", "bogus"]) is None

    def test_a_bare_command_may_still_take_an_argument(self, catalog):
        assert catalog.resolve(["label", "hello"]) == "label"

    def test_strips_leading_global_options(self, catalog):
        assert catalog.strip_options(["--raw", "show", "user"]) == ["show", "user"]
        assert catalog.strip_options(["--url", "https://x", "show", "user"]) == ["show", "user"]
        assert catalog.strip_options(["--url=https://x", "show"]) == ["show"]

    def test_leaves_a_line_without_leading_options_alone(self, catalog):
        assert catalog.strip_options(["show", "instances", "--raw"]) == ["show", "instances", "--raw"]

    def test_resolves_a_command_behind_leading_globals(self, catalog):
        assert catalog.resolve(catalog.strip_options(["--raw", "show", "user"])) == "show user"

    def test_option_looks_up_short_aliases(self, catalog):
        assert catalog.option("show instances", "-g") is catalog.flags("show instances")["--gpu-name"]

    def test_option_looks_up_abbreviations_and_inline_values(self, catalog):
        assert catalog.option("show instances", "--gpu") is not None
        assert catalog.option("show instances", "--gpu-name=H100") is not None

    def test_positional_completer_is_indexed(self, catalog):
        """`update ssh-key <id> <key>`: each positional has its own completer."""
        first = catalog.positional_completer("update ssh-key", 0)
        second = catalog.positional_completer("update ssh-key", 1)
        assert first is not None and second is not None and first is not second

    def test_no_positional_completer_past_the_last_positional(self, catalog):
        assert catalog.positional_completer("update ssh-key", 2) is None

    def test_no_positional_completer_without_a_positional(self, catalog):
        assert catalog.positional_completer("show instances") is None


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

    def test_completes_choices_of_a_short_alias(self, catalog):
        assert self._completer(catalog).suggestions("show instances -g ") == ["H100", "RTX_4090"]

    def test_a_multi_value_option_keeps_offering_choices(self, catalog):
        """`--verification` takes nargs='+', so the second value completes too."""
        assert self._completer(catalog).suggestions(
            "show instances --verification verified ") == ["unverified", "verified"]

    def test_a_single_value_option_stops_after_its_value(self, catalog, instance_ids):
        assert self._completer(catalog).suggestions("show instances -g H100 ") == []

    def test_completes_the_second_positional_with_its_own_completer(self, catalog, instance_ids):
        """`update ssh-key <id> <tab>` offers key paths, not instance ids again."""
        completer = self._completer(catalog)
        assert completer.suggestions("update ssh-key 1") == ["100", "101"]
        assert "100" not in completer.suggestions("update ssh-key 100 1")

    def test_completes_behind_leading_global_options(self, catalog):
        assert self._completer(catalog).suggestions("--raw show ") == ["instances", "user"]

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

    def test_completes_a_partial_meta_argument(self, catalog):
        """`:set r<tab>` completes the flag name, not its on/off values."""
        assert self._completer(catalog).suggestions(":set r") == ["raw"]

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
        argv = ["show", "instances", "--url", "https://other"]
        args = cli.parse_args(argv)
        apply_session_globals(cli, args, session, argv)
        assert args.url == "https://other"

    def test_a_line_flag_wins_even_when_it_equals_the_default(self, cli, session):
        """`vastai --retry 10 repl` then `show instances --retry 3`: the typed 3
        must survive, though it is also the parser's default."""
        session.retry = 10
        argv = ["show", "instances", "--retry", "3"]
        args = cli.parse_args(argv)
        apply_session_globals(cli, args, session, argv)
        assert args.retry == 3

    def test_options_after_a_remainder_belong_to_the_command(self, cli, session):
        """`create instance --args --raw` passes --raw to the container, so the
        session's raw flag still applies to the line itself."""
        session.raw = True
        argv = ["run", "container", "--args", "--raw", "-x"]
        args = cli.parse_args(argv)
        apply_session_globals(cli, args, session, argv)
        assert args.raw is True

    def test_an_inline_value_counts_as_typed(self, cli, session):
        session.url = "https://session"
        argv = ["show", "instances", "--url=https://console.vast.ai"]
        args = cli.parse_args(argv)
        apply_session_globals(cli, args, session, argv)
        assert args.url == "https://console.vast.ai"


class TestRunLine:
    def test_runs_the_command_with_session_globals(self, cli, session, calls):
        assert run_line(cli, "destroy instance 7 --force", session) == 0
        assert calls[0].force is True
        assert calls[0].api_key == "session-key"

    def test_quoted_arguments_are_split_like_a_shell(self, cli, session, calls):
        run_line(cli, "destroy instance 'a b'", session)
        assert calls[0].id == "a b"

    def test_unbalanced_quotes_report_a_parse_error(self, cli, session, calls, capsys):
        assert run_line(cli, "destroy instance 'oops", session) == 1
        assert "parse error" in capsys.readouterr().err
        assert calls == []

    def test_a_usage_error_does_not_end_the_session(self, cli, session, calls):
        assert run_line(cli, "destroy instance", session) == 2  # argparse's code
        assert calls == []

    def test_help_is_not_a_failure(self, cli, session):
        assert run_line(cli, "show instances --help", session) == 0

    def test_raw_prints_the_result_as_json(self, cli, session, capsys):
        session.raw = True
        run_line(cli, "show instances", session)
        assert '"id": 1' in capsys.readouterr().out

    def test_an_api_error_is_reported_not_raised(self, cli, session, capsys):
        response = MagicMock(status_code=403)
        response.json.return_value = {"msg": "forbidden"}
        cli.subparsers_.choices["show user"].set_defaults(
            func=MagicMock(side_effect=HTTPError(response=response)))
        assert run_line(cli, "show user", session) == 1
        assert "Failed with error 403: forbidden" in capsys.readouterr().err

    def test_an_expired_2fa_session_falls_back_and_retries(self, cli, session, tmp_path, capsys):
        """The one-shot CLI recovers from an expired 2FA session; so must the
        REPL, or the advertised same-auth promise breaks mid-session."""
        tfa_file = tmp_path / "vast_tfa_key"
        api_file = tmp_path / "vast_api_key"
        tfa_file.write_text("stale-tfa-key")
        api_file.write_text("normal-api-key")
        session.api_key = "stale-tfa-key"

        response = MagicMock(status_code=404)
        response.json.return_value = {"msg": "Session expired. Please log in again."}
        func = MagicMock(side_effect=[HTTPError(response=response), {"ok": True}])
        cli.subparsers_.choices["show user"].set_defaults(func=func)

        with patch("vastai.cli.main.TFAKEY_FILE", str(tfa_file)), \
             patch("vastai.cli.main.APIKEY_FILE", str(api_file)):
            assert run_line(cli, "show user", session) == 0

        assert func.call_count == 2
        assert not tfa_file.exists()
        assert session.api_key == "normal-api-key"  # later lines use it too
        assert "Your 2FA session has expired." in capsys.readouterr().out

    def test_an_expired_2fa_session_retries_only_once(self, cli, session, tmp_path):
        tfa_file = tmp_path / "vast_tfa_key"
        api_file = tmp_path / "vast_api_key"
        tfa_file.write_text("stale-tfa-key")
        api_file.write_text("normal-api-key")

        response = MagicMock(status_code=404)
        response.json.return_value = {"msg": "Session expired. Please log in again."}
        func = MagicMock(side_effect=HTTPError(response=response))
        cli.subparsers_.choices["show user"].set_defaults(func=func)

        with patch("vastai.cli.main.TFAKEY_FILE", str(tfa_file)), \
             patch("vastai.cli.main.APIKEY_FILE", str(api_file)):
            assert run_line(cli, "show user", session) == 1
        assert func.call_count == 2

    def test_a_commands_exit_code_becomes_the_line_status(self, cli, session):
        cli.subparsers_.choices["show user"].set_defaults(func=lambda args: 3)
        assert run_line(cli, "show user", session) == 3

    def test_an_expired_2fa_session_without_a_saved_key_reports_once(self, cli, session, tmp_path, capsys):
        """main.run_command stops after explaining the expiry; reporting the raw
        API error as well would say it twice (and mix text into --raw JSON)."""
        tfa_file = tmp_path / "vast_tfa_key"
        tfa_file.write_text("stale-tfa-key")
        response = MagicMock(status_code=404)
        response.json.return_value = {"msg": "Session expired. Please log in again."}
        cli.subparsers_.choices["show user"].set_defaults(
            func=MagicMock(side_effect=HTTPError(response=response)))

        with patch("vastai.cli.main.TFAKEY_FILE", str(tfa_file)), \
             patch("vastai.cli.main.APIKEY_FILE", str(tmp_path / "missing")):
            assert run_line(cli, "show user", session) == 1

        out, err = capsys.readouterr()
        assert "Your 2FA session has expired." in out
        assert "vastai tfa login" in out
        assert "Session expired. Please log in again." not in err

    def test_a_json_error_without_a_message_is_reported_not_raised(self, cli, session, capsys):
        """A 401 body that parses but carries no 'msg' used to hand None to
        _emit_error, whose `in` test raised TypeError and killed the session."""
        response = MagicMock(status_code=401)
        response.json.return_value = {}
        cli.subparsers_.choices["show user"].set_defaults(
            func=MagicMock(side_effect=HTTPError(response=response)))
        assert run_line(cli, "show user", session) == 1
        assert "Failed with error 401" in capsys.readouterr().err

    def test_an_unexpected_error_is_reported_not_raised(self, cli, session, capsys):
        cli.subparsers_.choices["show user"].set_defaults(
            func=MagicMock(side_effect=RuntimeError("boom")))
        assert run_line(cli, "show user", session) == 1
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

    def test_set_rejects_a_value_that_is_neither_on_nor_off(self, cli, session, capsys):
        """`:set raw onn` used to read as false and silently turn raw off."""
        repl = Repl(cli, session)
        repl.handle(":set raw on")
        repl.handle(":set raw onn")
        assert repl.args.raw is True
        assert "expected on or off" in capsys.readouterr().out

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

    def test_a_clean_script_succeeds(self, cli, session):
        assert Repl(cli, session).run_script(["show instances\n"]) == 0

    def test_a_script_fails_if_any_line_failed(self, cli, session, capsys):
        """`echo nonsense | vastai repl` must not look successful to CI."""
        assert Repl(cli, session).run_script(["show instances\n", "nonsense\n"]) == 1

    @pytest.mark.parametrize("line", [":nope", ":set nonsense on", ":set raw onn"])
    def test_a_rejected_meta_command_fails_the_script(self, cli, session, line):
        """run_script promises nonzero for any failed line — meta included."""
        assert Repl(cli, session).run_script([line + "\n"]) == 1

    def test_a_failing_shell_escape_fails_the_script(self, cli, session):
        assert Repl(cli, session).run_script(["!false\n"]) == 1

    def test_a_succeeding_shell_escape_does_not(self, cli, session):
        assert Repl(cli, session).run_script(["!true\n"]) == 0

    def test_a_failing_command_fails_the_script(self, cli, session):
        cli.subparsers_.choices["show user"].set_defaults(func=lambda args: 2)
        assert Repl(cli, session).run_script(["show user\n"]) == 1

    def test_a_key_written_mid_session_is_picked_up(self, cli, session, calls, tmp_path):
        """`set api-key` writes the config file, not our namespace: without a
        refresh every later line would keep sending the key we started with."""
        api_file = tmp_path / "vast_api_key"
        with patch("vastai.cli.repl.session.APIKEY_FILE", str(api_file)), \
             patch("vastai.cli.repl.session.TFAKEY_FILE", str(tmp_path / "missing")):
            session.api_key = None
            repl = Repl(cli, session)
            api_file.write_text("fresh-key\n")  # as `set api-key` would
            repl.handle("show user")
            repl.handle("show user")
        assert calls[-1].api_key == "fresh-key"

    @pytest.mark.parametrize("line", [
        "set api-key sk-secret", "show user --api-key sk-secret",
        "tfa login --secret S -c 123", "!vastai set api-key sk-secret",
        "tfa regen-codes --backup-code ABCD-EFGH", "tfa delete --code 456789",
        "tfa auth-new -bc ABCD --code 123456",
    ])
    def test_credential_lines_are_kept_out_of_history(self, line):
        assert _is_secret(line) is True

    def test_a_removed_key_is_dropped_from_the_session(self, cli, session, tmp_path):
        """An expired 2FA session with nothing to fall back to: keeping the dead
        key would fail every later line with the same misleading error."""
        api_file = tmp_path / "vast_api_key"
        api_file.write_text("stored-key")
        with patch("vastai.cli.repl.session.APIKEY_FILE", str(api_file)), \
             patch("vastai.cli.repl.session.TFAKEY_FILE", str(tmp_path / "missing")):
            session.api_key = "stored-key"
            repl = Repl(cli, session)
            api_file.unlink()
            repl.handle("show user")
        assert repl.args.api_key is None

    def test_a_key_we_never_adopted_is_left_alone(self, cli, session, tmp_path):
        """A key from --api-key or $VAST_API_KEY must survive a file that was
        never the session's source."""
        with patch("vastai.cli.repl.session.APIKEY_FILE", str(tmp_path / "missing")), \
             patch("vastai.cli.repl.session.TFAKEY_FILE", str(tmp_path / "missing")):
            session.api_key = "flag-key"
            repl = Repl(cli, session)
            repl.handle("show user")
        assert repl.args.api_key == "flag-key"

    def test_changing_the_key_clears_cached_completions(self, cli, session, tmp_path):
        api_file = tmp_path / "vast_api_key"
        with patch("vastai.cli.repl.session.APIKEY_FILE", str(api_file)), \
             patch("vastai.cli.repl.session.TFAKEY_FILE", str(tmp_path / "missing")):
            repl = Repl(cli, session)
            repl.completer.values._cache[object()] = (0.0, ["stale"])
            api_file.write_text("fresh-key")
            repl.handle("show user")
        assert repl.completer.values._cache == {}

    def test_completion_never_inherits_the_output_modes(self, cli, session):
        """`--curl` makes the API client print a curl line and exit; completion
        must not carry that (or --explain) into its own lookups."""
        session.curl = True
        session.explain = True
        session.api_key = "session-key"
        args = Repl(cli, session)._completion_args()
        assert args.curl is False and args.explain is False and args.raw is False
        assert args.api_key == "session-key"

    @pytest.mark.parametrize("line", ["show instances", "search offers 'gpu_name=RTX_4090'"])
    def test_ordinary_lines_are_remembered(self, line):
        assert _is_secret(line) is False
