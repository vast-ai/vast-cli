"""Integration tests for miscellaneous CLI commands with mocked HTTP."""

import pytest


class TestExecute:
    def test_execute(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"output": "hello"})
        args = parse_argv(["execute", "123", "ls -la"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/command/123/" in call_args[0][0]
        assert call_args[1]["json_data"]["command"] == "ls -la"


class TestLogs:
    def test_logs(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"result": "log output"})
        args = parse_argv(["logs", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/request_logs/123/" in call_args[0][0]


class TestReports:
    def test_reports(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, [
            {"id": 1, "machine_id": 100, "report": "test report"}
        ])
        args = parse_argv(["reports", "100"])
        args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/machines/100/reports" in call_args[0][0]


class TestSshUrl:
    def test_ssh_url(self, parse_argv, patch_get_client, mock_response, capsys):
        import time
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [{
                "id": 123, "start_date": time.time(), "extra_env": [],
                "ports": {"22/tcp": [{"HostPort": "12345"}]},
                "public_ipaddr": "1.2.3.4",
                "ssh_host": "ssh.vast.ai", "ssh_port": 22,
                "image_runtype": "ssh",
            }]
        })
        args = parse_argv(["ssh-url", "123"])
        args.func(args)
        captured = capsys.readouterr()
        assert "ssh://" in captured.out
        assert "12345" in captured.out


class TestScpUrl:
    def test_scp_url(self, parse_argv, patch_get_client, mock_response, capsys):
        import time
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [{
                "id": 123, "start_date": time.time(), "extra_env": [],
                "ports": {"22/tcp": [{"HostPort": "12345"}]},
                "public_ipaddr": "1.2.3.4",
                "ssh_host": "ssh.vast.ai", "ssh_port": 22,
                "image_runtype": "ssh",
            }]
        })
        args = parse_argv(["scp-url", "123"])
        args.func(args)
        captured = capsys.readouterr()
        assert "scp://" in captured.out
        assert "12345" in captured.out
