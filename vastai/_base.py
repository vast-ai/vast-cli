import os
from typing import Optional

_APIKEY_SENTINEL = object()

def _resolve_api_key(api_key: object) -> str:
    """
    Resolves the API key from (in order):
      1. Explicit argument
      2. VAST_API_KEY environment variable
      3. XDG config file: $XDG_CONFIG_HOME/vastai/vast_api_key
         (falls back to ~/.config/vastai/vast_api_key if xdg is unavailable)
      4. Legacy file: ~/.vast_api_key
    """
    if api_key is not _APIKEY_SENTINEL:
        return api_key

    env = os.getenv("VAST_API_KEY")
    if env:
        return env

    try:
        import xdg
        config_dir = xdg.xdg_config_home()
    except ImportError:
        config_dir = os.path.join(os.getenv("HOME"), ".config")
    xdg_path = os.path.join(config_dir, "vastai", "vast_api_key")
    if os.path.exists(xdg_path):
        return open(xdg_path).read().strip()

    legacy_path = os.path.expanduser("~/.vast_api_key")
    if os.path.exists(legacy_path):
        return open(legacy_path).read().strip()

    raise RuntimeError(
        "No API key found. Pass api_key=, set VAST_API_KEY, "
        f"or save your key to {xdg_path}"
    )


class _BaseClient:
    def __init__(self, api_key: object = _APIKEY_SENTINEL, vast_server: str = "https://console.vast.ai"):
        self._api_key = _resolve_api_key(api_key)
        self._vast_server = vast_server.rstrip("/")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _url(self, path: str) -> str:
        return f"{self._vast_server}{path}"
