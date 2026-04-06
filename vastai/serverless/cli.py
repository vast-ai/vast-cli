# vastai/serverless/cli.py
import os
import sys
import runpy
import subprocess


def main():
    if len(sys.argv) < 3:
        print("Usage: vast [deploy|serve|run|down] [--debug] <script> [script-args...]", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    remaining_args = sys.argv[2:]

    # Check for --debug flag
    debug = False
    if "--debug" in remaining_args:
        debug = True
        remaining_args.remove("--debug")

    if not remaining_args:
        print("Usage: vast [deploy|serve|run|down] [--debug] <script> [script-args...]", file=sys.stderr)
        sys.exit(1)

    script_path = remaining_args[0]
    script_args = remaining_args[1:]

    # For `run`, bypass runpy and just call python3
    if mode == "run":
        cmd = ["python3", script_path] + script_args
        # Replace the current process with python3
        os.execvp("python3", cmd)

    # For all other modes, set env var and run via runpy
    os.environ["VAST_DEPLOYMENT_MODE"] = mode
    if debug:
        os.environ["VAST_DEBUG"] = "1"

    # Rebuild sys.argv for the script we're about to run
    sys.argv = [script_path] + script_args

    # Execute the target script as __main__
    runpy.run_path(script_path, run_name="__main__")
