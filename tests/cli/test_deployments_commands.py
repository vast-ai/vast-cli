"""Unit tests for deployment CLI commands with mocked HTTP."""

import pytest
from requests.exceptions import HTTPError


class TestShowDeployments:
    def test_show_deployments_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "deployments": [{"id": 1, "name": "dep-1"}, {"id": 2, "name": "dep-2"}]
        })
        args = parse_argv(["show", "deployments", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/deployments" in call_args[0][0]

    def test_show_deployments_table(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "deployments": [{"id": 1, "name": "dep-1", "tag": "latest"}]
        })
        args = parse_argv(["show", "deployments"])
        args.func(args)
        patch_get_client.get.assert_called_once()

    def test_show_deployments_error(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(401, {"error": "unauthorized"})
        args = parse_argv(["show", "deployments", "--raw"])
        with pytest.raises(HTTPError):
            args.func(args)


class TestShowDeployment:
    def test_show_deployment_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "deployment": {"id": 42, "name": "dep-42", "state": "running"}
        })
        args = parse_argv(["show", "deployment", "42", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/deployment/42/" in call_args[0][0]

    def test_show_deployment_table(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "deployment": {"id": 42, "name": "dep-42", "state": "running"}
        })
        args = parse_argv(["show", "deployment", "42"])
        args.func(args)
        patch_get_client.get.assert_called_once()

    def test_show_deployment_not_found(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(404, {"error": "not found"})
        args = parse_argv(["show", "deployment", "999", "--raw"])
        with pytest.raises(HTTPError):
            args.func(args)


class TestDeleteDeployment:
    def test_delete_deployment(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["delete", "deployment", "42"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/deployment/42/" in call_args[0][0]
        captured = capsys.readouterr()
        assert "Deleted deployment 42" in captured.out

    def test_delete_deployment_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["delete", "deployment", "42", "--raw"])
        result = args.func(args)
        patch_get_client.delete.assert_called_once()

    def test_delete_deployment_error(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.delete.return_value = mock_response(404, {"error": "not found"})
        args = parse_argv(["delete", "deployment", "999"])
        with pytest.raises(HTTPError):
            args.func(args)
