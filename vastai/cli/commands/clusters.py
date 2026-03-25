"""CLI commands for managing clusters and overlays."""

import json

from vastai.cli.parser import argument
from vastai.cli.display import (
    display_table, cluster_fields, overlay_fields, deindent,
)
from vastai.api import clusters as clusters_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# clusters
# ---------------------------------------------------------------------------

@parser.command(
    argument("subnet", help="local subnet for cluster, ex: '0.0.0.0/24'", type=str),
    argument("manager_id", help="Machine ID of manager node in cluster", type=int),
    usage="vastai create cluster SUBNET MANAGER_ID",
    help="Create Vast cluster",
)
def create__cluster(args):
    """Create a Vast Cluster."""
    if args.explain:
        print("request json:", {"subnet": args.subnet, "manager_id": args.manager_id})

    client = get_client(args)
    result = clusters_api.create_cluster(client, subnet=args.subnet, manager_id=args.manager_id)

    if args.raw:
        return result

    print(result.get("msg", result))


@parser.command(
    usage="vastai show clusters",
    help="Show clusters associated with your account.",
)
def show__clusters(args):
    """Show clusters associated with your account."""
    client = get_client(args)
    response_data = clusters_api.show_clusters(client)

    if args.raw:
        return response_data

    rows = []
    for cluster_id, cluster_data in response_data['clusters'].items():
        machine_ids = [node["machine_id"] for node in cluster_data["nodes"]]
        manager_node = next(node for node in cluster_data['nodes'] if node['is_cluster_manager'])
        row_data = {
            'id': cluster_id,
            'subnet': cluster_data['subnet'],
            'node_count': len(cluster_data['nodes']),
            'machine_ids': str(machine_ids),
            'manager_id': str(manager_node['machine_id']),
            'manager_ip': manager_node['local_ip'],
        }
        rows.append(row_data)

    display_table(rows, cluster_fields, replace_spaces=False)


@parser.command(
    argument("cluster_id", help="ID of cluster to delete", type=int),
    usage="vastai delete cluster CLUSTER_ID",
    help="Delete Cluster",
)
def delete__cluster(args):
    """Delete a Vast Cluster."""
    if args.explain:
        print("request json:", {"cluster_id": args.cluster_id})

    client = get_client(args)
    result = clusters_api.delete_cluster(client, cluster_id=args.cluster_id)

    if args.raw:
        return result
    print(result["msg"])


@parser.command(
    argument("cluster_id", help="ID of cluster to add machine to", type=int),
    argument("machine_ids", help="machine id(s) to join cluster", type=int, nargs="+"),
    usage="vastai join cluster CLUSTER_ID MACHINE_IDS",
    help="Join Machine to Cluster",
)
def join__cluster(args):
    """Join machine(s) to a Vast Cluster."""
    if args.explain:
        print("request json:", {"cluster_id": args.cluster_id, "machine_ids": args.machine_ids})

    client = get_client(args)
    result = clusters_api.join_cluster(client, cluster_id=args.cluster_id, machine_ids=args.machine_ids)

    if args.raw:
        return result
    print(result["msg"])


@parser.command(
    argument("cluster_id", help="ID of cluster you want to remove machine from.", type=int),
    argument("machine_id", help="ID of machine to remove from cluster.", type=int),
    argument("new_manager_id", help="ID of machine to promote to manager", type=int, nargs="?"),
    usage="vastai remove-machine-from-cluster CLUSTER_ID MACHINE_ID NEW_MANAGER_ID",
    help="Removes machine from cluster",
)
def remove_machine_from_cluster(args):
    """Remove a machine from a cluster."""
    if args.explain:
        print("request json:", {"cluster_id": args.cluster_id, "machine_id": args.machine_id,
                                "new_manager_id": args.new_manager_id})

    client = get_client(args)
    result = clusters_api.remove_machine_from_cluster(
        client, cluster_id=args.cluster_id, machine_id=args.machine_id,
        new_manager_id=args.new_manager_id,
    )

    if args.raw:
        return result
    print(result.get("msg", result))


# ---------------------------------------------------------------------------
# overlays
# ---------------------------------------------------------------------------

@parser.command(
    argument("cluster_id", help="ID of cluster to create overlay on top of", type=int),
    argument("name", help="overlay network name"),
    usage="vastai create overlay CLUSTER_ID OVERLAY_NAME",
    help="Creates overlay network on top of a physical cluster",
)
def create__overlay(args):
    """Create an overlay network on a physical cluster."""
    if args.explain:
        print("request json:", {"cluster_id": args.cluster_id, "name": args.name})

    client = get_client(args)
    result = clusters_api.create_overlay(client, cluster_id=args.cluster_id, name=args.name)

    if args.raw:
        return result
    print(result["msg"])


@parser.command(
    usage="vastai show overlays",
    help="Show overlays associated with your account.",
)
def show__overlays(args):
    """Show overlays associated with your account."""
    client = get_client(args)
    response_data = clusters_api.show_overlays(client)
    if args.raw:
        return response_data

    rows = []
    for overlay in response_data:
        row_data = {
            'overlay_id': overlay['overlay_id'],
            'name': overlay['name'],
            'subnet': overlay['internal_subnet'] if overlay['internal_subnet'] else 'N/A',
            'cluster_id': overlay['cluster_id'],
            'instance_count': len(overlay['instances']),
            'instances': str(overlay['instances']),
        }
        rows.append(row_data)
    display_table(rows, overlay_fields, replace_spaces=False)


@parser.command(
    argument("overlay_identifier", help="ID (int) or name (str) of overlay to delete", nargs="?"),
    usage="vastai delete overlay OVERLAY_IDENTIFIER",
    help="Deletes overlay and removes all of its associated instances",
)
def delete__overlay(args):
    """Delete an overlay network."""
    if args.explain:
        print("request json:", {"overlay_identifier": args.overlay_identifier})

    client = get_client(args)
    result = clusters_api.delete_overlay(client, overlay_identifier=args.overlay_identifier)

    if args.raw:
        return result
    print(result["msg"])


@parser.command(
    argument("name", help="Overlay network name to join instance to.", type=str),
    argument("instance_id", help="Instance ID to add to overlay.", type=int),
    usage="vastai join overlay OVERLAY_NAME INSTANCE_ID",
    help="Adds instance to an overlay network",
)
def join__overlay(args):
    """Add an instance to an overlay network."""
    if args.explain:
        print("request json:", {"name": args.name, "instance_id": args.instance_id})

    client = get_client(args)
    result = clusters_api.join_overlay(client, name=args.name, instance_id=args.instance_id)

    if args.raw:
        return result
    print(result["msg"])
