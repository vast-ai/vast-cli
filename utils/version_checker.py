import sys
import os
import subprocess
from utils.pypi_api import get_project_data, get_pypi_version, BASE_PATH

def parse_version(version: str) -> tuple:
    """Parse a version string into a tuple for proper comparison."""
    parts = version.split('.')
    while len(parts) < 3:
        parts.append('0')
    return tuple(int(part) for part in parts)

def get_git_version():
    """Get version from git tags."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True
        )
        tag = result.stdout.strip()
        # Remove 'v' prefix if present
        return tag[1:] if tag.startswith('v') else tag
    except Exception:
        return "0.0.0"

def get_pip_version():
    """Get version from pip metadata."""
    try:
        import importlib.metadata
        return importlib.metadata.version("vast-cli-fork")
    except (ImportError, importlib.metadata.PackageNotFoundError):
        try:
            import pkg_resources
            return pkg_resources.get_distribution("vast-cli-fork").version
        except Exception:
            return "0.0.0"

def is_pip_package():
    """Check if running from pip-installed package."""
    return "site-packages" in sys.prefix

def check_for_update():
    """Check for updates and perform the update if requested."""
    try:
        # Get PyPI version
        pypi_data = get_project_data("vast-cli-fork")
        pypi_version = get_pypi_version(pypi_data)
        
        # Get local version based on installation type
        if is_pip_package():
            local_version = get_pip_version()
        else:
            local_version = get_git_version()
        
        print(f"Local version: {local_version}")
        print(f"PyPI version: {pypi_version}")
        
        # Parse and compare versions
        local_tuple = parse_version(local_version)
        pypi_tuple = parse_version(pypi_version)
        
        print(f"Parsed local version: {local_tuple}")
        print(f"Parsed PyPI version: {pypi_tuple}")
        
        # Check if update is needed
        if local_tuple >= pypi_tuple:
            print("You're using the latest version.")
            return
        
        # Prompt for update
        user_wants_update = input(
            f"Update available from {local_version} to {pypi_version}. Would you like to update [Y/n]: "
        ).lower()
        
        if user_wants_update not in ["y", ""]:
            return
        
        # Perform update based on installation type
        if is_pip_package():
            update_command = f"{sys.executable} -m pip install --force-reinstall --no-cache-dir vast-cli-fork"
        else:
            # For git, use a more direct checkout approach
            update_command = f"git fetch --all --tags --prune && git checkout tags/v{pypi_version}"
        
        print(f"Running update: {update_command}")
        
        # Execute the update command
        try:
            result = subprocess.run(
                update_command,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            print("Update completed successfully!")
            
            # For git updates, one additional step - create a version marker file
            if not is_pip_package():
                with open(".current_version", "w") as f:
                    f.write(pypi_version)
            
            print("Please restart the CLI manually to use the new version.")
            sys.exit(0)
            
        except subprocess.CalledProcessError as e:
            print(f"Update failed: {e.stderr}")
            
    except Exception as e:
        print(f"Error checking for updates: {e}")
