# CLI Examples

Common usage patterns and workflows for the Vast.ai CLI.

## Finding GPU Instances

### Basic Search

```bash
# List available offers
vastai search offers --limit 10

# Sort by price (cheapest first)
vastai search offers --order dph_total --limit 10
```

### Filtered Search

```bash
# Find 4+ GPU machines
vastai search offers 'num_gpus >= 4'

# Find RTX 4090s
vastai search offers 'gpu_name = RTX_4090'

# Find high-reliability machines
vastai search offers 'reliability > 0.99'

# Combined filter: 4+ GPUs, 24GB+ VRAM, under $2/hr
vastai search offers 'num_gpus >= 4 gpu_ram >= 24 dph_total < 2.0'
```

### Query Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `=`, `==` | `gpu_name = RTX_4090` | Exact match |
| `!=` | `verified != False` | Not equal |
| `>=` | `num_gpus >= 4` | Greater or equal |
| `<=` | `dph_total <= 1.0` | Less or equal |
| `>` | `reliability > 0.99` | Greater than |
| `<` | `gpu_ram < 16` | Less than |
| `in` | `gpu_name in [RTX_4090,RTX_3090]` | Value in list |
| `notin` | `geolocation notin [CN,RU]` | Value not in list |

## Creating Instances

### Basic Instance

```bash
# Get an offer ID
OFFER_ID=$(vastai search offers --raw | jq '.[0].id')

# Create instance with default image
vastai create instance $OFFER_ID --image pytorch/pytorch:latest
```

### Custom Configuration

```bash
vastai create instance $OFFER_ID \
    --image nvidia/cuda:12.0-devel-ubuntu22.04 \
    --disk 50 \
    --label "training-job" \
    --onstart-cmd "pip install requirements.txt"
```

### With SSH Access

```bash
vastai create instance $OFFER_ID \
    --image ubuntu:22.04 \
    --ssh \
    --direct
```

## Managing Instances

### List Instances

```bash
# Show all instances
vastai show instances

# JSON output for scripting
vastai show instances --raw
```

### Connect via SSH

```bash
# Get SSH command
vastai ssh-url $INSTANCE_ID

# Direct SSH (if direct SSH enabled)
ssh -p PORT root@HOST
```

### Copy Files

```bash
# Upload file
vastai copy local_file.txt $INSTANCE_ID:/root/

# Download file
vastai copy $INSTANCE_ID:/root/results.csv ./

# Upload directory
vastai copy ./data/ $INSTANCE_ID:/root/data/
```

### Destroy Instance

```bash
vastai destroy instance $INSTANCE_ID
```

## Scripting with --raw

### Get Instance IDs

```bash
# Get all instance IDs
vastai show instances --raw | jq '.[].id'

# Get first instance ID
ID=$(vastai show instances --raw | jq '.[0].id')
```

### Filter Offers

```bash
# Get cheapest offer with 4+ GPUs
vastai search offers 'num_gpus >= 4' --raw | \
    jq 'sort_by(.dph_total) | .[0]'
```

### Automated Deployment

```bash
#!/bin/bash
# deploy.sh - Find cheapest 4-GPU machine and deploy

# Find offer
OFFER=$(vastai search offers 'num_gpus >= 4' --raw | jq 'sort_by(.dph_total) | .[0]')
OFFER_ID=$(echo $OFFER | jq '.id')

echo "Found offer: $OFFER_ID at $(echo $OFFER | jq '.dph_total')/hr"

# Create instance
RESULT=$(vastai create instance $OFFER_ID \
    --image pytorch/pytorch:latest \
    --disk 50 \
    --raw)

INSTANCE_ID=$(echo $RESULT | jq '.new_contract')
echo "Created instance: $INSTANCE_ID"

# Wait for ready
sleep 60

# Get SSH info
vastai ssh-url $INSTANCE_ID
```

## Account Management

### Check Balance

```bash
vastai show user
```

### View Invoices

```bash
vastai show invoices
```

### Transfer Credits

```bash
# Recommended: named flags (clearer, order doesn't matter)
vastai transfer credit --recipient user@example.com --amount 10.00

# Short flags
vastai transfer credit -r user@example.com -a 10.00

# Legacy positional syntax (still supported)
vastai transfer credit user@example.com 10.00
```

## Host Commands

### List Your Machines

```bash
vastai show machines
```

### Set Minimum Bid

```bash
vastai set min-bid $MACHINE_ID --price 0.50
```

### Test a Machine

```bash
vastai self-test machine $MACHINE_ID
```

## Troubleshooting

### Check API Connectivity

```bash
vastai show user --explain
```

### Debug Request

```bash
vastai search offers --curl
# Shows equivalent curl command
```

### Verbose Output

```bash
LOGLEVEL=DEBUG vastai show instances
```
