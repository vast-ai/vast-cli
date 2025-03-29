import importlib.metadata


def is_git_distribution() -> bool:
    """
    Determine how the code is being run:
    - From PyPI installation
    - From source code (Git or direct script)
    """
    # Get the module/package name
    module_name = __name__.split(".")[0]

    try:
        # Check if the package is installed with metadata
        # This will succeed for PyPI/pip installed packages
        metadata = importlib.metadata.metadata(module_name)
        return False
    except importlib.metadata.PackageNotFoundError:
        return True
        # if os.path.isdir(os.path.join(os.getcwd(), ".git")):
        #     return "git_repository"
        # else:
        #     return "direct_script"


print(f"Running as: {is_git_distribution()}")
