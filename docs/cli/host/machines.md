# Machine Commands

Commands for managing your hosted machines on Vast.ai.

## show machines

[Host] List all your hosted machines

```bash
vastai show machines [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-q, --quiet` | only display numeric ids |

---

## show machine

[Host] Show details for a specific hosted machine

```bash
vastai show machine ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to display |

**Options:**

| Option | Description |
|--------|-------------|
| `-q, --quiet` | only display numeric ids |

---

## list machine

[Host] List a single machine for rent on the marketplace

```bash
vastai list machine ID [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to list |

**Options:**

| Option | Description |
|--------|-------------|
| `-g, --price_gpu PRICE_GPU` | per gpu rental price in $/hour  (price for active instances) |
| `-s, --price_disk PRICE_DISK` | storage price in $/GB/month (price for inactive instances), default: $0.10/GB/month |
| `-u, --price_inetu PRICE_INETU` | price for internet upload bandwidth in $/GB |
| `-d, --price_inetd PRICE_INETD` | price for internet download bandwidth in $/GB |
| `-b, --price_min_bid PRICE_MIN_BID` | per gpu minimum bid price floor in $/hour |
| `-r, --discount_rate DISCOUNT_RATE` | Max long term prepay discount rate fraction, default: 0.4 |
| `-m, --min_chunk MIN_CHUNK` | minimum amount of gpus |
| `-e, --end_date END_DATE` | contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format) |
| `-l, --duration DURATION` | Updates end_date daily to be duration from current date. Cannot be combined with end_date. Format is: `n days`, `n weeks`, `n months`, `n years`, or total intended duration in seconds. |
| `-v, --vol_size VOL_SIZE` | Size for volume contract offer. Defaults to half of available disk. Set 0 to not create a volume contract offer. |
| `-z, --vol_price VOL_PRICE` | Price for disk on volume contract offer. Defaults to price_disk. Invalid if vol_size is 0. |

!!! warning
    Performs the same action as pressing the "LIST" button on the site https://cloud.vast.ai/host/machines.
    On the end date the listing will expire and your machine will unlist. However any existing client jobs will still remain until ended by their owners.
    Once you list your machine and it is rented, it is extremely important that you don't interfere with the machine in any way.
    If your machine has an active client job and then goes offline, crashes, or has performance problems, this could permanently lower your reliability rating.
    We strongly recommend you test the machine first and only list when ready.

---

## list machines

[Host] List multiple machines for rent on the marketplace

```bash
vastai list machines IDS [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `ids` | ids of machines to list |

**Options:**

| Option | Description |
|--------|-------------|
| `-g, --price_gpu PRICE_GPU` | per gpu on-demand rental price in $/hour (base price for active instances) |
| `-s, --price_disk PRICE_DISK` | storage price in $/GB/month (price for inactive instances), default: $0.10/GB/month |
| `-u, --price_inetu PRICE_INETU` | price for internet upload bandwidth in $/GB |
| `-d, --price_inetd PRICE_INETD` | price for internet download bandwidth in $/GB |
| `-b, --price_min_bid PRICE_MIN_BID` | per gpu minimum bid price floor in $/hour |
| `-r, --discount_rate DISCOUNT_RATE` | Max long term prepay discount rate fraction, default: 0.4 |
| `-m, --min_chunk MIN_CHUNK` | minimum amount of gpus |
| `-e, --end_date END_DATE` | contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format) |
| `-l, --duration DURATION` | Updates end_date daily to be duration from current date. Cannot be combined with end_date. Format is: `n days`, `n weeks`, `n months`, `n years`, or total intended duration in seconds. |
| `-v, --vol_size VOL_SIZE` | Size for volume contract offer. Defaults to half of available disk. Set 0 to not create a volume contract offer. |
| `-z, --vol_price VOL_PRICE` | Price for disk on volume contract offer. Defaults to price_disk. Invalid if vol_size is 0. |

**Notes:**

This variant can be used to list or update the listings for multiple machines at once with the same args.
You could extend the end dates of all your machines using a command combo like this:
./vast.py list machines $(./vast.py show machines -q) -e 12/31/2024 --retry 6

---

## unlist machine

[Host] Remove a machine from the rental marketplace

```bash
vastai unlist machine <id>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to unlist |

---

## delete machine

