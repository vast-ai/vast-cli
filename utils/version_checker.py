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
        return f"git pull --force && git checkout v{stable_version}"

    if "test.pypi" in BASE_PATH:
        return f"pip install -i {BASE_PATH} vast-cli-fork --upgrade"

    return f"pip install {BASE_PATH} vast-cli-fork --upgrade"

def install_update(update_command: str):
    # try:
    print(f"Executing update: {update_command}")
    _ = subprocess.run(
        update_command.split(" "), 
        capture_output=True,
        text=True,
        check=True
    )
    print("Update completed successfully!")

def check_for_update():
    local_package_version = get_local_package_version()
    pypi_version = get_pypi_version(get_project_data("vast-cli-fork"))

    if local_package_version >= pypi_version:
        return

    # INFO - If we get to this point (no exception thrown), we know that there's an update available
    user_wants_update = input(f"Update available from {local_package_version} to {pypi_version}. Would you like to update [Y/n]: ").lower()
    
    if user_wants_update == "y" or user_wants_update == "":
        # TODO - do update here
        update_command = None
        if is_pip_package():
            # TODO: Prompt input to update using pip update
            update_command = get_update_command("pypi", pypi_version)
            # print("PIP PACKAGE")
        else:
            update_command = get_update_command("git", pypi_version)

        try:
            install_update(update_command)
        except Exception as e:
            print(f"Unexpected error occurred during update: {e}")




