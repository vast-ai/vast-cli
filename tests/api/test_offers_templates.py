"""Tests for vastai/api/offers.py — template create/update and the
fetch-tags/validate-auth/resolve-id helpers backing CLI-side validation."""

import pytest

from vastai.api import offers as offers_api


class TestSplitImageTag:
    @pytest.mark.parametrize("image,expected", [
        ("pytorch/pytorch", ("pytorch/pytorch", None)),
        ("pytorch/pytorch:2.4.0-cuda12.4", ("pytorch/pytorch", "2.4.0-cuda12.4")),
        ("myregistry.com:5000/image", ("myregistry.com:5000/image", None)),
        ("myregistry.com:5000/image:tag", ("myregistry.com:5000/image", "tag")),
        (None, (None, None)),
    ])
    def test_split_image_tag(self, image, expected):
        assert offers_api.split_image_tag(image) == expected


class TestFetchTemplateTags:
    def test_returns_tags_on_success(self, mock_client, mock_response):
        mock_client.post.return_value = mock_response(200, {"success": True, "tags": ["latest", "1.0"]})
        tags, err = offers_api.fetch_template_tags(mock_client, "pytorch/pytorch")
        assert tags == ["latest", "1.0"]
        assert err is None

    def test_reports_error_on_400(self, mock_client, mock_response):
        mock_client.post.return_value = mock_response(
            400, {"success": False, "error": "invalid_args", "msg": "Invalid image name"}
        )
        tags, err = offers_api.fetch_template_tags(mock_client, "bad image")
        assert tags is None
        assert "Invalid image name" in err

    def test_empty_result_is_not_an_error(self, mock_client, mock_response):
        mock_client.post.return_value = mock_response(200, {"success": False, "tags": [], "error": "No tags found"})
        tags, err = offers_api.fetch_template_tags(mock_client, "some/image")
        assert tags == []
        assert err == "No tags found"


class TestValidateTemplateAuth:
    def test_returns_ok_on_success(self, mock_client, mock_response):
        mock_client.post.return_value = mock_response(
            200, {"success": True, "authenticated": True, "repositories": ["acme/api"]}
        )
        ok, err = offers_api.validate_template_auth(mock_client, "docker.io", "bob", "token")
        assert ok is True
        assert err is None

    def test_reports_error_on_auth_failure(self, mock_client, mock_response):
        mock_client.post.return_value = mock_response(
            400, {"success": False, "error": "auth_failed", "msg": "bad creds"}
        )
        ok, err = offers_api.validate_template_auth(mock_client, "docker.io", "bob", "wrong")
        assert ok is False
        assert "bad creds" in err


class TestResolveTemplateId:
    def test_returns_id_when_found(self, mock_client, mock_response):
        mock_client.get.return_value = mock_response(200, {"templates": [{"id": 42, "hash_id": "abc"}]})
        template_id, err = offers_api.resolve_template_id(mock_client, "abc")
        assert template_id == 42
        assert err is None

    def test_reports_error_when_not_found(self, mock_client, mock_response):
        mock_client.get.return_value = mock_response(200, {"templates": []})
        template_id, err = offers_api.resolve_template_id(mock_client, "missing")
        assert template_id is None
        assert "missing" in err


class TestUpdateTemplateV1:
    """update_template moved off the deprecated, buggy /api/v0/template/ PUT
    onto /api/v1/template/, which identifies templates by numeric id."""

    def test_puts_to_v1_with_resolved_id(self, mock_client, mock_response):
        mock_client.get.return_value = mock_response(200, {"templates": [{"id": 42, "hash_id": "abc"}]})
        mock_client.put.return_value = mock_response(200, {"success": True, "template": {"id": 42}})

        result = offers_api.update_template(mock_client, hash_id="abc", name="new-name")

        mock_client.put.assert_called_once()
        call_args = mock_client.put.call_args
        assert call_args[0][0] == "/api/v1/template/"
        assert call_args[1]["json_data"]["id"] == 42
        assert result["success"] is True

    def test_skips_write_when_hash_id_not_found(self, mock_client, mock_response):
        mock_client.get.return_value = mock_response(200, {"templates": []})

        result = offers_api.update_template(mock_client, hash_id="missing")

        mock_client.put.assert_not_called()
        assert result["success"] is False

    def test_skips_id_lookup_under_curl(self, mock_client, mock_response):
        mock_client.curl = True
        mock_client.put.return_value = mock_response(200, {"success": True, "template": {}})

        offers_api.update_template(mock_client, hash_id="abc")

        mock_client.get.assert_not_called()
        mock_client.put.assert_called_once()