[Host] Remove a machine from your host account

```bash
vastai delete machine <id>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to delete |

---

## set min-bid

[Host] Set minimum price for interruptible/spot instance rentals

```bash
vastai set min_bid id [--price PRICE]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to set min bid price for |

**Options:**

| Option | Description |
|--------|-------------|
| `--price PRICE` | per gpu min bid price in $/hour |

**Notes:**

Change the current min bid price of machine id to PRICE.

---

## self-test machine

[Host] Run diagnostics on a hosted machine

```bash
vastai self-test machine <machine_id> [--debugging] [--explain] [--api_key API_KEY] [--url URL] [--retry RETRY] [--raw] [--ignore-requirements]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `machine_id` | Machine ID |

**Options:**

| Option | Description |
|--------|-------------|
| `--debugging` | Enable debugging output |
| `--explain` | Output verbose explanation of mapping of CLI calls to HTTPS API endpoints |
| `--raw` | Output machine-readable JSON |
| `--url URL` | Server REST API URL |
| `--retry RETRY` | Retry limit |
| `--ignore-requirements` | Ignore the minimum system requirements and run the self test regardless |

**Notes:**

This command tests if a machine meets specific requirements and
runs a series of tests to ensure it's functioning correctly.

**Examples:**

```bash
 vastai self-test machine 12345
 vastai self-test machine 12345 --debugging
 vastai self-test machine 12345 --explain
 vastai self-test machine 12345 --api_key <YOUR_API_KEY>
```

---

## list volume

[Host] List disk space as a rentable volume

```bash
vastai list volume ID [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to list |

**Options:**

| Option | Description |
|--------|-------------|
| `-p, --price_disk PRICE_DISK` | storage price in $/GB/month, default: $0.10/GB/month |
| `-e, --end_date END_DATE` | contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format), default 3 months |
| `-s, --size SIZE` | size of disk space allocated to offer in GB, default 15 GB |

**Notes:**

Allocates a section of disk on a machine to be used for volumes.

---

## list volumes

[Host] List disk space on multiple machines as rentable volumes

```bash
vastai list volumes IDS [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `ids` | ids of machines to list volumes on |

**Options:**

| Option | Description |
|--------|-------------|
| `-p, --price_disk PRICE_DISK` | storage price in $/GB/month, default: $0.10/GB/month |
| `-e, --end_date END_DATE` | contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format), default 3 months |
| `-s, --size SIZE` | size of disk space allocated to offer in GB, default 15 GB |

**Notes:**

Allocates a section of disk on machines to be used for volumes.

---

## unlist volume

[Host] Remove a volume offer from the marketplace

```bash
vastai unlist volume ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | volume ID you want to unlist |

---

## list network-volume

[Host] [Beta] List disk space as a rentable network volume

```bash
vastai list network volume DISK_ID [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `disk_id` | id of network disk to list |

**Options:**

| Option | Description |
|--------|-------------|
| `-p, --price_disk PRICE_DISK` | storage price in $/GB/month, default: $0.15/GB/month |
| `-e, --end_date END_DATE` | contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format), default 1 month |
| `-s, --size SIZE` | size of disk space allocated to offer in GB, default 15 GB |

---

## unlist network-volume

[Host] [Beta] Remove a network volume offer from the marketplace

```bash
vastai unlist network volume OFFER_ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of network volume offer to unlist |

---

## set defjob

[Host] Configure default background jobs for a machine

```bash
vastai set defjob id [--api-key API_KEY] [--price_gpu PRICE_GPU] [--price_inetu PRICE_INETU] [--price_inetd PRICE_INETD] [--image IMAGE] [--args ...]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to launch default instance on |

**Options:**

| Option | Description |
|--------|-------------|
| `--price_gpu PRICE_GPU` | per gpu rental price in $/hour |
| `--price_inetu PRICE_INETU` | price for internet upload bandwidth in $/GB |
| `--price_inetd PRICE_INETD` | price for internet download bandwidth in $/GB |
| `--image IMAGE` | docker container image to launch |
| `--args ...` | list of arguments passed to container launch |

**Notes:**

Performs the same action as creating a background job at https://cloud.vast.ai/host/create.

---

## remove defjob

[Host] Remove default background jobs from a machine

```bash
vastai remove defjob id
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of machine to remove default instance from |

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
