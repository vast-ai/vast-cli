"""Main VastAI SDK class that wraps all api/ module functions."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from vastai.api.client import VastClient
from vastai.api import instances, offers, machines, teams, keys, endpoints, billing, storage, clusters, auth, deployments


# Default API key file location (matches legacy CLI behavior)
APIKEY_FILE = os.path.join(os.path.expanduser("~"), ".vast_api_key")


class VastAI:
    """High-level SDK for the Vast.ai platform.

    Wraps the low-level api/ modules behind a single object with one method
    per API operation.  Every method delegates to the corresponding module
    function, passing ``self.client`` (a :class:`VastClient`) along with any
    caller-supplied arguments.

    Args:
        api_key: Vast.ai API key.  When *None*, the key is read from
            ``~/.vast_api_key`` if the file exists.
        server_url: Base URL of the Vast.ai API server.
        retry: Number of retries on transient HTTP errors.
        raw: If *True*, return raw JSON dicts instead of formatted output.
        explain: If *True*, print request details for debugging.
        quiet: If *True*, suppress informational output.
        curl: If *True*, print equivalent curl commands instead of executing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        server_url: Optional[str] = None,
        retry: int = 3,
        raw: bool = False,
        explain: bool = False,
        quiet: bool = False,
        curl: bool = False,
    ):
        if api_key is None and os.path.exists(APIKEY_FILE):
            with open(APIKEY_FILE, "r") as f:
                api_key = f.read().strip()

        self.client = VastClient(api_key, server_url, retry, explain, curl)
        self.raw = raw
        self.quiet = quiet

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    def show_instances(self) -> list[dict]:
        """Return all instances for the authenticated user."""
        return instances.show_instances(self.client)

    def show_instance(self, id: int) -> dict:
        """Return details of a single instance."""
        return instances.show_instance(self.client, id)

    def create_instance(self, id: int, image: Optional[str] = None, disk: float = 10, **kwargs) -> dict:
        """Create a new instance from a contract offer ID."""
        return instances.create_instance(self.client, id, image=image, disk=disk, **kwargs)

    def destroy_instance(self, id: int) -> dict:
        """Destroy an instance."""
        return instances.destroy_instance(self.client, id)

    def start_instance(self, id: int) -> dict:
        """Start a stopped instance."""
        return instances.start_instance(self.client, id)

    def stop_instance(self, id: int) -> dict:
        """Stop a running instance."""
        return instances.stop_instance(self.client, id)

    def reboot_instance(self, id: int) -> dict:
        """Reboot an instance."""
        return instances.reboot_instance(self.client, id)

    def recycle_instance(self, id: int) -> dict:
        """Recycle an instance."""
        return instances.recycle_instance(self.client, id)

    def label_instance(self, id: int, label: str) -> dict:
        """Set a label on an instance."""
        return instances.label_instance(self.client, id, label)

    def prepay_instance(self, id: int, amount: float) -> dict:
        """Prepay for an instance."""
        return instances.prepay_instance(self.client, id, amount)

    def change_bid(self, id: int, price: Optional[float] = None) -> dict:
        """Change the bid price for an instance."""
        return instances.change_bid(self.client, id, price=price)

    def execute(self, id: int, command: str) -> dict:
        """Execute a command on an instance."""
        return instances.execute(self.client, id, command)

    def logs(
        self,
        instance_id: int,
        tail: Optional[str] = None,
        filter: Optional[str] = None,
        daemon_logs: bool = False,
    ) -> str:
        """Retrieve logs for an instance."""
        return instances.logs(self.client, instance_id, tail=tail, filter=filter, daemon_logs=daemon_logs)

    def ssh_url(self, id: int) -> str:
        """Get the SSH URL for an instance."""
        inst = instances.show_instance(self.client, id)
        if isinstance(inst, list):
            inst = inst[0] if inst else {}
        port = inst.get("ssh_port") or (inst.get("ports") or {}).get("22/tcp", [{}])[0].get("HostPort")
        ip = inst.get("ssh_host") or inst.get("public_ipaddr")
        return f"ssh://root@{ip}:{port}" if port and ip else ""

    def scp_url(self, id: int) -> str:
        """Get the SCP URL for an instance."""
        inst = instances.show_instance(self.client, id)
        if isinstance(inst, list):
            inst = inst[0] if inst else {}
        port = inst.get("ssh_port") or (inst.get("ports") or {}).get("22/tcp", [{}])[0].get("HostPort")
        ip = inst.get("ssh_host") or inst.get("public_ipaddr")
        return f"scp://root@{ip}:{port}" if port and ip else ""

    def take_snapshot(self, instance_id, **kwargs) -> dict:
        """Take a container snapshot and push to a registry."""
        return instances.take_snapshot(self.client, instance_id, **kwargs)

    # ------------------------------------------------------------------
    # Deployment methods
    # ------------------------------------------------------------------

    def show_deployments(self) -> list[dict]:
        """Return all deployments for the authenticated user."""
        return deployments.show_deployments(self.client)

    def show_deployment(self, id: int) -> dict:
        """Return details of a single deployment."""
        return deployments.show_deployment(self.client, id)

    def delete_deployment(self, id: int) -> dict:
        """Delete a deployment."""
        return deployments.delete_deployment(self.client, id)

    # ------------------------------------------------------------------
    # Offer / search methods
    # ------------------------------------------------------------------

    def search_offers(
        self,
        query=None,
        type: str = "on-demand",
        order: str = "score-",
        limit: Optional[int] = None,
        storage: float = 5.0,
        no_default: bool = False,
        **kwargs,
    ) -> list:
        """Search for GPU offers.

        Args:
            query: Query string (e.g. "num_gpus=1 gpu_name=RTX_4090") or pre-parsed dict.
            type: One of "on-demand", "reserved", or "bid".
            order: Comma-separated sort fields, e.g. "score-" or "dph_total".
            limit: Max results.
            storage: Allocated storage in GiB for pricing.
            no_default: Skip default filters (verified, rentable, etc.).
        """
        from vastai.api.query import parse_query, offers_fields, offers_alias, offers_mult
        from vastai.utils import preprocess_search_query, postprocess_search_results

        # Expand georegion/chunked directives before parsing
        georegion_active, chunked = False, False
        if isinstance(query, str):
            georegion_active, chunked, query = preprocess_search_query(query)
            query = parse_query(query, {}, offers_fields, offers_alias, offers_mult)

        # Parse order string into list
        order_list = None
        if isinstance(order, str):
            order_list = []
            for name in order.split(","):
                name = name.strip()
                if not name:
                    continue
                direction = "asc"
                field = name
                if name.strip("-") != name:
                    direction = "desc"
                    field = name.strip("-")
                if name.strip("+") != name:
                    direction = "asc"
                    field = name.strip("+")
                if field in offers_alias:
                    field = offers_alias[field]
                order_list.append([field, direction])
        elif isinstance(order, list):
            order_list = order

        results = offers.search_offers(
            self.client, query=query, offer_type=type, order=order_list,
            limit=limit, storage=storage, no_default=no_default, **kwargs,
        )

        if isinstance(results, list):
            results = postprocess_search_results(results, georegion_active=georegion_active, chunked=chunked)

        return results

    def search_templates(self, query: Optional[str] = None) -> list[dict]:
        """Search for templates."""
        return offers.search_templates(self.client, query=query)

    def search_benchmarks(self, query: Optional[str] = None) -> list[dict]:
        """Search for benchmarks."""
        return offers.search_benchmarks(self.client, query=query)

    def search_volumes(self, query: Optional[str] = None, **kwargs) -> list[dict]:
        """Search for volume offers."""
        return offers.search_volumes(self.client, query=query, **kwargs)

    def search_network_volumes(self, query: Optional[str] = None, **kwargs) -> list[dict]:
        """Search for network volume offers."""
        return offers.search_network_volumes(self.client, query=query, **kwargs)

    def search_invoices(self, query: Optional[str] = None) -> list[dict]:
        """Search for invoices."""
        return offers.search_invoices(self.client, query=query)

    def search_offers_new(
        self,
        query=None,
        type: str = "on-demand",
        order: str = "score-",
        limit: Optional[int] = None,
        storage: float = 5.0,
        no_default: bool = False,
        **kwargs,
    ) -> list:
        """Search for GPU offers using the new /search/asks/ endpoint.

        Args:
            query: Query string (e.g. "num_gpus=1 gpu_name=RTX_4090") or pre-parsed dict.
            type: One of "on-demand", "reserved", or "bid".
            order: Comma-separated sort fields, e.g. "score-" or "dph_total".
            limit: Max results.
            storage: Allocated storage in GiB for pricing.
            no_default: Skip default filters (verified, rentable, etc.).
        """
        from vastai.api.query import parse_query, offers_fields, offers_alias, offers_mult
        from vastai.utils import preprocess_search_query, postprocess_search_results

        georegion_active, chunked = False, False
        if isinstance(query, str):
            georegion_active, chunked, query = preprocess_search_query(query)
            query = parse_query(query, {}, offers_fields, offers_alias, offers_mult)

        order_list = None
        if isinstance(order, str):
            order_list = []
            for name in order.split(","):
                name = name.strip()
                if not name:
                    continue
                direction = "asc"
                field = name
                if name.strip("-") != name:
                    direction = "desc"
                    field = name.strip("-")
                if name.strip("+") != name:
                    direction = "asc"
                    field = name.strip("+")
                if field in offers_alias:
                    field = offers_alias[field]
                order_list.append([field, direction])
        elif isinstance(order, list):
            order_list = order

        results = offers.search_offers_new(
            self.client, query=query, offer_type=type, order=order_list,
            limit=limit, storage=storage, no_default=no_default, **kwargs,
        )

        if isinstance(results, list):
            results = postprocess_search_results(results, georegion_active=georegion_active, chunked=chunked)

        return results

    def launch_instance(self, gpu_name: str, num_gpus: str, image: str, **kwargs) -> dict:
        """Launch the top instance from search offers matching the given criteria."""
        return offers.launch_instance(self.client, gpu_name, num_gpus, image, **kwargs)

    # ------------------------------------------------------------------
    # Machine methods
    # ------------------------------------------------------------------

    def show_machines(self) -> list[dict]:
        """Return all hosted machines."""
        return machines.show_machines(self.client)

    def show_machine(self, id: int) -> dict:
        """Return details of a single machine."""
        return machines.show_machine(self.client, id)

    def show_maints(self, ids) -> list[dict]:
        """Show maintenance information for machines."""
        return machines.show_maints(self.client, ids)

    def list_machine(self, id: int, **kwargs) -> dict:
        """List a machine for rent with optional pricing parameters."""
        return machines.list_machine(self.client, id, **kwargs)

    def list_machines(self, ids, **kwargs) -> list[dict]:
        """List multiple machines for rent."""
        results = []
        for mid in ids:
            results.append(machines.list_machine(self.client, mid, **kwargs))
        return results

    def unlist_machine(self, id: int) -> dict:
        """Unlist a machine from being available."""
        return machines.unlist_machine(self.client, id)

    def set_defjob(self, id: int, **kwargs) -> dict:
        """Set the default job on a machine."""
        return machines.set_defjob(self.client, id, **kwargs)

    def remove_defjob(self, id: int) -> dict:
        """Remove the default job from a machine."""
        return machines.remove_defjob(self.client, id)

    def set_min_bid(self, id: int, price: Optional[float] = None) -> dict:
        """Set the minimum bid price for a machine."""
        return machines.set_min_bid(self.client, id, price=price)

    def schedule_maint(self, id: int, sdate, duration, category: str = "not provided") -> dict:
        """Schedule maintenance for a machine."""
        return machines.schedule_maint(self.client, id, sdate, duration, maintenance_category=category)

    def cancel_maint(self, id: int) -> dict:
        """Cancel scheduled maintenance for a machine."""
        return machines.cancel_maint(self.client, id)

    def cleanup_machine(self, id: int) -> dict:
        """Clean up a machine's configuration and resources."""
        return machines.cleanup_machine(self.client, id)

    def defrag_machines(self, ids) -> dict:
        """Defragment machines."""
        return machines.defrag_machines(self.client, ids)

    def delete_machine(self, id: int) -> dict:
        """Delete a machine if not being used by clients."""
        return machines.delete_machine(self.client, id)

    def reports(self, id: int) -> list[dict]:
        """Generate reports for a machine."""
        return machines.reports(self.client, id)

    # ------------------------------------------------------------------
    # Team methods
    # ------------------------------------------------------------------

    def create_team(self, team_name: str) -> dict:
        """Create a new team."""
        return teams.create_team(self.client, team_name)

    def destroy_team(self) -> dict:
        """Destroy the current team."""
        return teams.destroy_team(self.client)

    def show_members(self) -> list[dict]:
        """Show all team members."""
        return teams.show_members(self.client)

    def invite_member(self, email: str, role: str) -> dict:
        """Invite a new member to the team."""
        return teams.invite_member(self.client, email, role)

    def remove_member(self, id: int) -> dict:
        """Remove a member from the team."""
        return teams.remove_member(self.client, id)

    def show_team_roles(self) -> list[dict]:
        """Show all team roles."""
        return teams.show_team_roles(self.client)

    def show_team_role(self, name: str) -> dict:
        """Show details of a specific team role."""
        return teams.show_team_role(self.client, name)

    def create_team_role(self, name: str, permissions) -> dict:
        """Create a new team role."""
        return teams.create_team_role(self.client, name, permissions)

    def remove_team_role(self, name: str) -> dict:
        """Remove a team role."""
        return teams.remove_team_role(self.client, name)

    # ------------------------------------------------------------------
    # SSH / API key methods
    # ------------------------------------------------------------------

    def show_ssh_keys(self) -> list[dict]:
        """Show all SSH keys."""
        return keys.show_ssh_keys(self.client)

    def create_ssh_key(self, ssh_key: Optional[str] = None) -> dict:
        """Create a new SSH key."""
        return keys.create_ssh_key(self.client, ssh_key=ssh_key)

    def delete_ssh_key(self, id: int) -> dict:
        """Delete an SSH key."""
        return keys.delete_ssh_key(self.client, id)

    def attach_ssh(self, instance_id: int, ssh_key: str) -> dict:
        """Attach an SSH key to an instance."""
        return keys.attach_ssh(self.client, instance_id, ssh_key)

    def detach_ssh(self, instance_id: int, ssh_key_id: str) -> dict:
        """Detach an SSH key from an instance."""
        return keys.detach_ssh(self.client, instance_id, ssh_key_id)

    def show_api_keys(self) -> list[dict]:
        """Show all API keys."""
        return keys.show_api_keys(self.client)

    def show_api_key(self, id: int) -> dict:
        """Show details of an API key."""
        return keys.show_api_key(self.client, id)

    def create_api_key(self, name, permissions, key_params=None) -> dict:
        """Create a new API key."""
        return keys.create_api_key(self.client, name, permissions, key_params=key_params)

    def delete_api_key(self, id: int) -> dict:
        """Delete an API key."""
        return keys.delete_api_key(self.client, id)

    def reset_api_key(self) -> dict:
        """Reset the API key."""
        return keys.reset_api_key(self.client)

    def update_ssh_key(self, id: int, ssh_key: str) -> dict:
        """Update an SSH key."""
        return keys.update_ssh_key(self.client, id, ssh_key)

    # ------------------------------------------------------------------
    # Endpoint methods
    # ------------------------------------------------------------------

    def show_endpoints(self) -> list[dict]:
        """Show all serverless endpoints."""
        return endpoints.show_endpoints(self.client)

    def create_endpoint(self, **kwargs) -> dict:
        """Create a new serverless endpoint."""
        return endpoints.create_endpoint(self.client, **kwargs)

    def delete_endpoint(self, id: int) -> dict:
        """Delete a serverless endpoint."""
        return endpoints.delete_endpoint(self.client, id)

    def get_endpt_logs(self, id: int, level: int = 1, tail: Optional[int] = None) -> dict:
        """Fetch logs for a serverless endpoint."""
        return endpoints.get_endpt_logs(self.client, id, level=level, tail=tail)

    def show_workergroups(self) -> list[dict]:
        """Show all worker groups."""
        return endpoints.show_workergroups(self.client)

    def create_workergroup(self, **kwargs) -> dict:
        """Create a new autoscale worker group."""
        return endpoints.create_workergroup(self.client, **kwargs)

    def delete_workergroup(self, id: int) -> dict:
        """Delete a worker group."""
        return endpoints.delete_workergroup(self.client, id)

    def get_wrkgrp_logs(self, id: int, level: int = 1, tail: Optional[int] = None) -> dict:
        """Fetch logs for a worker group."""
        return endpoints.get_wrkgrp_logs(self.client, id, level=level, tail=tail)

    # ------------------------------------------------------------------
    # Billing methods
    # ------------------------------------------------------------------

    def show_invoices(self, **kwargs) -> list[dict]:
        """Show invoice details."""
        return billing.show_invoices(self.client, **kwargs)

    def show_earnings(self, **kwargs) -> list[dict]:
        """Show earnings information."""
        return billing.show_earnings(self.client, **kwargs)

    def show_deposit(self, id: int) -> dict:
        """Show deposit details."""
        return billing.show_deposit(self.client, id)

    def show_user(self) -> dict:
        """Show current user details."""
        return billing.show_user(self.client)

    def set_user(self, params) -> dict:
        """Set user parameters."""
        return billing.set_user(self.client, params)

    def show_subaccounts(self) -> list[dict]:
        """Show all subaccounts."""
        return billing.show_subaccounts(self.client)

    def create_subaccount(
        self,
        email: str,
        username: str,
        password: str,
        type: Optional[str] = None,
    ) -> dict:
        """Create a new subaccount."""
        host_only = type is not None and type.lower() == "host"
        return billing.create_subaccount(self.client, email, username, password, host_only=host_only)

    def show_ipaddrs(self) -> list[dict]:
        """Show IP addresses."""
        return billing.show_ipaddrs(self.client)

    def fetch_contracts(self, label: Optional[str] = None, contract_ids: Optional[list] = None) -> list:
        """Fetch contracts, optionally filtered by label."""
        return billing.fetch_contracts(self.client, label=label, contract_ids=contract_ids)

    # ------------------------------------------------------------------
    # Storage methods
    # ------------------------------------------------------------------

    def copy(self, src: str, dst: str) -> dict:
        """Copy files between instances.

        Args:
            src: Source in vast URL format, e.g. "instance_id:/path" or just "/local/path".
            dst: Destination in vast URL format.
        """
        from vastai.utils import parse_vast_url
        src_id, src_path = parse_vast_url(src)
        dst_id, dst_path = parse_vast_url(dst)
        return storage.copy(self.client, src_id, dst_id, src_path, dst_path)

    def cancel_copy(self, dst_id) -> dict:
        """Cancel a file copy operation."""
        return storage.cancel_copy(self.client, dst_id)

    def cancel_sync(self, dst_id) -> dict:
        """Cancel a file sync operation."""
        return storage.cancel_sync(self.client, dst_id)

    def cloud_copy(self, **kwargs) -> dict:
        """Copy files between cloud and instance."""
        return storage.cloud_copy(self.client, **kwargs)

    def clone_volume(self, source: int, dest: int, **kwargs) -> dict:
        """Clone an existing volume."""
        return storage.clone_volume(self.client, source, dest, **kwargs)

    def show_volumes(self, type: str = "all") -> list[dict]:
        """Show stats on owned volumes."""
        return storage.show_volumes(self.client, type=type)

    def create_volume(self, id: int, size: float = 15, name: Optional[str] = None) -> dict:
        """Create a new volume from an offer ID."""
        return storage.create_volume(self.client, id, size=size, name=name)

    def delete_volume(self, id: int) -> dict:
        """Delete a volume."""
        return storage.delete_volume(self.client, id)

    def list_volume(self, id: int, **kwargs) -> dict:
        """List disk space for rent as a volume."""
        return storage.list_volume(self.client, id, **kwargs)

    def unlist_volume(self, id: int) -> dict:
        """Unlist a volume offer."""
        return storage.unlist_volume(self.client, id)

    def create_network_volume(self, id: int, size: float = 15, name: Optional[str] = None) -> dict:
        """Create a new network volume."""
        return storage.create_network_volume(self.client, id, size=size, name=name)

    def list_network_volume(self, disk_id: int, **kwargs) -> dict:
        """List disk space for rent as a network volume."""
        return storage.list_network_volume(self.client, disk_id, **kwargs)

    def unlist_network_volume(self, id: int) -> dict:
        """Unlist a network volume offer."""
        return storage.unlist_network_volume(self.client, id)

    def show_network_disks(self) -> dict:
        """Show network disks associated with your account."""
        return storage.show_network_disks(self.client)

    def add_network_disk(self, machines: List[int], mount_point: str, disk_id: Optional[int] = None) -> dict:
        """Add a network disk to a physical cluster."""
        return storage.add_network_disk(self.client, machines, mount_point, disk_id=disk_id)

    def show_connections(self) -> list[dict]:
        """Show all connections."""
        return storage.show_connections(self.client)

    # ------------------------------------------------------------------
    # Cluster methods
    # ------------------------------------------------------------------

    def show_clusters(self) -> dict:
        """Show clusters associated with your account."""
        return clusters.show_clusters(self.client)

    def create_cluster(self, subnet: str, manager_id: int) -> dict:
        """Create a Vast cluster."""
        return clusters.create_cluster(self.client, subnet, manager_id)

    def delete_cluster(self, cluster_id: int) -> dict:
        """Delete a cluster."""
        return clusters.delete_cluster(self.client, cluster_id)

    def join_cluster(self, cluster_id: int, machine_ids: List[int]) -> dict:
        """Join machines to a cluster."""
        return clusters.join_cluster(self.client, cluster_id, machine_ids)

    def remove_machine_from_cluster(
        self,
        cluster_id: int,
        machine_id: int,
        new_manager_id: Optional[int] = None,
    ) -> dict:
        """Remove a machine from a cluster."""
        return clusters.remove_machine_from_cluster(
            self.client, cluster_id, machine_id, new_manager_id=new_manager_id,
        )

    def show_overlays(self) -> list[dict]:
        """Show overlays associated with your account."""
        return clusters.show_overlays(self.client)

    def create_overlay(self, cluster_id: int, name: str) -> dict:
        """Create an overlay network on a physical cluster."""
        return clusters.create_overlay(self.client, cluster_id, name)

    def delete_overlay(self, overlay_identifier: Optional[str] = None) -> dict:
        """Delete an overlay and remove all associated instances."""
        return clusters.delete_overlay(self.client, overlay_identifier=overlay_identifier)

    def join_overlay(self, name: str, instance_id: int) -> dict:
        """Add an instance to an overlay network."""
        return clusters.join_overlay(self.client, name, instance_id)

    # ------------------------------------------------------------------
    # Auth / account methods
    # ------------------------------------------------------------------

    def set_api_key(self, api_key: str) -> None:
        """Update the API key used by this client."""
        self.client.api_key = api_key

    def show_audit_logs(self) -> list[dict]:
        """Display account audit logs."""
        return auth.show_audit_logs(self.client)

    def show_env_vars(self, show_values: bool = False) -> dict:
        """Show user environment variables.

        Args:
            show_values: If True, return actual values. If False, mask them.
        """
        secrets = auth.show_env_vars(self.client)
        if not show_values and isinstance(secrets, dict):
            return {k: "****" for k in secrets}
        return secrets

    def create_env_var(self, name: str, value: str) -> dict:
        """Create a new user environment variable."""
        return auth.create_env_var(self.client, name, value)

    def delete_env_var(self, name: str) -> dict:
        """Delete a user environment variable."""
        return auth.delete_env_var(self.client, name)

    def show_scheduled_jobs(self) -> list[dict]:
        """Show scheduled jobs for the account."""
        return auth.show_scheduled_jobs(self.client)

    def create_scheduled_job(self, start_time, end_time, api_endpoint, request_method,
                             request_body, frequency, instance_id, **kwargs) -> dict:
        """Create a new scheduled job."""
        return auth.create_scheduled_job(
            self.client, start_time, end_time, api_endpoint, request_method,
            request_body, frequency, instance_id, **kwargs,
        )

    def update_scheduled_job(self, id: int, request_body, **kwargs) -> dict:
        """Update an existing scheduled job."""
        return auth.update_scheduled_job(self.client, id, request_body, **kwargs)

    def delete_scheduled_job(self, id: int) -> dict:
        """Delete a scheduled job."""
        return auth.delete_scheduled_job(self.client, id)

    def create_template(self, **kwargs) -> dict:
        """Create a new template.

        Accepts user-friendly kwargs (jupyter, ssh, direct, login, etc.)
        and translates them to the API parameters.
        """
        jupyter = kwargs.pop("jupyter", False)
        ssh = kwargs.pop("ssh", False)
        direct = kwargs.pop("direct", False)
        login = kwargs.pop("login", None)
        hide_readme = kwargs.pop("hide_readme", False)
        public = kwargs.pop("public", False)
        jupyter_lab = kwargs.pop("jupyter_lab", False)
        # Remove kwargs not accepted by offers.create_template
        kwargs.pop("search_params", None)
        kwargs.pop("no_default", None)

        jup_direct = jupyter and direct
        ssh_direct = ssh and direct
        use_ssh = ssh or jupyter
        runtype = "jupyter" if jupyter else ("ssh" if ssh else "args")

        docker_login_repo = None
        if login:
            docker_login_repo = login.split(" ")[0]

        return offers.create_template(
            self.client,
            jup_direct=jup_direct,
            ssh_direct=ssh_direct,
            use_ssh=use_ssh,
            use_jupyter_lab=jupyter_lab,
            runtype=runtype,
            docker_login_repo=docker_login_repo,
            readme_visible=not hide_readme,
            private=not public,
            **kwargs,
        )

    def delete_template(self, template_id: Optional[int] = None, hash_id: Optional[str] = None) -> dict:
        """Delete a template by ID or hash."""
        return offers.delete_template(self.client, template_id=template_id, hash_id=hash_id)

    def update_template(self, hash_id: str, **kwargs) -> dict:
        """Update an existing template."""
        return offers.update_template(self.client, hash_id=hash_id, **kwargs)

    # ------------------------------------------------------------------
    # Batch instance methods
    # ------------------------------------------------------------------

    def create_instances(self, ids: List[int], **kwargs) -> dict:
        """Create multiple instances from a list of offer IDs."""
        return instances.create_instance(self.client, id=ids, **kwargs)

    def destroy_instances(self, ids: List[int]) -> dict:
        """Destroy multiple instances."""
        return instances.destroy_instance(self.client, id=ids)

    def start_instances(self, ids: List[int]) -> dict:
        """Start multiple instances."""
        return instances.start_instance(self.client, id=ids)

    def stop_instances(self, ids: List[int]) -> dict:
        """Stop multiple instances."""
        return instances.stop_instance(self.client, id=ids)

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    def update_endpoint(self, id: int, **kwargs) -> dict:
        """Update an existing endpoint."""
        return endpoints.update_endpoint(self.client, id=id, **kwargs)

    def update_env_var(self, name: str, value: str) -> dict:
        """Update an existing user environment variable."""
        return auth.update_env_var(self.client, name, value)

    def update_instance(self, id: int, **kwargs) -> dict:
        """Update/recreate an instance from a new/updated template."""
        return instances.update_instance(self.client, id=id, **kwargs)

    def update_workergroup(self, id: int, **kwargs) -> dict:
        """Update an existing autoscale worker group."""
        return endpoints.update_workergroup(self.client, id=id, **kwargs)

    def update_team_role(self, id: int, **kwargs) -> dict:
        """Update an existing team role."""
        return teams.update_team_role(self.client, id=id, **kwargs)

    # ------------------------------------------------------------------
    # TFA (Two-Factor Authentication) methods
    # ------------------------------------------------------------------

    def tfa_activate(self, **kwargs) -> dict:
        """Activate a new 2FA method by verifying the code."""
        return auth.tfa_activate(self.client, **kwargs)

    def tfa_delete(self, **kwargs) -> dict:
        """Remove a 2FA method from your account."""
        return auth.tfa_delete(self.client, **kwargs)

    def tfa_login(self, **kwargs) -> dict:
        """Complete 2FA login by verifying code."""
        return auth.tfa_login(self.client, **kwargs)

    def tfa_regen_codes(self, **kwargs) -> dict:
        """Regenerate backup codes for 2FA."""
        return auth.tfa_regen_codes(self.client, **kwargs)

    def tfa_resend_sms(self, **kwargs) -> dict:
        """Resend SMS 2FA code."""
        return auth.tfa_resend_sms(self.client, **kwargs)

    def tfa_send_sms(self, **kwargs) -> dict:
        """Request a 2FA SMS verification code."""
        return auth.tfa_send_sms(self.client, **kwargs)

    def tfa_status(self) -> dict:
        """Show the current 2FA status and configured methods."""
        return auth.tfa_status(self.client)

    def tfa_totp_setup(self) -> dict:
        """Generate TOTP secret and QR code for Authenticator app setup."""
        return auth.tfa_totp_setup(self.client)

    def tfa_update(self, **kwargs) -> dict:
        """Update a 2FA method's settings."""
        return auth.tfa_update(self.client, **kwargs)

    # ------------------------------------------------------------------
    # Additional billing methods
    # ------------------------------------------------------------------

    def generate_pdf_invoices(self, **kwargs):
        """Generate PDF invoices based on filters."""
        raise NotImplementedError("generate_pdf_invoices is not yet implemented")

    def show_invoices_v1(self, **kwargs) -> dict:
        """Get billing history reports with advanced filtering and pagination."""
        return billing.show_invoices_v1(self.client, kwargs)

    def transfer_credit(self, recipient: str, amount: float) -> dict:
        """Transfer credit to another account."""
        return teams.transfer_credit(self.client, recipient=recipient, amount=amount)

    # ------------------------------------------------------------------
    # Additional methods
    # ------------------------------------------------------------------

    def list_volumes(self, ids, **kwargs) -> dict:
        """List disk space for rent as volumes on multiple machines."""
        return storage.list_volumes(self.client, ids=ids, **kwargs)

    def self_test_machine(self, machine_id, **kwargs):
        """Perform a self-test on the specified machine."""
        raise NotImplementedError("self_test_machine requires CLI")

    # ------------------------------------------------------------------
    # Backward-compatible aliases
    # ------------------------------------------------------------------

    invite_team_member = invite_member
    remove_team_member = remove_member
    show_team_members = show_members
