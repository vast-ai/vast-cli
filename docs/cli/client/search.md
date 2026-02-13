# Search Commands

Commands for searching offers, templates, and other resources.


## Query Syntax for String Values

When searching for values that contain spaces (like GPU names), you have two options:

1. **Underscores (recommended)** - most portable across shells:
   ```bash
   vastai search offers "gpu_name=RTX_4090"
   ```

2. **Escaped double quotes** - wrap query in single quotes, escape inner double quotes:
   ```bash
   vastai search offers 'gpu_name=\"RTX 4090\"'
   ```

!!! warning
    Single quotes around values do NOT work: `gpu_name='RTX 4090'` will fail.

---

## search offers

Search available GPU offers with filters

```bash
vastai search offers [--help] [--api-key API_KEY] [--raw] <query>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `query` | Query to search for. default: 'external=false rentable=true verified=true', pass -n to ignore default |

**Options:**

| Option | Description |
|--------|-------------|
| `-t, --type TYPE` | Show 'on-demand', 'reserved', or 'bid'(interruptible) pricing. default: on-demand |
| `-i, --interruptible` | Alias for --type=bid |
| `-b, --bid` | Alias for --type=bid |
| `-r, --reserved` | Alias for --type=reserved |
| `-d, --on-demand` | Alias for --type=on-demand |
| `-n, --no-default` | Disable default query |
| `--new` | New search exp |
| `--disable-bundling` | Deprecated |
| `--storage STORAGE` | Amount of storage to use for pricing, in GiB. default=5.0GiB |
| `-o, --order ORDER` | Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'num_gpus,total_flops-'.  default='score-' |

**Notes:**

Query syntax:
query = comparison comparison...
comparison = field op value
field = <name of a field>
op = one of: <, <=, ==, !=, >=, >, in, notin
value = <bool, int, float, string> | 'any' | [value0, value1, ...]
bool: True, False
note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

**Examples:**

```bash

    # search for somewhat reliable single RTX 3090 instances, filter out any duplicates or offers that conflict with our existing stopped instances
    vastai search offers 'reliability > 0.98 num_gpus=1 gpu_name=RTX_3090 rented=False'

    # search for datacenter gpus with minimal compute_cap and total_flops
    vastai search offers 'compute_cap > 610 total_flops > 5 datacenter=True'

    # search for reliable 4 gpu offers in Taiwan or Sweden
    vastai search offers 'reliability>0.99 num_gpus=4 geolocation in [TW,SE]'

    # search for reliable RTX 3090 or 4090 gpus NOT in China or Vietnam
    vastai search offers 'reliability>0.99 gpu_name in ["RTX 4090", "RTX 3090"] geolocation notin [CN,VN]'

    # search for machines with nvidia drivers 535.86.05 or greater (and various other options)
    vastai search offers 'disk_space>146 duration>24 gpu_ram>10 cuda_vers>=12.1 direct_port_count>=2 driver_version >= 535.86.05'

    # search for reliable machines with at least 4 gpus, unverified, order by num_gpus, allow conflicts
    vastai search offers 'reliability > 0.99  num_gpus>=4 verified=False rented=any' -o 'num_gpus-'

    # search for arm64 cpu architecture
    vastai search offers 'cpu_arch=arm64'
