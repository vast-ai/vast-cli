"""Call shapes that worked before HOST-3728 must keep working.

Closing the **kwargs signatures is what makes the docs honest, but a closed
signature also stops accepting anything it does not name. These pin the shapes
that a long-running script could plausibly be using today, including the raw
api-layer spellings that were the *only* working way to drive update_template
before the friendly flags existed.
"""

import inspect

import pytest

from vastai.api import instances as instances_api
from vastai.api import offers as offers_api
from vastai.sdk import VastAI


@pytest.fixture
def sdk():
    return VastAI(api_key="a" * 64)


class StubResponse:
    status_code = 200

    def json(self):
        return {"offers": [], "instances": [], "templates": []}

    def raise_for_status(self):
        return None


@pytest.fixture
def sent(monkeypatch):
    captured = []

    def record(self, url, json_data=None, query_args=None, **kwargs):
        # GET-based searches carry the query in query_args, not a JSON body.
        captured.append(json_data if json_data is not None else query_args)
        return StubResponse()

    for verb in ("put", "post", "get", "delete"):
        monkeypatch.setattr(f"vastai.api.client.VastClient.{verb}", record)
    return captured


class TestPositionalOrderIsStable:
    """New parameters were appended, never inserted."""

    def test_api_create_instance_positional_order(self):
        params = list(inspect.signature(instances_api.create_instance).parameters)
        assert params[:21] == [
            "client", "id", "image", "disk", "env", "price", "label", "extra",
            "onstart_cmd", "login", "python_utf8", "lang_utf8", "jupyter_lab",
            "jupyter_dir", "force", "cancel_unavail", "template_hash", "user",
            "runtype", "args", "volume_info",
        ]

    def test_api_launch_instance_positional_order(self):
        params = list(inspect.signature(offers_api.launch_instance).parameters)
        assert params[:22] == [
            "client", "gpu_name", "num_gpus", "image", "region", "disk", "order",
            "limit", "env", "label", "extra", "onstart_cmd", "login",
            "python_utf8", "lang_utf8", "jupyter_lab", "jupyter_dir",
            "cancel_unavail", "template_hash", "runtype", "args", "query",
        ]

    def test_sdk_create_instance_takes_id_image_disk_positionally(self, sdk, sent):
        sdk.create_instance(1, "img", 32)
        assert sent[-1]["image"] == "img"
        assert sent[-1]["disk"] == 32


class TestCreateInstanceKwargs:
    """Every keyword the old **kwargs forwarded still binds."""

    OLD_KWARGS = dict(
        image="img", disk=32, env={"A": "B"}, price=0.2, label="l", extra="e",
        onstart_cmd="echo", login="dockerhub u p", python_utf8=True,
        lang_utf8=True, jupyter_lab=True, jupyter_dir="/", force=True,
        cancel_unavail=True, user="root", runtype="ssh_proxy", args=["a"],
        volume_info={"mount_path": "/v"},
    )

    def test_all_old_kwargs_still_accepted(self, sdk, sent):
        sdk.create_instance(id=1, **self.OLD_KWARGS)
        payload = sent[-1]
        assert payload["runtype"] == "ssh_proxy"
        assert payload["price"] == 0.2
        assert payload["volume_info"] == {"mount_path": "/v"}

    def test_bare_create_sends_no_runtype(self, sdk, sent):
        """The compat pin: the SDK never adopted the CLI's 'ssh' default."""
        sdk.create_instance(id=1, image="img")
        assert "runtype" not in sent[-1]

    def test_explicit_runtype_is_untouched(self, sdk, sent):
        """The workaround shipped to the customer must keep working verbatim."""
        sdk.create_instance(
            id=1, image="img", disk=32,
            runtype="jupyter_direc ssh_direc ssh_proxy",
            jupyter_lab=True, jupyter_dir="/",
        )
        assert sent[-1]["runtype"] == "jupyter_direc ssh_direc ssh_proxy"


class TestTemplateRawFields:
    """update_template forwarded **kwargs, so raw api names are what works today."""

    RAW = dict(
        runtype="ssh", use_ssh=True, jup_direct=False, ssh_direct=True,
        use_jupyter_lab=True, docker_login_repo="docker.io/repo",
        extra_filters={"num_gpus": {"eq": "2"}}, readme_visible=False,
        private=False,
    )

    def test_update_template_raw_fields_still_bind(self, sdk, sent):
        sdk.update_template(hash_id="h", image="img", **self.RAW)
        payload = sent[-1]
        for key, value in self.RAW.items():
            assert payload[key] == value, key

    def test_create_template_extra_filters_still_binds(self, sdk, sent):
        sdk.create_template(image="img", extra_filters={"num_gpus": {"eq": "2"}})
        assert sent[-1]["extra_filters"] == {"num_gpus": {"eq": "2"}}

    def test_raw_fields_win_over_the_friendly_flags(self, sdk, sent):
        sdk.update_template(hash_id="h", jupyter=True, runtype="args")
        assert sent[-1]["runtype"] == "args"

    def test_no_search_params_sends_no_filters(self, sdk, sent):
        """A template created without search params used to carry no filters."""
        sdk.create_template(image="img")
        assert sent[-1]["extra_filters"] == {}


class TestSearchOffers:
    def test_disable_bundling_still_accepted(self, sdk, sent):
        sdk.search_offers(query="num_gpus=2", disable_bundling=True)
        assert sent

    def test_type_and_order_still_positional(self, sdk, sent):
        sdk.search_offers("num_gpus=2", "bid")
        assert sent


class TestSearchQueryStrings:
    """HOST-3684: the search wrappers advertise CLI-style strings.

    They used to forward the string straight into a layer contracted on dicts,
    so it landed on the wire as a filter value and the search silently ignored
    it. A VIP client hit this on search_templates.
    """

    def test_search_templates_parses_the_string(self, sdk, sent):
        sdk.search_templates("name=pytorch")
        assert sent[-1]["select_filters"] == {"name": {"eq": "pytorch"}}

    def test_search_invoices_parses_the_string(self, sdk, sent):
        sdk.search_invoices("when>1700000000")
        assert sent[-1]["select_filters"] == {"when": {"gt": 1700000000.0}}

    def test_search_volumes_parses_the_string(self, sdk, sent):
        sdk.search_volumes("disk_space>=100")
        assert sent[-1]["disk_space"] == {"gte": "100"}

    def test_search_network_volumes_parses_the_string(self, sdk, sent):
        sdk.search_network_volumes("disk_space>=100")
        assert sent[-1]["disk_space"] == {"gte": "100"}

    def test_order_string_becomes_pairs(self, sdk, sent):
        sdk.search_volumes("disk_space>=100", order="dph-")
        assert sent[-1]["order"] == [["dph_total", "desc"]]

    @pytest.mark.parametrize("method", [
        "search_templates", "search_invoices", "search_volumes",
        "search_network_volumes",
    ])
    def test_a_dict_still_passes_through_untouched(self, method, sdk, sent):
        """Callers already passing dicts are the ones who worked; keep them."""
        getattr(sdk, method)({"disk_space": {"gte": 7}})
        payload = sent[-1]
        filters = payload.get("select_filters", payload)
        assert filters["disk_space"] == {"gte": 7}
