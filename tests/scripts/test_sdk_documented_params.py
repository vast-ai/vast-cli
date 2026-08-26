"""
Every parameter the SDK reference publishes must exist and must reach the wire.

A customer read ``jupyter`` off the generated SDK reference, called
``VastAI.create_instance(jupyter=True)`` and got a TypeError. The generator
fabricates the parameter table for any ``**kwargs`` method by scraping the
matching CLI command's argparse flags, so CLI-only concepts get published as
SDK parameters and nothing checks that the SDK can actually take them.

Two probes, because a parameter can fail in two ways:

* :func:`test_documented_params_bind` -- the loud failure. Bind each documented
  parameter against the real method with the transport stubbed and assert it is
  not rejected with ``unexpected keyword argument``.
* :func:`test_documented_param_reaches_payload` -- the quiet one. Accepting a
  parameter and then dropping it is not a fix, so the create-instance surface
  asserts the observable effect on the JSON body.

Everything is offline: the HTTP verbs on ``VastClient`` are stubbed and the GPU
name lookup that the CLI parser performs at import time is patched out.
"""

import importlib.util
import inspect
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Documented create_instance parameters and the payload effect each must have.
PAYLOAD_EFFECTS = [
    ("jupyter", True, "runtype", "jupyter_proxy ssh_proxy"),
    ("ssh", True, "runtype", "ssh_proxy"),
    ("bid_price", 0.25, "price", 0.25),
    ("label", "mine", "label", "mine"),
    ("disk", 32, "disk", 32),
    ("jupyter_lab", True, "use_jupyter_lab", True),
    ("jupyter_dir", "/", "jupyter_dir", "/"),
    ("onstart_cmd", "echo hi", "onstart", "echo hi"),
    ("login", "docker.io u p", "image_login", "docker.io u p"),
    ("user", "root", "user", "root"),
]


