"""Instance CRUD operations."""
import re
import time
import requests
from typing import Optional
from vastai.api.client import VastClient
from vastai.utils import parse_env


def _poll_result_url(result_url, retries=30, delay=0.3):
    """Poll a result URL until the content is ready. Total timeout ~9s."""
    for _ in range(retries):
        time.sleep(delay)
        r = requests.get(result_url, timeout=10)
        if r.status_code == 200:
            return r.text
    raise TimeoutError(f"Result not ready after {retries * delay}s: {result_url}")


def _strip_strings(value):
    """Recursively strip whitespace from string values."""
    if isinstance(value, str):
        return value.strip()
    elif isinstance(value, dict):
        return {k: _strip_strings(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_strip_strings(item) for item in value]
    return value


def show_instances(client: VastClient, select_filters: Optional[dict] = None, order_by: Optional[list] = None) -> list:
    """Return all of the user's instances (optionally filtered/sorted) as a flat list.

    Pages through the v1 ``/api/v1/instances/`` endpoint, following
    ``next_token`` until it is exhausted, and concatenates every page into one
    flat list. ``select_cols`` is omitted on purpose: the backend then returns
    full instance rows, matching the shape scripts and the SDK have always
    depended on for this function's output.
    """
    rows = []
    params = {
        "select_filters": select_filters or {},
        "order_by": order_by or [{"col": "id", "dir": "asc"}],
        "limit": 25,
    }
    while True:
        data = show_instances_v1(client, params)
        page = data.get("instances") or []
        for row in page:
            row = {k: _strip_strings(v) for k, v in row.items()}
            row['duration'] = time.time() - row['start_date']
            row['extra_env'] = {env_var[0]: env_var[1] for env_var in row['extra_env']}
            rows.append(row)
        next_token = data.get("next_token")
        if not next_token:
            break
        params["after_token"] = next_token
    return rows


def show_instances_v1(client: VastClient, params: dict) -> dict:
    """Fetch instances using the v1 paginated API.

    Args:
        client: VastClient instance.
        params: Dict with select_filters, order_by, limit, after_token, select_cols.

    Returns:
        Full response dict (instances, next_token, total_instances, label_counts).
    """
    r = client.get("/api/v1/instances/", query_args=params)
    r.raise_for_status()
    return r.json()


def show_instance_filters(client: VastClient) -> list:
    """Fetch distinct filterable values for instances."""
    r = client.get("/instances/filters/")
    r.raise_for_status()
    return r.json().get("filters", [])


def show_instance(client: VastClient, id: int) -> Optional[dict]:
    r = client.get(f"/instances/{id}/", query_args={"owner": "me"})
    r.raise_for_status()
    row = r.json()["instances"]
    if row is None:
        return None
    row['duration'] = time.time() - row['start_date']
    row['extra_env'] = {env_var[0]: env_var[1] for env_var in row['extra_env']}
    return row


VALID_MOUNT_PATH = re.compile(r'^(/)?([^/\0]+(/)?)+$')


def resolve_runtype(runtype=None, *, ssh=False, jupyter=False, direct=False,
                    args=None, jupyter_lab=False, jupyter_dir=None,
                    default=None):
    """Translate the friendly connection flags into a runtype string.

    Returns ``(runtype, args)``. ``args`` comes back because an empty ``--args``
    selects the args runtype and then has to be dropped from the payload.

    ``default`` is what an unflagged call resolves to: the CLI passes ``'ssh'``,
    the SDK passes ``None`` so the key stays out of the payload entirely.
    """
    if args in ('', [''], []):
        args = None
        empty_args = True
    else:
        empty_args = False

    if runtype:
        if ssh or jupyter or direct:
            raise ValueError(
                "Pass either runtype= or the ssh/jupyter/direct flags, not both."
            )
        return runtype, args

    resolved = default
    if args or empty_args:
        resolved = 'args'

    if not jupyter and (jupyter_dir or jupyter_lab):
        jupyter = True

    if jupyter and resolved == 'args':
        raise ValueError(
            "Can't use jupyter and args together. "
            "Try onstart_cmd instead of args."
        )

    if jupyter:
        resolved = 'jupyter_direc ssh_direc ssh_proxy' if direct else 'jupyter_proxy ssh_proxy'
    elif ssh:
        resolved = 'ssh_direc ssh_proxy' if direct else 'ssh_proxy'
    elif direct and default is None:
        # The CLI reaches here with default='ssh' and keeps it, which is the
        # long-standing behaviour of a bare --direct. There is no such fallback
        # for the SDK, so say so instead of dropping the flag.
        raise ValueError("direct=True requires ssh=True or jupyter=True.")

    return resolved, args


def build_volume_info(*, create_volume=None, link_volume=None, volume_size=None,
                      mount_path=None, volume_label=None):
    """Build the volume_info blob, or None when no volume was requested."""
    if volume_size and not create_volume:
        raise ValueError("volume_size can only be used with create_volume.")
    if not (create_volume or link_volume):
        if mount_path or volume_label:
            raise ValueError("mount_path and volume_label need create_volume or link_volume.")
        return None
    if not mount_path:
        raise ValueError("mount_path is required when creating or linking a volume.")
    if not VALID_MOUNT_PATH.match(mount_path):
        raise ValueError(f"mount_path '{mount_path}' is not a valid Linux file path.")

    volume_info = {
        "mount_path": mount_path,
        "create_new": True if create_volume else False,
        "volume_id": create_volume if create_volume else link_volume,
    }
    if volume_label:
        volume_info["name"] = volume_label
    if volume_size:
        volume_info["size"] = volume_size
    elif create_volume:
        volume_info["size"] = 15
    return volume_info


def apply_portal_config(env, runtype):
    """Return env with jupyter portal entries stripped on non-jupyter runtypes."""
    if runtype and 'jupyter' in runtype:
        return env
    if "PORTAL_CONFIG" not in env:
        return env

    filtered = [c for c in env["PORTAL_CONFIG"].split("|") if 'jupyter' not in c.lower()]
    if not filtered:
        raise ValueError(
            "env variable PORTAL_CONFIG must contain at least one non-jupyter "
            "related config string if runtype is not jupyter"
        )
    env = dict(env)
    env["PORTAL_CONFIG"] = "|".join(filtered)
    return env


def build_create_instance_payload(
    *, image=None, disk=10, env=None, price=None, bid_price=None, label=None,
    extra=None, onstart_cmd=None, login=None, python_utf8=False,
    lang_utf8=False, jupyter_lab=False, jupyter_dir=None, force=False,
    cancel_unavail=False, template_hash=None, user=None, runtype=None,
    ssh=False, jupyter=False, direct=False, args=None, volume_info=None,
    create_volume=None, link_volume=None, volume_size=None, mount_path=None,
    volume_label=None,
) -> dict:
    """Build the JSON body for a create-instance request.

    The one place the CLI, the SDK and the docs generator agree on what a
    create-instance call takes. Pure: no client, no argparse, no printing.
    """
    if price is not None and bid_price is not None:
        raise ValueError("Pass either price= or bid_price=, not both.")
    if price is None:
        price = bid_price

    if isinstance(env, str):
        env = parse_env(env)
    env = dict(env or {})

    if template_hash is None:
        runtype, args = resolve_runtype(
            runtype, ssh=ssh, jupyter=jupyter, direct=direct, args=args,
            jupyter_lab=jupyter_lab, jupyter_dir=jupyter_dir,
        )
    env = apply_portal_config(env, runtype)

    if volume_info is None:
        volume_info = build_volume_info(
            create_volume=create_volume, link_volume=link_volume,
            volume_size=volume_size, mount_path=mount_path,
            volume_label=volume_label,
        )
    elif create_volume or link_volume:
        raise ValueError("Pass either volume_info= or the create/link volume flags, not both.")

    json_blob = {
        "client_id": "me",
        "image": image,
        "env": env,
        "price": price,
        "disk": disk,
        "label": label,
        "extra": extra,
        "onstart": onstart_cmd,
        "image_login": login,
        "python_utf8": python_utf8,
        "lang_utf8": lang_utf8,
        "use_jupyter_lab": jupyter_lab,
        "jupyter_dir": jupyter_dir,
        "force": force,
        "cancel_unavail": cancel_unavail,
        "template_hash_id": template_hash,
        "user": user,
    }
    if runtype:
        json_blob["runtype"] = runtype
    if args is not None:
        json_blob["args"] = args
    if volume_info:
        json_blob["volume_info"] = volume_info
    return json_blob


def create_instance(client: VastClient, id, image=None, disk=10, env=None,
                    price=None, label=None, extra=None, onstart_cmd=None,
                    login=None, python_utf8=False, lang_utf8=False,
                    jupyter_lab=False, jupyter_dir=None, force=False,
                    cancel_unavail=False, template_hash=None, user=None,
                    runtype=None, args=None, volume_info=None,
                    # Appended, never inserted: the parameters above keep their
                    # original positions so existing positional calls still bind
                    # the same values.
                    bid_price=None, ssh=False, jupyter=False, direct=False,
                    create_volume=None, link_volume=None, volume_size=None,
                    mount_path=None, volume_label=None) -> dict:
    """Create one instance, or several when ``id`` is a list of offer ids."""
    json_blob = build_create_instance_payload(
        image=image, disk=disk, env=env, price=price, bid_price=bid_price,
        label=label, extra=extra, onstart_cmd=onstart_cmd, login=login,
        python_utf8=python_utf8, lang_utf8=lang_utf8, jupyter_lab=jupyter_lab,
        jupyter_dir=jupyter_dir, force=force, cancel_unavail=cancel_unavail,
        template_hash=template_hash, user=user, runtype=runtype, ssh=ssh,
        jupyter=jupyter, direct=direct, args=args, volume_info=volume_info,
        create_volume=create_volume, link_volume=link_volume,
        volume_size=volume_size, mount_path=mount_path, volume_label=volume_label,
    )

    return create_instance_from_payload(client, id, json_blob)


def create_instance_from_payload(client: VastClient, id, json_blob: dict) -> dict:
    """Send an already-built create-instance payload for one or many offers."""
    if isinstance(id, list):
        json_blob["ids"] = id
        r = client.post("/asks/bulk/", json_data=json_blob)
    else:
        r = client.put(f"/asks/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def destroy_instance(client: VastClient, id) -> dict:
    json_blob = {}
    if isinstance(id, list):
        json_blob["instance_ids"] = id
        r = client.delete("/instances/", json_data=json_blob)
    else:
        r = client.delete(f"/instances/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def start_instance(client: VastClient, id) -> dict:
    json_blob = {"state": "running"}
    if isinstance(id, list):
        json_blob["ids"] = id
        r = client.put("/instances/", json_data=json_blob)
    else:
        r = client.put(f"/instances/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def stop_instance(client: VastClient, id) -> dict:
    json_blob = {"state": "stopped"}
    if isinstance(id, list):
        json_blob["ids"] = id
        r = client.put("/instances/", json_data=json_blob)
    else:
        r = client.put(f"/instances/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def reboot_instance(client: VastClient, id: int) -> dict:
    r = client.put(f"/instances/reboot/{id}/", json_data={})
    r.raise_for_status()
    return r.json()


def recycle_instance(client: VastClient, id: int) -> dict:
    r = client.put(f"/instances/recycle/{id}/", json_data={})
    r.raise_for_status()
    return r.json()


def label_instance(client: VastClient, id: int, label: str) -> dict:
    r = client.put(f"/instances/{id}/", json_data={"label": label})
    r.raise_for_status()
    return r.json()


def prepay_instance(client: VastClient, id: int, amount: float) -> dict:
    r = client.put(f"/instances/prepay/{id}/", json_data={"amount": amount})
    r.raise_for_status()
    return r.json()


def change_bid(client: VastClient, id: int, price: float = None) -> dict:
    r = client.put(f"/instances/bid_price/{id}/", json_data={"client_id": "me", "price": price})
    r.raise_for_status()
    return r.json()


def accept_price_increase(client: VastClient, id: int = None,
                          instance_ids=None, host_id: int = None) -> dict:
    """Deprecated shim that resolves to the per-row endpoint.

    Prefer :func:`vastai.api.price_increase.accept`. The old
    ``id`` / ``instance_ids`` / ``host_id`` selectors are no longer
    supported by the backend; ``id`` here is reinterpreted as an
    instance id, looked up against the pending list, and forwarded
    to the per-row accept. ``instance_ids`` and ``host_id`` raise.
    Removed in the release after this one.
    """
    from vastai.api import price_increase as _pi
    if instance_ids is not None or host_id is not None:
        raise TypeError(
            "accept_price_increase: instance_ids and host_id are no longer "
            "supported. Use vastai.api.price_increase.accept(client, pending_id) "
            "per row, or vastai.sdk.VastAI.accept_price_increase(instance_id=…).")
    if id is None:
        raise TypeError("accept_price_increase: instance id is required")
    try:
        match = _pi.resolve_instance_to_pending(client, id)
    except LookupError as err:
        raise LookupError(
            f"accept_price_increase: no pending price increase for instance {id}"
        ) from err
    return _pi.accept(client, match["pending_price_increase_id"])


def execute(client: VastClient, id: int, command: str):
    """Execute a command on an instance and return the output."""
    r = client.put(f"/instances/command/{id}/", json_data={"command": command})
    r.raise_for_status()
    rj = r.json()
    result_url = rj.get("result_url")
    if not result_url:
        return rj
    return _poll_result_url(result_url)


def logs(client: VastClient, instance_id: int, tail=None, filter=None, daemon_logs=False):
    """Request logs for an instance and return the log text."""
    json_blob = {}
    if filter:
        json_blob['filter'] = filter
    if tail:
        json_blob['tail'] = tail
    if daemon_logs:
        json_blob['daemon_logs'] = 'true'
    r = client.put(f"/instances/request_logs/{instance_id}/", json_data=json_blob)
    r.raise_for_status()
    rj = r.json()
    result_url = rj.get("result_url")
    if not result_url:
        return rj
    return _poll_result_url(result_url)


def update_instance(client: VastClient, id: int, template_id=None, template_hash_id=None,
                    image=None, args=None, env=None, onstart=None) -> dict:
    json_blob = {"id": id}
    if template_id is not None:
        json_blob["template_id"] = template_id
    if template_hash_id is not None:
        json_blob["template_hash_id"] = template_hash_id
    if image is not None:
        json_blob["image"] = image
    if args is not None:
        json_blob["args"] = args
    if env is not None:
        json_blob["env"] = env
    if onstart is not None:
        json_blob["onstart"] = onstart
    r = client.put(f"/instances/update_template/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def take_snapshot(client: VastClient, instance_id, repo=None, container_registry="docker.io",
                  docker_login_user=None, docker_login_pass=None, pause="true") -> dict:
    req_json = {
        "id": instance_id,
        "container_registry": container_registry,
        "personal_repo": repo,
        "docker_login_user": docker_login_user,
        "docker_login_pass": docker_login_pass,
        "pause": pause
    }
    r = client.post(f"/instances/take_snapshot/{instance_id}/", json_data=req_json)
    r.raise_for_status()
    return r.json()
