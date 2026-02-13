"""Unit tests for VastAIBase class method signatures and structure.

This module verifies that VastAIBase methods exist with correct signatures,
ensuring backwards compatibility and API contract stability.
"""

import pytest
import inspect
from abc import ABC
import sys
from pathlib import Path

# Add vast-cli to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vastai.vastai_base import VastAIBase


class TestVastAIBaseClassStructure:
    """Verify VastAIBase class structure and attributes."""

    def test_is_abstract_base_class(self):
        """VastAIBase should inherit from ABC."""
        assert issubclass(VastAIBase, ABC)

    def test_has_docstring(self):
        """VastAIBase should have a class docstring."""
        assert VastAIBase.__doc__ is not None
        assert len(VastAIBase.__doc__) > 0

    def test_docstring_mentions_sdk(self):
        """Docstring should describe SDK purpose."""
        assert "SDK" in VastAIBase.__doc__ or "sdk" in VastAIBase.__doc__.lower()


class TestVastAIBaseInstanceMethodSignatures:
    """Verify instance method signatures exist with correct parameters."""

    def test_attach_ssh_signature(self):
        """attach_ssh should have instance_id and ssh_key parameters."""
        sig = inspect.signature(VastAIBase.attach_ssh)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "instance_id" in params
        assert "ssh_key" in params

    def test_cancel_copy_signature(self):
        """cancel_copy should have dst parameter."""
        sig = inspect.signature(VastAIBase.cancel_copy)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "dst" in params

    def test_cancel_sync_signature(self):
        """cancel_sync should have dst parameter."""
        sig = inspect.signature(VastAIBase.cancel_sync)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "dst" in params

    def test_change_bid_signature(self):
        """change_bid should have id and optional price parameters."""
        sig = inspect.signature(VastAIBase.change_bid)
        params = sig.parameters
        assert "self" in params
        assert "id" in params
        assert "price" in params
        assert params["price"].default is None

    def test_copy_signature(self):
        """copy should have src, dst, and optional identity parameters."""
        sig = inspect.signature(VastAIBase.copy)
        params = sig.parameters
        assert "self" in params
        assert "src" in params
        assert "dst" in params
        assert "identity" in params

    def test_create_instance_signature(self):
        """create_instance should have id as int and disk with default 10."""
        sig = inspect.signature(VastAIBase.create_instance)
        params = sig.parameters
        assert "self" in params
        assert "id" in params
        assert "disk" in params
        assert params["disk"].default == 10
        assert "image" in params
        assert "ssh" in params
        assert "jupyter" in params

    def test_create_workergroup_signature(self):
        """create_workergroup should have expected parameters."""
        sig = inspect.signature(VastAIBase.create_workergroup)
        params = sig.parameters
        assert "self" in params
        assert "test_workers" in params
        assert params["test_workers"].default == 3
        assert "gpu_ram" in params
        assert "template_hash" in params
        assert "endpoint_name" in params

    def test_create_endpoint_signature(self):
        """create_endpoint should have min_load, target_util, cold_mult defaults."""
        sig = inspect.signature(VastAIBase.create_endpoint)
        params = sig.parameters
        assert "self" in params
        assert "min_load" in params
        assert params["min_load"].default == 0.0
        assert "target_util" in params
        assert params["target_util"].default == 0.9
        assert "cold_mult" in params
        assert params["cold_mult"].default == 2.5

    def test_destroy_instance_signature(self):
        """destroy_instance should have id parameter."""
        sig = inspect.signature(VastAIBase.destroy_instance)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "id" in params

    def test_destroy_instances_signature(self):
        """destroy_instances should have ids list parameter."""
        sig = inspect.signature(VastAIBase.destroy_instances)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "ids" in params

    def test_execute_signature(self):
        """execute should have id and COMMAND parameters."""
        sig = inspect.signature(VastAIBase.execute)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "id" in params
        assert "COMMAND" in params

    def test_search_offers_signature(self):
        """search_offers should have type, query, limit and other parameters."""
        sig = inspect.signature(VastAIBase.search_offers)
        params = sig.parameters
        assert "self" in params
        assert "type" in params
        assert "query" in params
        assert "limit" in params
        assert "no_default" in params
        assert params["no_default"].default is False

    def test_show_instances_signature(self):
        """show_instances should have quiet parameter with False default."""
        sig = inspect.signature(VastAIBase.show_instances)
        params = sig.parameters
        assert "self" in params
        assert "quiet" in params
        assert params["quiet"].default is False

    def test_logs_signature(self):
        """logs should have INSTANCE_ID and optional tail parameters."""
        sig = inspect.signature(VastAIBase.logs)
        params = sig.parameters
        assert "self" in params
        assert "INSTANCE_ID" in params
        assert "tail" in params


