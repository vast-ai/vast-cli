import json
import os
import pytest
import argparse
import requests
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_args():
    """Minimal argparse.Namespace for testing CLI functions."""
    return argparse.Namespace(
        api_key="test-key",
        url="https://console.vast.ai",
        retry=3,
        raw=False,
        explain=False,
        quiet=False,
        curl=False,
        full=False,
        no_color=True,
        debugging=False,
    )


@pytest.fixture
def mock_response():
    """Mock HTTP response with configurable status and JSON body."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"success": True}
    response.text = '{"success": true}'
    response.content = b'{"success": true}'
    response.headers = {"Content-Type": "application/json"}
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def mock_api_response():
    """Factory fixture for creating mock API responses with configurable status and data."""
    def _make_response(status_code=200, json_data=None, text=None, headers=None):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data if json_data is not None else {}
        response.text = text if text is not None else json.dumps(json_data or {})
        response.content = response.text.encode()
        response.headers = headers if headers is not None else {"Content-Type": "application/json"}
        if status_code >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(f"{status_code} Error")
        else:
            response.raise_for_status = MagicMock()
        return response
    return _make_response


@pytest.fixture
def mock_http_get(mock_api_response):
    """Patch vast.http_get to return controlled responses."""
    with patch('vast.http_get') as mock:
        mock.return_value = mock_api_response(200, {"success": True})
        yield mock


@pytest.fixture
def mock_http_post(mock_api_response):
    """Patch vast.http_post to return controlled responses."""
    with patch('vast.http_post') as mock:
        mock.return_value = mock_api_response(200, {"success": True})
        yield mock


@pytest.fixture
def vast_cli_path():
    """Return path to vast.py for subprocess tests."""
    return os.path.join(os.path.dirname(__file__), '..', 'vast.py')
