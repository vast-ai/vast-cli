# Maintenance Commands

Commands for scheduling and managing machine maintenance.

## schedule maint

[Host] Schedule a maintenance window for a machine

```bash
vastai schedule maintenance id [--sdate START_DATE --duration DURATION --maintenance_category MAINTENANCE_CATEGORY]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to schedule maintenance for |

**Options:**

| Option | Description |
|--------|-------------|
| `--sdate SDATE` | maintenance start date in unix epoch time (UTC seconds) |
| `--duration DURATION` | maintenance duration in hours |
| `--maintenance_category MAINTENANCE_CATEGORY` | (optional) can be one of [power, internet, disk, gpu, software, other] |

**Notes:**

The proper way to perform maintenance on your machine is to wait until all active contracts have expired or the machine is vacant.
For unplanned or unscheduled maintenance, use this schedule maint command. That will notify the client that you have to take the machine down and that they should save their work.
You can specify a date, duration, reason and category for the maintenance.

---

## cancel maint

[Host] Cancel a scheduled maintenance window

```bash
vastai cancel maint id
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to cancel maintenance(s) for |

**Notes:**

For deleting a machine's scheduled maintenance window(s), use this cancel maint command.

---

## show maints

[Host] List scheduled maintenance windows

```bash
vastai show maints --ids MACHINE_IDS [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-i, --ids IDS` | comma separated string of machine_ids for which to get maintenance information |
| `-q, --quiet` | only display numeric ids of the machines in maintenance |

---

## cleanup machine

[Host] Clean up expired storage to free disk space

```bash
vastai cleanup machine ID [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to cleanup |

**Notes:**

Instances expire on their end date. Expired instances still pay storage fees, but can not start.
Since hosts are still paid storage fees for expired instances, we do not auto delete them.
Instead you can use this CLI/API function to delete all expired storage instances for a machine.
This is useful if you are running low on storage, want to do maintenance, or are subsidizing storage, etc.

---

## defrag machines

[Host] Rebuild larger GPU offers from orphaned single GPUs when possible

```bash
vastai defragment machines IDs
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `IDs` | ids of machines |

**Notes:**

Defragment some of your machines. This will rearrange GPU assignments to try and make more multi-gpu offers available.

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