class TestVastAIBaseVolumeMethodSignatures:
    """Verify volume method signatures."""

    def test_clone_volume_signature(self):
        """clone_volume should have source, dest, size, disable_compression."""
        sig = inspect.signature(VastAIBase.clone_volume)
        params = sig.parameters
        assert "self" in params
        assert "source" in params
        assert "dest" in params
        assert "size" in params
        assert "disable_compression" in params
        assert params["disable_compression"].default is False

    def test_create_volume_signature(self):
        """create_volume should have id, size with default 15, and optional name."""
        sig = inspect.signature(VastAIBase.create_volume)
        params = sig.parameters
        assert "self" in params
        assert "id" in params
        assert "size" in params
        assert params["size"].default == 15
        assert "name" in params

    def test_delete_volume_signature(self):
        """delete_volume should have id parameter."""
        sig = inspect.signature(VastAIBase.delete_volume)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "id" in params

    def test_search_volumes_signature(self):
        """search_volumes should have query, no_default, limit, storage, order."""
        sig = inspect.signature(VastAIBase.search_volumes)
        params = sig.parameters
        assert "self" in params
        assert "query" in params
        assert "no_default" in params
        assert "limit" in params
        assert "storage" in params
        assert params["storage"].default == 1.0
        assert "order" in params
        assert params["order"].default == "score-"

    def test_show_volumes_signature(self):
        """show_volumes should have type parameter with 'all' default."""
        sig = inspect.signature(VastAIBase.show_volumes)
        params = sig.parameters
        assert "self" in params
        assert "type" in params
        assert params["type"].default == "all"


class TestVastAIBaseClusterMethodSignatures:
    """Verify cluster method signatures."""

    def test_create_cluster_signature(self):
        """create_cluster should have subnet and manager_id parameters."""
        sig = inspect.signature(VastAIBase.create_cluster)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "subnet" in params
        assert "manager_id" in params

    def test_delete_cluster_signature(self):
        """delete_cluster should have cluster_id parameter."""
        sig = inspect.signature(VastAIBase.delete_cluster)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "cluster_id" in params

    def test_join_cluster_signature(self):
        """join_cluster should have cluster_id and machine_ids parameters."""
        sig = inspect.signature(VastAIBase.join_cluster)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "cluster_id" in params
        assert "machine_ids" in params

    def test_show_clusters_signature(self):
        """show_clusters should exist with self parameter only."""
        sig = inspect.signature(VastAIBase.show_clusters)
        params = list(sig.parameters.keys())
        assert "self" in params


class TestVastAIBaseOverlayMethodSignatures:
    """Verify overlay method signatures."""

    def test_create_overlay_signature(self):
        """create_overlay should have cluster_id and name parameters."""
        sig = inspect.signature(VastAIBase.create_overlay)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "cluster_id" in params
        assert "name" in params

    def test_delete_overlay_signature(self):
        """delete_overlay should have overlay_identifier parameter."""
        sig = inspect.signature(VastAIBase.delete_overlay)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "overlay_identifier" in params

    def test_join_overlay_signature(self):
        """join_overlay should have name and instance_id parameters."""
        sig = inspect.signature(VastAIBase.join_overlay)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "name" in params
        assert "instance_id" in params

    def test_show_overlays_signature(self):
        """show_overlays should exist with self parameter only."""
        sig = inspect.signature(VastAIBase.show_overlays)
        params = list(sig.parameters.keys())
        assert "self" in params


class TestVastAIBaseEnvVarMethodSignatures:
    """Verify environment variable method signatures."""

    def test_create_env_var_signature(self):
        """create_env_var should have name and value parameters."""
        sig = inspect.signature(VastAIBase.create_env_var)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "name" in params
        assert "value" in params

    def test_delete_env_var_signature(self):
        """delete_env_var should have name parameter."""
        sig = inspect.signature(VastAIBase.delete_env_var)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "name" in params

    def test_update_env_var_signature(self):
        """update_env_var should have name and value parameters."""
        sig = inspect.signature(VastAIBase.update_env_var)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "name" in params
        assert "value" in params

    def test_show_env_vars_signature(self):
        """show_env_vars should have show_values parameter with False default."""
        sig = inspect.signature(VastAIBase.show_env_vars)
        params = sig.parameters
        assert "self" in params
        assert "show_values" in params
        assert params["show_values"].default is False


