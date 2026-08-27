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


ENDPOINT_ONLY_SCALING_FLAGS = ("--target_util", "--cold_mult")


class TestWorkergroupEndpointOnlyScalingFlags:
    """target_util and cold_mult scale the endpoint group, never a workergroup."""

    @pytest.mark.parametrize("flag", ENDPOINT_ONLY_SCALING_FLAGS)
    def test_create_workergroup_rejects_flag(self, cli_parser, flag):
        with pytest.raises(SystemExit):
            cli_parser.parse_args(["create", "workergroup", flag, "0.9"])

    @pytest.mark.parametrize("flag", ENDPOINT_ONLY_SCALING_FLAGS)
    def test_update_workergroup_rejects_flag(self, cli_parser, flag):
        with pytest.raises(SystemExit):
            cli_parser.parse_args(["update", "workergroup", "1", flag, "0.9"])

    def test_create_workergroup_payload_omits_fields(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.post.return_value = mock_response(200, {"success": True, "id": 7})
        args = parse_argv(["create", "workergroup", "--endpoint_id", "3",
                           "--template_hash", "abc123"])
        args.func(args)
        payload = patch_get_client.post.call_args.kwargs["json_data"]
        assert "target_util" not in payload
        assert "cold_mult" not in payload

    def test_update_workergroup_payload_omits_fields(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["update", "workergroup", "42", "--min_load", "100"])
        args.func(args)
        payload = patch_get_client.put.call_args.kwargs["json_data"]
        assert "target_util" not in payload
        assert "cold_mult" not in payload

    @pytest.mark.parametrize("flag", ENDPOINT_ONLY_SCALING_FLAGS)
    def test_endpoint_commands_keep_flag(self, cli_parser, flag):
        create = cli_parser.parse_args(["create", "endpoint", flag, "0.5"])
        update = cli_parser.parse_args(["update", "endpoint", "1", flag, "0.5"])
        dest = flag.lstrip("-")
        assert getattr(create, dest) == 0.5
        assert getattr(update, dest) == 0.5
