"""Instance CRUD operations."""
import time
import requests
from vastai.api.client import VastClient


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


def show_instances(client: VastClient) -> list:
    r = client.get("/instances", query_args={"owner": "me"})
    r.raise_for_status()
    rows = r.json()["instances"]
    for i, row in enumerate(rows):
        row = {k: _strip_strings(v) for k, v in row.items()}
        row['duration'] = time.time() - row['start_date']
        row['extra_env'] = {env_var[0]: env_var[1] for env_var in row['extra_env']}
        rows[i] = row
    return rows


def show_instance(client: VastClient, id: int) -> dict:
    r = client.get(f"/instances/{id}/", query_args={"owner": "me"})
    r.raise_for_status()
    row = r.json()["instances"]
    row['duration'] = time.time() - row['start_date']
    row['extra_env'] = {env_var[0]: env_var[1] for env_var in row['extra_env']}
    return row


def create_instance(client: VastClient, id, image=None, disk=10, env=None, price=None,
                    label=None, extra=None, onstart_cmd=None, login=None,
                    python_utf8=False, lang_utf8=False, jupyter_lab=False,
                    jupyter_dir=None, force=False, cancel_unavail=False,
                    template_hash=None, user=None, runtype=None, args=None,
                    volume_info=None) -> dict:
    json_blob = {
        "client_id": "me",
        "image": image,
        "env": env or {},
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
