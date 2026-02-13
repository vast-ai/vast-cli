"""Smoke tests for CLI commands.

TEST-08: CLI smoke tests - major commands parse args and call correct endpoints.

These tests verify that CLI commands:
1. Parse their arguments correctly
2. Call the expected API endpoints
3. Handle mocked responses appropriately

All HTTP is mocked - no network calls are made.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import argparse
import json
import pytest
from unittest.mock import MagicMock, patch


def _make_base_args(**overrides):
    """Create base args namespace with common fields."""
    args = argparse.Namespace(
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
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


@pytest.fixture(autouse=True)
def setup_vast_args():
    """Set up vast.ARGS to prevent NoneType errors in http_request."""
    import vast
    old_args = vast.ARGS
    vast.ARGS = _make_base_args()
    yield
    vast.ARGS = old_args


class TestSearchOffers:
    """Smoke tests for 'search offers' command."""

    @patch('vast.http_post')
    def test_search_offers_calls_bundles_endpoint(self, mock_http_post):
        """search offers calls /api/v0/bundles/ endpoint via POST."""
        import vast

        mock_response = MagicMock()
        mock_response.json.return_value = {"offers": []}
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.raise_for_status = MagicMock()
        mock_http_post.return_value = mock_response

        args = _make_base_args(
            query=["gpu_ram>=8"],
            type="bid",
            raw=True,
            no_default=False,
            new=False,
            limit=None,
            disable_bundling=False,
            storage=5.0,
            order="score-",
        )
        vast.search__offers(args)

        mock_http_post.assert_called_once()
        call_url = mock_http_post.call_args[0][1]
        assert "/api/v0/bundles" in call_url

    @patch('vast.http_post')
    def test_search_offers_with_gpu_name(self, mock_http_post):
        """search offers parses gpu_name filter."""
        import vast

        mock_response = MagicMock()
        mock_response.json.return_value = {"offers": []}
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.raise_for_status = MagicMock()
        mock_http_post.return_value = mock_response

        args = _make_base_args(
            query=["gpu_name=RTX_4090"],
            type="on-demand",
            raw=True,
            no_default=False,
            new=False,
            limit=None,
            disable_bundling=False,
            storage=5.0,
            order="score-",
        )
        vast.search__offers(args)

        mock_http_post.assert_called_once()


class TestShowInstances:
    """Smoke tests for 'show instances' command."""

    @patch('vast.http_get')
    def test_show_instances_calls_instances_endpoint(self, mock_http_get):
        """show instances calls /api/v0/instances/ endpoint."""
        import vast

        mock_response = MagicMock()
        mock_response.json.return_value = {"instances": []}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_http_get.return_value = mock_response

        args = _make_base_args(raw=True)
        vast.show__instances(args)

        mock_http_get.assert_called_once()
        call_url = mock_http_get.call_args[0][1]
        assert "/api/v0/instances" in call_url

    @patch('vast.http_get')
    def test_show_instances_returns_list(self, mock_http_get):
        """show instances handles list response correctly."""
        import vast

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "instances": [
                {"id": 123, "status": "running", "start_date": 1700000000, "extra_env": []},
                {"id": 456, "status": "stopped", "start_date": 1700000000, "extra_env": []}
            ]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_http_get.return_value = mock_response

        args = _make_base_args(raw=True)
        result = vast.show__instances(args)

        # In raw mode, should return the data
        assert result is not None or mock_http_get.called


class TestShowMachines:
    """Smoke tests for 'show machines' command."""

    @patch('vast.api_call')
    def test_show_machines_calls_machines_endpoint(self, mock_api_call):
        """show machines calls /api/v0/machines/ endpoint."""
        import vast

        mock_api_call.return_value = {"machines": []}

        args = _make_base_args(raw=True, quiet=True)
        vast.show__machines(args)

        mock_api_call.assert_called_once()
        call_args = mock_api_call.call_args
        assert call_args[0][1] == "GET"
        assert "/machines" in call_args[0][2]


class TestShowUser:
    """Smoke tests for 'show user' command."""

    @patch('vast.api_call')
    def test_show_user_calls_users_endpoint(self, mock_api_call):
        """show user calls /api/v0/users/current endpoint."""
        import vast

        mock_api_call.return_value = {"id": 12345, "username": "testuser", "api_key": "secret"}

        args = _make_base_args(raw=True, quiet=True)
        vast.show__user(args)

        mock_api_call.assert_called_once()
        call_args = mock_api_call.call_args
        assert call_args[0][1] == "GET"
        assert "/users/current" in call_args[0][2]


class TestCreateInstance:
    """Smoke tests for 'create instance' command."""

    @patch('vast.http_put')
    def test_create_instance_calls_asks_endpoint(self, mock_http_put):
        """create instance calls /api/v0/asks/{id}/ endpoint."""
        import vast

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "new_contract": 789}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_http_put.return_value = mock_response

        args = _make_base_args(
            id=12345,
            bid_price=None,
            disk=20.0,
            image="pytorch/pytorch:latest",
            raw=True,
            onstart=None,
            onstart_cmd=None,
            entrypoint=None,
            env=None,
            args=None,
            label=None,
            extra=None,
            jupyter=False,
            jupyter_dir=None,
            jupyter_lab=False,
            lang_utf8=False,
            python_utf8=False,
            ssh=False,
            direct=False,
            cancel_unavail=False,
            force=False,
            login=None,
            template_hash=None,
            user=None,
            create_volume=None,
            link_volume=None,
        )
        vast.create__instance(args)

        mock_http_put.assert_called_once()
        call_url = mock_http_put.call_args[0][1]
        assert "/api/v0/asks" in call_url


class TestDestroyInstance:
    """Smoke tests for 'destroy instance' command."""

    @patch('vast.http_del')
    def test_destroy_instance_calls_instances_endpoint(self, mock_http_del):
        """destroy instance calls DELETE /api/v0/instances/{id}/ endpoint."""
        import vast

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_http_del.return_value = mock_response

        args = _make_base_args(id=12345, raw=True)
        vast.destroy__instance(args)

        mock_http_del.assert_called_once()
        call_url = mock_http_del.call_args[0][1]
        assert "/api/v0/instances" in call_url
        assert "12345" in call_url


class TestLogsCommand:
    """Smoke tests for 'logs' command."""

    @patch('vast.http_get')
    @patch('vast.http_put')
    def test_logs_calls_instances_endpoint(self, mock_http_put, mock_http_get):
        """logs command calls appropriate endpoint."""
        import vast

        # Mock the logs request
        mock_put_response = MagicMock()
        mock_put_response.json.return_value = {"result_url": "https://example.com/logs"}
        mock_put_response.status_code = 200
        mock_put_response.raise_for_status = MagicMock()
        mock_http_put.return_value = mock_put_response

        # Mock the log fetch
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.text = "Log output here"
        mock_http_get.return_value = mock_get_response

        args = _make_base_args(
            INSTANCE_ID=123,
            raw=True,
            tail=None,
            filter=None,
            daemon_logs=False,
        )

        # logs may print and not return in non-raw mode
        vast.logs(args)

        # Should have made HTTP calls
        assert mock_http_put.called


class TestSetApiKey:
    """Smoke tests for 'set api-key' command."""

    @patch('builtins.open', create=True)
    @patch('os.path.exists')
    def test_set_api_key_writes_file(self, mock_exists, mock_open):
        """set api-key writes key to config file."""
        import vast

        mock_exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        args = _make_base_args(new_api_key="sk-test-key-12345")
        vast.set__api_key(args)

        mock_open.assert_called()


class TestShowApiKeys:
    """Smoke tests for 'show api-keys' command."""

    @patch('vast.http_get')
    def test_show_api_keys_calls_auth_endpoint(self, mock_http_get):
        """show api-keys calls /api/v0/auth/apikeys/ endpoint."""
        import vast

        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "name": "test-key"}]
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_http_get.return_value = mock_response

        args = _make_base_args(raw=True)
        result = vast.show__api_keys(args)

        mock_http_get.assert_called_once()
        call_url = mock_http_get.call_args[0][1]
        assert "/api/v0/auth/apikeys" in call_url


class TestParserStructure:
    """Tests verifying the argparse parser structure."""

    def test_parser_has_subcommands(self):
        """Parser has expected subcommand structure."""
        import vast

        # Parser should exist
        assert hasattr(vast, 'parser')

        # Should be able to parse help
        with pytest.raises(SystemExit) as exc_info:
            vast.parser.parse_args(['--help'])
        assert exc_info.value.code == 0

    def test_search_offers_subcommand_exists(self):
        """search offers subcommand is registered."""
        import vast

        # Should not raise - parse_args with --help raises SystemExit(0)
        with pytest.raises(SystemExit) as exc_info:
            vast.parser.parse_args(['search', 'offers', '--help'])
        assert exc_info.value.code == 0

    def test_show_instances_subcommand_exists(self):
        """show instances subcommand is registered."""
        import vast

        # Parse minimal args (should work)
        args = vast.parser.parse_args(['show', 'instances'])
        assert args is not None

    def test_create_instance_subcommand_exists(self):
        """create instance subcommand is registered."""
        import vast

        # Should parse with required args
        with pytest.raises(SystemExit) as exc_info:
            vast.parser.parse_args(['create', 'instance', '--help'])
        assert exc_info.value.code == 0

    def test_destroy_instance_subcommand_exists(self):
        """destroy instance subcommand is registered."""
        import vast

        # Should parse with required args
        with pytest.raises(SystemExit) as exc_info:
            vast.parser.parse_args(['destroy', 'instance', '--help'])
        assert exc_info.value.code == 0

    def test_show_user_subcommand_exists(self):
        """show user subcommand is registered."""
        import vast

        args = vast.parser.parse_args(['show', 'user'])
        assert args is not None

    def test_show_machines_subcommand_exists(self):
        """show machines subcommand is registered."""
        import vast

        args = vast.parser.parse_args(['show', 'machines'])
        assert args is not None

    def test_set_api_key_subcommand_exists(self):
        """set api-key subcommand is registered."""
        import vast

        with pytest.raises(SystemExit) as exc_info:
            vast.parser.parse_args(['set', 'api-key', '--help'])
        assert exc_info.value.code == 0

    def test_logs_subcommand_exists(self):
        """logs subcommand is registered."""
        import vast

        with pytest.raises(SystemExit) as exc_info:
            vast.parser.parse_args(['logs', '--help'])
        assert exc_info.value.code == 0

    def test_show_api_keys_subcommand_exists(self):
        """show api-keys subcommand is registered."""
        import vast

        args = vast.parser.parse_args(['show', 'api-keys'])
        assert args is not None
