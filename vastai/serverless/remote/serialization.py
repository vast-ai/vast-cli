import base64
from typing import Any, TypeAlias
from importlib import import_module
import logging

logger = logging.getLogger("vastai")


def relativize_module(mod: str, root_module):
    if mod == root_module:
        return {"type": "relative", "path": []}
    elif mod.startswith(root_module):
        return {
            "type": "relative",
            "path": mod[len(root_module) :].lstrip(".").split("."),
        }  # will be non-empty
    else:
        return {"type": "absolute", "path": mod.split(".")}


def derelativize_module(mod, root_module: str):
    if mod["type"] == "relative":
        prefix = [] if root_module == "__main__" else root_module.split(".")
        return ".".join(prefix + mod["path"])
    else:
        return ".".join(mod["path"])


JSON: TypeAlias = int | str | float | list["JSON"] | dict[str, "JSON"]


def serialize(obj, root_module: str) -> JSON:
    if type(obj) in [int, str, float, type(None)]:
        return obj
    elif type(obj) is bytes:
        return {"type": "bytes", "contents": base64.b64encode(obj).decode("utf-8")}
    elif type(obj) in [list, tuple]:
        return {
            "type": type(obj).__name__,
            "contents": [serialize(child, root_module) for child in obj],
        }
    elif (
        type(obj) is dict
    ):  # JSON dicts must have string keys, so instead we do this as list of tuples
        return {
            "type": "dict",
            "contents": [
                [serialize(k, root_module), serialize(v, root_module)]
                for k, v in obj.items()
            ],
        }
    elif hasattr(obj, "__dict__") and hasattr(
        obj, "__class__"
    ):  # is a member of a normal Python class
        return {
            "type": "obj",
            "module": relativize_module(obj.__class__.__module__, root_module),
            "class": obj.__class__.__qualname__,
            "contents": {k: serialize(v, root_module) for k, v in obj.__dict__.items()},
        }
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable!")


def deserialize(json, root_module: str, globals):
    if type(json) in [int, str, float, type(None)]:
        return json
    elif json["type"] == "bytes":
        return base64.b64decode(json["contents"])
    elif json["type"] in ["list", "tuple"]:
        return __builtins__[json["type"]](
            deserialize(child, root_module, globals) for child in json["contents"]
        )
    elif json["type"] == "dict":
        return dict(
            (deserialize(k, root_module, globals), deserialize(v, root_module, globals))
            for k, v in json["contents"]
        )
    elif json["type"] == "obj":
        modname = derelativize_module(json["module"], root_module)
        namespace = globals if modname == "" else import_module(modname).__dict__
        cls = namespace[json["class"]]
        obj = cls.__new__(cls)
        for k, v in json["contents"].items():
            setattr(obj, k, deserialize(v, root_module, globals))
        return obj
    raise TypeError(
        f"JSON does not correspond to known Vast deployment datatype: {json}"
    )


def serialize_ok(obj, root_module: str):
    return {"ok": serialize(obj, root_module)}


def serialize_err(err, root_module: str):
    return {"err": serialize(err, root_module)}


def deserialize_unwrap_error(json, root_module: str, globals):
    logger.debug(f"got json: \n{json}")
    for k, v in json.items():
        if (k) == "ok":
            return deserialize(v, root_module, globals)
        if (k) == "err":
            err = deserialize(v, root_module, globals)
            if isinstance(err, Exception):
                raise err
    raise TypeError(
        'Expected json to have format {"ok": deserializable} or {"err": deserializes_to_error_object}: '
        + json
    )
