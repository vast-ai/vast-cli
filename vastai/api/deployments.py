"""Deployment CRUD operations."""
from vastai.api.client import VastClient


def show_deployments(client: VastClient) -> list:
    r = client.get("/deployments")
    r.raise_for_status()
    return r.json()["deployments"]


def show_deployment(client: VastClient, id: int) -> dict:
    r = client.get(f"/deployment/{id}/")
    r.raise_for_status()
    return r.json()["deployment"]


def show_deployment_versions(client: VastClient, id: int) -> list:
    r = client.get(f"/deployment/{id}/versions/")
    r.raise_for_status()
    rj = r.json()
    if rj.get("success"):
        return rj["versions"]
    else:
        raise RuntimeError(rj.get("msg", "Unknown error"))


def delete_deployment(client: VastClient, id: int) -> dict:
    r = client.delete(f"/deployment/{id}/")
    r.raise_for_status()
    return r.json()