```

!!! tip
    Available fields:
    Name                  Type       Description
    bw_nvlink               float     bandwidth NVLink
    compute_cap:            int       cuda compute capability*100  (ie:  650 for 6.5, 700 for 7.0)
    cpu_arch                string    host machine cpu architecture (e.g. amd64, arm64)
    cpu_cores:              int       # virtual cpus
    cpu_ghz:                Float     # cpu clock speed GHZ
    cpu_cores_effective:    float     # virtual cpus you get
    cpu_ram:                float     system RAM in gigabytes
    cuda_vers:              float     machine max supported cuda version (based on driver version)
    datacenter:             bool      show only datacenter offers
    direct_port_count       int       open ports on host's router
    disk_bw:                float     disk read bandwidth, in MB/s
    disk_space:             float     disk storage space, in GB
    dlperf:                 float     DL-perf score  (see FAQ for explanation)
    dlperf_usd:             float     DL-perf/$
    dph:                    float     $/hour rental cost
    driver_version:         string    machine's nvidia/amd driver version as 3 digit string ex. "535.86.05,"
    duration:               float     max rental duration in days
    external:               bool      show external offers in addition to datacenter offers
    flops_usd:              float     TFLOPs/$
    geolocation:            string    Two letter country code. Works with operators =, !=, in, notin (e.g. geolocation not in ['XV','XZ'])
    gpu_arch                string    host machine gpu architecture (e.g. nvidia, amd)
    gpu_max_power           float     GPU power limit (watts)
    gpu_max_temp            float     GPU temp limit (C)
    gpu_mem_bw:             float     GPU memory bandwidth in GB/s
    gpu_name:               string    GPU model name (no quotes, replace spaces with underscores, ie: RTX_3090 rather than 'RTX 3090')
    gpu_ram:                float     per GPU RAM in GB
    gpu_total_ram:          float     total GPU RAM in GB
    gpu_frac:               float     Ratio of GPUs in the offer to gpus in the system
    gpu_display_active:     bool      True if the GPU has a display attached
    has_avx:                bool      CPU supports AVX instruction set.
    id:                     int       instance unique ID
    inet_down:              float     internet download speed in Mb/s
    inet_down_cost:         float     internet download bandwidth cost in $/GB
    inet_up:                float     internet upload speed in Mb/s
    inet_up_cost:           float     internet upload bandwidth cost in $/GB
    machine_id              int       machine id of instance
    min_bid:                float     current minimum bid price in $/hr for interruptible
    num_gpus:               int       # of GPUs
    pci_gen:                float     PCIE generation
    pcie_bw:                float     PCIE bandwidth (CPU to GPU)
    reliability:            float     machine reliability score (see FAQ for explanation)
    rentable:               bool      is the instance currently rentable
    rented:                 bool      allow/disallow duplicates and potential conflicts with existing stopped instances
    storage_cost:           float     storage cost in $/GB/month
    static_ip:              bool      is the IP addr static/stable
    total_flops:            float     total TFLOPs from all GPUs
    ubuntu_version          string    host machine ubuntu OS version
    verified:               bool      is the machine verified
    vms_enabled:            bool      is the machine a VM instance

---

## search templates

Search available templates with filters

```bash
vastai search templates [--help] [--api-key API_KEY] [--raw] <query>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `query` | Search query in simple query syntax (see below) |

**Notes:**

Query syntax:
query = comparison comparison...
comparison = field op value
field = <name of a field>
op = one of: <, <=, ==, !=, >=, >, in, notin
value = <bool, int, float, string> | 'any' | [value0, value1, ...]
bool: True, False
note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

**Examples:**

```bash

        # search for somewhat reliable single RTX 3090 instances, filter out any duplicates or offers that conflict with our existing stopped instances
        vastai search templates 'count_created > 100  creator_id in [38382,48982]'
```

!!! tip
    Available fields:
    Name                  Type       Description
    creator_id              int        ID of creator
    created_at              float      time of initial template creation (UTC epoch timestamp)
    count_created           int        #instances created (popularity)
    default_tag             string     image default tag
    docker_login_repo       string     image docker repository
    id                      int        template unique ID
    image                   string     image used for template
    jup_direct              bool       supports jupyter direct
    hash_id                 string     unique hash ID of template
    name                    string     displayable name
    recent_create_date      float      last time of instance creation (UTC epoch timestamp)
    recommended_disk_space  float      min disk space required
    recommended             bool       is templated on our recommended list
    ssh_direct              bool       supports ssh direct
    tag                     string     image tag
    use_ssh                 bool       supports ssh (direct or proxy)

---

## search volumes

Search available volume offers with filters

```bash
vastai search volumes [--help] [--api-key API_KEY] [--raw] <query>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `query` | Query to search for. default: 'external=false verified=true disk_space>=1', pass -n to ignore default |

**Options:**

| Option | Description |
|--------|-------------|
| `-n, --no-default` | Disable default query |
| `--storage STORAGE` | Amount of storage to use for pricing, in GiB. default=1.0GiB |
| `-o, --order ORDER` | Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'disk_space,inet_up-'.  default='score-' |

**Notes:**

Query syntax:
query = comparison comparison...
comparison = field op value
field = <name of a field>
op = one of: <, <=, ==, !=, >=, >, in, notin
value = <bool, int, float, string> | 'any' | [value0, value1, ...]
bool: True, False
note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

**Examples:**

```bash

    # search for volumes with greater than 50GB of available storage and greater than 500 Mb/s upload and download speed
    vastai search volumes "disk_space>50 inet_up>500 inet_down>500"
```

!!! tip
    Available fields:
    Name                  Type       Description
    cpu_arch:               string    host machine cpu architecture (e.g. amd64, arm64)
    cuda_vers:              float     machine max supported cuda version (based on driver version)
    datacenter:             bool      show only datacenter offers
    disk_bw:                float     disk read bandwidth, in MB/s
    disk_space:             float     disk storage space, in GB
    driver_version:         string    machine's nvidia/amd driver version as 3 digit string ex. "535.86.05"
    duration:               float     max rental duration in days
    geolocation:            string    Two letter country code. Works with operators =, !=, in, notin (e.g. geolocation not in ['XV','XZ'])
    gpu_arch:               string    host machine gpu architecture (e.g. nvidia, amd)
    gpu_name:               string    GPU model name (no quotes, replace spaces with underscores, ie: RTX_3090 rather than 'RTX 3090')
    has_avx:                bool      CPU supports AVX instruction set.
    id:                     int       volume offer unique ID
    inet_down:              float     internet download speed in Mb/s
    inet_up:                float     internet upload speed in Mb/s
    machine_id:             int       machine id of volume offer
    pci_gen:                float     PCIE generation
    pcie_bw:                float     PCIE bandwidth (CPU to GPU)
    reliability:            float     machine reliability score (see FAQ for explanation)
    storage_cost:           float     storage cost in $/GB/month
    static_ip:              bool      is the IP addr static/stable
    total_flops:            float     total TFLOPs from all GPUs
    ubuntu_version:         string    host machine ubuntu OS version
    verified:               bool      is the machine verified

---

## search network-volumes

[Host] [Beta] Search available network volume offers with filters

```bash
vastai search network volumes [--help] [--api-key API_KEY] [--raw] <query>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `query` | Query to search for. default: 'external=false verified=true disk_space>=1', pass -n to ignore default |

