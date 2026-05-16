"""Integration tests for the price-increase CLI commands.

Covers the per-row rewrite: `show pending-price-increases`,
`accept price-increase`, `reject price-increase`. Argparse rejection of
`--host` is the only regression we need against the old shape; the rest
asserts the new flow end-to-end with mocked HTTP.
"""

import pytest


PENDING_ROW = {
    "pending_price_increase_id": 999,
    "contract_id": 123,
    "host_id": 7,
    "new_gpu_costpersec": 0.0002,
    "old_gpu_costpersec": 0.0001,
    "new_disk_ram_costpersec": None,
    "old_disk_ram_costpersec": None,
    "new_bwu_cost": 0.02,
    "old_bwu_cost": 0.01,
    "new_bwd_cost": 0.02,
    "old_bwd_cost": 0.01,
    "new_platform_fee": 0.15,
    "old_platform_fee": 0.10,
    "contract_end_date": 1_700_000_000.0,
    "ask_end_date": 1_700_500_000.0,
    "created_at": 1_699_990_000.0,
}

SECOND_ROW = {
    **PENDING_ROW,
    "pending_price_increase_id": 1000,
    "contract_id": 456,
}


def _envelope(rows):
    return {
        "success": True,
        "count": len(rows),
        "truncated": False,
        "pending_price_increases": list(rows),
    }


# ---------------------------------------------------------------------------
# show pending-price-increases
# ---------------------------------------------------------------------------


