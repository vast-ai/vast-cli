import os
import importlib.metadata

PACKAGE_NAME = "vast-cli-fork"


def is_git_distribution() -> bool:
    try:
        # Get package location
        dist = importlib.metadata.distribution(PACKAGE_NAME)
        package_location = dist.locate_file("")

        package_path = str(package_location)

        marker_path = os.path.join(package_path, "DISTRIBUTION_SOURCE")
        if os.path.exists(marker_path):
            with open(marker_path, "r") as f:
                source = f.read().strip()
            return source != "pypi"
        else:
            # No marker file = git installation
            return True
    except Exception:
        # Any error = assume git installation
        return True


print(is_git_distribution())
