"""The shared create-instance payload builder.

The CLI used to own the friendly-option translation, so the SDK published
parameters it could not take. These cover the library functions both layers now
go through, and the CLI/SDK differences that have to survive the move.
"""

import pytest

from vastai.api.instances import (
    apply_portal_config,
    build_create_instance_payload,
    build_volume_info,
    resolve_runtype,
)


class TestResolveRuntype:
    """Mirrors the CLI's old get_runtype, minus the argparse and the int-1 sentinel."""

    @pytest.mark.parametrize("flags,expected", [
        ({"jupyter": True}, "jupyter_proxy ssh_proxy"),
        ({"jupyter": True, "direct": True}, "jupyter_direc ssh_direc ssh_proxy"),
        ({"ssh": True}, "ssh_proxy"),
        ({"ssh": True, "direct": True}, "ssh_direc ssh_proxy"),
        ({"jupyter_lab": True}, "jupyter_proxy ssh_proxy"),
        ({"jupyter_dir": "/"}, "jupyter_proxy ssh_proxy"),
    ])
    def test_flags_produce_the_cli_runtype_strings(self, flags, expected):
        assert resolve_runtype(**flags)[0] == expected

    def test_unspecified_is_absent_for_the_sdk(self):
        """Tri-state: no flags and no default means no runtype key at all."""
        assert resolve_runtype()[0] is None

    def test_unspecified_is_ssh_for_the_cli(self):
        assert resolve_runtype(default="ssh")[0] == "ssh"

    def test_args_selects_the_args_runtype(self):
        assert resolve_runtype(args=["sleep", "1"])[0] == "args"

    def test_empty_args_selects_args_and_drops_the_value(self):
        assert resolve_runtype(args=[""]) == ("args", None)

    def test_jupyter_with_args_is_rejected(self):
        with pytest.raises(ValueError, match="jupyter and args"):
            resolve_runtype(jupyter=True, args=["sleep", "1"])

    def test_explicit_runtype_wins_and_flags_are_rejected(self):
        assert resolve_runtype("ssh_proxy")[0] == "ssh_proxy"
        with pytest.raises(ValueError, match="not both"):
            resolve_runtype("ssh_proxy", jupyter=True)

    def test_explicit_runtype_still_takes_jupyter_lab(self):
        """The documented workaround pairs a runtype string with jupyter_lab."""
        assert resolve_runtype("jupyter_proxy ssh_proxy", jupyter_lab=True)[0] == \
            "jupyter_proxy ssh_proxy"

    def test_bare_direct_is_rejected_for_the_sdk(self):
        with pytest.raises(ValueError, match="requires ssh"):
            resolve_runtype(direct=True)

    def test_bare_direct_keeps_the_cli_default(self):
        assert resolve_runtype(direct=True, default="ssh")[0] == "ssh"


class TestBuildVolumeInfo:
    def test_no_volume_requested(self):
        assert build_volume_info() is None

    def test_create_defaults_to_fifteen_gb(self):
        info = build_volume_info(create_volume=7, mount_path="/root/vol")
        assert info == {"mount_path": "/root/vol", "create_new": True,
                        "volume_id": 7, "size": 15}

    def test_link_carries_no_default_size(self):
        info = build_volume_info(link_volume=7, mount_path="/root/vol")
        assert info == {"mount_path": "/root/vol", "create_new": False, "volume_id": 7}

    def test_size_without_create_is_rejected(self):
        with pytest.raises(ValueError, match="volume_size"):
            build_volume_info(link_volume=7, mount_path="/x", volume_size=20)

    def test_mount_path_is_required(self):
        with pytest.raises(ValueError, match="mount_path is required"):
            build_volume_info(create_volume=7)

    def test_invalid_mount_path_is_rejected(self):
        with pytest.raises(ValueError, match="not a valid Linux file path"):
            build_volume_info(create_volume=7, mount_path="//")


class TestApplyPortalConfig:
    def test_jupyter_runtype_is_left_alone(self):
        env = {"PORTAL_CONFIG": "localhost:8080:18080:/:Jupyter"}
        assert apply_portal_config(env, "jupyter_proxy ssh_proxy") is env

    def test_jupyter_entries_are_stripped_on_other_runtypes(self):
        env = {"PORTAL_CONFIG": "localhost:8080:18080:/:Jupyter|localhost:1:2:/:App"}
        assert apply_portal_config(env, "ssh_proxy") == {
            "PORTAL_CONFIG": "localhost:1:2:/:App"
        }

    def test_does_not_mutate_the_callers_env(self):
        env = {"PORTAL_CONFIG": "localhost:8080:18080:/:Jupyter|localhost:1:2:/:App"}
        apply_portal_config(env, "ssh_proxy")
        assert env["PORTAL_CONFIG"].count("|") == 1

    def test_all_jupyter_entries_is_an_error(self):
        with pytest.raises(ValueError, match="at least one non-jupyter"):
            apply_portal_config({"PORTAL_CONFIG": "localhost:8080:18080:/:Jupyter"},
                                "ssh_proxy")


class TestBuildCreateInstancePayload:
    def test_bid_price_is_the_price_field(self):
        assert build_create_instance_payload(bid_price=0.25)["price"] == 0.25

    def test_price_and_bid_price_together_are_rejected(self):
        with pytest.raises(ValueError, match="not both"):
            build_create_instance_payload(price=0.2, bid_price=0.25)

    def test_env_string_is_parsed(self):
        payload = build_create_instance_payload(env="-e FOO=bar -p 8080:8080")
        assert payload["env"] == {"FOO": "bar", "-p 8080:8080": "1"}

    def test_template_hash_suppresses_runtype_resolution(self):
        payload = build_create_instance_payload(template_hash="abc", jupyter=True)
        assert "runtype" not in payload

    def test_volume_flags_build_volume_info(self):
        payload = build_create_instance_payload(create_volume=7, mount_path="/root/vol")
        assert payload["volume_info"]["volume_id"] == 7

    def test_volume_info_and_flags_together_are_rejected(self):
        with pytest.raises(ValueError, match="not both"):
            build_create_instance_payload(volume_info={"mount_path": "/x"},
                                          link_volume=7)

    def test_portal_config_is_filtered_against_the_resolved_runtype(self):
        payload = build_create_instance_payload(
            ssh=True,
            env={"PORTAL_CONFIG": "localhost:8080:18080:/:Jupyter|localhost:1:2:/:App"},
        )
        assert payload["env"]["PORTAL_CONFIG"] == "localhost:1:2:/:App"


class TestBillingDateParsing:
    """A malformed date used to fall back to yesterday and return wrong data."""

    def test_bad_date_raises_naming_the_argument(self):
        from vastai.api.billing import parse_date_arg

        with pytest.raises(ValueError, match="end_date: could not parse"):
            parse_date_arg("not-a-date", "end_date")

    def test_valid_date_parses(self):
        from vastai.api.billing import parse_date_arg

        assert parse_date_arg("2026-08-24", "start_date").year == 2026
