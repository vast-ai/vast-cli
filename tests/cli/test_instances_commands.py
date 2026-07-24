"""Integration tests for instance CLI commands with mocked HTTP."""

import time
import pytest
from requests.exceptions import HTTPError


class TestShowInstances:
    def test_show_instances_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [
                {"id": 1, "gpu_name": "RTX_3090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": [["KEY", "VAL"]]}
            ]
        })
        args = parse_argv(["show", "instances", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/instances" in call_args[0][0]
        assert isinstance(result, list)

    def test_show_instances_raw_null_instances(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": None})
        args = parse_argv(["show", "instances", "--raw"])

        result = args.func(args)

        assert result == []

    def test_show_instances_display(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [
                {"id": 1, "gpu_name": "RTX_3090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": []}
            ]
        })
        args = parse_argv(["show", "instances"])
        args.func(args)
        captured = capsys.readouterr()
        assert "ID" in captured.out

    def test_show_instances_quiet_prints_bare_ids(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [
                {"id": 1, "gpu_name": "RTX_3090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": []},
                {"id": 2, "gpu_name": "RTX_4090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": []},
            ]
        })
        args = parse_argv(["show", "instances", "-q"])
        args.func(args)
        captured = capsys.readouterr()
        assert captured.out == "1\n2\n"

    def test_show_instances_v1_is_hidden_alias(self, parse_argv, patch_get_client, mock_response):
        from vastai.cli.commands.instances import show__instances
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [
                {"id": 1, "gpu_name": "RTX_3090", "actual_status": "running",
                 "start_date": time.time() - 3600, "extra_env": [["KEY", "VAL"]]}
            ]
        })
        args = parse_argv(["show", "instances-v1", "--raw"])
        assert args.func is show__instances
        result = args.func(args)
        assert isinstance(result, list)

    def test_show_instances_no_deprecation_warning_stderr(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"instances": [], "next_token": None})
        args = parse_argv(["show", "instances", "--raw"])
        args.func(args)
        captured = capsys.readouterr()
        assert "DEPRECATED" not in captured.err


