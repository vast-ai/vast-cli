import sys
import os
import subprocess

from utils.pypi_api import get_project_data, get_pypi_version, BASE_PATH


# INFO: This is strictly for propogating the correct update command when prompted
def is_pip_package() -> bool:
    executable = os.path.basename(sys.argv[0])

    if executable == "vast-cli-fork":
        return True

    if executable == "vast.py":
        return False

    # For edge cases (like python -m vast), check the main module's path
    import __main__

    main_path = getattr(__main__, "__file__", "")

    # If main module filename contains 'site-packages', it's likely the installed package
    if "site-packages" in main_path:
        return True

    return False


def get_local_package_version():
    try:
        result = subprocess.run(
            ["poetry", "version", "--short"], capture_output=True, text=True, check=True
        )

        version = result.stdout.strip()

        if version.count("-") >= 1:
            return version.split("-")[0]

        return version

    except Exception as e:
        return f"Unexpected error: {e}"


def get_update_command(distribution: str, stable_version: str) -> str:
    if distribution != "git" and distribution != "pypi":
        raise Exception("Not a valid distribution")

    if distribution == "git":
        return f"git fetch --all --tags --prune && git checkout tags/v{stable_version} -b v{stable_version}"

    if "test.pypi" in BASE_PATH:
        return f"pip install -i {BASE_PATH} vast-cli-fork --upgrade"

    return f"pip install {BASE_PATH} vast-cli-fork --upgrade"


def install_update(update_command: str, stable_version: str):
    try:
        _ = subprocess.run(
            update_command,
            check=True,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        print("Update completed successfully!")

        # INFO - For both pip and git updates, restart the current process to use the new version
        print("Restarting with new version...")

        # INFO - restart current process
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except subprocess.CalledProcessError as e:

        # INFO - If the branch already exists locally for whatever reason, we need to just checkout the tagged commit instead
        if "already exists":
            update_command = f"git checkout tags/v{stable_version}"
            try:
                _ = subprocess.run(update_command, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                print(f"Update failed: {e.stderr}")
            os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        print(f"Unexpected error during update: {str(e)}")


def check_for_update():
    local_package_version = get_local_package_version()
    pypi_version = get_pypi_version(get_project_data("vast-cli-fork"))

    if local_package_version == pypi_version:
        return

    # INFO - If we get to this point (no exception thrown), we know that there's an update available
    user_wants_update = input(
        f"Update available from {local_package_version} to {pypi_version}. Would you like to update [Y/n]: "
    ).lower()

    if user_wants_update == "y" or user_wants_update == "":
        update_command = None
        if is_pip_package():
            update_command = get_update_command("pypi", pypi_version)
        else:
            update_command = get_update_command("git", pypi_version)

        try:
            install_update(update_command, pypi_version)
        except Exception as e:
            print(f"Unexpected error occurred during update: {e}")

        # This line will only be reached if the restart in install_update fails
        print("Please restart the CLI manually to use the new version.")
