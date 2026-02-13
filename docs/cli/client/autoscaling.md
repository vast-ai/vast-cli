# Autoscaling Commands

Commands for managing autoscale/worker groups and serverless endpoints.

## create workergroup

Create an autoscaling worker group for serverless inference

```bash
vastai workergroup create [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--template_hash TEMPLATE_HASH` | template hash (required, but **Note**: if you use this field, you can skip search_params, as they are automatically inferred from the template) |
| `--template_id TEMPLATE_ID` | template id (optional) |
| `-n, --no-default` | Disable default search param query args |
| `--launch_args LAUNCH_ARGS` | launch args  string for create instance  ex: "--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64" |
| `--endpoint_name ENDPOINT_NAME` | deployment endpoint name (allows multiple workergroups to share same deployment endpoint) |
| `--endpoint_id ENDPOINT_ID` | deployment endpoint id (allows multiple workergroups to share same deployment endpoint) |
| `--test_workers TEST_WORKERS` | number of workers to create to get an performance estimate for while initializing workergroup (default 3) |
| `--gpu_ram GPU_RAM` | estimated GPU RAM req  (independent of search string) |
| `--search_params SEARCH_PARAMS` | search param string for search offers    ex: "gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64" |
| `--min_load MIN_LOAD` | [NOTE: this field isn't currently used at the workergroup level] minimum floor load in perf units/s  (token/s for LLms) |
| `--target_util TARGET_UTIL` | [NOTE: this field isn't currently used at the workergroup level] target capacity utilization (fraction, max 1.0, default 0.9) |
| `--cold_mult COLD_MULT` | [NOTE: this field isn't currently used at the workergroup level]cold/stopped instance capacity target as multiple of hot capacity target (default 2.0) |
| `--cold_workers COLD_WORKERS` | min number of workers to keep 'cold' for this workergroup |

**Notes:**

Create a new autoscaling group to manage a pool of worker instances.

---

## delete workergroup

Delete an autoscaling worker group

```bash
vastai delete workergroup ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of group to delete |

**Notes:**

Note that deleting a workergroup doesn't automatically destroy all the instances that are associated with your workergroup.

---

## update workergroup

Update an existing autoscale group

```bash
vastai update workergroup WORKERGROUP_ID --endpoint_id ENDPOINT_ID [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of autoscale group to update |

**Options:**

| Option | Description |
|--------|-------------|
| `--min_load MIN_LOAD` | minimum floor load in perf units/s  (token/s for LLms) |
| `--target_util TARGET_UTIL` | target capacity utilization (fraction, max 1.0, default 0.9) |
| `--cold_mult COLD_MULT` | cold/stopped instance capacity target as multiple of hot capacity target (default 2.5) |
| `--cold_workers COLD_WORKERS` | min number of workers to keep 'cold' for this workergroup |
| `--test_workers TEST_WORKERS` | number of workers to create to get an performance estimate for while initializing workergroup (default 3) |
| `--gpu_ram GPU_RAM` | estimated GPU RAM req  (independent of search string) |
| `--template_hash TEMPLATE_HASH` | template hash (**Note**: if you use this field, you can skip search_params, as they are automatically inferred from the template) |
| `--template_id TEMPLATE_ID` | template id |
| `--search_params SEARCH_PARAMS` | search param string for search offers    ex: "gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64" |
| `-n, --no-default` | Disable default search param query args |
| `--launch_args LAUNCH_ARGS` | launch args  string for create instance  ex: "--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/public.vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64" |
| `--endpoint_name ENDPOINT_NAME` | deployment endpoint name (allows multiple workergroups to share same deployment endpoint) |
| `--endpoint_id ENDPOINT_ID` | deployment endpoint id (allows multiple workergroups to share same deployment endpoint) |

---

## show workergroups

List all your autoscaling worker groups

```bash
vastai show workergroups [--api-key API_KEY]
```

---

## get wrkgrp-logs

Get logs for an autoscaling worker group

```bash
vastai get wrkgrp-logs ID [--api-key API_KEY]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of endpoint group to fetch logs from |

**Options:**

| Option | Description |
|--------|-------------|
| `--level LEVEL` | log detail level (0 to 3) |

---

## create endpoint

Create a serverless inference endpoint

```bash
vastai create endpoint [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--min_load MIN_LOAD` | minimum floor load in perf units/s  (token/s for LLms) |
| `--min_cold_load MIN_COLD_LOAD` | minimum floor load in perf units/s (token/s for LLms), but allow handling with cold workers |
| `--target_util TARGET_UTIL` | target capacity utilization (fraction, max 1.0, default 0.9) |
| `--cold_mult COLD_MULT` | cold/stopped instance capacity target as multiple of hot capacity target (default 2.5) |
| `--cold_workers COLD_WORKERS` | min number of workers to keep 'cold' when you have no load (default 5) |
| `--max_workers MAX_WORKERS` | max number of workers your endpoint group can have (default 20) |
| `--endpoint_name ENDPOINT_NAME` | deployment endpoint name (allows multiple autoscale groups to share same deployment endpoint) |

**Notes:**

Create a new endpoint group to manage many autoscaling groups

---

## delete endpoint

Delete a serverless inference endpoint

```bash
vastai delete endpoint ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of endpoint group to delete |

---

## update endpoint

Update an existing endpoint group

```bash
vastai update endpoint ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of endpoint group to update |

**Options:**

| Option | Description |
|--------|-------------|
| `--min_load MIN_LOAD` | minimum floor load in perf units/s  (token/s for LLms) |
| `--min_cold_load MIN_COLD_LOAD` | minimum floor load in perf units/s  (token/s for LLms), but allow handling with cold workers |
| `--endpoint_state ENDPOINT_STATE` | active, suspended, or stopped |
| `--target_util TARGET_UTIL` | target capacity utilization (fraction, max 1.0, default 0.9) |
| `--cold_mult COLD_MULT` | cold/stopped instance capacity target as multiple of hot capacity target (default 2.5) |
| `--cold_workers COLD_WORKERS` | min number of workers to keep 'cold' when you have no load (default 5) |
| `--max_workers MAX_WORKERS` | max number of workers your endpoint group can have (default 20) |
| `--endpoint_name ENDPOINT_NAME` | deployment endpoint name (allows multiple workergroups to share same deployment endpoint) |

---

## show endpoints

List all your serverless endpoints

```bash
vastai show endpoints [--api-key API_KEY]
```

---

## get endpt-logs

Get logs for a serverless endpoint

```bash
vastai get endpt-logs ID [--api-key API_KEY]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of endpoint group to fetch logs from |

**Options:**

| Option | Description |
|--------|-------------|
| `--level LEVEL` | log detail level (0 to 3) |

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