class TestShowInstancesFilters:
    def test_status_filter_sent(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": [], "next_token": None})
        args = parse_argv(["show", "instances", "--raw", "--status", "running", "loading"])
        args.func(args)
        select_filters = patch_get_client.get.call_args.kwargs["query_args"]["select_filters"]
        assert select_filters == {"actual_status": {"in": ["running", "loading"]}}

    def test_invalid_status_warns(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"instances": [], "next_token": None})
        args = parse_argv(["show", "instances", "--raw", "--status", "bogus"])
        args.func(args)
        captured = capsys.readouterr()
        assert "unknown status value" in captured.err

    def test_label_filter_empty_string_means_unlabeled(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": [], "next_token": None})
        args = parse_argv(["show", "instances", "--raw", "--label", ""])
        args.func(args)
        select_filters = patch_get_client.get.call_args.kwargs["query_args"]["select_filters"]
        assert select_filters == {"label": {"in": [None]}}

    def test_gpu_name_filter_sent(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": [], "next_token": None})
        args = parse_argv(["show", "instances", "--raw", "--gpu-name", "RTX 4090"])
        args.func(args)
        select_filters = patch_get_client.get.call_args.kwargs["query_args"]["select_filters"]
        assert select_filters == {"gpu_name": {"in": ["RTX 4090"]}}

    def test_verification_filter_sent(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": [], "next_token": None})
        args = parse_argv(["show", "instances", "--raw", "--verification", "verified"])
        args.func(args)
        select_filters = patch_get_client.get.call_args.kwargs["query_args"]["select_filters"]
        assert select_filters == {"verification": {"in": ["verified"]}}

    def test_order_by_default_sorts_by_id(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": [], "next_token": None})
        args = parse_argv(["show", "instances", "--raw"])
        args.func(args)
        order_by = patch_get_client.get.call_args.kwargs["query_args"]["order_by"]
        assert order_by == [{"col": "id", "dir": "asc"}]

    def test_order_by_custom_column_still_tiebreaks_on_id(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": [], "next_token": None})
        args = parse_argv(["show", "instances", "--raw", "--order-by", "start_date desc"])
        args.func(args)
        order_by = patch_get_client.get.call_args.kwargs["query_args"]["order_by"]
        assert order_by == [{"col": "start_date", "dir": "desc"}, {"col": "id", "dir": "asc"}]

    def test_custom_cols_limits_table_columns(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": [{
                "id": 1, "dph_total": 0.5, "actual_status": "running",
                "gpu_name": "RTX_3090", "num_gpus": 1, "start_date": time.time() - 10,
            }],
            "next_token": None, "total_instances": 1, "label_counts": {},
        })
        args = parse_argv(["show", "instances", "--cols", "id,dph", "--full"])
        args.func(args)
        captured = capsys.readouterr()
        assert "$/hr" in captured.out
        assert "Status" not in captured.out


class TestShowInstancesPagination:
    def test_default_fetches_every_page_and_concatenates(self, parse_argv, patch_get_client, mock_response):
        page1 = {"instances": [{"id": 1, "start_date": time.time() - 10, "extra_env": []}], "next_token": "tok1"}
        page2 = {"instances": [{"id": 2, "start_date": time.time() - 10, "extra_env": []}], "next_token": None}
        patch_get_client.get.side_effect = [mock_response(200, page1), mock_response(200, page2)]
        args = parse_argv(["show", "instances", "--raw"])
        result = args.func(args)
        assert [r["id"] for r in result] == [1, 2]
        assert patch_get_client.get.call_count == 2

    def test_explicit_limit_returns_single_page_dict(self, parse_argv, patch_get_client, mock_response):
        page = {"instances": [{"id": 1}], "next_token": "tok1", "total_instances": 5, "label_counts": {}}
        patch_get_client.get.return_value = mock_response(200, page)
        args = parse_argv(["show", "instances", "--raw", "--limit", "1"])
        result = args.func(args)
        assert result == page
        patch_get_client.get.assert_called_once()

    def test_all_flag_fetches_every_page_even_with_explicit_limit(self, parse_argv, patch_get_client, mock_response, capsys):
        page1 = {"instances": [{"id": 1}], "next_token": "tok1", "total_instances": 2, "label_counts": {}}
        page2 = {"instances": [{"id": 2}], "next_token": None, "total_instances": 2, "label_counts": {}}
        patch_get_client.get.side_effect = [mock_response(200, page1), mock_response(200, page2)]
        args = parse_argv(["show", "instances", "-q", "--limit", "1", "--all"])
        args.func(args)
        captured = capsys.readouterr()
        assert captured.out == "1\n2\n"
        assert patch_get_client.get.call_count == 2

    @pytest.mark.parametrize("extra_argv", [[], ["--all"]])
    def test_fetch_all_never_throttles_between_pages(self, parse_argv, patch_get_client, mock_response, monkeypatch, extra_argv):
        """No inter-page sleep, with or without --all -- there's no rate-limit reason to pace
        one fetch-all path differently from the other when both hit the same endpoint."""
        sleep_calls = []
        monkeypatch.setattr("vastai.cli.commands.instances.time.sleep", lambda s: sleep_calls.append(s))
        page1 = {"instances": [{"id": 1}], "next_token": "tok1"}
        page2 = {"instances": [{"id": 2}], "next_token": None}
        patch_get_client.get.side_effect = [mock_response(200, page1), mock_response(200, page2)]
        args = parse_argv(["show", "instances", "-q", *extra_argv])
        args.func(args)
        assert sleep_calls == []

    def test_non_tty_never_blocks_on_pagination_prompt(self, parse_argv, patch_get_client, mock_response, monkeypatch, capsys):
        def boom(*a, **kw):
            raise AssertionError("must not prompt for input in a non-interactive invocation")
        monkeypatch.setattr("builtins.input", boom)
        page = {
            "instances": [{"id": 1, "start_date": time.time() - 10}],
            "next_token": "tok1", "total_instances": 5, "label_counts": {},
        }
        patch_get_client.get.return_value = mock_response(200, page)
        args = parse_argv(["show", "instances", "--limit", "1", "--full"])
        args.func(args)
        captured = capsys.readouterr()
        assert "Next page token: tok1" in captured.out


class TestShowInstancesQuietRawPrecedence:
    """Regression: --quiet must always win over --raw, matching the legacy command."""

    def test_quiet_wins_over_raw_in_fetch_all_mode(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"instances": [{"id": 7}], "next_token": None})
        args = parse_argv(["show", "instances", "--quiet", "--raw"])
        result = args.func(args)
        captured = capsys.readouterr()
        assert captured.out == "7\n"
        assert result is None

    def test_quiet_wins_over_raw_in_explicit_pagination_mode(self, parse_argv, patch_get_client, mock_response, capsys):
        page = {"instances": [{"id": 7}], "next_token": None, "total_instances": 1, "label_counts": {}}
        patch_get_client.get.return_value = mock_response(200, page)
        args = parse_argv(["show", "instances", "--quiet", "--raw", "--limit", "5"])
        result = args.func(args)
        captured = capsys.readouterr()
        assert captured.out == "7\n"
        assert result is None


class TestShowInstance:
    def test_show_instance_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "instances": {"id": 123, "gpu_name": "RTX_4090", "start_date": time.time() - 100, "extra_env": []}
        })
        args = parse_argv(["show", "instance", "123", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "123" in call_args[0][0]

    def test_show_instance_raw_deleted_instance(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"instances": None})
        args = parse_argv(["show", "instance", "123", "--raw"])

        result = args.func(args)

        assert result == {"instances": None}

    def test_show_instance_display_deleted_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"instances": None})
        args = parse_argv(["show", "instance", "123"])

        result = args.func(args)

        assert result == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Instance 123 not found or no longer exists." in captured.err


