"""`vastai run serverless-ui`: what it refuses, where the key came from, and which Host names it
answers to."""
import errno

import pytest

from vastai.cli.commands import serverless_ui
from vastai.serverless.ui import server as ui
from .fake_vast import KEY

TOKEN = "ui-token-0123456789-abcd"


@pytest.fixture
def started(monkeypatch):
    calls = []

    def run_app(app, **kw):  # binds nothing; says it has, as aiohttp does once it is listening
        calls.append((app, kw))
        kw["print"]("======== Running ========")
    monkeypatch.setattr(ui.web, "run_app", run_app)
    monkeypatch.setattr(ui, "configure_logging", lambda: None)
    for name in ("VAST_DEBUG_WORKER_URL", "HOST", "VAST_API_KEY", serverless_ui.TOKEN_VAR,
                 "SERVERLESS_UI_HOST", "SERVERLESS_UI_PORT"):
        monkeypatch.delenv(name, raising=False)
    return calls


def start(*argv, api_key=KEY):
    """Parses the command line as vastai does; the CLI's own key resolution fills api_key."""
    args = serverless_ui.parser.parse_args(["run", "serverless-ui", *argv])
    args.api_key, args.url = api_key, None
    args.func(args)


def test_refuses_to_start_with_a_debug_worker_url(started, monkeypatch):
    monkeypatch.setenv("VAST_DEBUG_WORKER_URL", "http://attacker.example")
    with pytest.raises(SystemExit):
        start()
    assert started == []


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_on_localhost_only_localhost_names_are_accepted(started, capsys, host):
    start("--host", host)
    [(app, kw)] = started
    assert app[ui.ALLOWED_HOSTS] == ui.LOOPBACK and kw["host"] == host and kw["port"] == 8765
    assert app[ui.SHARE_TRAFFIC]  # every caller has the token
    assert KEY not in capsys.readouterr().out


def test_with_a_key_a_token_is_made_for_the_run_and_printed_in_the_link(started, capsys):
    """Localhost is open to every user and process on the machine, and a proxy in front may
    rewrite Host, so a server holding a key never runs without a token."""
    start()
    [(app, _)] = started
    token = app[ui.ACCESS_TOKEN]
    assert len(token) >= ui.MIN_TOKEN
    out = capsys.readouterr().out
    assert f"Serverless UI -> http://127.0.0.1:8765/#token={token}\n" in out  # the fragment never reaches the server
    assert f"  export SERVERLESS_UI_TOKEN={token}\n" in out and "Ctrl+C to stop." in out
    start()
    assert started[1][0][ui.ACCESS_TOKEN] != token  # a new one each run


def test_a_given_token_is_used_and_never_printed(started, monkeypatch, capsys):
    monkeypatch.setenv(serverless_ui.TOKEN_VAR, TOKEN)
    start()
    assert started[0][0][ui.ACCESS_TOKEN] == TOKEN
    out = capsys.readouterr().out
    assert "Access token: from SERVERLESS_UI_TOKEN" in out and TOKEN not in out and "#token" not in out


def test_without_a_key_on_localhost_there_is_no_token(started):
    """Callers bring their own Vast keys; nothing of the server's can be spent."""
    start(api_key="")
    assert started[0][0][ui.ACCESS_TOKEN] == ""


def test_bound_beyond_localhost_the_machines_names_and_any_allowed_are_accepted(started, monkeypatch, capsys):
    monkeypatch.setattr(ui, "bind_names", lambda host: {"box", "192.168.1.5"})
    monkeypatch.setenv(serverless_ui.TOKEN_VAR, TOKEN)
    start("--host", "0.0.0.0", "--allowed-host", "Console.LAN")
    [(app, _)] = started
    assert app[ui.ALLOWED_HOSTS] == ui.LOOPBACK | {"box", "192.168.1.5", "console.lan"}
    assert not app[ui.SHARE_TRAFFIC]
    assert app[ui.ACCESS_TOKEN] == TOKEN
    out = capsys.readouterr().out
    assert "Access token: from SERVERLESS_UI_TOKEN" in out and "console.lan" in out and "--share-traffic" in out
    assert "plain HTTP" in out
    assert KEY not in out and TOKEN not in out


