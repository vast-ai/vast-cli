# CLI Overview

The Vast.ai CLI provides command-line access to all Vast.ai platform features using a simple "verb-object" pattern.

## Installation

=== "Standalone (wget)"

    ```bash
    wget https://raw.githubusercontent.com/vast-ai/vast-cli/master/vast.py
    chmod +x vast.py
    ./vast.py --help
    ```

=== "Package (pip)"

    ```bash
    pip install vastai
    vastai --help
    ```

## Command Pattern

Commands follow a **verb-object** pattern:

```
vastai <verb> <object> [arguments] [options]
```

Examples:

| Command | Description |
|---------|-------------|
| `vastai search offers` | Search for available GPU offers |
| `vastai show instances` | List your running instances |
| `vastai create instance` | Create a new instance |
| `vastai destroy instance` | Destroy an instance |
| `vastai set api-key` | Set your API key |

## Authentication

Get your API key from [https://cloud.vast.ai/manage-keys/](https://cloud.vast.ai/manage-keys/).

```bash
vastai set api-key YOUR_API_KEY
```

### API Key Storage

Keys are searched in this order:

1. `--api-key` command-line argument
2. `VAST_API_KEY` environment variable
3. `~/.config/vastai/vast_api_key` (XDG standard, preferred)
4. `~/.vast_api_key` (legacy location, still supported)

The CLI stores keys in the XDG-compliant location by default.

## Global Options

All commands support these options:

| Option | Description |
|--------|-------------|
| `--api-key KEY` | Override stored API key |
| `--url URL` | Override server URL |
| `--raw` | Output machine-readable JSON |
| `--explain` | Show API endpoint being called |
| `--curl` | Show equivalent curl command |
| `--retry N` | Set retry limit (default: 3) |

## Reading Command Help

Understanding the help output format:

### Required vs Optional Arguments

- **Positional arguments** (shown without `--`) are **required**
- **Options** (shown with `--`) are **optional** unless noted

### Argument Types

- **Flags** like `--ssh` or `--raw` are boolean toggles (no value needed)
- **Value options** show a metavar: `--disk DISK` means `--disk 50`
- **UPPERCASE** metavars indicate the expected value type:
    - `ID` - typically an integer identifier
    - `PRICE` - a decimal number
    - `IMAGE` - a string (docker image name)
    - `PATH` - a file/directory path

### Example

```
usage: vastai create instance ID [OPTIONS]

positional arguments:
  id                    id of instance type to launch  ← REQUIRED (integer)

options:
  --disk DISK           size of local disk in GB       ← OPTIONAL (takes number)
  --image IMAGE         docker image to launch         ← OPTIONAL (takes string)
  --ssh                 Launch as SSH instance         ← OPTIONAL (flag, no value)
```

## Output Formats

### Human-Readable (default)

```bash
vastai show instances
```

Output is formatted as tables for easy reading.

### JSON (--raw)

```bash
vastai show instances --raw
```

Output is valid JSON for scripting:

```bash
vastai show instances --raw | jq '.[0].id'
```

## Tab Completion

Enable tab completion with argcomplete:

```bash
pip install argcomplete
activate-global-python-argcomplete
```

Or for a single session:

```bash
eval "$(register-python-argcomplete vastai)"
```

## Query Syntax

Many commands accept a `--query` parameter for filtering results. The query language supports flexible operators and field comparisons.

### Operators

| Operator | Aliases | Description | Example |
|----------|---------|-------------|---------|
| `=` | `==`, `eq` | Equals | `gpu_name = RTX_4090` |
| `!=` | `neq`, `not eq`, `noteq` | Not equals | `gpu_name != GTX_1080` |
| `>` | `gt` | Greater than | `gpu_ram > 16` |
| `>=` | `gte` | Greater or equal | `num_gpus >= 2` |
| `<` | `lt` | Less than | `dph_total < 1.0` |
| `<=` | `lte` | Less or equal | `reliability <= 0.99` |
| `in` | | Value in list | `geolocation in [US,CA,UK]` |
| `notin` | `not in`, `nin` | Value not in list | `geolocation notin [CN,RU]` |

### Wildcards

Special values for flexible matching:

| Wildcard | Description | Example |
|----------|-------------|---------|
| `any` | Match any value | `cuda_vers = any` |
| `?` | Nullable (any or null) | `inet_up = ?` |
| `*` | Wildcard in strings | `gpu_name = RTX_*` |

### String Values with Spaces

When searching for values that contain spaces (like GPU names), you have two options:

1. **Underscores (recommended)** - most portable across shells:
   ```bash
   vastai search offers "gpu_name=RTX_4090"
   ```
   Underscores in values are converted to spaces when sent to the API.

2. **Escaped double quotes** - wrap query in single quotes, escape inner double quotes:
   ```bash
   vastai search offers 'gpu_name=\"RTX 4090\"'
   ```

!!! warning
    Single quotes around values do NOT work: `gpu_name='RTX 4090'` will fail.

### Quoting Rules

- Simple values don't need quotes: `gpu_ram >= 24`
- Values with spaces: use underscores (`RTX_4090`) or escaped quotes (`\"RTX 4090\"`)
- List values use brackets: `geolocation in [US,CA,UK]`
- Multiple conditions are space-separated (implicit AND)

### Common Query Fields

| Field | Description | Type |
|-------|-------------|------|
| `num_gpus` | Number of GPUs | int |
| `gpu_name` | GPU model name | string |
| `gpu_ram` | GPU memory (GB) | float |
| `gpu_frac` | GPU fraction (for partial GPU) | float |
| `cpu_cores` | Number of CPU cores | int |
| `cpu_ram` | System memory (GB) | float |
| `disk_space` | Available disk (GB) | float |
| `dph_total` | Total price per hour ($) | float |
| `reliability` | Host reliability score (0-1) | float |
| `geolocation` | Country code | string |
| `inet_up` | Upload bandwidth (Mbps) | float |
| `inet_down` | Download bandwidth (Mbps) | float |
| `cuda_vers` | CUDA version | float |
| `dlperf` | Deep learning performance score | float |

### Examples

```bash
# High-end GPUs with good reliability
vastai search offers "num_gpus>=4 gpu_ram>=24 reliability>0.99"

# Budget option under $1/hour
vastai search offers "dph_total<1.0" --order "dph_total"

# Specific GPU model in North America
vastai search offers "gpu_name=RTX_4090 geolocation in [US,CA]"

# Exclude certain regions
vastai search offers "geolocation notin [CN,RU,IR]"
```

## Next Steps

- [Command Reference](commands.md) - Full list of all commands
- [Examples](examples.md) - Common usage patterns
