import os


def is_git_distribution() -> bool:
    # INFO - Check if .git directory exists at the same level as the current working directory
    return os.path.isdir(os.path.join(os.getcwd(), ".git"))


print(is_git_distribution())
