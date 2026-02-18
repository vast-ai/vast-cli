# Reports & Earnings

Commands for viewing machine reports and earning history.

## show earnings

[Host] Show rental income history for your machines

```bash
vastai show earnings [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-q, --quiet` | only display numeric ids |
| `-s, --start_date START_DATE` | start date and time for report. Many formats accepted |
| `-e, --end_date END_DATE` | end date and time for report. Many formats accepted |
| `-m, --machine_id MACHINE_ID` | Machine id (optional) |

---

## reports

[Host] Get usage and performance reports for a machine

```bash
vastai reports ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | machine id |

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