**Options:**

| Option | Description |
|--------|-------------|
| `-n, --no-default` | Disable default query |
| `--storage STORAGE` | Amount of storage to use for pricing, in GiB. default=1.0GiB |
| `-o, --order ORDER` | Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'disk_space,inet_up-'.  default='score-' |

**Notes:**

Query syntax:
query = comparison comparison...
comparison = field op value
field = <name of a field>
op = one of: <, <=, ==, !=, >=, >, in, notin
value = <bool, int, float, string> | 'any' | [value0, value1, ...]
bool: True, False
note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

**Examples:**

```bash

    # search for volumes with greater than 50GB of available storage and greater than 500 Mb/s upload and download speed
    vastai search volumes "disk_space>50 inet_up>500 inet_down>500"
```

!!! tip
    Available fields:
    Name                  Type       Description
    duration:               float     max rental duration in days
    geolocation:            string    Two letter country code. Works with operators =, !=, in, notin (e.g. geolocation not in ['XV','XZ'])
    id:                     int       volume offer unique ID
    inet_down:              float     internet download speed in Mb/s
    inet_up:                float     internet upload speed in Mb/s
    reliability:            float     machine reliability score (see FAQ for explanation)
    storage_cost:           float     storage cost in $/GB/month
    verified:               bool      is the machine verified

---

## search benchmarks

Search machine benchmark results with filters

```bash
vastai search benchmarks [--help] [--api-key API_KEY] [--raw] <query>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `query` | Search query in simple query syntax (see below) |

**Notes:**

Query syntax:
query = comparison comparison...
comparison = field op value
field = <name of a field>
op = one of: <, <=, ==, !=, >=, >, in, notin
value = <bool, int, float, string> | 'any' | [value0, value1, ...]
bool: True, False
note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

**Examples:**

```bash

    # search for benchmarks with score > 100 for llama2_70B model on 2 specific machines
    vastai search benchmarks 'score > 100.0  model=llama2_70B  machine_id in [302,402]'
```

!!! tip
    Available fields:
    Name                  Type       Description
    contract_id             int        ID of instance/contract reporting benchmark
    id                      int        benchmark unique ID
    image                   string     image used for benchmark
    last_update             float      date of benchmark
    machine_id              int        id of machine benchmarked
    model                   string     name of model used in benchmark
    name                    string     name of benchmark
    num_gpus                int        number of gpus used in benchmark
    score                   float      benchmark score result

---

## search invoices

Search billing invoices with filters

```bash
vastai search invoices [--help] [--api-key API_KEY] [--raw] <query>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `query` | Search query in simple query syntax (see below) |

**Notes:**

Query syntax:
query = comparison comparison...
comparison = field op value
field = <name of a field>
op = one of: <, <=, ==, !=, >=, >, in, notin
value = <bool, int, float, string> | 'any' | [value0, value1, ...]
bool: True, False
note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

**Examples:**

```bash

        # search for somewhat reliable single RTX 3090 instances, filter out any duplicates or offers that conflict with our existing stopped instances
        vastai search invoices 'amount_cents>3000  '
```

!!! tip
    Available fields:
    Name                  Type       Description
    id                  int,
    user_id             int,
    when                float,          utc epoch timestamp of initial invoice creation
    paid_on             float,          actual payment date (utc epoch timestamp )
    payment_expected    float,          expected payment date (utc epoch timestamp )
    amount_cents        int,            amount of payment in cents
    is_credit           bool,           is a credit purchase
    is_delayed          bool,           is not yet paid
    balance_before      float,          balance before
    balance_after       float,          balance after
    original_amount     int,            original amount of payment
    event_id            string,
    cut_amount          int,
    cut_percent         float,
    extra               json,
    service             string,         type of payment
    stripe_charge       json,
    stripe_refund       json,
    stripe_payout       json,
    error               json,
    paypal_email        string,         email for paypal/wise payments
    transfer_group      string,
    failed              bool,
    refunded            bool,
    is_check            bool,

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
