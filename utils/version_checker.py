import sys
import os
import importlib.metadata
import subprocess
from utils.pypi_api import get_project_data, get_pypi_version, BASE_PATH


def parse_version(version: str) -> tuple[int, ...]:
    parts = version.split(".")

    if len(parts) < 3:
        print(f"Invalid version format: {version}", file=sys.stderr)

    return tuple(int(part) for part in parts)


def get_git_version():
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True,
        )
        tag = result.stdout.strip()

        return tag[1:] if tag.startswith("v") else tag
    except Exception:
        return "0.0.0"


def get_pip_version():
    return importlib.metadata.version("vast-cli-fork")


def is_pip_package():
    script_path = sys.argv[0]
    executable_name = os.path.basename(script_path)

    return executable_name != "vast.py"


def get_update_command(stable_version: str) -> str:
    if is_pip_package():
        if "test.pypi.org" in BASE_PATH:
            return f"{sys.executable} -m pip install --force-reinstall --no-cache-dir -i {BASE_PATH} vast-cli-fork=={stable_version}"
        else:
            return f"{sys.executable} -m pip install --force-reinstall --no-cache-dir vast-cli-fork=={stable_version}"
    else:
        return f"git fetch --all --tags --prune && git checkout tags/v{stable_version}"


def get_local_version():
    if is_pip_package():
        return get_pip_version()
    return get_git_version()


def check_for_update():
    pypi_data = get_project_data("vast-cli-fork")
    pypi_version = get_pypi_version(pypi_data)

    local_version = get_local_version()

    local_tuple = parse_version(local_version)
    pypi_tuple = parse_version(pypi_version)

    if local_tuple >= pypi_tuple:
        return

    user_wants_update = input(
        f"Update available from {local_version} to {pypi_version}. Would you like to update [Y/n]: "
    ).lower()

    if user_wants_update not in ["y", ""]:
        return

    update_command = get_update_command(pypi_version)

    _ = subprocess.run(
        update_command,
        shell=True,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    print("Update completed successfully!\nAttempt to run your command again!")
    sys.exit(0)

