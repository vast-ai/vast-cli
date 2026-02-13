# Host Commands

Commands for GPU providers hosting machines on Vast.ai.

!!! note "For Hosts Only"
    These commands are for users who are providing GPU compute on the Vast.ai marketplace.
    If you're renting GPUs, see [Client Commands](../client/index.md).

## Command Categories

### Machine Management

| Command | Description |
|---------|-------------|
| [`show machines`](machines.md#show-machines) | List your hosted machines |
| [`show machine`](machines.md#show-machine) | Show machine details |
| [`list machine`](machines.md#list-machine) | List a machine for rent |
| [`unlist machine`](machines.md#unlist-machine) | Remove machine from marketplace |
| [`delete machine`](machines.md#delete-machine) | Delete a machine |
| [`self-test machine`](machines.md#self-test-machine) | Run self-test diagnostics |

### Pricing

| Command | Description |
|---------|-------------|
| [`set min-bid`](machines.md#set-min-bid) | Set minimum rental price |

### Volumes (Host)

| Command | Description |
|---------|-------------|
| [`list volume`](machines.md#list-volume) | List disk space for rent |
| [`list volumes`](machines.md#list-volumes) | List volumes on multiple machines |
| [`unlist volume`](machines.md#unlist-volume) | Remove volume from marketplace |
| [`list network-volume`](machines.md#list-network-volume) | List network volume for rent |
| [`unlist network-volume`](machines.md#unlist-network-volume) | Remove network volume |

### Maintenance

| Command | Description |
|---------|-------------|
| [`schedule maint`](maintenance.md#schedule-maint) | Schedule maintenance window |
| [`cancel maint`](maintenance.md#cancel-maint) | Cancel maintenance window |
| [`show maints`](maintenance.md#show-maints) | Show maintenance info |
| [`cleanup machine`](maintenance.md#cleanup-machine) | Remove expired storage |
| [`defrag machines`](maintenance.md#defrag-machines) | Defragment machines |

### Reports & Earnings

| Command | Description |
|---------|-------------|
| [`show earnings`](reports.md#show-earnings) | View earning history |
| [`reports`](reports.md#reports) | Get machine reports |

### Default Jobs

| Command | Description |
|---------|-------------|
| [`set defjob`](machines.md#set-defjob) | Create default jobs |
| [`remove defjob`](machines.md#remove-defjob) | Delete default jobs |

### Clusters (Beta)

| Command | Description |
|---------|-------------|
| [`add network-disk`](clusters.md#add-network-disk) | Add network disk to cluster |
| [`show network-disks`](clusters.md#show-network-disks) | Show network disks |

## Quick Reference

```bash
# List your machines
vastai show machines

# Set pricing for a machine
vastai set min-bid 12345 0.50

# Run diagnostics
vastai self-test machine 12345

# Schedule maintenance
vastai schedule maint 12345 --start "2025-03-01 00:00" --end "2025-03-01 06:00"

# Check earnings
vastai show earnings
```

## See Also

- [Full Command Reference](../commands.md) - Complete command list with help text
- [CLI Overview](../index.md) - Query syntax and global options
- [Client Commands](../client/index.md) - Commands for GPU renters