def _load_generator():
    path = SCRIPTS_DIR / "generate_cli_sdk_docs.py"
    spec = importlib.util.spec_from_file_location("generate_cli_sdk_docs", path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the module defines dataclasses, and @dataclass
    # resolves annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def documented_methods():
    """SDK methods as the docs generator publishes them, built without network."""
    from vastai.cli import util as cli_util

    with patch.object(cli_util, "_get_gpu_names", return_value=["RTX_4090"]), \
         patch.object(cli_util, "_get_gpu_types", return_value=[]):
        generator = _load_generator()
        cli_commands = generator.collect_cli_commands(generator.load_cli_parser())
        return generator.extract_sdk_methods(cli_commands)


class StubResponse:
    """Enough of a response for any api-layer call, including paged loops."""

    status_code = 200
    text = "{}"

    def json(self):
        return {}

    def raise_for_status(self):
        return None


@pytest.fixture
def sdk():
    from vastai.sdk import VastAI

    return VastAI(api_key="a" * 64)


@pytest.fixture
def stub_transport():
    """Stub every HTTP verb on the client; yields the list of sent payloads."""
    sent = []

    def record(self, url, json_data=None, **kwargs):
        sent.append(json_data)
        return StubResponse()

    with patch("vastai.api.client.VastClient.put", record), \
         patch("vastai.api.client.VastClient.post", record), \
         patch("vastai.api.client.VastClient.delete", record), \
         patch("vastai.api.client.VastClient.get", record):
        yield sent


def _demo_value(param):
    """A value of roughly the documented type, so binding is what fails."""
    label = param.type_label.replace("Optional[", "").rstrip("]")
    return {
        "bool": True,
        "int": 1,
        "float": 1.0,
        "list": [],
        "dict": {},
    }.get(label, "x")


def _bind_kwargs(method, param):
    kwargs = {p.name: _demo_value(p) for p in method.params if p.required}
    kwargs[param.name] = _demo_value(param)
    return kwargs


def _probe(sdk, method, param):
    """Return the rejection reason for one documented parameter, or None.

    A TypeError is a binding failure and always counts. Only two shapes of it
    are understood; any other shape is reported rather than waved through,
    because a positional-arity TypeError also means the call never bound and
    silently passing it would hide exactly what this test exists to find.
    Non-TypeError failures happen past the signature and are not policed here.
    """
    try:
        getattr(sdk, method.name)(**_bind_kwargs(method, param))
    except TypeError as exc:
        if "unexpected keyword argument" in str(exc):
            return f"{param.name}: rejected"
        if "multiple values for" in str(exc):
            return f"{param.name}: shadowed by the wrapper"
        if "required positional argument" in str(exc):
            # The parameter under test bound; the delegate is complaining about
            # a different argument this probe did not supply, because an open
            # signature gives it no way to know which ones are mandatory.
            return None
        return f"{param.name}: unclassifiable TypeError ({exc})"
    except Exception:
        pass
    return None


def test_probe_covers_the_whole_published_surface(documented_methods):
    """Guard the probe itself: an empty extraction would make it vacuous."""
    names = {m.name for m in documented_methods}
    assert len(names) > 100
    assert {"create_instance", "launch_instance", "update_template"} <= names


def test_documented_params_bind(documented_methods, sdk, stub_transport):
    """No published parameter may be rejected by the method it is published on."""
    failures = {}
    for method in documented_methods:
        if not hasattr(sdk, method.name):
            continue
        rejected = [r for r in (_probe(sdk, method, p) for p in method.params) if r]
        if rejected:
            failures[method.name] = rejected
    assert failures == {}


@pytest.mark.parametrize("kwarg,value,payload_key,expected", PAYLOAD_EFFECTS,
                         ids=[e[0] for e in PAYLOAD_EFFECTS])
def test_documented_param_reaches_payload(kwarg, value, payload_key, expected,
                                          sdk, stub_transport):
    """Accepting a parameter and dropping it is not a fix."""
    sdk.create_instance(id=1, image="img", **{kwarg: value})
    assert stub_transport, "no request was sent"
    assert stub_transport[-1].get(payload_key) == expected


def test_runtype_absent_when_unspecified(sdk, stub_transport):
    """Tri-state pin: the SDK must not adopt the CLI's 'ssh' default.

    Sending runtype='ssh' for a bare create would silently change the payload
    for every existing SDK caller.
    """
    sdk.create_instance(id=1, image="img")
    assert "runtype" not in stub_transport[-1]


def test_env_string_is_parsed_into_a_dict(sdk, stub_transport):
    """The wire wants a dict; the docs type the parameter off the CLI flag."""
    sdk.create_instance(id=1, image="img", env="-e FOO=bar -p 8080:8080")
    assert stub_transport[-1]["env"] == {"FOO": "bar", "-p 8080:8080": "1"}


def test_env_dict_is_passed_through(sdk, stub_transport):
    sdk.create_instance(id=1, image="img", env={"FOO": "bar"})
    assert stub_transport[-1]["env"] == {"FOO": "bar"}


def test_create_template_translates_search_params(sdk, stub_transport):
    """search_params must become extra_filters, not be silently discarded."""
    sdk.create_template(image="img", search_params="num_gpus=2")
    assert stub_transport[-1]["extra_filters"].get("num_gpus") == {"eq": "2"}


def test_signature_is_closed_for_create_instance():
    """Closed signatures are what make the generated docs correct by construction."""
    from vastai.sdk import VastAI

    for name in ("create_instance", "create_instances", "launch_instance",
                 "update_template"):
        sig = inspect.signature(getattr(VastAI, name))
        var_kw = [p for p in sig.parameters.values()
                  if p.kind == inspect.Parameter.VAR_KEYWORD]
        assert not var_kw, f"VastAI.{name} still has **kwargs; docs get fabricated"


def test_cloud_copy_flags_reach_the_payload(sdk, stub_transport):
    """The rclone flags are the same CLI-side translation as the runtype flags."""
    sdk.cloud_copy(src="/data", dst="/workspace", instance="1", connection="2",
                   dry_run=True, size_only=True)
    assert stub_transport[-1]["flags"] == ["--dry-run", "--size-only"]


def test_cloud_copy_no_longer_publishes_scheduling(documented_methods):
    """Scheduling posts to add_scheduled_job, so it must not be documented here."""
    method = next(m for m in documented_methods if m.name == "cloud_copy")
    published = {p.name for p in method.params}
    assert not published & {"schedule", "day", "hour", "start_date", "end_date"}


def test_converted_methods_are_not_open_signatures():
    """The docs verifier cannot judge extra params on a **kwargs method.

    These four were open signatures, which is why fabricated parameters stayed
    published unchallenged. Closing them is what puts them back under the
    checker; reopening one would silently exempt it again.
    """
    import importlib.util

    path = SCRIPTS_DIR / "verify_cli_sdk_docs.py"
    spec = importlib.util.spec_from_file_location("verify_cli_sdk_docs", path)
    verifier = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = verifier
    spec.loader.exec_module(verifier)

    _, open_signatures = verifier.get_sdk_methods()

    for name in ("create_instance", "create_instances", "launch_instance",
                 "update_template"):
        assert name not in open_signatures, f"{name} is open again; docs get fabricated"
