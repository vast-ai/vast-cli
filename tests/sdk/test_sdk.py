"""Tests for VastAI SDK class — covers methods with real logic beyond simple delegation."""

import pytest
from unittest.mock import patch, MagicMock, mock_open

from vastai.sdk import VastAI, APIKEY_FILE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sdk():
    """VastAI instance with a mock client."""
    with patch("vastai.sdk.VastClient"):
        v = VastAI(api_key="test-key")
        v.client = MagicMock()
        yield v


# ---------------------------------------------------------------------------
# __init__ — API key resolution
# ---------------------------------------------------------------------------


class TestInit:
    def test_explicit_key(self):
        with patch("vastai.sdk.VastClient") as MockClient:
            VastAI(api_key="explicit-key")
            assert MockClient.call_args[0][0] == "explicit-key"

    def test_reads_key_from_file(self, tmp_path):
        key_file = tmp_path / ".vast_api_key"
        key_file.write_text("  file-key  \n")
        with patch("vastai.sdk.APIKEY_FILE", str(key_file)), \
             patch("vastai.sdk.VastClient") as MockClient:
            VastAI()
            assert MockClient.call_args[0][0] == "file-key"

    def test_no_key_no_file(self):
        with patch("vastai.sdk.os.path.exists", return_value=False), \
             patch("vastai.sdk.VastClient") as MockClient:
            VastAI()
            assert MockClient.call_args[0][0] is None

    def test_options_passed_through(self):
        with patch("vastai.sdk.VastClient") as MockClient:
            v = VastAI(api_key="k", server_url="http://test", retry=5, explain=True, curl=True, raw=True, quiet=True)
            MockClient.assert_called_once_with("k", "http://test", 5, True, True)
            assert v.raw is True
            assert v.quiet is True


# ---------------------------------------------------------------------------
# ssh_url / scp_url — URL building with fallback logic
# ---------------------------------------------------------------------------


class TestSshUrl:
    def test_direct_fields(self, sdk):
        with patch("vastai.api.instances.show_instance", return_value={"ssh_host": "1.2.3.4", "ssh_port": 2222}):
            assert sdk.ssh_url(1) == "ssh://root@1.2.3.4:2222"

    def test_falls_back_to_ports_dict(self, sdk):
        inst = {"public_ipaddr": "5.6.7.8", "ports": {"22/tcp": [{"HostPort": "9999"}]}}
        with patch("vastai.api.instances.show_instance", return_value=inst):
            assert sdk.ssh_url(1) == "ssh://root@5.6.7.8:9999"

    def test_empty_when_missing(self, sdk):
        with patch("vastai.api.instances.show_instance", return_value={}):
            assert sdk.ssh_url(1) == ""

    def test_unwraps_list_response(self, sdk):
        with patch("vastai.api.instances.show_instance", return_value=[{"ssh_host": "1.2.3.4", "ssh_port": 22}]):
            assert sdk.ssh_url(1) == "ssh://root@1.2.3.4:22"

    def test_empty_list_response(self, sdk):
        with patch("vastai.api.instances.show_instance", return_value=[]):
            assert sdk.ssh_url(1) == ""


class TestScpUrl:
    def test_builds_scp_url(self, sdk):
        with patch("vastai.api.instances.show_instance", return_value={"ssh_host": "1.2.3.4", "ssh_port": 22}):
            assert sdk.scp_url(1) == "scp://root@1.2.3.4:22"

    def test_empty_when_missing(self, sdk):
        with patch("vastai.api.instances.show_instance", return_value={}):
            assert sdk.scp_url(1) == ""


# ---------------------------------------------------------------------------
# search_offers — query/order string parsing
# ---------------------------------------------------------------------------