@pytest.mark.parametrize("api_key", [KEY, ""])
def test_shared_there_is_always_a_token(started, monkeypatch, api_key):
    """Bound beyond localhost, with a key or without: without one, the token keeps strangers
    from using the server, and each caller's own key, as a relay."""
    monkeypatch.setattr(ui, "bind_names", lambda host: set())
    start("--host", "0.0.0.0", api_key=api_key)
    assert len(started[0][0][ui.ACCESS_TOKEN]) >= ui.MIN_TOKEN


def test_a_short_token_is_refused(started):
    with pytest.raises(SystemExit, match="too short"):
        start("--access-token", "short")
    assert started == []


def test_share_traffic_shows_the_servers_traffic_beyond_localhost(started, monkeypatch):
    monkeypatch.setattr(ui, "bind_names", lambda host: set())
    start("--host", "0.0.0.0", "--share-traffic", "--access-token", TOKEN)
    assert started[0][0][ui.SHARE_TRAFFIC]


def test_an_unrelated_HOST_variable_does_not_move_the_server(started, monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")  # set by many platforms for other purposes
    start()
    assert started[0][1]["host"] == "127.0.0.1"


def test_the_startup_line_names_where_the_key_came_from_never_the_key(started, monkeypatch, tmp_path, capsys):
    saved = tmp_path / "vast_api_key"
    saved.write_text(KEY + "\n")
    monkeypatch.setattr(serverless_ui, "APIKEY_FILE", str(saved))
    monkeypatch.setattr(serverless_ui, "TFAKEY_FILE", str(tmp_path / "none"))
    assert serverless_ui.key_source(KEY) == str(saved)
    monkeypatch.setenv("VAST_API_KEY", KEY)
    assert serverless_ui.key_source(KEY) == "VAST_API_KEY"
    assert serverless_ui.key_source("another-key-0123456789") == "--api-key"
    assert serverless_ui.key_source("") == "none"
    start()
    out = capsys.readouterr().out
    assert "Key: VAST_API_KEY" in out and KEY not in out


def test_behind_a_proxy_on_localhost_it_is_shared(started, capsys):
    """A reverse proxy or tunnel in front of 127.0.0.1 is named with --allowed-host: then others
    can reach it, though it is bound to localhost."""
    start("--allowed-host", "ui.example", api_key="")
    [(app, _)] = started
    assert app[ui.ACCESS_TOKEN] and not app[ui.SHARE_TRAFFIC]
    assert "plain HTTP" in capsys.readouterr().out


def test_a_port_in_use_is_one_line_and_no_url(started, monkeypatch, capsys):
    def busy(app, **kw):
        raise OSError(errno.EADDRINUSE, "Address already in use")
    monkeypatch.setattr(ui.web, "run_app", busy)
    with pytest.raises(SystemExit, match="Port 8765 on 127.0.0.1 is in use. Pass --port"):
        start()
    assert "http://" not in capsys.readouterr().out  # no URL for a server that isn't there


@pytest.mark.parametrize("port", ["abc", "0", "70000"])
def test_a_bad_port_is_this_commands_usage_error(started, capsys, port):
    with pytest.raises(SystemExit):
        serverless_ui.parser.parse_args(["run", "serverless-ui", "--port", port])
    assert "SERVERLESS_UI_PORT" in capsys.readouterr().err


def test_host_and_port_variables_are_read_when_it_runs(started, monkeypatch):
    monkeypatch.setenv("SERVERLESS_UI_HOST", "::1")
    monkeypatch.setenv("SERVERLESS_UI_PORT", "9123")
    start()
    assert started[0][1]["host"] == "::1" and started[0][1]["port"] == 9123
    monkeypatch.setenv("SERVERLESS_UI_PORT", "abc")
    with pytest.raises(SystemExit, match="SERVERLESS_UI_PORT"):
        start()


def test_a_client_that_goes_away_cancels_its_request(started):
    """aiohttp's default leaves a handler running after its client has gone."""
    start()
    assert started[0][1]["handler_cancellation"] is True


def test_the_request_timeout_is_passed_on_and_must_be_a_number(started, capsys):
    start("--request-timeout", "45")
    assert started[0][0][ui.TIMEOUT] == 45.0
    for bad in ("0", "-1", "soon"):
        with pytest.raises(SystemExit):
            serverless_ui.parser.parse_args(["run", "serverless-ui", "--request-timeout", bad])
