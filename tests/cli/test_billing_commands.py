"""Integration tests for billing CLI commands with mocked HTTP."""

import pytest
from requests.exceptions import HTTPError


class TestShowUser:
    def test_show_user_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "email": "test@test.com", "id": 1, "balance": 10.0, "api_key": "secret"
        })
        args = parse_argv(["show", "user", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/users/current" in call_args[0][0]

    def test_show_user_display(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "email": "test@test.com", "id": 1, "balance": 10.0,
        })
        args = parse_argv(["show", "user"])
        args.func(args)
        captured = capsys.readouterr()
        assert "Email" in captured.out or "test@test.com" in captured.out


class TestShowInvoices:
    def test_show_invoices_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "invoices": [{"id": 1, "amount": 5.0, "type": "charge", "timestamp": 1700000000}],
            "current": {"total": 5.0},
        })
        args = parse_argv(["show", "invoices", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/users/me/invoices" in call_args[0][0]


class TestShowEarnings:
    def test_show_earnings_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"earnings": []})
        args = parse_argv(["show", "earnings", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/users/me/machine-earnings" in call_args[0][0]


class TestShowDeposit:
    def test_show_deposit(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"balance": 100.0})
        args = parse_argv(["show", "deposit", "123"])
        args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "123" in call_args[0][0]


class TestShowSubaccounts:
    def test_show_subaccounts_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "users": [{"id": 2, "email": "sub@test.com"}]
        })
        args = parse_argv(["show", "subaccounts", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/subaccounts" in call_args[0][0]


class TestShowIpaddrs:
    def test_show_ipaddrs_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "results": [{"ip": "1.2.3.4", "first_seen": "2024-01-01"}]
        })
        args = parse_argv(["show", "ipaddrs", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/users/me/ipaddrs" in call_args[0][0]


class TestShowScheduledJobs:
    def test_show_scheduled_jobs_display(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, [
            {
                "id": 1, "instance_id": 100, "api_endpoint": "/api/v0/instances/reboot/100/",
                "start_time": 1700000000, "end_time": 1700100000,
                "day_of_the_week": None, "hour_of_the_day": None,
                "min_of_the_hour": None, "frequency": "HOURLY",
            }
        ])
        args = parse_argv(["show", "scheduled-jobs"])
        args.func(args)
        captured = capsys.readouterr()
        assert "Scheduled Job ID" in captured.out or "HOURLY" in captured.out or "Everyday" in captured.out


class TestHttpErrors:
    def test_401_raises(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(401, {"msg": "Unauthorized"})
        args = parse_argv(["show", "user", "--raw"])
        with pytest.raises(HTTPError):
            args.func(args)

    def test_500_raises(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(500, {"msg": "Server error"})
        args = parse_argv(["show", "user", "--raw"])
        with pytest.raises(HTTPError):
            args.func(args)
