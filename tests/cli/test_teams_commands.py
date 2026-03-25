"""Integration tests for team CLI commands with mocked HTTP."""

import pytest


class TestCreateTeam:
    def test_create_team(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.post.return_value = mock_response(200, {"success": True, "team_id": 1})
        args = parse_argv(["create", "team", "--team_name", "my-team"])
        args.func(args)
        patch_get_client.post.assert_called_once()
        call_args = patch_get_client.post.call_args
        assert "/team/" in call_args[0][0]
        assert call_args[1]["json_data"]["team_name"] == "my-team"


class TestDestroyTeam:
    def test_destroy_team(self, parse_argv, patch_get_client, mock_response, capsys):
        patch_get_client.delete.return_value = mock_response(200, {"success": True})
        args = parse_argv(["destroy", "team"])
        args.func(args)
        patch_get_client.delete.assert_called_once()
        call_args = patch_get_client.delete.call_args
        assert "/team/" in call_args[0][0]


class TestShowMembers:
    def test_show_members_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, {
            "members": [{"id": 1, "email": "user@test.com", "role": "admin"}]
        })
        args = parse_argv(["show", "members", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/team/members/" in call_args[0][0]


class TestShowTeamRoles:
    def test_show_team_roles_raw(self, parse_argv, patch_get_client, mock_response):
        patch_get_client.get.return_value = mock_response(200, [
            {"name": "admin", "permissions": {"all": True}}
        ])
        args = parse_argv(["show", "team-roles", "--raw"])
        result = args.func(args)
        patch_get_client.get.assert_called_once()
        call_args = patch_get_client.get.call_args
        assert "/team/roles-full/" in call_args[0][0]
