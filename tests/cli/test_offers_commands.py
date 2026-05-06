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

    def test_search_offers_display(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {
            "offers": [{"id": 1, "gpu_name": "RTX_3090", "dph_total": 0.5, "num_gpus": 1}]
        })
        args = parse_argv(["search", "offers", "--no-default"])
        args.func(args)
        captured = capsys.readouterr()
        assert "ID" in captured.out

    def test_search_offers_rentable_any_preserved(self, parse_argv, patch_get_client, mock_response):
        """Regression for #391: `rentable=any` must not be silently stripped.

        Without the fix the field disappears from the body (parse_query
        deletes `=any` keys), and the API server re-applies its implicit
        `rentable=true` default — so `rented=true rentable=any` returns 0.
        The CLI must instead send `{"rentable": {"eq": "any"}}` to override
        the server-side default.
        """
        patch_get_client.post.return_value = mock_response(200, {"offers": []})
        args = parse_argv(["search", "offers", "--raw", "rented=true rentable=any"])
        args.func(args)
        patch_get_client.post.assert_called_once()
        json_data = patch_get_client.post.call_args[1]["json_data"]
        assert json_data["rentable"] == {"eq": "any"}, (
            f"rentable should be present as {{'eq': 'any'}} but body was: {json_data}"
        )
        assert json_data["rented"] == {"eq": True}

    def test_search_offers_seeded_defaults_preserved_when_unmentioned(self, parse_argv, patch_get_client, mock_response):
        """Defaults the user does NOT touch must remain at their seeded values."""
        patch_get_client.post.return_value = mock_response(200, {"offers": []})
        args = parse_argv(["search", "offers", "--raw", "num_gpus=1"])
        args.func(args)
        json_data = patch_get_client.post.call_args[1]["json_data"]
        assert json_data["verified"] == {"eq": True}
        assert json_data["external"] == {"eq": False}
        assert json_data["rentable"] == {"eq": True}
        assert json_data["rented"] == {"eq": False}


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
        patch_get_client.get.return_value = mock_response(200, [
            {"id": 1, "score": 95.5, "gpu_name": "RTX_3090"}
        ])
        args = parse_argv(["search", "benchmarks"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/benchmarks" in call_args[0][0]


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
