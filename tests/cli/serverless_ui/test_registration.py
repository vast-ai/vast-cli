"""The command as vastai itself registers it: main.py's import list, in a fresh interpreter
(test_main imports the command module directly, which registers it on its own)."""
import os
import subprocess
import sys

VASTAI = "import sys; from vastai.cli.main import main; sys.argv[0] = 'vastai'; main()"


def vastai(*argv, **env):
    return subprocess.run([sys.executable, "-c", VASTAI, *argv], capture_output=True, text=True,
                          timeout=60, env={**os.environ, "VASTAI_NO_UPDATE_CHECK": "1", **env})


def test_vastai_registers_the_command():
    out = vastai("run", "serverless-ui", "--help")
    assert out.returncode == 0, out.stderr
    assert "--access-token" in out.stdout


def test_a_bad_port_variable_breaks_only_this_command():
    """Every command module is imported on every call, so its defaults must not fail."""
    assert vastai("--help", SERVERLESS_UI_PORT="abc").returncode == 0
    out = vastai("run", "serverless-ui", SERVERLESS_UI_PORT="abc")
    assert out.returncode != 0 and "SERVERLESS_UI_PORT" in out.stderr


def test_an_empty_api_key_runs_without_a_key_whatever_the_environment_holds():
    """`--api-key=` is how docs/serverless-ui.md says to run without a key: vastai's own key
    resolution must not fall back to VAST_API_KEY or the saved key for it."""
    stubbed = ("import sys; from vastai.serverless.ui import server as ui; "
               "ui.configure_logging = lambda: None; "
               "ui.web.run_app = lambda app, **kw: print('SERVER_KEY=' + repr(app[ui.SERVER_KEY])); "
               "from vastai.cli.main import main; sys.argv[0] = 'vastai'; main()")
    env = {**os.environ, "VASTAI_NO_UPDATE_CHECK": "1", "VAST_API_KEY": "env-key-0123456789abcdef"}
    run = lambda *argv: subprocess.run([sys.executable, "-c", stubbed, "run", "serverless-ui", *argv],  # noqa: E731
                                       capture_output=True, text=True, timeout=60, env=env)
    out = run("--api-key=")
    assert "SERVER_KEY=''" in out.stdout, out.stderr
    assert "SERVER_KEY='env-key-0123456789abcdef'" in run().stdout  # the control: it would be used
