#!/usr/bin/python
"""
Deployment bootstrap script invoked by start_server.sh when IS_DEPLOYMENT=true.

Downloads and extracts the deployment tarball, applies config.json
(env vars, apt packages, pip packages, run scripts), then starts the
deployment worker.
"""

import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


VAST_API_URL = os.environ.get("VAST_API_URL", "https://console.vast.ai")


def get_api_key() -> str:
    """Resolve an API key from the container environment.

    Inside a Vast instance, Kaalia sets CONTAINER_API_KEY with the
    instance-level API key that has permissions to fetch deployment blobs.
    """
    key = os.environ.get("CONTAINER_API_KEY") or os.environ.get("VAST_API_KEY")
    if not key:
        raise RuntimeError(
            "No API key found in environment (CONTAINER_API_KEY or VAST_API_KEY)"
        )
    return key


def get_download_url(deployment_id: str, api_key: str) -> str:
    """Fetch the presigned S3 download URL for the deployment blob."""
    url = f"{VAST_API_URL}/api/v0/deployment/{deployment_id}/download_url/"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    if not data.get("success"):
        raise RuntimeError(f"Failed to get download URL: {data}")
    return data["download_url"]


def download_tarball(download_url: str) -> str:
    """Download the deployment tarball to a temp file, returning its path."""
    fd, path = tempfile.mkstemp(suffix=".tar.gz")
    try:
        with urllib.request.urlopen(download_url) as resp, os.fdopen(fd, "wb") as f:
            while True:
                chunk = resp.read(1 << 20)  # 1 MB
                if not chunk:
                    break
                f.write(chunk)
    except Exception:
        os.unlink(path)
        raise
    return path


def extract_tarball(tarball_path: str):
    cwd = os.getcwd()
    with tarfile.open(tarball_path, "r:gz") as tf:
        for member in tf.getmembers():
            tf.extract(
                member, filter="fully_trusted"
            )  # preserve absolute paths; deployment .tar files are created by client via deployments SDK and are trusted inside the container.


def get_config(path: str):
    """Load and return config.json as a Config dataclass."""
    from vastai.serverless.remote.base import Config

    with open(path) as f:
        raw = json.load(f)
    return Config(
        name=raw["name"],
        pip_installs=raw.get("pip_installs", []),
        apt_gets=raw.get("apt_gets", []),
        envs=raw.get("envs", []),
        runs=raw.get("runs", []),
    )


def export_envs(envs: list):
    """Export environment variables and append to /etc/environment."""
    etc_lines = []
    for entry in envs:
        key, value = entry[0], entry[1]
        os.environ[key] = value
        etc_lines.append(f'{key}="{value}"\n')
    if etc_lines:
        with open("/etc/environment", "a") as f:
            f.writelines(etc_lines)


def run_apt_gets(packages: list[str]):
    """Install apt packages."""
    if not packages:
        return
    subprocess.run(
        ["apt-get", "update", "-qq"],
        check=True,
    )
    subprocess.run(
        ["apt-get", "install", "-y", "-qq"] + packages,
        check=True,
    )


def run_pip_installs(packages: list[str]):
    """Install pip packages using uv."""
    if not packages:
        return
    subprocess.run(
        ["uv", "pip", "install"] + packages,
        check=True,
    )


def run_scripts(runs: list):
    """Run scripts from config.

    Each entry is either a string (passed to sh -c) or a list of args (execvp style).
    """
    for entry in runs:
        if isinstance(entry, str):
            subprocess.run(["sh", "-c", entry], check=True)
        elif isinstance(entry, (list, tuple)):
            subprocess.run(list(entry), check=True)
        else:
            raise ValueError(f"Invalid run entry: {entry!r}")


def main():
    deployment_id = os.environ.get("DEPLOYMENT_ID")
    if not deployment_id:
        raise RuntimeError("DEPLOYMENT_ID environment variable not set")

    debug_deployment_tar = os.environ.get("DEBUG_DEPLOYMENT_TAR")
    if debug_deployment_tar:
        tarball_path = debug_deployment_tar
    else:
        api_key = get_api_key()

        # Download deployment tarball
        print(f"Fetching download URL for deployment {deployment_id}")
        download_url = get_download_url(deployment_id, api_key)

        print("Downloading deployment tarball")
        tarball_path = download_tarball(download_url)

    # Extract preserving absolute paths — the deployment runs in a
    # container owned by the client, and we trust their path choices.
    print("Extracting deployment tarball")
    try:
        extract_tarball(tarball_path)
    finally:
        os.unlink(tarball_path)

    # Load config
    config = get_config("config.json")
    print(f"Loaded config for deployment: {config.name}")

    # (1) Export envs
    if config.envs:
        print(f"Exporting {len(config.envs)} environment variables")
        export_envs(config.envs)

    # (2) Install packages
    if config.apt_gets:
        print(f"Installing {len(config.apt_gets)} apt packages")
        run_apt_gets(config.apt_gets)

    if config.pip_installs:
        print(f"Installing {len(config.pip_installs)} pip packages")
        run_pip_installs(config.pip_installs)

    # (3) Run scripts
    if config.runs:
        print(f"Running {len(config.runs)} setup scripts")
        run_scripts(config.runs)

    # Look up and start deployment
    from vastai.serverless.remote.serve import Deployment

    # ensure deployment import time code is run in serve mode.
    os.environ["IS_DEPLOYMENT"] = "1"
    # deployment module/package is guaranteed from tarball
    sys.path.insert(0, os.getcwd())
    import deployment  # running this import has the side effect of registering deployments and remote functions with vastai.serverless.remote.serve.Deployment

    our_deployment = Deployment.lookup(config.name)
    if our_deployment is None:
        raise RuntimeError(f"Failed to lookup registered deployment: {config.name}")

    print(f"Starting deployment worker: {config.name}")
    worker = our_deployment.into_worker()
    worker.run()


if __name__ == "__main__":
    main()
