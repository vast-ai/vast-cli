from abc import ABC
from typing import Optional, List


class VastAIBase(ABC):
    """VastAI SDK base class that defines the methods to be implemented by the VastAI class."""

    def attach_ssh(self, instance_id: int, ssh_key: str) -> str:
        """Attach an SSH key to an instance."""
        pass

    def cancel_copy(self, dst: str) -> str:
        """Cancel a file copy operation."""
        pass

    def cancel_sync(self, dst: str) -> str:
        """Cancel a file sync operation."""
        pass

    def change_bid(self, id: int, price: Optional[float] = None) -> str:
        """Change the bid price for a machine."""
        pass

    def copy(self, src: str, dst: str, identity: Optional[str] = None) -> str:
        """Copy files between instances."""
        pass

    def cloud_copy(
        self,
        src: Optional[str] = None,
        dst: Optional[str] = "/workspace",
        instance: Optional[str] = None,
        connection: Optional[str] = None,
        transfer: str = "Instance to Cloud",
    ) -> str:
        """Copy files between cloud and instance."""
        pass

    def create_api_key(
        self,
        name: Optional[str] = None,
        permission_file: Optional[str] = None,
        key_params: Optional[str] = None,
    ) -> str:
        """Create a new API key."""
        pass

    def create_ssh_key(self, ssh_key: str) -> str:
        """Create a new SSH key."""
        pass

    def create_autoscaler(
        self,
        test_workers: int = 3,
        gpu_ram: Optional[float] = None,
        template_hash: Optional[str] = None,
        template_id: Optional[int] = None,
        search_params: Optional[str] = None,
        launch_args: Optional[str] = None,
        endpoint_name: Optional[str] = None,
        endpoint_id: Optional[int] = None,
        min_load: Optional[float] = None,
        target_util: Optional[float] = None,
        cold_mult: Optional[float] = None,
    ) -> str:
        """Create a new autoscaler."""
        pass

    def create_endpoint(
        self,
        min_load: float = 0.0,
        target_util: float = 0.9,
        cold_mult: float = 2.5,
        cold_workers: int = 5,
        max_workers: int = 20,
        endpoint_name: Optional[str] = None,
    ) -> str:
        pass

    def create_instance(
        self,
        id: int,
        price: Optional[float] = None,
        disk: Optional[float] = 10,
        image: Optional[str] = None,
        login: Optional[str] = None,
        label: Optional[str] = None,
        onstart: Optional[str] = None,
        onstart_cmd: Optional[str] = None,
        entrypoint: Optional[str] = None,
        ssh: bool = False,
        jupyter: bool = False,
        direct: bool = False,
        jupyter_dir: Optional[str] = None,
        jupyter_lab: bool = False,
        lang_utf8: bool = False,
        python_utf8: bool = False,
        extra: Optional[str] = None,
        env: Optional[str] = None,
        args: Optional[List[str]] = None,
        force: bool = False,
        cancel_unavail: bool = False,
        template_hash: Optional[str] = None,
    ) -> str:
        """Create a new instance from a contract offer ID."""
        pass

    def create_subaccount(
        self,
        email: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        type: Optional[str] = None,
    ) -> str:
        pass

    def create_team(self, team_name: Optional[str] = None) -> str:
        """Create a new team."""
        pass

    def create_team_role(
        self, name: Optional[str] = None, permissions: Optional[str] = None
    ) -> str:
        """Create a new team role."""
        pass

    def create_template(
        self,
        name: Optional[str] = None,
        image: Optional[str] = None,
        image_tag: Optional[str] = None,
        login: Optional[str] = None,
        env: Optional[str] = None,
        ssh: bool = False,
        jupyter: bool = False,
        direct: bool = False,
        jupyter_dir: Optional[str] = None,
        jupyter_lab: bool = False,
        onstart_cmd: Optional[str] = None,
        search_params: Optional[str] = None,
        disk_space: Optional[str] = None,
    ) -> str:
        """Create a new template."""
        pass

    def delete_api_key(self, id: int) -> str:
        pass

    def delete_ssh_key(self, id: int) -> str:
        pass

    def delete_autoscaler(self, id: int) -> str:
        pass

    def delete_endpoint(self, id: int) -> str:
        pass

    def destroy_instance(self, id: int) -> str:
        pass

    def destroy_instances(self, ids: List[int]) -> str:
        pass

    def destroy_team(self) -> str:
        pass

    def detach_ssh(self, instance_id: int, ssh_key_id: str) -> str:
        pass

    def execute(self, id: int, COMMAND: str) -> str:
        """Execute a command on an instance."""
        pass

    def invite_team_member(
        self, email: Optional[str] = None, role: Optional[str] = None
    ) -> str:
        """Invite a new member to the team."""
        pass

    def label_instance(self, id: int, label: str) -> str:
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
        args: list = None,
        force: bool = False,
        cancel_unavail: bool = False,
        template_hash: str = None,
        explain: bool = False,
        raw: bool = False,
    ) -> str:
        """
        Launches the top instance from the search offers based on the given parameters.

        Returns:
            str: Confirmation message of the instance launch or details about the operation.
        """
        pass

    def logs(self, INSTANCE_ID: int, tail: Optional[str] = None) -> str:
        """Retrieve logs for an instance."""
        pass

    def prepay_instance(self, id: int, amount: float) -> str:
        """Prepay for an instance."""
        pass

    def reboot_instance(self, id: int) -> str:
        """Reboot an instance."""
        pass

    def recycle_instance(self, id: int) -> str:
        """Recycle an instance."""
        pass

    def remove_team_member(self, id: int) -> str:
        """Remove a member from the team."""
        pass

    def remove_team_role(self, NAME: str) -> str:
        """Remove a role from the team."""
        pass

    def reports(self, id: int) -> str:
        """Generate reports for a machine."""
        pass

    def reset_api_key(self) -> str:
        """Reset the API key."""
        pass

    def start_instance(self, id: int) -> str:
        """Start an instance."""
        pass

    def start_instances(self, ids: List[int]) -> str:
        """Start multiple instances."""
        pass

    def stop_instance(self, id: int) -> str:
        """Stop an instance."""
        pass

    def stop_instances(self, ids: List[int]) -> str:
        """Stop multiple instances."""
        pass

    def search_benchmarks(self, query: Optional[str] = None) -> str:
        """Search for benchmarks based on a query."""
        pass

    def search_invoices(self, query: Optional[str] = None) -> str:
        """Search for invoices based on a query."""
        pass

    def search_offers(
        self,
        type: Optional[str] = None,
        no_default: bool = False,
        new: bool = False,
        limit: Optional[int] = None,
        disable_bundling: bool = False,
        storage: Optional[float] = None,
        order: Optional[str] = None,
        query: Optional[str] = None,
    ) -> str:
        """Search for offers based on various criteria."""
        pass

    def search_templates(self, query: Optional[str] = None) -> str:
        """Search for templates based on a query."""
        pass

    def set_api_key(self, new_api_key: str) -> str:
        """Set a new API key."""
        pass

    def set_user(self, file: Optional[str] = None) -> str:
        """Set user parameters from a file."""
        pass

    def ssh_url(self, id: int) -> str:
        """Get the SSH URL for an instance."""
        pass

    def scp_url(self, id: int) -> str:
        """Get the SCP URL for transferring files to/from an instance."""
        pass

    def show_api_key(self, id: int) -> str:
        """Show details of an API key."""
        pass

    def show_api_keys(self) -> str:
        """Show all API keys."""
        pass

    def show_ssh_keys(self) -> str:
        """Show all SSH keys."""
        pass

    def show_autoscalers(self) -> str:
        """Show all autoscalers."""
        pass

    def show_endpoints(self) -> str:
        """Show all endpoints."""
        pass

    def show_connections(self) -> str:
        """Show all connections."""
        pass

    def show_deposit(self, Id: int) -> str:
        """Show deposit details for an instance."""
        pass

    def show_earnings(
        self,
        quiet: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        machine_id: Optional[int] = None,
    ) -> str:
        """Show earnings information."""
        pass

    def show_invoices(
        self,
        quiet: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        only_charges: bool = False,
        only_credits: bool = False,
        instance_label: Optional[str] = None,
    ) -> str:
        """Show invoice details."""
        pass

    def show_instance(self, id: int) -> str:
        """Show details of an instance."""
        pass

    def show_instances(self, quiet: bool = False) -> str:
        """Show all instances."""
        pass

    def show_ipaddrs(self) -> str:
        """Show IP addresses."""
        pass

    def show_user(self, quiet: bool = False) -> str:
        """Show user details."""
        pass

    def show_subaccounts(self, quiet: bool = False) -> str:
        """Show all subaccounts of the current user."""
        pass

    def show_team_members(self) -> str:
        """Show all team members."""
        pass

    def show_team_role(self, NAME: str) -> str:
        """Show details of a specific team role."""
        pass

    def show_team_roles(self) -> str:
        """Show all team roles."""
        pass

    def transfer_credit(self, recipient: str, amount: float) -> str:
        """Transfer credit to another account."""
        pass

    def update_autoscaler(
        self,
        id: int,
        min_load: Optional[float] = None,
        target_util: Optional[float] = None,
        cold_mult: Optional[float] = None,
        test_workers: Optional[int] = None,
        gpu_ram: Optional[float] = None,
        template_hash: Optional[str] = None,
        template_id: Optional[int] = None,
        search_params: Optional[str] = None,
        launch_args: Optional[str] = None,
        endpoint_name: Optional[str] = None,
        endpoint_id: Optional[int] = None,
    ) -> str:
        pass

    def update_endpoint(
        self,
        id: int,
        min_load: Optional[float] = None,
        target_util: Optional[float] = None,
        cold_mult: Optional[float] = None,
        cold_workers: Optional[int] = None,
        max_workers: Optional[int] = None,
        endpoint_name: Optional[str] = None,
    ) -> str:
        pass

    def update_team_role(
        self, id: int, name: Optional[str] = None, permissions: Optional[str] = None
    ) -> str:
        """Update details of a team role."""
        pass

    def update_ssh_key(self, id: int, ssh_key: str) -> str:
        """Update an SSH key."""
        pass

    def generate_pdf_invoices(
        self,
        quiet: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        only_charges: bool = False,
        only_credits: bool = False,
    ) -> str:
        """Generate PDF invoices based on filters."""
        pass

    def cleanup_machine(self, id: int) -> str:
        """Clean up a machine's configuration and resources."""
        pass

    def list_machine(
        self,
        id: int,
        price_gpu: Optional[float] = None,
        price_disk: Optional[float] = None,
        price_inetu: Optional[float] = None,
        price_inetd: Optional[float] = None,
        discount_rate: Optional[float] = None,
        min_chunk: Optional[int] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """List details of a single machine with optional pricing and configuration parameters."""
        pass

    def list_machines(
        self,
        ids: List[int],
        price_gpu: Optional[float] = None,
        price_disk: Optional[float] = None,
        price_inetu: Optional[float] = None,
        price_inetd: Optional[float] = None,
        discount_rate: Optional[float] = None,
        min_chunk: Optional[int] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """List details of multiple machines with optional pricing and configuration parameters."""
        pass

    def remove_defjob(self, id: int) -> str:
        """Remove the default job from a machine."""
        pass

    def set_defjob(
        self,
        id: int,
        price_gpu: Optional[float] = None,
        price_inetu: Optional[float] = None,
        price_inetd: Optional[float] = None,
        image: Optional[str] = None,
        args: Optional[List[str]] = None,
    ) -> str:
        """Set a default job on a machine with specified parameters."""
        pass

    def set_min_bid(self, id: int, price: Optional[float] = None) -> str:
        """Set the minimum bid price for a machine."""
        pass

    def schedule_maint(
        self, id: int, sdate: Optional[float] = None, duration: Optional[float] = None
    ) -> str:
        """Schedule maintenance for a machine."""
        pass

    def cancel_maint(self, id: int) -> str:
        """Cancel scheduled maintenance for a machine."""
        pass

    def unlist_machine(self, id: int) -> str:
        """Unlist a machine from being available for new jobs."""
        pass

    def show_machines(self, quiet: bool = False, filter: Optional[str] = None) -> str:
        """
        Retrieve and display a list of machines based on specified criteria.

        Parameters:
        - quiet (bool): If True, limit the output to minimal details such as IDs.
        - filter (str, optional): A string used to filter the machines based on specific criteria.

        Returns:
        - str: A string representation of the machines information, possibly formatted as JSON or a human-readable list.
        """
        pass
