"""Integration tests for endpoint/workergroup CLI commands with mocked HTTP."""

import pytest


class TestShowEndpoints:
    def test_show_endpoints_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "success": True,
            "results": [{"id": 1, "endpoint_name": "my-endpoint"}]
        })
        args = parse_argv(["show", "endpoints", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/endptjobs/" in call_args[0][0]


class TestCreateEndpoint:
    def test_create_endpoint(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {"success": True, "id": 1})
        args = parse_argv(["create", "endpoint", "--endpoint_name", "test-ep"])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/endptjobs/" in call_args[0][0]


class TestDeleteEndpoint:
    def test_delete_endpoint(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["delete", "endpoint", "1"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/endptjobs/1/" in call_args[0][0]


class TestShowWorkergroups:
    def test_show_workergroups_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "success": True,
            "results": [{"id": 1, "name": "wg1"}]
        })
        args = parse_argv(["show", "workergroups", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/autojobs/" in call_args[0][0]
