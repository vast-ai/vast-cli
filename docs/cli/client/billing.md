# Billing & Account Commands

Commands for managing billing, invoices, and account information.

## show user

Show your account information and balance

```bash
vastai show user [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-q, --quiet` | display information about user |

**Notes:**

Displays account information for the authenticated user.

**Examples:**

```bash
    vastai show user                           # Show user info in table format
    vastai show user --raw                     # Output as JSON for scripting
```

!!! tip
    Information displayed:
    - Account balance and credit
    - Email address
    - Username
    - SSH public key (if configured)
    - Account settings
    Note: API key is NOT displayed for security reasons.
    Use 'vastai set api-key' to update your stored API key.

---

## show invoices

[Deprecated] Get billing history - use show invoices-v1 instead

```bash
(DEPRECATED) vastai show invoices [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-q, --quiet` | only display numeric ids |
| `-s, --start_date START_DATE` | start date and time for report. Many formats accepted (optional) |
| `-e, --end_date END_DATE` | end date and time for report. Many formats accepted (optional) |
| `-c, --only_charges` | Show only charge items |
| `-p, --only_credits` | Show only credit items |
| `--instance_label INSTANCE_LABEL` | Filter charges on a particular instance label (useful for autoscaler groups) |

---

## show invoices-v1

Get billing history with invoices and charges

```bash
vastai show invoices-v1 [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-i, --invoices` | Show invoices instead of charges |
| `-c, --charges` | Show charges instead of invoices |
| `-s, --start-date START_DATE` | Start date (YYYY-MM-DD or timestamp) |
| `-e, --end-date END_DATE` | End date (YYYY-MM-DD or timestamp) |
| `-l, --limit LIMIT` | Number of results per page (default: 20, max: 100) |
| `-t, --next-token NEXT_TOKEN` | Pagination token for next page |
| `-f, --format {table,tree}` | Output format for charges (default: table) |
| `-v, --verbose` | Include full Instance Charge details and Invoice Metadata (tree view only) |
| `--latest-first` | Sort by latest first |

**Notes:**

This command supports colored output and rich formatting if the 'rich' python module is installed!

**Examples:**

```bash
    # Show the first 20 invoices in the last week  (note: default window is a 7 day period ending today)
    vastai show invoices-v1 --invoices

    # Show the first 50 charges over a 7 day period starting from 2025-11-30 in tree format
    vastai show invoices-v1 --charges -s 2025-11-30 -f tree -l 50

    # Show the first 20 invoices of specific types for the month of November 2025
    vastai show invoices-v1 -i -it stripe bitpay transfers --start-date 2025-11-01 --end-date 2025-11-30

    # Show the first 20 charges for only volumes and serverless instances between two dates, including all details and metadata
    vastai show invoices-v1 -c --charge-type v s -s 2025-11-01 -e 2025-11-05 --format tree --verbose

    # Get the next page of paginated invoices, limit to 50 per page  (note: type/date filters MUST match previous request for pagination to work)
    vastai show invoices-v1 --invoices --limit 50 --next-token eyJ2YWx1ZXMiOiB7ImlkIjogMjUwNzgyMzR9LCAib3NfcGFnZSI6IDB9

    # Show the last 10 instance (only) charges over a 7 day period ending in 2025-12-25, sorted by latest charges first
    vastai show invoices-v1 --charges -ct instance --end-date 2025-12-25 -l 10 --latest-first
```

---

## transfer credit

Transfer credits to another account

```bash
vastai transfer credit [--recipient EMAIL] [--amount DOLLARS] [RECIPIENT AMOUNT]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--skip` | skip confirmation |

!!! warning
    Transfer credits to another account. This action is irreversible.
    Supports two syntax styles (named flags recommended):

**Examples:**

```bash
  vastai transfer credit --recipient user@example.com --amount 10.00
  vastai transfer credit user@example.com 10.00  (legacy positional)

  vastai transfer credit --recipient user@example.com --amount 25.50
  vastai transfer credit -r user@example.com -a 25.50
  vastai transfer credit user@example.com 25.50
```

---

## show deposit

Show prepaid deposit balance for a reserved instance

```bash
vastai show deposit ID [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to get info for |

---

## show audit-logs

Show account activity and audit logs

```bash
vastai show audit-logs [--api-key API_KEY] [--raw]
```

---

## show ipaddrs

Show history of IP addresses used by your instances

```bash
vastai show ipaddrs [--api-key API_KEY] [--raw]
```

---

## create subaccount

Create a subaccount for delegated access

```bash
vastai create subaccount --email EMAIL --username USERNAME --password PASSWORD --type TYPE
```

**Options:**

| Option | Description |
|--------|-------------|
| `--email EMAIL` | email address to use for login |
| `--username USERNAME` | username to use for login |
| `--password PASSWORD` | password to use for login |
| `--type TYPE` | host/client |

**Notes:**

Creates a new account that is considered a child of your current account as defined via the API key.

**Examples:**

```bash
vastai create subaccount --email bob@gmail.com --username bob --password password --type host

vastai create subaccount --email vast@gmail.com --username vastai --password password --type host
```

---

## show subaccounts

List all subaccounts under your account

```bash
vastai show subaccounts [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-q, --quiet` | display subaccounts from current user |

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
