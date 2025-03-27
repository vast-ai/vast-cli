import os
import json
from importlib.metadata import distribution

PACKAGE_NAME = "vast-cli-fork"
def is_pip_package():
    dist = distribution(PACKAGE_NAME)
    print(dist)


def check_local_version():
    return NotImplemented

def check_stable_version():
    return NotImplemented

is_pip_package()
