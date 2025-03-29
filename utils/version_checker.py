import sys
import os
import subprocess

from utils.pypi_api import get_project_data, get_pypi_version


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
            ["poetry", "version", "--short"],
            capture_output=True,
            text=True, 
            check=True
        )

        version = result.stdout.strip()

        if version.count("-") >= 1:
            return version.split("-")[0]

        return version

    except Exception as e:
        return f"Unexpected error: {e}"

def check_for_update():
    local_package_version = get_local_package_version()
    pypi_version = get_pypi_version(get_project_data("vast-cli-fork"))

    if is_pip_package():
        # TODO: Prompt input to update using pip update
        print("PIP PACKAGE")

    else:
        print("PROMPT UPDATE TO GIT")
    print(f"{local_package_version=}")
    print(f"{pypi_version=}")

check_for_update()
