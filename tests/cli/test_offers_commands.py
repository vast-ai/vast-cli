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
        args = parse_argv([
            "create", "template", "--name", "Test", "--image", "pytorch/pytorch",
            "--no-default", "--no-verify",
        ])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/template/" in call_args[0][0]
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "Test"
        assert json_data["image"] == "pytorch/pytorch"

    def test_create_template_verifies_image_by_default(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.post.side_effect = [
            mock_response(200, {"success": True, "tags": ["latest"]}),
            mock_response(200, {"success": True, "template": {"id": 1}}),
        ]
        args = parse_argv(["create", "template", "--name", "Test", "--image", "pytorch/pytorch", "--no-default"])
        args.func(args)
        assert patch_get_client.post.call_count == 2
        first_url = patch_get_client.post.call_args_list[0][0][0]
        second_url = patch_get_client.post.call_args_list[1][0][0]
        assert "fetch-tags" in first_url
        assert "/template/" in second_url

    def test_create_template_aborts_on_bad_credentials(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.post.return_value = mock_response(
            400, {"success": False, "error": "auth_failed", "msg": "bad creds"}
        )
        args = parse_argv([
            "create", "template", "--name", "Test", "--image", "acme/private", "--no-default",
            "--docker_login_user", "bob", "--docker_login_pass", "wrong",
        ])
        args.func(args)
        patch_get_client.post.assert_called_once()  # only validate-auth, never the create call
        assert "validate-auth" in patch_get_client.post.call_args[0][0]


class TestUpdateTemplate:
    def test_update_template_puts_to_v1_with_resolved_id(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"templates": [{"id": 42, "hash_id": "abc123"}]})
        patch_get_client.put.return_value = mock_response(200, {
            "success": True, "template": {"id": 42}, "msg": "Template 42 Updated Successfully",
        })
        args = parse_argv([
            "update", "template", "abc123", "--name", "renamed", "--no-default", "--no-verify",
        ])
        args.func(args)
        patch_get_client.put.assert_called_once()
        call_args = patch_get_client.put.call_args
        assert call_args[0][0] == "/api/v1/template/"
        assert call_args[1]["json_data"]["id"] == 42

    def test_update_template_aborts_when_hash_id_not_found(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.get.return_value = mock_response(200, {"templates": []})
        args = parse_argv(["update", "template", "missing-hash", "--no-default", "--no-verify"])
        args.func(args)
        patch_get_client.put.assert_not_called()
        assert "missing-hash" in capsys.readouterr().out

    def test_update_template_aborts_on_bad_credentials(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {"templates": [{"id": 42, "hash_id": "abc123"}]})
        patch_get_client.post.return_value = mock_response(
            400, {"success": False, "error": "auth_failed", "msg": "bad creds"}
        )
        args = parse_argv([
            "update", "template", "abc123", "--image", "acme/private", "--no-default",
            "--docker_login_user", "bob", "--docker_login_pass", "wrong",
        ])
        args.func(args)
        patch_get_client.put.assert_not_called()


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
