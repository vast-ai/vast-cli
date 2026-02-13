from abc import ABC
from typing import Any


class VastAIBase(ABC):
    """VastAI SDK base class that defines the methods to be implemented by the VastAI class."""

    def attach_ssh(self, instance_id: int, ssh_key: str) -> dict[str, Any]:
        """Attach an SSH key to an instance."""
        pass

    def cancel_copy(self, dst: str) -> dict[str, Any]:
        """Cancel a file copy operation."""
        pass

    def cancel_sync(self, dst: str) -> dict[str, Any]:
        """Cancel a file sync operation."""
        pass

    def change_bid(self, id: int, price: float | None = None) -> dict[str, Any]:
        """Change the bid price for a machine."""
        pass

    def copy(self, src: str, dst: str, identity: str | None = None) -> dict[str, Any]:
        """Copy files between instances."""
        pass

    def cloud_copy(
        self,
        src: str | None = None,
        dst: str | None = "/workspace",
        instance: str | None = None,
        connection: str | None = None,
        transfer: str = "Instance to Cloud",
    ) -> dict[str, Any]:
        """Copy files between cloud and instance."""
        pass

    def create_api_key(
        self,
        name: str | None = None,
        permission_file: str | None = None,
        key_params: str | None = None,
    ) -> dict[str, Any]:
        """Create a new API key."""
        pass

    def create_ssh_key(self, ssh_key: str) -> dict[str, Any]:
        """Create a new SSH key."""
        pass

    def create_workergroup(
        self,
        test_workers: int = 3,
        gpu_ram: float | None = None,
        template_hash: str | None = None,
        template_id: int | None = None,
        search_params: str | None = None,
        launch_args: str | None = None,
        endpoint_name: str | None = None,
        endpoint_id: int | None = None,
        min_load: float | None = None,
        target_util: float | None = None,
        cold_mult: float | None = None,
    ) -> dict[str, Any]:
        """Create a new workergroup (autoscaler)."""
        pass

    # Backwards compatibility alias (deprecated: use create_workergroup)
    create_autogroup = create_workergroup

    def create_endpoint(
        self,
        min_load: float = 0.0,
        target_util: float = 0.9,
        cold_mult: float = 2.5,
        cold_workers: int = 5,
        max_workers: int = 20,
        endpoint_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new serverless endpoint."""
        pass

    def create_instance(
        self,
        id: int,
        price: float | None = None,
        disk: float | None = 10,
        image: str | None = None,
        login: str | None = None,
        label: str | None = None,
        onstart: str | None = None,
        onstart_cmd: str | None = None,
        entrypoint: str | None = None,
        ssh: bool = False,
        jupyter: bool = False,
        direct: bool = False,
        jupyter_dir: str | None = None,
        jupyter_lab: bool = False,
        lang_utf8: bool = False,
        python_utf8: bool = False,
        extra: str | None = None,
        env: str | None = None,
        args: list[str] | None = None,
        force: bool = False,
        cancel_unavail: bool = False,
        template_hash: str | None = None,
    ) -> dict[str, Any]:
        """Create a new instance from a contract offer ID."""
        pass

    def create_subaccount(
        self,
        email: str | None = None,
        username: str | None = None,
        password: str | None = None,
        type: str | None = None,
    ) -> dict[str, Any]:
        """Create a new subaccount."""
        pass

    def create_team(self, team_name: str | None = None) -> dict[str, Any]:
        """Create a new team."""
        pass

    def create_team_role(
        self, name: str | None = None, permissions: str | None = None
    ) -> dict[str, Any]:
        """Create a new team role."""
        pass

    def create_template(
        self,
        name: str | None = None,
        image: str | None = None,
        image_tag: str | None = None,
        login: str | None = None,
        env: str | None = None,
        ssh: bool = False,
        jupyter: bool = False,
        direct: bool = False,
        jupyter_dir: str | None = None,
        jupyter_lab: bool = False,
        onstart_cmd: str | None = None,
        search_params: str | None = None,
        disk_space: str | None = None,
    ) -> dict[str, Any]:
        """Create a new template."""
        pass

    def delete_api_key(self, id: int) -> dict[str, Any]:
        """Delete an API key."""
        pass

    def delete_ssh_key(self, id: int) -> dict[str, Any]:
        """Delete an SSH key."""
        pass

    def delete_workergroup(self, id: int) -> dict[str, Any]:
        """Delete a workergroup."""
        pass

    # Backwards compatibility alias (deprecated: use delete_workergroup)
    delete_autoscaler = delete_workergroup

    def delete_endpoint(self, id: int) -> dict[str, Any]:
        """Delete a serverless endpoint."""
        pass

    def destroy_instance(self, id: int) -> dict[str, Any]:
        """Destroy an instance."""
        pass

    def destroy_instances(self, ids: list[int]) -> dict[str, Any]:
        """Destroy multiple instances."""
        pass

    def destroy_team(self) -> dict[str, Any]:
        """Destroy the current team."""
        pass

    def detach_ssh(self, instance_id: int, ssh_key_id: str) -> dict[str, Any]:
        """Detach an SSH key from an instance."""
        pass

    def execute(self, id: int, COMMAND: str) -> dict[str, Any]:
        """Execute a command on an instance."""
        pass

    def invite_team_member(
        self, email: str | None = None, role: str | None = None
    ) -> dict[str, Any]:
        """Invite a new member to the team."""
        pass

    def label_instance(self, id: int, label: str) -> dict[str, Any]:
        """Label an instance."""
        pass

    def launch_instance(
        gpu_name: str,
        num_gpus: str,
        image: str,
        region: str = None,
        disk: float = 16.0,
        limit: int = 3,
        order: str = "score-",
        login: str = None,
        label: str = None,
        onstart: str = None,
        onstart_cmd: str = None,
        entrypoint: str = None,
        ssh: bool = False,
        jupyter: bool = False,
        direct: bool = False,
        jupyter_dir: str = None,
        jupyter_lab: bool = False,
        lang_utf8: bool = False,
        python_utf8: bool = False,
        extra: str = None,
        env: str = None,
        args: list[str] | None = None,
        force: bool = False,
        cancel_unavail: bool = False,
        template_hash: str = None,
        explain: bool = False,
        raw: bool = False,
    ) -> dict[str, Any]:
        """
        Launches the top instance from the search offers based on the given parameters.

        Returns:
            str: Confirmation message of the instance launch or details about the operation.
        """
        pass

    def logs(self, INSTANCE_ID: int, tail: str | None = None) -> dict[str, Any]:
        """Retrieve logs for an instance."""
        pass

    def prepay_instance(self, id: int, amount: float) -> dict[str, Any]:
        """Prepay for an instance."""
        pass

    def reboot_instance(self, id: int) -> dict[str, Any]:
        """Reboot an instance."""
        pass

    def recycle_instance(self, id: int) -> dict[str, Any]:
        """Recycle an instance."""
        pass

    def remove_team_member(self, id: int) -> dict[str, Any]:
        """Remove a member from the team."""
        pass

    def remove_team_role(self, NAME: str) -> dict[str, Any]:
        """Remove a role from the team."""
        pass

    def reports(self, id: int) -> dict[str, Any]:
        """Generate reports for a machine."""
        pass

    def reset_api_key(self) -> dict[str, Any]:
        """Reset the API key."""
        pass

    def start_instance(self, id: int) -> dict[str, Any]:
        """Start an instance."""
        pass

    def start_instances(self, ids: list[int]) -> dict[str, Any]:
        """Start multiple instances."""
        pass

    def stop_instance(self, id: int) -> dict[str, Any]:
        """Stop an instance."""
        pass

    def stop_instances(self, ids: list[int]) -> dict[str, Any]:
        """Stop multiple instances."""
        pass

    def search_benchmarks(self, query: str | None = None) -> list[dict[str, Any]]:
        """Search for benchmarks based on a query."""
        pass

    def search_invoices(self, query: str | None = None) -> list[dict[str, Any]]:
        """Search for invoices based on a query."""
        pass

    def search_offers(
        self,
        type: str | None = None,
        no_default: bool = False,
        new: bool = False,
        limit: int | None = None,
        disable_bundling: bool = False,
        storage: float | None = None,
        order: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for offers based on various criteria."""
        pass

    def search_templates(self, query: str | None = None) -> list[dict[str, Any]]:
        """Search for templates based on a query."""
        pass

    def set_api_key(self, new_api_key: str) -> dict[str, Any]:
        """Set a new API key."""
        pass

    def set_user(self, file: str | None = None) -> dict[str, Any]:
        """Set user parameters from a file."""
        pass

    def ssh_url(self, id: int) -> dict[str, Any]:
        """Get the SSH URL for an instance."""
        pass

    def scp_url(self, id: int) -> dict[str, Any]:
        """Get the SCP URL for transferring files to/from an instance."""
        pass

    def show_api_key(self, id: int) -> dict[str, Any]:
        """Show details of an API key."""
        pass

    def show_api_keys(self) -> list[dict[str, Any]]:
        """Show all API keys."""
        pass

    def show_ssh_keys(self) -> list[dict[str, Any]]:
        """Show all SSH keys."""
        pass

    def show_workergroups(self) -> list[dict[str, Any]]:
        """Show all workergroups (autoscalers)."""
        pass

    # Backwards compatibility alias (deprecated: use show_workergroups)
    show_autoscalers = show_workergroups

    def show_endpoints(self) -> list[dict[str, Any]]:
        """Show all endpoints."""
        pass

    def show_connections(self) -> list[dict[str, Any]]:
        """Show all connections."""
        pass

    def show_deposit(self, Id: int) -> dict[str, Any]:
        """Show deposit details for an instance."""
        pass

    def show_earnings(
        self,
        quiet: bool = False,
        start_date: str | None = None,
        end_date: str | None = None,
        machine_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Show earnings information."""
        pass

    def show_invoices(
        self,
        quiet: bool = False,
        start_date: str | None = None,
        end_date: str | None = None,
        only_charges: bool = False,
        only_credits: bool = False,
        instance_label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Show invoice details."""
        pass

    def show_instance(self, id: int) -> dict[str, Any]:
        """Show details of an instance."""
        pass

    def show_instances(self, quiet: bool = False) -> list[dict[str, Any]]:
        """Show all instances."""
        pass

    def show_ipaddrs(self) -> list[dict[str, Any]]:
        """Show IP addresses."""
        pass

    def show_user(self, quiet: bool = False) -> dict[str, Any]:
        """Show user details."""
        pass

    def show_subaccounts(self, quiet: bool = False) -> list[dict[str, Any]]:
        """Show all subaccounts of the current user."""
        pass

    def show_team_members(self) -> list[dict[str, Any]]:
        """Show all team members."""
        pass

    def show_team_role(self, NAME: str) -> dict[str, Any]:
        """Show details of a specific team role."""
        pass

    def show_team_roles(self) -> list[dict[str, Any]]:
        """Show all team roles."""
        pass

    def transfer_credit(self, recipient: str, amount: float) -> dict[str, Any]:
        """Transfer credit to another account."""
        pass

    def update_workergroup(
        self,
        id: int,
        min_load: float | None = None,
        target_util: float | None = None,
        cold_mult: float | None = None,
        test_workers: int | None = None,
        gpu_ram: float | None = None,
        template_hash: str | None = None,
        template_id: int | None = None,
        search_params: str | None = None,
        launch_args: str | None = None,
        endpoint_name: str | None = None,
        endpoint_id: int | None = None,
    ) -> dict[str, Any]:
        """Update a workergroup (autoscaler)."""
        pass

    # Backwards compatibility alias (deprecated: use update_workergroup)
    update_autoscaler = update_workergroup

    def update_endpoint(
        self,
        id: int,
        min_load: float | None = None,
        target_util: float | None = None,
        cold_mult: float | None = None,
        cold_workers: int | None = None,
        max_workers: int | None = None,
        endpoint_name: str | None = None,
    ) -> dict[str, Any]:
        """Update a serverless endpoint configuration."""
        pass

    def update_team_role(
        self, id: int, name: str | None = None, permissions: str | None = None
    ) -> dict[str, Any]:
        """Update details of a team role."""
        pass

    def update_ssh_key(self, id: int, ssh_key: str) -> dict[str, Any]:
        """Update an SSH key."""
        pass

    def generate_pdf_invoices(
        self,
        quiet: bool = False,
        start_date: str | None = None,
        end_date: str | None = None,
        only_charges: bool = False,
        only_credits: bool = False,
    ) -> dict[str, Any]:
        """Generate PDF invoices based on filters."""
        pass

    def cleanup_machine(self, id: int) -> dict[str, Any]:
        """Clean up a machine's configuration and resources."""
        pass

    def list_machine(
        self,
        id: int,
        price_gpu: float | None = None,
        price_disk: float | None = None,
        price_inetu: float | None = None,
        price_inetd: float | None = None,
        discount_rate: float | None = None,
        min_chunk: int | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """List details of a single machine with optional pricing and configuration parameters."""
        pass

    def list_machines(
        self,
        ids: list[int],
        price_gpu: float | None = None,
        price_disk: float | None = None,
        price_inetu: float | None = None,
        price_inetd: float | None = None,
        discount_rate: float | None = None,
        min_chunk: int | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """List details of multiple machines with optional pricing and configuration parameters."""
        pass

    def remove_defjob(self, id: int) -> dict[str, Any]:
        """Remove the default job from a machine."""
        pass

    def set_defjob(
        self,
        id: int,
        price_gpu: float | None = None,
        price_inetu: float | None = None,
        price_inetd: float | None = None,
        image: str | None = None,
        args: list[str] | None = None,
    ) -> dict[str, Any]:
        """Set a default job on a machine with specified parameters."""
        pass

    def set_min_bid(self, id: int, price: float | None = None) -> dict[str, Any]:
        """Set the minimum bid price for a machine."""
        pass

    def schedule_maint(
        self, id: int, sdate: float | None = None, duration: float | None = None
    ) -> dict[str, Any]:
        """Schedule maintenance for a machine."""
        pass

    def cancel_maint(self, id: int) -> dict[str, Any]:
        """Cancel scheduled maintenance for a machine."""
        pass

    def unlist_machine(self, id: int) -> dict[str, Any]:
        """Unlist a machine from being available for new jobs."""
        pass

    def show_machines(self, quiet: bool = False, filter: str | None = None) -> list[dict[str, Any]]:
        """
        Retrieve and display a list of machines based on specified criteria.

        Parameters:
        - quiet (bool): If True, limit the output to minimal details such as IDs.
        - filter (str, optional): A string used to filter the machines based on specific criteria.

        Returns:
        - list[dict[str, Any]]: A list of machine information dictionaries.
        """
        pass

    # Volume Methods

    def clone_volume(
        self,
        source: int,
        dest: int,
        size: float | None = None,
        disable_compression: bool = False,
    ) -> dict[str, Any]:
        """Clone an existing volume to a new location.

        Args:
            source: ID of the volume contract being cloned.
            dest: ID of the volume offer the volume is being copied to.
            size: Size of the new volume contract in GB. Must be >= source and <= dest offer.
            disable_compression: If True, do not compress volume data before copying.

        Returns:
            Confirmation message or volume creation details.
        """
        pass

    def create_volume(
        self,
        id: int,
        size: float = 15,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new volume from an offer ID.

        Args:
            id: ID of the volume offer (from search volumes).
            size: Size in GB of the volume. Default is 15 GB.
            name: Optional name for the volume.

        Returns:
            Confirmation message with volume creation details.
        """
        pass

    def delete_volume(self, id: int) -> dict[str, Any]:
        """Delete a volume.

        Args:
            id: ID of the volume contract to delete.

        Returns:
            Confirmation message of deletion.
        """
        pass

    def list_volume(
        self,
        id: int,
        price_disk: float = 0.10,
        size: int = 15,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """List disk space for rent as a volume on a machine.

        Args:
            id: ID of the machine to list volume on.
            price_disk: Storage price in $/GB/month. Default is $0.10/GB/month.
            size: Size of disk space allocated to offer in GB. Default is 15 GB.
            end_date: Contract offer expiration date (unix timestamp or MM/DD/YYYY format).

        Returns:
            Confirmation message with listing details.
        """
        pass

    def list_volumes(
        self,
        ids: list[int],
        price_disk: float = 0.10,
        size: int = 15,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """List disk space for rent as volumes on multiple machines.

        Args:
            ids: List of machine IDs to list volumes on.
            price_disk: Storage price in $/GB/month. Default is $0.10/GB/month.
            size: Size of disk space allocated to offer in GB. Default is 15 GB.
            end_date: Contract offer expiration date (unix timestamp or MM/DD/YYYY format).

        Returns:
            Confirmation message with listing details.
        """
        pass

    def search_volumes(
        self,
        query: str | None = None,
        no_default: bool = False,
        limit: int | None = None,
        storage: float = 1.0,
        order: str = "score-",
    ) -> list[dict[str, Any]]:
        """Search for volume offers using custom query.

        Args:
            query: Query string for filtering volumes.
            no_default: If True, disable default query filters.
            limit: Maximum number of results to return.
            storage: Amount of storage for pricing in GiB. Default is 1.0 GiB.
            order: Comma-separated list of fields to sort on. Default is 'score-'.

        Returns:
            List of matching volume offers.
        """
        pass

    def show_volumes(self, type: str = "all") -> list[dict[str, Any]]:
        """Show stats on owned volumes.

        Args:
            type: Volume type to display. Options: 'local', 'network', 'all'. Default is 'all'.

        Returns:
            List of owned volumes with their details.
        """
        pass

    def unlist_volume(self, id: int) -> dict[str, Any]:
        """Unlist a volume offer.

        Args:
            id: Volume ID to unlist.

        Returns:
            Confirmation message of unlisting.
        """
        pass

    # Network Volume Methods

    def create_network_volume(
        self,
        id: int,
        size: float = 15,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new network volume from an offer ID.

        Args:
            id: ID of the network volume offer (from search network volumes).
            size: Size in GB of the network volume. Default is 15 GB.
            name: Optional name for the network volume.

        Returns:
            Confirmation message with network volume creation details.
        """
        pass

    def list_network_volume(
        self,
        disk_id: int,
        price_disk: float = 0.15,
        size: int = 15,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """List disk space for rent as a network volume.

        Args:
            disk_id: ID of the network disk to list.
            price_disk: Storage price in $/GB/month. Default is $0.15/GB/month.
            size: Size of disk space allocated to offer in GB. Default is 15 GB.
            end_date: Contract offer expiration date (unix timestamp or MM/DD/YYYY format).

        Returns:
            Confirmation message with listing details.
        """
        pass

    def search_network_volumes(
        self,
        query: str | None = None,
        no_default: bool = False,
        limit: int | None = None,
        storage: float = 1.0,
        order: str = "score-",
    ) -> list[dict[str, Any]]:
        """Search for network volume offers using custom query.

        Args:
            query: Query string for filtering network volumes.
            no_default: If True, disable default query filters.
            limit: Maximum number of results to return.
            storage: Amount of storage for pricing in GiB. Default is 1.0 GiB.
            order: Comma-separated list of fields to sort on. Default is 'score-'.

        Returns:
            List of matching network volume offers.
        """
        pass

    def unlist_network_volume(self, id: int) -> dict[str, Any]:
        """Unlist a network volume offer.

        Args:
            id: Network volume offer ID to unlist.

        Returns:
            Confirmation message of unlisting.
        """
        pass

    # Cluster Methods

    def create_cluster(
        self,
        subnet: str,
        manager_id: int,
    ) -> dict[str, Any]:
        """Create a new Vast cluster.

        Args:
            subnet: Local subnet for cluster (e.g., '0.0.0.0/24').
            manager_id: Machine ID of manager node in cluster. Must exist already.

        Returns:
            Confirmation message with cluster creation details.
        """
        pass

    def delete_cluster(self, cluster_id: int) -> dict[str, Any]:
        """Delete a cluster.

        Args:
            cluster_id: ID of the cluster to delete.

        Returns:
            Confirmation message of deletion.
        """
        pass

    def join_cluster(
        self,
        cluster_id: int,
        machine_ids: list[int],
    ) -> dict[str, Any]:
        """Join machines to a cluster.

        Args:
            cluster_id: ID of the cluster to add machines to.
            machine_ids: List of machine IDs to join to the cluster.

        Returns:
            Confirmation message of machines joining cluster.
        """
        pass

    def show_clusters(self) -> list[dict[str, Any]]:
        """Show clusters associated with your account.

        Returns:
            List of clusters with their details (id, subnet, node count, etc.).
        """
        pass

    # Overlay Methods

    def create_overlay(
        self,
        cluster_id: int,
        name: str,
    ) -> dict[str, Any]:
        """Create an overlay network on top of a physical cluster.

        Args:
            cluster_id: ID of the cluster to create overlay on.
            name: Overlay network name.

        Returns:
            Confirmation message with overlay creation details.
        """
        pass

    def delete_overlay(self, overlay_identifier: str) -> dict[str, Any]:
        """Delete an overlay network.

        Args:
            overlay_identifier: ID (int) or name (str) of the overlay to delete.

        Returns:
            Confirmation message of deletion.
        """
        pass

    def join_overlay(
        self,
        name: str,
        instance_id: int,
    ) -> dict[str, Any]:
        """Add an instance to an overlay network.

        Args:
            name: Overlay network name to join instance to.
            instance_id: Instance ID to add to overlay.

        Returns:
            Confirmation message of instance joining overlay.
        """
        pass

    def show_overlays(self) -> list[dict[str, Any]]:
        """Show overlay networks associated with your account.

        Returns:
            List of overlays with their details (id, name, subnet, cluster_id, instances).
        """
        pass

    # Environment Variable Methods

    def create_env_var(
        self,
        name: str,
        value: str,
    ) -> dict[str, Any]:
        """Create a new user environment variable.

        Args:
            name: Environment variable name.
            value: Environment variable value.

        Returns:
            Confirmation message with creation details.
        """
        pass

    def delete_env_var(self, name: str) -> dict[str, Any]:
        """Delete an environment variable.

        Args:
            name: Name of the environment variable to delete.

        Returns:
            Confirmation message of deletion.
        """
        pass

    def update_env_var(
        self,
        name: str,
        value: str,
    ) -> dict[str, Any]:
        """Update an existing environment variable.

        Args:
            name: Environment variable name to update.
            value: New value for the environment variable.

        Returns:
            Confirmation message with update details.
        """
        pass

    def show_env_vars(self, show_values: bool = False) -> list[dict[str, Any]]:
        """Show user environment variables.

        Args:
            show_values: If True, display actual values. Default is False (masked).

        Returns:
            List of environment variables (values masked unless show_values=True).
        """
        pass

    # Miscellaneous Methods

    def create_account(
        self,
        email: str,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        """Create a new account.

        Note: This command is deprecated. Use the web interface instead.

        Args:
            email: Email address for the new account.
            username: Username for the new account.
            password: Password for the new account.

        Returns:
            Deprecation message.
        """
        pass

    def add_network_disk(
        self,
        instance_id: int,
        volume_id: int,
        mount_path: str = "/mnt/network",
    ) -> dict[str, Any]:
        """Add a network disk (volume) to an instance.

        Args:
            instance_id: ID of the instance to add the network disk to.
            volume_id: ID of the network volume to attach.
            mount_path: Path where the volume will be mounted. Default is '/mnt/network'.

        Returns:
            Confirmation message with attachment details.
        """
        pass

    # Machine Management Methods

    def defrag_machines(self, ids: list[int]) -> dict[str, Any]:
        """Defragment machines to optimize GPU assignments.

        Rearranges GPU assignments to make more multi-GPU offers available.

        Args:
            ids: List of machine IDs to defragment.

        Returns:
            Defragment result message.
        """
        pass

    def delete_machine(self, id: int) -> dict[str, Any]:
        """Delete a machine if not in use by clients.

        Force deletes a machine, disregarding host jobs on own machines.

        Args:
            id: ID of the machine to delete.

        Returns:
            Confirmation message of deletion.
        """
        pass

    def self_test_machine(
        self,
        machine_id: int,
        debugging: bool = False,
        ignore_requirements: bool = False,
    ) -> dict[str, Any]:
        """Perform a self-test on a machine.

        Verifies machine compliance with required specifications and functionality.

        Args:
            machine_id: ID of the machine to test.
            debugging: Enable debugging output. Default is False.
            ignore_requirements: Ignore minimum system requirements. Default is False.

        Returns:
            Self-test results.
        """
        pass

    def show_machine(self, id: int, quiet: bool = False) -> dict[str, Any]:
        """Show details of a single machine.

        Args:
            id: ID of the machine to display.
            quiet: If True, only display numeric IDs. Default is False.

        Returns:
            Machine details.
        """
        pass

    # Template Methods

    def delete_template(
        self,
        template_id: int | None = None,
        hash_id: str | None = None,
    ) -> dict[str, Any]:
        """Delete a template by ID or hash.

        Note: Deleting a template only removes the user's relationship to a template.

        Args:
            template_id: Template ID to delete.
            hash_id: Hash ID of template to delete.

        Returns:
            Confirmation message.
        """
        pass

    def update_template(
        self,
        hash_id: str,
        name: str | None = None,
        image: str | None = None,
        image_tag: str | None = None,
        login: str | None = None,
        env: str | None = None,
        ssh: bool = False,
        jupyter: bool = False,
        direct: bool = False,
        jupyter_dir: str | None = None,
        jupyter_lab: bool = False,
        onstart_cmd: str | None = None,
        search_params: str | None = None,
        disk_space: str | None = None,
        no_default: bool = False,
    ) -> dict[str, Any]:
        """Update an existing template.

        Args:
            hash_id: Hash ID of the template to update.
            name: New name for the template.
            image: Docker image for the template.
            image_tag: Image tag.
            login: Docker login credentials.
            env: Environment variables string.
            ssh: Enable SSH access.
            jupyter: Enable Jupyter.
            direct: Enable direct port access.
            jupyter_dir: Jupyter working directory.
            jupyter_lab: Use JupyterLab instead of Jupyter Notebook.
            onstart_cmd: Command to run on startup.
            search_params: Search parameters for matching offers.
            disk_space: Recommended disk space.
            no_default: Disable default query filters.

        Returns:
            Update confirmation message.
        """
        pass

    # Snapshot Methods

    def take_snapshot(
        self,
        instance_id: int,
        repo: str | None = None,
        container_registry: str = "docker.io",
        docker_login_user: str | None = None,
        docker_login_pass: str | None = None,
        pause: str = "true",
    ) -> dict[str, Any]:
        """Take a container snapshot and push to registry.

        Args:
            instance_id: ID of the instance to snapshot.
            repo: Docker repository to push snapshot to.
            container_registry: Container registry URL. Default is 'docker.io'.
            docker_login_user: Registry username.
            docker_login_pass: Registry password or token.
            pause: Pause container during commit ('true'/'false'). Default is 'true'.

        Returns:
            Snapshot scheduling confirmation.
        """
        pass

    # Instance Update Methods

    def update_instance(
        self,
        id: int,
        template_id: int | None = None,
        template_hash_id: str | None = None,
        image: str | None = None,
        args: str | None = None,
        env: str | None = None,
        onstart: str | None = None,
    ) -> dict[str, Any]:
        """Update instance configuration from a new/updated template.

        Args:
            id: ID of the instance to update.
            template_id: New template ID to associate.
            template_hash_id: New template hash ID to associate.
            image: New image UUID.
            args: New arguments for the instance.
            env: New environment variables.
            onstart: New onstart script.

        Returns:
            Update confirmation message.
        """
        pass

    # VM Copy Methods

    def vm_copy(self, src: int, dst: int) -> dict[str, Any]:
        """Copy VM image from one instance to another.

        Note: Destination VM must be stopped during copy. Source VM does not need
        to be stopped, but it's recommended to stop it for the duration.

        Args:
            src: Instance ID of the source VM.
            dst: Instance ID of the destination VM.

        Returns:
            Copy operation confirmation.
        """
        pass

    # Team Member Methods

    def invite_member(
        self,
        email: str,
        role: str | None = None,
    ) -> dict[str, Any]:
        """Invite a member to the team.

        Args:
            email: Email address of the user to invite.
            role: Role to assign to the invited user.

        Returns:
            Invitation confirmation message.
        """
        pass

    def remove_member(self, id: int) -> dict[str, Any]:
        """Remove a member from the team.

        Args:
            id: ID of the team member to remove.

        Returns:
            Removal confirmation message.
        """
        pass

    def show_members(self) -> list[dict[str, Any]]:
        """Show team members.

        Returns:
            List of team members.
        """
        pass

    # Log Methods

    def get_endpt_logs(
        self,
        id: int,
        level: int = 1,
        tail: int | None = None,
    ) -> dict[str, Any]:
        """Get logs for a serverless endpoint.

        Args:
            id: ID of the endpoint group to fetch logs from.
            level: Log detail level (0-3). Default is 1.
            tail: Number of log lines to return from the end.

        Returns:
            Endpoint logs.
        """
        pass

    def get_wrkgrp_logs(
        self,
        id: int,
        level: int = 1,
        tail: int | None = None,
    ) -> dict[str, Any]:
        """Get logs for a serverless worker group.

        Args:
            id: ID of the worker group to fetch logs from.
            level: Log detail level (0-3). Default is 1.
            tail: Number of log lines to return from the end.

        Returns:
            Worker group logs.
        """
        pass

    def show_audit_logs(self) -> list[dict[str, Any]]:
        """Show account audit logs.

        Displays history of important actions and IP address accesses.

        Returns:
            List of audit log entries.
        """
        pass

    # Scheduled Job Methods

    def delete_scheduled_job(self, id: int) -> dict[str, Any]:
        """Delete a scheduled job.

        Args:
            id: ID of the scheduled job to delete.

        Returns:
            Deletion confirmation message.
        """
        pass

    def show_scheduled_jobs(self) -> list[dict[str, Any]]:
        """Show scheduled jobs.

        Returns:
            List of scheduled jobs for the account.
        """
        pass

    # Maintenance Methods

    def show_maints(self, ids: str, quiet: bool = False) -> list[dict[str, Any]]:
        """Show maintenance information for host machines.

        Args:
            ids: Comma-separated string of machine IDs.
            quiet: If True, only display numeric IDs. Default is False.

        Returns:
            Maintenance information for specified machines.
        """
        pass

    # Network Disk Methods

    def show_network_disks(self) -> list[dict[str, Any]]:
        """Show network disks associated with your account.

        Returns:
            Network disk information grouped by cluster.
        """
        pass

    # Invoice V1 Methods

    def show_invoices_v1(
        self,
        invoices: bool = False,
        charges: bool = False,
        invoice_type: list[str] | None = None,
        charge_type: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 20,
        next_token: str | None = None,
        format: str = "table",
        verbose: bool = False,
        latest_first: bool = False,
    ) -> dict[str, Any]:
        """Show invoices or charges with advanced filtering (v1 API).

        Args:
            invoices: Show invoices instead of charges.
            charges: Show charges instead of invoices.
            invoice_type: Filter by invoice types (transfers, stripe, bitpay, etc.).
            charge_type: Filter by charge types (instance, volume, serverless).
            start_date: Start date (YYYY-MM-DD or timestamp).
            end_date: End date (YYYY-MM-DD or timestamp).
            limit: Number of results per page (default: 20, max: 100).
            next_token: Pagination token for next page.
            format: Output format ('table' or 'tree'). Default is 'table'.
            verbose: Include full details (tree view only). Default is False.
            latest_first: Sort by latest first. Default is False.

        Returns:
            Invoice or charge information based on selected filters.
        """
        pass