class TestVastAIBaseBackwardsCompatibility:
    """Verify backwards compatibility aliases exist and point to correct methods."""

    def test_create_autogroup_is_create_workergroup(self):
        """create_autogroup should be an alias for create_workergroup."""
        assert VastAIBase.create_autogroup is VastAIBase.create_workergroup

    def test_delete_autoscaler_is_delete_workergroup(self):
        """delete_autoscaler should be an alias for delete_workergroup."""
        assert VastAIBase.delete_autoscaler is VastAIBase.delete_workergroup

    def test_update_autoscaler_is_update_workergroup(self):
        """update_autoscaler should be an alias for update_workergroup."""
        assert VastAIBase.update_autoscaler is VastAIBase.update_workergroup

    def test_show_autoscalers_is_show_workergroups(self):
        """show_autoscalers should be an alias for show_workergroups."""
        assert VastAIBase.show_autoscalers is VastAIBase.show_workergroups


class TestVastAIBaseMethodCount:
    """Verify expected number of public methods exist."""

    def test_has_many_methods(self):
        """VastAIBase should have 100+ public methods."""
        methods = [
            m for m in dir(VastAIBase)
            if not m.startswith('_') and callable(getattr(VastAIBase, m))
        ]
        assert len(methods) >= 100, f"Expected 100+ methods, got {len(methods)}"

    def test_no_missing_core_methods(self):
        """Essential methods should exist."""
        core_methods = [
            'attach_ssh', 'cancel_copy', 'change_bid', 'copy',
            'create_instance', 'destroy_instance', 'execute',
            'search_offers', 'show_instances', 'logs',
            'create_volume', 'delete_volume', 'show_volumes',
            'create_cluster', 'show_clusters',
            'create_overlay', 'show_overlays',
            'create_env_var', 'show_env_vars',
        ]
        for method in core_methods:
            assert hasattr(VastAIBase, method), f"Missing method: {method}"
            assert callable(getattr(VastAIBase, method)), f"Not callable: {method}"


class TestVastAIBaseMethodDocstrings:
    """Verify methods have docstrings for IDE autocomplete support."""

    def test_attach_ssh_has_docstring(self):
        """attach_ssh should have a docstring."""
        assert VastAIBase.attach_ssh.__doc__ is not None

    def test_create_instance_has_docstring(self):
        """create_instance should have a docstring."""
        assert VastAIBase.create_instance.__doc__ is not None

    def test_search_offers_has_docstring(self):
        """search_offers should have a docstring."""
        assert VastAIBase.search_offers.__doc__ is not None

    def test_create_volume_has_docstring(self):
        """create_volume should have a docstring."""
        assert VastAIBase.create_volume.__doc__ is not None

    def test_create_cluster_has_docstring(self):
        """create_cluster should have a docstring."""
        assert VastAIBase.create_cluster.__doc__ is not None

    def test_show_invoices_v1_has_docstring(self):
        """show_invoices_v1 should have a docstring."""
        assert VastAIBase.show_invoices_v1.__doc__ is not None


class TestVastAIBaseAdditionalMethodSignatures:
    """Additional method signature tests for coverage."""

    def test_take_snapshot_signature(self):
        """take_snapshot should have instance_id, repo, and other parameters."""
        sig = inspect.signature(VastAIBase.take_snapshot)
        params = sig.parameters
        assert "self" in params
        assert "instance_id" in params
        assert "repo" in params
        assert "container_registry" in params
        assert params["container_registry"].default == "docker.io"

    def test_update_instance_signature(self):
        """update_instance should have id and optional template parameters."""
        sig = inspect.signature(VastAIBase.update_instance)
        params = sig.parameters
        assert "self" in params
        assert "id" in params
        assert "template_id" in params
        assert "template_hash_id" in params

    def test_vm_copy_signature(self):
        """vm_copy should have src and dst parameters."""
        sig = inspect.signature(VastAIBase.vm_copy)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "src" in params
        assert "dst" in params

    def test_get_endpt_logs_signature(self):
        """get_endpt_logs should have id, level, and tail parameters."""
        sig = inspect.signature(VastAIBase.get_endpt_logs)
        params = sig.parameters
        assert "self" in params
        assert "id" in params
        assert "level" in params
        assert params["level"].default == 1
        assert "tail" in params

    def test_show_invoices_v1_signature(self):
        """show_invoices_v1 should have extensive filtering parameters."""
        sig = inspect.signature(VastAIBase.show_invoices_v1)
        params = sig.parameters
        assert "self" in params
        assert "invoices" in params
        assert "charges" in params
        assert "invoice_type" in params
        assert "charge_type" in params
        assert "limit" in params
        assert params["limit"].default == 20
        assert "format" in params
        assert params["format"].default == "table"
