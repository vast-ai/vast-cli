"""Tests for which objects ``vastai.serverless.remote.serialization.deserialize`` will rebuild."""

import subprocess
import sys
from dataclasses import dataclass

import pytest

from vastai.serverless.remote.serialization import deserialize, serialize

ROOT = __name__


@dataclass
class Point:
    x: int
    y: int


class DeploymentError(Exception):
    pass


def _obj(path, cls, contents=None, kind="absolute"):
    return {
        "type": "obj",
        "module": {"type": kind, "path": path},
        "class": cls,
        "contents": contents or {},
    }


def test_round_trips_deployment_class() -> None:
    p = deserialize(serialize(Point(1, [2, 3]), ROOT), ROOT, globals())
    assert p == Point(1, [2, 3])


def test_round_trips_deployment_class_from_main_globals() -> None:
    data = _obj([], "Point", {"x": 1, "y": 2}, kind="relative")
    assert deserialize(data, "__main__", {"Point": type("Point", (), {"__module__": "__main__"})}).x == 1


def test_round_trips_exceptions() -> None:
    assert isinstance(deserialize(serialize(ValueError("x"), ROOT), ROOT, globals()), ValueError)
    assert isinstance(
        deserialize(serialize(DeploymentError("x"), ROOT), ROOT, globals()), DeploymentError
    )


def test_refuses_stdlib_gadget_class() -> None:
    import tempfile  # noqa: F401

    with pytest.raises(TypeError):
        deserialize(_obj(["tempfile"], "_TemporaryFileCloser"), ROOT, globals())


def test_refuses_class_imported_into_deployment_globals() -> None:
    data = _obj([], "Popen", kind="relative")
    with pytest.raises(TypeError):
        deserialize(data, "__main__", {"Popen": subprocess.Popen})


def test_refuses_non_class_global() -> None:
    data = _obj([], "run", kind="relative")
    with pytest.raises(TypeError):
        deserialize(data, "__main__", {"run": subprocess.run})


def test_does_not_import_named_module() -> None:
    sys.modules.pop("this", None)
    with pytest.raises(TypeError):
        deserialize(_obj(["this"], "Anything"), ROOT, globals())
    assert "this" not in sys.modules


def test_refuses_dunder_attributes() -> None:
    data = serialize(Point(1, 2), ROOT)
    data["contents"]["__dict__"] = {"type": "dict", "contents": []}
    with pytest.raises(TypeError):
        deserialize(data, ROOT, globals())
