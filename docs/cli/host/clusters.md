# Cluster Commands (Host)

Commands for managing physical clusters and network disks.

## add network-disk

[Host] [Beta] Attach a network disk to a machine cluster

```bash
vastai add network-disk MACHINES MOUNT_PATH [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `machines` | ids of machines to add disk to, that is networked to be on the same LAN as machine |
| `mount_point` | mount path of disk to add |

**Options:**

| Option | Description |
|--------|-------------|
| `-d, --disk_id [DISK_ID]` | id of network disk to attach to machines in the cluster |

**Notes:**

This variant can be used to add a network disk to a physical cluster.
When you add a network disk for the first time, you just need to specify the machine(s) and mount_path.
When you add a network disk for the second time, you need to specify the disk_id.

**Examples:**

```bash
vastai add network-disk 1 /mnt/disk1
vastai add network-disk 1 /mnt/disk1 -d 12345
```

---

## show network-disks

[Host] [Beta] List network disks attached to your machines

```bash
vastai show network-disks
```

**Notes:**

Show network disks associated with your account.

---

## create cluster

[Beta] Create a new machine cluster

```bash
vastai create cluster SUBNET MANAGER_ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `subnet` | local subnet for cluster, ex: '0.0.0.0/24' |
| `manager_id` | Machine ID of manager node in cluster. Must exist already. |

**Notes:**

Create Vast Cluster by defining a local subnet and manager id.

---

## delete cluster

[Beta] Delete a machine cluster

```bash
vastai delete cluster CLUSTER_ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `cluster_id` | ID of cluster to delete |

**Notes:**

Delete Vast Cluster

---

## join cluster

[Beta] Add a machine to an existing cluster

```bash
vastai join cluster CLUSTER_ID MACHINE_IDS
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `cluster_id` | ID of cluster to add machine to |
| `machine_ids` | machine id(s) to join cluster |

**Notes:**

Join's Machine to Vast Cluster

---

## show clusters

[Beta] List all your machine clusters

```bash
vastai show clusters
```

**Notes:**

Show clusters associated with your account.

---

## remove-machine-from-cluster

[Host] [Beta] Remove a machine from a cluster

```bash
vastai remove-machine-from-cluster CLUSTER_ID MACHINE_ID NEW_MANAGER_ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `cluster_id` | ID of cluster you want to remove machine from. |
| `machine_id` | ID of machine to remove from cluster. |
| `new_manager_id` | ID of machine to promote to manager. Must already be in cluster |

**Notes:**

Removes machine from cluster and also reassigns manager ID,
if we're removing the manager node

---

## create overlay

[Beta] Create a virtual overlay network on a cluster

```bash
vastai create overlay CLUSTER_ID OVERLAY_NAME
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `cluster_id` | ID of cluster to create overlay on top of |
| `name` | overlay network name |

**Notes:**

Creates an overlay network to allow local networking between instances on a physical cluster

---

## delete overlay

[Beta] Delete an overlay network and its instances

```bash
vastai delete overlay OVERLAY_IDENTIFIER
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `overlay_identifier` | ID (int) or name (str) of overlay to delete |

---

## show overlays

[Beta] List all your overlay networks

```bash
vastai show overlays
```

**Notes:**

Show overlays associated with your account.

---

## join overlay

[Beta] Connect an instance to an overlay network

```bash
vastai join overlay OVERLAY_NAME INSTANCE_ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Overlay network name to join instance to. |
| `instance_id` | Instance ID to add to overlay. |

**Notes:**

Adds an instance to a compatible overlay network.

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