class TestSearchOffers:
    def test_string_query_is_parsed(self, sdk):
        with patch("vastai.api.offers.search_offers", return_value=[]) as mock:
            sdk.search_offers("num_gpus=1")
            query = mock.call_args.kwargs["query"]
            assert isinstance(query, dict)
            assert "num_gpus" in query

    def test_dict_query_passed_through(self, sdk):
        q = {"num_gpus": {"eq": 1}}
        with patch("vastai.api.offers.search_offers", return_value=[]) as mock:
            sdk.search_offers(q)
            assert mock.call_args.kwargs["query"] is q

    def test_none_query(self, sdk):
        with patch("vastai.api.offers.search_offers", return_value=[]) as mock:
            sdk.search_offers()
            assert mock.call_args.kwargs["query"] is None

    def test_order_desc(self, sdk):
        with patch("vastai.api.offers.search_offers", return_value=[]) as mock:
            sdk.search_offers(order="score-")
            assert mock.call_args.kwargs["order"] == [["score", "desc"]]

    def test_order_asc(self, sdk):
        with patch("vastai.api.offers.search_offers", return_value=[]) as mock:
            sdk.search_offers(order="dph_total+")
            assert mock.call_args.kwargs["order"] == [["dph_total", "asc"]]

    def test_order_multi_field(self, sdk):
        with patch("vastai.api.offers.search_offers", return_value=[]) as mock:
            sdk.search_offers(order="score-,dph_total")
            order = mock.call_args.kwargs["order"]
            assert len(order) == 2
            assert order[0] == ["score", "desc"]
            assert order[1][1] == "asc"

    def test_order_list_passed_through(self, sdk):
        order = [["score", "desc"]]
        with patch("vastai.api.offers.search_offers", return_value=[]) as mock:
            sdk.search_offers(order=order)
            assert mock.call_args.kwargs["order"] is order

    def test_empty_order_segments_skipped(self, sdk):
        """Empty segments in order string (e.g. trailing comma) should be skipped."""
        with patch("vastai.api.offers.search_offers", return_value=[]) as mock:
            sdk.search_offers(order="score-,")
            order = mock.call_args.kwargs["order"]
            assert len(order) == 1


# ---------------------------------------------------------------------------
# show_env_vars — value masking
# ---------------------------------------------------------------------------


class TestShowEnvVars:
    def test_masks_values_by_default(self, sdk):
        with patch("vastai.api.auth.show_env_vars", return_value={"SECRET": "real_value", "OTHER": "also_secret"}):
            result = sdk.show_env_vars()
            assert result["SECRET"] == "****"
            assert result["OTHER"] == "****"

    def test_shows_values_when_requested(self, sdk):
        with patch("vastai.api.auth.show_env_vars", return_value={"SECRET": "real_value"}):
            result = sdk.show_env_vars(show_values=True)
            assert result["SECRET"] == "real_value"

    def test_handles_non_dict_response(self, sdk):
        """If API returns non-dict, pass through without masking."""
        with patch("vastai.api.auth.show_env_vars", return_value=[]):
            result = sdk.show_env_vars()
            assert result == []


# ---------------------------------------------------------------------------
# create_template — kwarg translation
# ---------------------------------------------------------------------------


