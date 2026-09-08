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


class TestEveryParameterLands:
    """Exhaustive map: every create_instance parameter must change the payload.

    The probe test proves a documented parameter binds. This proves each one is
    actually wired to something, so a parameter cannot be quietly accepted and
    then ignored -- which is the failure mode that is invisible from the outside.
    """

    # param -> (value, payload key, expected value in the payload)
    EFFECTS = {
        "image": ("img", "image", "img"),
        "disk": (32, "disk", 32),
        "env": ({"A": "B"}, "env", {"A": "B"}),
        "price": (0.2, "price", 0.2),
        "bid_price": (0.25, "price", 0.25),
        "label": ("l", "label", "l"),
        "extra": ("x", "extra", "x"),
        "onstart_cmd": ("echo", "onstart", "echo"),
        "login": ("u p", "image_login", "u p"),
        "python_utf8": (True, "python_utf8", True),
        "lang_utf8": (True, "lang_utf8", True),
        "jupyter_lab": (True, "use_jupyter_lab", True),
        "jupyter_dir": ("/", "jupyter_dir", "/"),
        "force": (True, "force", True),
        "cancel_unavail": (True, "cancel_unavail", True),
        "template_hash": ("h", "template_hash_id", "h"),
        "user": ("root", "user", "root"),
        "runtype": ("ssh_proxy", "runtype", "ssh_proxy"),
        "args": (["a"], "args", ["a"]),
        "volume_info": ({"mount_path": "/v"}, "volume_info", {"mount_path": "/v"}),
        "ssh": (True, "runtype", "ssh_proxy"),
        "jupyter": (True, "runtype", "jupyter_proxy ssh_proxy"),
    }

    # These only make sense together, so they are checked as a group below.
    VOLUME_GROUP = {"create_volume", "link_volume", "volume_size", "mount_path",
                    "volume_label", "direct"}

    def test_the_effects_table_covers_every_parameter(self):
        """Guard the guard: a new parameter must be added here or to the group."""
        import inspect

        from vastai.sdk import VastAI

        params = {p for p in inspect.signature(VastAI.create_instance).parameters
                  if p != "self"} - {"id"}
        covered = set(self.EFFECTS) | self.VOLUME_GROUP
        assert params == covered, f"unmapped parameters: {params - covered}"

    @pytest.mark.parametrize("param", sorted(EFFECTS))
    def test_parameter_lands_in_the_payload(self, param):
        value, key, expected = self.EFFECTS[param]
        payload = build_create_instance_payload(**{param: value})
        assert payload.get(key) == expected

    def test_volume_group_lands(self):
        payload = build_create_instance_payload(
            create_volume=7, mount_path="/root/vol", volume_size=20,
            volume_label="name-it",
        )
        assert payload["volume_info"] == {
            "mount_path": "/root/vol", "create_new": True, "volume_id": 7,
            "name": "name-it", "size": 20,
        }

    def test_link_volume_lands(self):
        payload = build_create_instance_payload(link_volume=9, mount_path="/root/vol")
        assert payload["volume_info"]["volume_id"] == 9
        assert payload["volume_info"]["create_new"] is False

    def test_direct_lands(self):
        assert build_create_instance_payload(ssh=True, direct=True)["runtype"] == \
            "ssh_direc ssh_proxy"


class TestVolumeSizeIsNotSilentlyDropped:
    def test_zero_size_without_create_volume_still_raises(self):
        """0 is falsy but still a value the caller passed, so it must not vanish."""
        with pytest.raises(ValueError, match="volume_size"):
            build_volume_info(volume_size=0)
