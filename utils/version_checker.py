import os
import sys
import importlib.metadata
from git import Repo

PACKAGE_NAME = "vast-cli-fork"


def is_git_distribution() -> bool:
    distribution = None
    try:
        # INFO - throws an error if the package isn't installed from PyPi
        distribution = importlib.metadata.distribution(PACKAGE_NAME)

        return False
    except Exception as e:
        # INFO - at this point we know the package isn't installed from PyPi, we need to check if it's from git now
        repo = Repo(os.path.dirname(distribution.locate_file("")))
        print("repo:", repo)
        # print("Repo:", Repo.rev_parse)
        # print(f"{distribution.locate_file("")=}")
        # repo = Repo(os.path.dirname(distribution.locate_file("")))
        # Repo.rev_parse(rev="HEAD")
        # base.Repo.rev_parse()
        return True

        # if hasattr(distribution, "_path"):
        #     location = os.path.dirname(distribution._path)
        # else:
        #     location = distribution.locate_file("")
        #
        # # Check if we're in a git repository
        # project_root = location
        #
        # print(f"{distribution=}")
        # Look upward for .git directory
        # for _ in range(4):  # Check up to 4 levels up
        #     if os.path.exists(os.path.join(project_root, ".git")):
        #         # This is a git repository
        #         try:
        #             # Try to get the git remote URL
        #             result = subprocess.run(
        #                 [
        #                     "git",
        #                     "-C",
        #                     project_root,
        #                     "config",
        #                     "--get",
        #                     "remote.origin.url",
        #                 ],
        #                 capture_output=True,
        #                 text=True,
        #                 check=False,
        #             )
        #             if result.returncode == 0:
        #                 git_url = result.stdout.strip()
        #                 return f"{PACKAGE_NAME} is installed from git repository: {git_url}"
        #             return f"{PACKAGE_NAME} is installed from a local git repository at {project_root}"
        #         except Exception:
        #             return f"{PACKAGE_NAME} is installed from a git repository at {project_root}"
        #
        #     # Move up one directory
        #     new_root = os.path.dirname(project_root)
        #     if new_root == project_root:  # Reached root directory
        #         break
        #     project_root = new_root
        #
        # Poetry-specific check
    #     if "pypoetry/virtualenvs" in location:
    #         # This is installed via Poetry, but need to determine if it's from pip or git
    #         version = distribution.version
    #
    #         # If version contains a git hash-like string (typically with +), it might be from git
    #         if "+" in version or "dev" in version:
    #             return f"{PACKAGE_NAME} (version {version}) appears to be installed from git via Poetry"
    #
    #         return (
    #             f"{PACKAGE_NAME} (version {version}) was installed via Poetry from PyPI"
    #         )
    #
    #     # Default to assuming it's from pip
    #     version = distribution.version
    #     return f"{PACKAGE_NAME} (version {version}) was installed via pip to {location}"
    #
    # except (importlib.metadata.PackageNotFoundError, ModuleNotFoundError):
    #     # Check if we're in the package directory itself
    #     cwd = os.getcwd()
    #     if (
    #         os.path.basename(os.path.dirname(cwd)) == PACKAGE_NAME
    #         or os.path.basename(cwd) == PACKAGE_NAME
    #     ):
    #         if os.path.exists(os.path.join(cwd, ".git")) or os.path.exists(
    #             os.path.join(os.path.dirname(cwd), ".git")
    #         ):
    #             return f"{PACKAGE_NAME} is the current working directory (in a git repository, not installed)"
    #         return f"{PACKAGE_NAME} is the current working directory (not installed)"
    #
    #     return f"Package {PACKAGE_NAME} is not installed"
    #


print(is_git_distribution())