class TestCreateTemplate:
    def test_jupyter_direct(self, sdk):
        with patch("vastai.api.offers.create_template", return_value={"success": True}) as mock:
            sdk.create_template(image="test", jupyter=True, direct=True)
            kw = mock.call_args.kwargs
            assert kw["jup_direct"] is True
            assert kw["runtype"] == "jupyter"
            assert kw["use_ssh"] is True

    def test_ssh_mode(self, sdk):
        with patch("vastai.api.offers.create_template", return_value={"success": True}) as mock:
            sdk.create_template(image="test", ssh=True)
            kw = mock.call_args.kwargs
            assert kw["ssh_direct"] is False
            assert kw["use_ssh"] is True
            assert kw["runtype"] == "ssh"

    def test_args_mode_default(self, sdk):
        with patch("vastai.api.offers.create_template", return_value={"success": True}) as mock:
            sdk.create_template(image="test")
            kw = mock.call_args.kwargs
            assert kw["runtype"] == "args"
            assert kw["use_ssh"] is False
            assert kw["jup_direct"] is False

    def test_login_extracts_repo(self, sdk):
        with patch("vastai.api.offers.create_template", return_value={"success": True}) as mock:
            sdk.create_template(image="test", login="docker.io/myrepo user pass")
            assert mock.call_args.kwargs["docker_login_repo"] == "docker.io/myrepo"

    def test_public_and_hide_readme(self, sdk):
        with patch("vastai.api.offers.create_template", return_value={"success": True}) as mock:
            sdk.create_template(image="test", public=True, hide_readme=True)
            kw = mock.call_args.kwargs
            assert kw["private"] is False
            assert kw["readme_visible"] is False

    def test_strips_non_api_kwargs(self, sdk):
        """search_params and no_default should be removed before calling API."""
        with patch("vastai.api.offers.create_template", return_value={"success": True}) as mock:
            sdk.create_template(image="test", search_params="x", no_default=True)
            kw = mock.call_args.kwargs
            assert "search_params" not in kw
            assert "no_default" not in kw


# ---------------------------------------------------------------------------
# copy — vast URL parsing
# ---------------------------------------------------------------------------


class TestCopy:
    def test_parses_urls(self, sdk):
        with patch("vastai.api.storage.copy", return_value={"success": True}) as mock:
            sdk.copy("12345:/data/input", "67890:/data/output")
            # parse_vast_url returns string IDs
            mock.assert_called_once_with(sdk.client, "12345", "67890", "/data/input", "/data/output")


# ---------------------------------------------------------------------------
# create_subaccount — type translation
# ---------------------------------------------------------------------------


class TestCreateSubaccount:
    def test_host_type(self, sdk):
        with patch("vastai.api.billing.create_subaccount", return_value={"success": True}) as mock:
            sdk.create_subaccount("a@b.com", "user", "pass", type="host")
            assert mock.call_args.kwargs["host_only"] is True

    def test_no_type(self, sdk):
        with patch("vastai.api.billing.create_subaccount", return_value={"success": True}) as mock:
            sdk.create_subaccount("a@b.com", "user", "pass")
            assert mock.call_args.kwargs["host_only"] is False

    def test_non_host_type(self, sdk):
        with patch("vastai.api.billing.create_subaccount", return_value={"success": True}) as mock:
            sdk.create_subaccount("a@b.com", "user", "pass", type="client")
            assert mock.call_args.kwargs["host_only"] is False


# ---------------------------------------------------------------------------
# list_machines — loops over IDs
# ---------------------------------------------------------------------------


class TestListMachines:
    def test_calls_per_id(self, sdk):
        with patch("vastai.api.machines.list_machine", return_value={"success": True}) as mock:
            result = sdk.list_machines([1, 2, 3], gpu_name="RTX_4090")
            assert mock.call_count == 3
            assert len(result) == 3
            # Verify each ID was called
            called_ids = [call.args[1] for call in mock.call_args_list]
            assert called_ids == [1, 2, 3]

    def test_empty_list(self, sdk):
        with patch("vastai.api.machines.list_machine") as mock:
            result = sdk.list_machines([])
            assert result == []
            mock.assert_not_called()


# ---------------------------------------------------------------------------
# set_api_key — direct mutation
# ---------------------------------------------------------------------------


class TestSetApiKey:
    def test_updates_client(self, sdk):
        sdk.set_api_key("new-key")
        assert sdk.client.api_key == "new-key"


# ---------------------------------------------------------------------------
# NotImplementedError methods
# ---------------------------------------------------------------------------


class TestNotImplemented:
    def test_generate_pdf_invoices(self, sdk):
        with pytest.raises(NotImplementedError):
            sdk.generate_pdf_invoices()

    def test_self_test_machine(self, sdk):
        with pytest.raises(NotImplementedError):
            sdk.self_test_machine(1)
