import sys
import os

def is_running_as_package():
    """
    Determines if we're running the installed package ('vast-cli-fork' command)
    or directly via './vast.py'
    
    Returns:
        bool: True if running as installed package, False if running from source
    """
    # Get the executable name (without path)
    executable = os.path.basename(sys.argv[0])
    print(f"[{executable=}]:")
    
    # If the executable is 'vast-cli-fork', we're running the installed package
    if executable == 'vast-cli-fork':
        return True
        
    # If the executable is 'vast.py', we're running from source
    if executable == 'vast.py':
        return False
        
    # For edge cases (like python -m vast), check the main module's path
    import __main__
    main_path = getattr(__main__, '__file__', '')
    
    # If main module filename contains 'site-packages', it's likely the installed package
    if 'site-packages' in main_path:
        return True
        
    return False

def check_for_updates():
    """
    Checks if the current version is up-to-date with PyPI and prompts for update if needed.
    """
    if not is_running_as_package():
        # Running from source, no need to check for updates
        return

    # Get current version
    try:
        import importlib.metadata
        current_version = importlib.metadata.version('vast-cli-fork')

        # Here you'd check PyPI for latest version and compare
        # (Code for checking PyPI omitted for brevity)
        print(f"Current version: {current_version}")
        print("Running as installed package. Would check for updates here.")
    except Exception as e:
        print(f"Error checking version: {e}")

