# Volume Commands

Commands for managing persistent storage volumes.

## create volume

Create a new persistent storage volume

```bash
vastai create volume ID [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of volume offer |

**Options:**

| Option | Description |
|--------|-------------|
| `-s, --size SIZE` | size in GB of volume. Default 15 GB. |
| `-n, --name NAME` | Optional name of volume. |

**Notes:**

Creates a volume from an offer ID (which is returned from "search volumes"). Each offer ID can be used to create multiple volumes,
provided the size of all volumes does not exceed the size of the offer.

---

## create network-volume

[Host] [Beta] Create a new network-attached storage volume

```bash
vastai create network volume ID [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of network volume offer |

**Options:**

| Option | Description |
|--------|-------------|
| `-s, --size SIZE` | size in GB of network volume. Default 15 GB. |
| `-n, --name NAME` | Optional name of network volume. |

**Notes:**

Creates a network volume from an offer ID (which is returned from "search network volumes"). Each offer ID can be used to create multiple volumes,
provided the size of all volumes does not exceed the size of the offer.

---

## delete volume

Delete a persistent storage volume

```bash
vastai delete volume ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of volume contract |

**Notes:**

Deletes volume with the given ID. All instances using the volume must be destroyed before the volume can be deleted.

---

## clone volume

Create a copy of an existing volume

```bash
vastai copy volume <source_id> <dest_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `source` | id of volume contract being cloned |
| `dest` | id of volume offer volume is being copied to |

**Options:**

| Option | Description |
|--------|-------------|
| `-s, --size SIZE` | Size of new volume contract, in GB. Must be greater than or equal to the source volume, and less than or equal to the destination offer. |
| `-d, --disable_compression` | Do not compress volume data before copying. |

**Notes:**

Create a new volume with the given offer, by copying the existing volume.
Size defaults to the size of the existing volume, but can be increased if there is available space.

---

## show volumes

List all your storage volumes and their status

```bash
vastai show volumes [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-t, --type TYPE` | volume type to display. Default to all. Possible values are "local", "all", "network" |

**Notes:**

Show stats on owned volumes

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
