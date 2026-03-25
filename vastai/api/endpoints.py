"""Endpoint and workergroup API functions for the Vast.ai SDK."""

import requests


def show_endpoints(client):
    """Display user's current endpoint groups.

    GET /endptjobs/

    Args:
        client: VastClient instance.

    Returns:
        list: Endpoint group results with sensitive fields removed.
    """
    json_blob = {"client_id": "me", "api_key": client.api_key}
    r = client.get("/endptjobs/", json_data=json_blob)
    r.raise_for_status()

    if r.status_code == 200:
        rj = r.json()
        if rj["success"]:
            rows = rj["results"]
            for row in rows:
                row.pop("api_key", None)
                row.pop("auto_delete_in_seconds", None)
                row.pop("auto_delete_due_24h", None)
            return rows
        else:
            return {"error": rj["msg"]}
    return r.json()


def create_endpoint(client, **kwargs):
    """Create a new endpoint group.

    POST /endptjobs/

    Args:
        client: VastClient instance.
        **kwargs: Endpoint configuration options:
            min_load (float): Minimum floor load in perf units/s. Default 0.0.
            min_cold_load (float): Minimum floor load allowing cold workers. Default 0.0.
            target_util (float): Target capacity utilization (max 1.0). Default 0.9.
            cold_mult (float): Cold capacity target as multiple of hot. Default 2.5.
            cold_workers (int): Min cold workers when no load. Default 5.
            max_workers (int): Max workers for the endpoint group. Default 20.
            endpoint_name (str): Deployment endpoint name.
            auto_instance (str): Autoscaler instance type. Default "prod".

    Returns:
        dict: API response data.
    """
    json_blob = {
        "client_id": "me",
        "min_load": kwargs.get("min_load", 0.0),
        "min_cold_load": kwargs.get("min_cold_load", 0.0),
        "target_util": kwargs.get("target_util", 0.9),
        "cold_mult": kwargs.get("cold_mult", 2.5),
        "cold_workers": kwargs.get("cold_workers", 5),
        "max_workers": kwargs.get("max_workers", 20),
        "endpoint_name": kwargs.get("endpoint_name"),
        "autoscaler_instance": kwargs.get("auto_instance", "prod"),
    }

    r = client.post("/endptjobs/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def update_endpoint(client, id, **kwargs):
    """Update an existing endpoint group.

    PUT /endptjobs/{id}/

    Args:
        client: VastClient instance.
        id (int): ID of endpoint group to update.
        **kwargs: Endpoint configuration options.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "client_id": "me",
        "endptjob_id": id,
        "min_load": kwargs.get("min_load"),
        "min_cold_load": kwargs.get("min_cold_load"),
        "target_util": kwargs.get("target_util"),
        "cold_mult": kwargs.get("cold_mult"),
        "cold_workers": kwargs.get("cold_workers"),
        "max_workers": kwargs.get("max_workers"),
        "endpoint_name": kwargs.get("endpoint_name"),
        "endpoint_state": kwargs.get("endpoint_state"),
        "autoscaler_instance": kwargs.get("auto_instance", "prod"),
    }
    r = client.put(f"/endptjobs/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def delete_endpoint(client, id):
    """Delete an endpoint group.

    DELETE /endptjobs/{id}/

    Args:
        client: VastClient instance.
        id (int): ID of endpoint group to delete.

    Returns:
        dict: API response data.
    """
    json_blob = {"client_id": "me", "endptjob_id": id}
    r = client.delete(f"/endptjobs/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def _get_logs_base_url(client):
    """Derive the base URL for log endpoints.

    If the client is using the default console.vast.ai URL, logs are served
    from run.vast.ai.  Otherwise the user's custom URL is used.
    """
    from vastai.api.client import server_url_default
    if client.server_url == server_url_default:
        return "https://run.vast.ai"
    return client.server_url


def get_endpt_logs(client, id, level=1, tail=None):
    """Fetch logs for a specific serverless endpoint group.

    POST to <base>/get_endpoint_logs/

    Args:
        client: VastClient instance.
        id (int): ID of endpoint group to fetch logs from.
        level (int): Log detail level (0 to 3). Default 1.
            0: info0, 1: info1, 2: trace, 3: debug
        tail (int, optional): Number of tail lines.

    Returns:
        dict: Log data from the API response.
    """
    base = _get_logs_base_url(client)
    url = base + "/get_endpoint_logs/"
    json_blob = {"id": id, "api_key": client.api_key}
    if tail is not None:
        json_blob["tail"] = tail

    headers = {}
    if client.api_key is not None:
        headers["Authorization"] = "Bearer " + client.api_key

    r = requests.post(url, headers=headers, json=json_blob)
    r.raise_for_status()

    if r.status_code == 200:
        rj = r.json()
        return rj
    return {"error": r.text}


def show_workergroups(client):
    """Display user's current workergroups.

    GET /autojobs/

    Args:
        client: VastClient instance.

    Returns:
        list: Workergroup results.
    """
    json_blob = {"client_id": "me", "api_key": client.api_key}
    r = client.get("/autojobs/", json_data=json_blob)
    r.raise_for_status()

    if r.status_code == 200:
        rj = r.json()
        if rj["success"]:
            return rj["results"]
        else:
            return {"error": rj["msg"]}
    return r.json()


def create_workergroup(client, **kwargs):
    """Create a new autoscale/workergroup.

    POST /autojobs/

    Args:
        client: VastClient instance.
        **kwargs: Workergroup configuration options:
            template_hash (str): Template hash (required).
            template_id (int): Template ID (optional).
            search_params (str): Search param string for search offers.
            launch_args (str): Launch args string for create instance.
            endpoint_name (str): Deployment endpoint name.
            endpoint_id (int): Deployment endpoint ID.
            test_workers (int): Number of test workers. Default 3.
            gpu_ram (float): Estimated GPU RAM requirement.
            min_load (float): Minimum floor load.
            target_util (float): Target capacity utilization.
            cold_mult (float): Cold capacity target multiple.
            cold_workers (int): Min cold workers.
            no_default (bool): Disable default search param query args.
            auto_instance (str): Autoscaler instance type. Default "prod".

    Returns:
        dict: API response data.
    """
    no_default = kwargs.get("no_default", False)
    if no_default:
        query = ""
    else:
        query = " verified=True rentable=True rented=False"

    search_params_arg = kwargs.get("search_params")
    search_params = ((search_params_arg if search_params_arg is not None else "") + query).strip()

    json_blob = {
        "client_id": "me",
        "min_load": kwargs.get("min_load"),
        "target_util": kwargs.get("target_util"),
        "cold_mult": kwargs.get("cold_mult"),
        "cold_workers": kwargs.get("cold_workers"),
        "test_workers": kwargs.get("test_workers", 3),
        "template_hash": kwargs.get("template_hash"),
        "template_id": kwargs.get("template_id"),
        "search_params": search_params,
        "launch_args": kwargs.get("launch_args"),
        "gpu_ram": kwargs.get("gpu_ram"),
        "endpoint_name": kwargs.get("endpoint_name"),
        "endpoint_id": kwargs.get("endpoint_id"),
        "autoscaler_instance": kwargs.get("auto_instance", "prod"),
    }

    r = client.post("/autojobs/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def update_workergroup(client, id, **kwargs):
    """Update an existing workergroup.

    PUT /autojobs/{id}/

    Args:
        client: VastClient instance.
        id (int): ID of workergroup to update.
        **kwargs: Workergroup configuration options.

    Returns:
        dict: API response data.
    """
    no_default = kwargs.get("no_default", False)
    if no_default:
        query = ""
    else:
        query = " verified=True rentable=True rented=False"

    search_params_arg = kwargs.get("search_params")
    search_params = ((search_params_arg if search_params_arg is not None else "") + query).strip()

    json_blob = {
        "client_id": "me",
        "autojob_id": id,
        "min_load": kwargs.get("min_load"),
        "target_util": kwargs.get("target_util"),
        "cold_mult": kwargs.get("cold_mult"),
        "cold_workers": kwargs.get("cold_workers"),
        "test_workers": kwargs.get("test_workers"),
        "template_hash": kwargs.get("template_hash"),
        "template_id": kwargs.get("template_id"),
        "search_params": search_params,
        "launch_args": kwargs.get("launch_args"),
        "gpu_ram": kwargs.get("gpu_ram"),
        "endpoint_name": kwargs.get("endpoint_name"),
        "endpoint_id": kwargs.get("endpoint_id"),
    }
    r = client.put(f"/autojobs/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def delete_workergroup(client, id):
    """Delete a workergroup.

    DELETE /autojobs/{id}/

    Note: Deleting a workergroup does not automatically destroy all
    associated instances.

    Args:
        client: VastClient instance.
        id (int): ID of workergroup to delete.

    Returns:
        dict: API response data.
    """
    json_blob = {"client_id": "me", "autojob_id": id}
    r = client.delete(f"/autojobs/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def get_wrkgrp_logs(client, id, level=1, tail=None):
    """Fetch logs for a specific serverless worker group.

    POST to <base>/get_autogroup_logs/

    Args:
        client: VastClient instance.
        id (int): ID of worker group to fetch logs from.
        level (int): Log detail level (0 to 3). Default 1.
            0: info0, 1: info1, 2: trace, 3: debug
        tail (int, optional): Number of tail lines.

    Returns:
        dict: Log data from the API response.
    """
    base = _get_logs_base_url(client)
    url = base + "/get_autogroup_logs/"
    json_blob = {"id": id, "api_key": client.api_key}
    if tail is not None:
        json_blob["tail"] = tail

    headers = {}
    if client.api_key is not None:
        headers["Authorization"] = "Bearer " + client.api_key

    r = requests.post(url, headers=headers, json=json_blob)
    r.raise_for_status()

    if r.status_code == 200:
        rj = r.json()
        return rj
    return {"error": r.text}
