"""Integration tests for offers/search CLI commands with mocked HTTP."""

import pytest


class TestSearchOffers:
    def test_search_offers_no_default_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.post.return_value = mock_response(200, {
            "offers": [{"id": 1, "gpu_name": "RTX_3090", "dph_total": 0.5}]
        })
        args = parse_argv(["search", "offers", "--no-default", "--raw"])
        result = args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/bundles/" in call_args[0][0]
        assert isinstance(result, list)

    def test_search_offers_with_query(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.post.return_value = mock_response(200, {
            "offers": [{"id": 1, "gpu_name": "RTX_4090", "num_gpus": 1}]
        })
        args = parse_argv(["search", "offers", "--no-default", "--raw", "num_gpus=1"])
        result = args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert "num_gpus" in json_data

    def test_search_offers_cpu_arch_any_sends_every_arch(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.post.return_value = mock_response(200, {"offers": []})
        args = parse_argv(["search", "offers", "--raw", "gpu_name=GB200 cpu_arch=any"])
        args.func(args)
        json_data = patch_get_client.post.call_args[1]["json_data"]
        assert json_data["cpu_arch"] == {"in": ["amd64", "arm64"]}

    def test_search_offers_empty_hints_at_hidden_arm(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {"offers": []})
        args = parse_argv(["search", "offers", "--raw", "gpu_name=GB200"])
        assert args.func(args) == []
        captured = capsys.readouterr()
        assert "cpu_arch=any" in captured.err
        assert captured.out == ""

    def test_search_offers_empty_no_hint_when_arch_named(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {"offers": []})
        args = parse_argv(["search", "offers", "--raw", "gpu_name=GB200 cpu_arch=arm64"])
        args.func(args)
        assert "cpu_arch" not in capsys.readouterr().err

    def test_search_offers_display(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {
            "offers": [{"id": 1, "gpu_name": "RTX_3090", "dph_total": 0.5, "num_gpus": 1}]
        })
        args = parse_argv(["search", "offers", "--no-default"])
        args.func(args)
        captured = capsys.readouterr()
        assert "ID" in captured.out


class TestSearchTemplates:
    def test_search_templates(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, [
            {"id": 1, "name": "PyTorch", "image": "pytorch/pytorch"}
        ])
        args = parse_argv(["search", "templates"])
        args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/template/" in call_args[0][0]


class TestSearchBenchmarks:
    def test_search_benchmarks(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "success": True, "benchmarks_found": 1, "next_token": None,
            "benchmarks": [{"id": 1, "score": 95.5, "gpu_name": "RTX_3090"}],
        })
        args = parse_argv(["search", "benchmarks"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/benchmarks" in call_args[0][0]

    def test_raw_returns_flat_list_when_fetching_every_page(
            self, parse_argv, patch_get_client, mock_response):
        """The shape scripts have always gotten from `search benchmarks --raw`."""
        patch_get_client.get.return_value = mock_response(200, {
            "success": True, "benchmarks_found": 1, "next_token": None,
            "benchmarks": [{"id": 1, "gpu_name": "RTX_3090"}],
        })
        args = parse_argv(["search", "benchmarks", "--raw"])
        result = args.func(args)
        assert result == [{"id": 1, "gpu_name": "RTX_3090"}]

    def test_raw_returns_envelope_in_single_page_mode(
            self, parse_argv, patch_get_client, mock_response):
        """--limit pages manually, so the caller needs next_token back."""
        patch_get_client.get.return_value = mock_response(200, {
            "success": True, "benchmarks_found": 1, "next_token": "TOK",
            "benchmarks": [{"id": 1, "gpu_name": "RTX_3090"}],
        })
        args = parse_argv(["search", "benchmarks", "--raw", "--limit", "1"])
        result = args.func(args)
        assert result["next_token"] == "TOK"
        assert result["benchmarks"] == [{"id": 1, "gpu_name": "RTX_3090"}]


class TestSearchInvoices:
    def test_search_invoices(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, [
            {"id": 1, "amount_cents": 500}
        ])
        args = parse_argv(["search", "invoices"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/invoices" in call_args[0][0]


class TestCreateTemplate:
    def test_create_template(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {
            "success": True, "template": {"id": 1, "hash_id": "abc123"}
        })
        args = parse_argv(["create", "template", "--name", "Test", "--image", "pytorch/pytorch", "--no-default"])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/template/" in call_args[0][0]
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "Test"
        assert json_data["image"] == "pytorch/pytorch"


class TestDeleteTemplate:
    def test_delete_template_by_hash_id(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"msg": "Deleted"})
        args = parse_argv(["delete", "template", "--hash-id", "abc123"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/template/" in call_args[0][0]
        assert call_args[1]["json_data"]["hash_id"] == "abc123"

    def test_delete_template_by_id(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"msg": "Deleted"})
        args = parse_argv(["delete", "template", "--template-id", "42"])
        args.func(args)
        patch_get_client.delete.assert_called_once()


class TestUpdateTemplate:
    def test_update_template_resolves_id_then_puts_v1(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "success": True, "templates": [{"id": 42, "hash_id": "abc123"}]
        })
        patch_get_client.put.return_value = mock_response(200, {
            "success": True, "template": {"id": 43, "hash_id": "def456"}
        })
        args = parse_argv(["update", "template", "abc123", "--name", "Renamed", "--no-default"])
        assert args.func(args) is None
        get_args = patch_get_client.get.call_args
        assert get_args[0][0] == "/template/"
        assert get_args[1]["query_args"]["select_filters"] == {"hash_id": {"eq": "abc123"}}
        put_args = patch_get_client.put.call_args
        assert put_args[0][0] == "/api/v1/template/"
        assert put_args[1]["json_data"]["id"] == 42
        assert put_args[1]["json_data"]["hash_id"] == "abc123"
        assert put_args[1]["json_data"]["name"] == "Renamed"
        assert "updated template" in capsys.readouterr().out

    def test_update_template_prefers_the_callers_own_row_when_hashes_collide(self, parse_argv, patch_get_client, mock_response):
        """The hash is content-based, so a popular public template by someone else can share it."""
        responses = {
            "/template/": mock_response(200, {"success": True, "templates": [
                {"id": 41, "hash_id": "abc123", "creator_id": 999},
                {"id": 42, "hash_id": "abc123", "creator_id": 7},
            ]}),
            "/users/current": mock_response(200, {"id": 7}),
        }
        patch_get_client.get.side_effect = lambda path, **kwargs: responses[path]
        patch_get_client.put.return_value = mock_response(200, {"success": True, "template": {"id": 43}})
        args = parse_argv(["update", "template", "abc123", "--no-default"])
        assert args.func(args) is None
        assert patch_get_client.put.call_args.kwargs["json_data"]["id"] == 42

    def test_update_template_single_match_skips_the_user_lookup(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "success": True, "templates": [{"id": 42, "hash_id": "abc123", "creator_id": 999}]
        })
        patch_get_client.put.return_value = mock_response(200, {"success": True, "template": {"id": 43}})
        args = parse_argv(["update", "template", "abc123", "--no-default"])
        assert args.func(args) is None
        assert [call.args[0] for call in patch_get_client.get.call_args_list] == ["/template/"]
        assert patch_get_client.put.call_args.kwargs["json_data"]["id"] == 42

    def test_update_template_unknown_hash_does_not_put(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"success": False, "msg": "No templates found"})
        args = parse_argv(["update", "template", "nope", "--no-default"])
        assert args.func(args) == 1
        patch_get_client.put.assert_not_called()
        assert capsys.readouterr().out.strip() == "No template found with hash_id nope"

    def test_update_template_failed_response_prints_msg_and_fails(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "success": True, "templates": [{"id": 42, "hash_id": "abc123"}]
        })
        patch_get_client.put.return_value = mock_response(200, {"success": False, "msg": "Template name is required"})
        args = parse_argv(["update", "template", "abc123", "--no-default"])
        assert args.func(args) == 1
        assert capsys.readouterr().out.strip() == "Template name is required"

    def test_update_template_http_error_prints_api_msg_and_fails(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {
            "success": True, "templates": [{"id": 42, "hash_id": "abc123"}]
        })
        patch_get_client.put.return_value = mock_response(400, {
            "success": False, "error": "invalid_args", "msg": "Template ID is required for update"
        })
        args = parse_argv(["update", "template", "abc123", "--no-default"])
        assert args.func(args) == 1
        assert capsys.readouterr().out.strip() == "Template ID is required for update"
