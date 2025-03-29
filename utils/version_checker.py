import importlib.resources

PACKAGE_NAME = "vast-cli-fork"
MODULE_NAME = "vast-cli-fork"


def is_git_distribution() -> bool:
    try:
        try:
            source = importlib.resources.read_text(
                MODULE_NAME, "DISTRIBUTION_SOURCE"
            ).strip()
            return source != "pypi"
        except (ImportError, FileNotFoundError):
            # INFO - File doesn't exist = git installation
            return True
    except Exception:
        # INFO - assume git
        return True