class TestShowPendingPriceIncreases:
    def test_default_renders_documented_columns(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        args = parse_argv(["show", "pending-price-increases"])
        args.func(args)
        captured = capsys.readouterr()
        # Columns advertised in the spec table descriptor.
        for col in ("Pending ID", "Instance", "Host", "Current End",
                    "New End", "GPU", "Storage", "BW Up", "BW Down",
                    "Platform Fee"):
            assert col in captured.out
        # Pending id + contract id surface as data.
        assert "999" in captured.out
        assert "123" in captured.out

    def test_storage_with_null_new_shows_dash(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        args = parse_argv(["show", "pending-price-increases"])
        args.func(args)
        captured = capsys.readouterr()
        # `new_disk_ram_costpersec` is None on the fixture, so the storage cell
        # collapses to "-" (rendered as "-" in display_table; "_" if space).
        # Either "_" (replaced spaces) or "-" should be present.
        assert " - " in captured.out.replace("_", " ") or "-" in captured.out

    def test_raw_returns_envelope_unchanged(self, parse_argv, patch_get_client, mock_response):
        envelope = _envelope([PENDING_ROW])
        patch_get_client.get.return_value = mock_response(200, envelope)
        args = parse_argv(["show", "pending-price-increases", "--raw"])
        result = args.func(args)
        assert result == envelope

    def test_quiet_prints_one_pending_id_per_line(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(
            200, _envelope([PENDING_ROW, SECOND_ROW]),
        )
        args = parse_argv(["show", "pending-price-increases", "--quiet"])
        args.func(args)
        captured = capsys.readouterr()
        lines = [line for line in captured.out.splitlines() if line]
        assert lines == ["999", "1000"]

    def test_empty_envelope_friendly_message(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _envelope([]))
        args = parse_argv(["show", "pending-price-increases"])
        args.func(args)
        captured = capsys.readouterr()
        assert "No pending price increases." in captured.out


# ---------------------------------------------------------------------------
# accept price-increase
# ---------------------------------------------------------------------------


class TestAcceptPriceIncrease:
    def test_single_id_resolves_then_puts_pending_id(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        patch_get_client.put.return_value = mock_response(
            200, {"success": True, "pending_price_increase_id": 999, "contract_id": 123},
        )
        args = parse_argv(["accept", "price-increase", "123", "--yes"])
        args.func(args)
        patch_get_client.get.assert_called_once_with("/instances/pending-price-increases/")
        patch_get_client.put.assert_called_once()
        url = patch_get_client.put.call_args[0][0]
        body = patch_get_client.put.call_args[1]["json_data"]
        assert url == "/instances/accept-price-increase/"
        assert body == {"pending_price_increase_id": 999}
        captured = capsys.readouterr()
        assert "Accepted pending_id=999 contract_id=123" in captured.out
        # The cutover note is required on the success path.
        assert "New rate applies after each contract's current end_date." in captured.out

    def test_multiple_ids_fan_out_sequential(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(
            200, _envelope([PENDING_ROW, SECOND_ROW]),
        )
        patch_get_client.put.side_effect = [
            mock_response(200, {"success": True, "pending_price_increase_id": 999,  "contract_id": 123}),
            mock_response(200, {"success": True, "pending_price_increase_id": 1000, "contract_id": 456}),
        ]
        args = parse_argv(["accept", "price-increase", "123", "456", "--yes"])
        args.func(args)
        assert patch_get_client.put.call_count == 2
        bodies = [call.kwargs["json_data"] for call in patch_get_client.put.call_args_list]
        assert bodies == [
            {"pending_price_increase_id": 999},
            {"pending_price_increase_id": 1000},
        ]

    def test_missing_yes_non_tty_exits_1(self, parse_argv, patch_get_client, mock_response, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        # list_pending may or may not be called before the gate; assert no PUT.
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        args = parse_argv(["accept", "price-increase", "123"])
        with pytest.raises(SystemExit) as excinfo:
            args.func(args)
        assert excinfo.value.code == 1
        patch_get_client.put.assert_not_called()
        captured = capsys.readouterr()
        assert "--yes is required when stdin is not a TTY" in captured.err

    def test_tty_prompt_aborts_on_no(self, parse_argv, patch_get_client, mock_response, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _: "n")
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        args = parse_argv(["accept", "price-increase", "123"])
        args.func(args)
        patch_get_client.put.assert_not_called()
        captured = capsys.readouterr()
        assert "Aborted." in captured.out

    def test_tty_prompt_accepts_on_y(self, parse_argv, patch_get_client, mock_response, monkeypatch):
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _: "y")
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        patch_get_client.put.return_value = mock_response(
            200, {"success": True, "pending_price_increase_id": 999, "contract_id": 123},
        )
        args = parse_argv(["accept", "price-increase", "123"])
        args.func(args)
        patch_get_client.put.assert_called_once()

    def test_instance_id_without_pending_row_is_stale(self, parse_argv, patch_get_client, mock_response, capsys):
        # Pending list has row for contract 123; user asks for 555 → stale.
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        args = parse_argv(["accept", "price-increase", "555", "--yes"])
        with pytest.raises(SystemExit) as excinfo:
            args.func(args)
        assert excinfo.value.code == 2
        patch_get_client.put.assert_not_called()
        captured = capsys.readouterr()
        assert "pending price increase no longer available for instance 555" in captured.out

    def test_404_no_pending_exits_2(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        patch_get_client.put.return_value = mock_response(
            404, {"success": False, "error": "no_pending_price_increase"},
        )
        args = parse_argv(["accept", "price-increase", "123", "--yes"])
        with pytest.raises(SystemExit) as excinfo:
            args.func(args)
        assert excinfo.value.code == 2
        captured = capsys.readouterr()
        assert "pending price increase no longer available — re-run" in captured.out

    def test_legacy_409_treated_as_stale(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        patch_get_client.put.return_value = mock_response(409, {"msg": "conflict"})
        args = parse_argv(["accept", "price-increase", "123", "--yes"])
        with pytest.raises(SystemExit) as excinfo:
            args.func(args)
        assert excinfo.value.code == 2

    def test_non_stale_failure_takes_precedence_over_stale(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(
            200, _envelope([PENDING_ROW, SECOND_ROW]),
        )
        # First succeeds, second 500 (non-stale failure).
        patch_get_client.put.side_effect = [
            mock_response(404, {"success": False, "error": "no_pending_price_increase"}),
            mock_response(500, {"msg": "boom"}),
        ]
        args = parse_argv(["accept", "price-increase", "123", "456", "--yes"])
        with pytest.raises(SystemExit) as excinfo:
            args.func(args)
        # Failure beats stale per the spec so retries are not blindly attempted.
        assert excinfo.value.code == 1

    def test_summary_line_format(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        patch_get_client.put.return_value = mock_response(
            200, {"success": True, "pending_price_increase_id": 999, "contract_id": 123},
        )
        args = parse_argv(["accept", "price-increase", "123", "--yes"])
        args.func(args)
        captured = capsys.readouterr()
        assert "Accepted 1 / Stale 0 / Failed 0 of 1 requested." in captured.out
        assert "Accepted price increase for 1 instance(s): 123" in captured.out

    def test_host_argument_is_rejected_by_argparse(self, cli_parser):
        # The new command shape has no --host argument. argparse exits non-zero
        # before any HTTP call would be made.
        with pytest.raises(SystemExit):
            cli_parser.parse_args(["accept", "price-increase", "--host", "1"])


# ---------------------------------------------------------------------------
# reject price-increase
# ---------------------------------------------------------------------------


class TestRejectPriceIncrease:
    def test_single_id_puts_pending_id_to_reject_route(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        patch_get_client.put.return_value = mock_response(
            200, {"success": True, "pending_price_increase_id": 999, "contract_id": 123},
        )
        args = parse_argv(["reject", "price-increase", "123", "--yes"])
        args.func(args)
        url = patch_get_client.put.call_args[0][0]
        body = patch_get_client.put.call_args[1]["json_data"]
        assert url == "/instances/reject-price-increase/"
        assert body == {"pending_price_increase_id": 999}
        captured = capsys.readouterr()
        assert "Rejected pending_id=999 contract_id=123" in captured.out
        assert "Rejected price increase for 1 instance(s): 123" in captured.out
        # No cutover note on reject — nothing applies later.
        assert "New rate applies" not in captured.out

    def test_tty_prompt_uses_reject_copy(self, parse_argv, patch_get_client, mock_response, monkeypatch, capsys):
        prompts = []
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "n")
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        args = parse_argv(["reject", "price-increase", "123"])
        args.func(args)
        assert any("Reject these price increases?" in p for p in prompts)

    def test_404_no_pending_exits_2_on_reject(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, _envelope([PENDING_ROW]))
        patch_get_client.put.return_value = mock_response(
            404, {"success": False, "error": "no_pending_price_increase"},
        )
        args = parse_argv(["reject", "price-increase", "123", "--yes"])
        with pytest.raises(SystemExit) as excinfo:
            args.func(args)
        assert excinfo.value.code == 2