class TestDestroyInstance:
    def test_destroy_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["destroy", "instance", "123", "--raw", "--yes"])
        result = args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/instances/123/" in call_args[0][0]

    def test_destroy_instance_confirm_yes(self, parse_argv, patch_get_client, mock_response, capsys, monkeypatch):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        monkeypatch.setattr("builtins.input", lambda _: "y")
        args = parse_argv(["destroy", "instance", "123"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        captured = capsys.readouterr()
        assert "destroying instance 123" in captured.out

    def test_destroy_instance_confirm_no(self, parse_argv, patch_get_client, mock_response, capsys, monkeypatch):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        monkeypatch.setattr("builtins.input", lambda _: "n")
        args = parse_argv(["destroy", "instance", "123"])
        args.func(args)
        patch_get_client.delete.assert_not_called()
        captured = capsys.readouterr()
        assert "Aborted" in captured.out


class TestStartInstance:
    def test_start_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["start", "instance", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/123/" in call_args[0][0]
        assert call_args[1]["json_data"]["state"] == "running"


class TestStopInstance:
    def test_stop_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["stop", "instance", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/123/" in call_args[0][0]
        assert call_args[1]["json_data"]["state"] == "stopped"


class TestRebootInstance:
    def test_reboot_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["reboot", "instance", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/reboot/123/" in call_args[0][0]


class TestRecycleInstance:
    def test_recycle_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["recycle", "instance", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert "/instances/recycle/123/" in call_args[0][0]


class TestLabelInstance:
    def test_label_instance(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.put.return_value = mock_response(200, {"success": True})
        args = parse_argv(["label", "instance", "123", "my-label"])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert call_args[1]["json_data"]["label"] == "my-label"


# TestAcceptPriceIncrease was rewritten against the per-row backend and moved
# to tests/cli/test_price_increase_commands.py alongside the show + reject
# command tests.
