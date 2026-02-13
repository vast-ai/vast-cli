# SDK Quick Start

This guide walks through common SDK operations with working examples.

## Installation

```bash
pip install vastai
```

Or for development:

```bash
pip install -e ".[dev]"
```

## Authentication

```python
from vastai import VastAI

# Option 1: Pass API key directly
client = VastAI(api_key="your-api-key")

# Option 2: Use environment variable
import os
os.environ["VAST_API_KEY"] = "your-api-key"
client = VastAI()

# Option 3: Use stored key from CLI login
# (Run `vastai set api-key YOUR_KEY` first)
client = VastAI()  # Reads from ~/.config/vastai/vast_api_key
```

## Searching for Offers

```python
# Get all offers
offers = client.search_offers()
print(f"Found {len(offers)} offers")

# Limit results
offers = client.search_offers(limit=10)

# Filter by query
offers = client.search_offers(query="num_gpus >= 4 gpu_ram >= 24")

# Sort by price
offers = client.search_offers(order="dph_total")
```

### Query Syntax

The query parameter supports various operators:

```python
# GPU requirements
offers = client.search_offers(query="num_gpus >= 2 gpu_name = RTX_4090")

# Memory requirements
offers = client.search_offers(query="gpu_ram >= 24 cpu_ram >= 64")

# Reliability filter
offers = client.search_offers(query="reliability > 0.99")

# Combined filters
offers = client.search_offers(
    query="num_gpus >= 4 gpu_ram >= 24 dph_total < 2.0",
    order="dph_total"
)
```

### Query Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Equals | `gpu_name = RTX_4090` |
| `!=` | Not equals | `gpu_name != GTX_1080` |
| `>` | Greater than | `gpu_ram > 16` |
| `>=` | Greater or equal | `num_gpus >= 2` |
| `<` | Less than | `dph_total < 1.0` |
| `<=` | Less or equal | `reliability <= 0.99` |
| `in` | In list | `geolocation in ["US", "CA"]` |
| `notin` | Not in list | `geolocation notin ["CN", "RU"]` |

### Common Query Fields

| Field | Description |
|-------|-------------|
| `num_gpus` | Number of GPUs |
| `gpu_name` | GPU model name |
| `gpu_ram` | GPU memory (GB) |
| `cpu_cores` | Number of CPU cores |
| `cpu_ram` | CPU memory (GB) |
| `disk_space` | Available disk (GB) |
| `dph_total` | Total price per hour |
| `reliability` | Host reliability (0-1) |
| `geolocation` | Country code |

## Managing Instances

### Create an Instance

```python
# Find an offer
offers = client.search_offers(query="num_gpus = 1", limit=1)
offer_id = offers[0]["id"]

# Create instance
result = client.create_instance(
    id=offer_id,
    image="pytorch/pytorch:latest",
    disk=20,  # GB
    label="my-instance"
)

if result.get("success"):
    instance_id = result["new_contract"]
    print(f"Created instance: {instance_id}")
```

### List Instances

```python
instances = client.show_instances()
for inst in instances:
    print(f"ID: {inst['id']}, Status: {inst['actual_status']}")
```

### Instance Status Values

| Status | Description |
|--------|-------------|
| `running` | Instance is active and ready |
| `loading` | Instance is starting up |
| `exited` | Instance has stopped |
| `offline` | Host is offline |

### Stop and Start Instances

```python
# Stop an instance
client.stop_instance(id=instance_id)

# Start it again
client.start_instance(id=instance_id)

# Reboot
client.reboot_instance(id=instance_id)
```

### Destroy an Instance

```python
result = client.destroy_instance(id=instance_id)
if result.get("success"):
    print("Instance destroyed")
```

## SSH Access

```python
# Get SSH command for an instance
instances = client.show_instances()
for inst in instances:
    ssh_host = inst.get("ssh_host")
    ssh_port = inst.get("ssh_port")
    if ssh_host and ssh_port:
        print(f"ssh -p {ssh_port} root@{ssh_host}")
```

## File Transfer

```python
# Copy files to instance
client.copy(
    src="/local/path/file.txt",
    dst=f"{instance_id}:/remote/path/"
)

# Copy files from instance
client.copy(
    src=f"{instance_id}:/remote/path/results/",
    dst="/local/path/"
)
```

## Billing

```python
# Show current balance
user = client.show_user()
print(f"Credit: ${user.get('credit', 0):.2f}")

# Show invoices
invoices = client.show_invoices()
for inv in invoices:
    print(f"Invoice {inv['id']}: ${inv.get('total', 0):.2f}")
```

## Error Handling Best Practices

```python
from vastai import VastAI

client = VastAI(api_key="your-api-key")

def create_instance_safely(offer_id: int, image: str) -> dict | None:
    """Create an instance with proper error handling."""
    try:
        result = client.create_instance(id=offer_id, image=image)

        if not result.get("success"):
            print(f"API error: {result.get('msg', 'Unknown error')}")
            return None

        return result

    except Exception as e:
        print(f"Exception: {e}")
        return None

# Usage
result = create_instance_safely(12345, "ubuntu:22.04")
```

## Debug Mode

Enable debug output to see API calls:

```python
client = VastAI(api_key="your-key", explain=True, quiet=False)
client.search_offers(limit=1)
# Prints: GET https://console.vast.ai/api/v0/bundles?...
```

## Working with Teams

```python
# Create a team
result = client.create_team(team_name="my-team")

# List team members
members = client.show_members()
for member in members:
    print(f"Member: {member['email']} (ID: {member['id']})")

# Invite a member
client.invite_member(email="colleague@example.com")

# Remove a member
client.remove_member(id=member_id)
```

## Volumes (Persistent Storage)

```python
# Search volume offers
volume_offers = client.search_volumes()

# List your volumes
volumes = client.show_volumes()
for vol in volumes:
    print(f"Volume: {vol['name']} ({vol['size']}GB)")

# Clone a volume
result = client.clone_volume(src_id=source_volume_id, dst_id=dest_offer_id)

# Delete a volume
client.delete_volume(id=volume_id)
```

Note: Volumes are associated with instances at creation time, not attached/detached dynamically.

## Templates

```python
# Search available templates
templates = client.search_templates()

# Create instance from template
result = client.create_instance(
    id=offer_id,
    template_id=template_id
)
```

## Next Steps

- [API Reference](reference/vastai.md) - Full method documentation
- [CLI Commands](../cli/index.md) - CLI reference
