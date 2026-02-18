# Instance Commands

Commands for creating and managing GPU instances.

## create instance

Create a new GPU instance from an offer

```bash
vastai create instance ID [OPTIONS] [--args ...]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance type to launch (returned from search offers) |

**Options:**

| Option | Description |
|--------|-------------|
| `--template_hash TEMPLATE_HASH` | Create instance from template info |
| `--user USER` | User to use with docker create. This breaks some images, so only use this if you are certain you need it. |
| `--disk DISK` | size of local disk partition in GB |
| `--image IMAGE` | docker container image to launch |
| `--login LOGIN` | docker login arguments for private repo authentication, surround with '' |
| `--label LABEL` | label to set on the instance |
| `--onstart ONSTART` | filename to use as onstart script |
| `--onstart-cmd ONSTART_CMD` | contents of onstart script as single argument |
| `--entrypoint ENTRYPOINT` | override entrypoint for args launch instance |
| `--ssh` | Launch as an ssh instance type |
| `--jupyter` | Launch as a jupyter instance instead of an ssh instance |
| `--direct` | Use (faster) direct connections for jupyter & ssh |
| `--jupyter-dir JUPYTER_DIR` | For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory |
| `--jupyter-lab` | For runtype 'jupyter', Launch instance with jupyter lab |
| `--lang-utf8` | Workaround for images with locale problems: install and generate locales before instance launch, and set locale to C.UTF-8 |
| `--python-utf8` | Workaround for images with locale problems: set python's locale to C.UTF-8 |
| `--env ENV` | env variables and port mapping options, surround with '' |
| `--args ...` | list of arguments passed to container ENTRYPOINT. Onstart is recommended for this purpose. (must be last argument) |
| `--force` | Skip sanity checks when creating from an existing instance |
| `--cancel-unavail` | Return error if scheduling fails (rather than creating a stopped instance) |
| `--bid_price BID_PRICE` | (OPTIONAL) create an INTERRUPTIBLE instance with per machine bid price in $/hour |
| `--create-volume VOLUME_ASK_ID` | Create a new local volume using an ID returned from the "search volumes" command and link it to the new instance |
| `--link-volume EXISTING_VOLUME_ID` | ID of an existing rented volume to link to the instance during creation. (returned from "show volumes" cmd) |
| `--volume-size VOLUME_SIZE` | Size of the volume to create in GB. Only usable with --create-volume (default 15GB) |
| `--mount-path MOUNT_PATH` | The path to the volume from within the new instance container. e.g. /root/volume |
| `--volume-label VOLUME_LABEL` | (optional) A name to give the new volume. Only usable with --create-volume |

**Notes:**

Performs the same action as pressing the "RENT" button on the website at https://console.vast.ai/create/
Creates an instance from an offer ID (which is returned from "search offers"). Each offer ID can only be used to create one instance.
Besides the offer ID, you must pass in an '--image' argument as a minimum.
If you use args/entrypoint launch mode, we create a container from your image as is, without attempting to inject ssh and or jupyter.
If you use the args launch mode, you can override the entrypoint with --entrypoint, and pass arguments to the entrypoint with --args.
If you use --args, that must be the last argument, as any following tokens are consumed into the args string.
For ssh/jupyter launch types, use --onstart-cmd to pass in startup script, instead of --entrypoint and --args.

**Examples:**

```bash

# create an on-demand instance with the PyTorch (cuDNN Devel) template and 64GB of disk
vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 --disk 64

# create an on-demand instance with the pytorch/pytorch image, 40GB of disk, open 8081 udp, direct ssh, set hostname to billybob, and a small onstart script
vastai create instance 6995713 --image pytorch/pytorch --disk 40 --env '-p 8081:8081/udp -h billybob' --ssh --direct --onstart-cmd "env | grep _ >> /etc/environment; echo 'starting up'";

# create an on-demand instance with the bobsrepo/pytorch:latest image, 20GB of disk, open 22, 8080, jupyter ssh, and set some env variables
vastai create instance 384827  --image bobsrepo/pytorch:latest --login '-u bob -p 9d8df!fd89ufZ docker.io' --jupyter --direct --env '-e TZ=PDT -e XNAME=XX4 -p 22:22 -p 8080:8080' --disk 20

# create an on-demand instance with the pytorch/pytorch image, 40GB of disk, override the entrypoint to bash and pass bash a simple command to keep the instance running. (args launch without ssh/jupyter)
vastai create instance 5801802 --image pytorch/pytorch --disk 40 --onstart-cmd 'bash' --args -c 'echo hello; sleep infinity;'

# create an interruptible (spot) instance with the PyTorch (cuDNN Devel) template, 64GB of disk, and a bid price of $0.10/hr
vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 --disk 64 --bid_price 0.1
```

**Return Value:**

```json
Returns a json reporting the instance ID of the newly created instance:
{'success': True, 'new_contract': 7835610}
```

---

## launch instance

Launch a new instance using search parameters to auto-select the best offer

```bash
vastai launch instance [--help] [--api-key API_KEY] <gpu_name> <num_gpus> <image> [geolocation] [disk_space]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-n, --num-gpus {1,2,4,8,12,14}` | Number of GPUs required |
| `-r, --region REGION` | Geographical location of the instance |
| `-i, --image IMAGE` | Name of the image to use for instance |
| `-d, --disk DISK` | Disk space required in GB |
| `-o, --order ORDER` | Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'num_gpus,total_flops-'.  default='score-' |
| `--login LOGIN` | docker login arguments for private repo authentication, surround with '' |
| `--label LABEL` | label to set on the instance |
| `--onstart ONSTART` | filename to use as onstart script |
| `--onstart-cmd ONSTART_CMD` | contents of onstart script as single argument |
| `--entrypoint ENTRYPOINT` | override entrypoint for args launch instance |
| `--ssh` | Launch as an ssh instance type |
| `--jupyter` | Launch as a jupyter instance instead of an ssh instance |
| `--direct` | Use (faster) direct connections for jupyter & ssh |
| `--jupyter-dir JUPYTER_DIR` | For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory |
| `--jupyter-lab` | For runtype 'jupyter', Launch instance with jupyter lab |
| `--lang-utf8` | Workaround for images with locale problems: install and generate locales before instance launch, and set locale to C.UTF-8 |
| `--python-utf8` | Workaround for images with locale problems: set python's locale to C.UTF-8 |
| `--env ENV` | env variables and port mapping options, surround with '' |
| `--args ...` | list of arguments passed to container ENTRYPOINT. Onstart is recommended for this purpose. (must be last argument) |
| `--force` | Skip sanity checks when creating from an existing instance |
| `--cancel-unavail` | Return error if scheduling fails (rather than creating a stopped instance) |
| `--template_hash TEMPLATE_HASH` | template hash which contains all relevant information about an instance. This can be used as a replacement for other parameters describing the instance configuration |

**Notes:**

Launches an instance based on the given parameters. The instance will be created with the top offer from the search results.
Besides the gpu_name and num_gpus, you must pass in an '--image' argument as a minimum.
If you use args/entrypoint launch mode, we create a container from your image as is, without attempting to inject ssh and or jupyter.
If you use the args launch mode, you can override the entrypoint with --entrypoint, and pass arguments to the entrypoint with --args.
If you use --args, that must be the last argument, as any following tokens are consumed into the args string.
For ssh/jupyter launch types, use --onstart-cmd to pass in startup script, instead of --entrypoint and --args.

**Examples:**

```bash

    # launch a single RTX 3090 instance with the pytorch image and 16 GB of disk space located anywhere
    # launch a 4x RTX 3090 instance with the pytorch image and 32 GB of disk space located in North America
```

!!! tip
    python vast.py launch instance -g RTX_3090 -n 1 -i pytorch/pytorch
    python vast.py launch instance -g RTX_3090 -n 4 -i pytorch/pytorch -d 32.0 -r North_America
    Available fields:
    Name                    Type      Description
    num_gpus:               int       # of GPUs
    gpu_name:               string    GPU model name
    region:                 string    Region of the instance
    image:                  string    Docker image name
    disk_space:             float     Disk space in GB
    ssh, jupyter, direct:   bool      Flags to specify the instance type and connection method.
    env:                    str       Environment variables and port mappings, encapsulated in single quotes.
    args:                   list      Arguments passed to the container's ENTRYPOINT, used only if '--args' is specified.

---

## destroy instance

Destroy an instance (irreversible, deletes data)

```bash
vastai destroy instance id [-h] [--api-key API_KEY] [--raw]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to delete |

!!! warning
    Performs the same action as pressing the "DESTROY" button on the website at https://console.vast.ai/instances/
    WARNING: This action is IMMEDIATE and IRREVERSIBLE. All data on the instance will be permanently
    deleted unless you have saved it to a persistent volume or external storage.

**Examples:**

```bash
    vastai destroy instance 12345              # Destroy instance with ID 12345
```

!!! tip
    Before destroying:
    - Save any important data using 'vastai copy' or by mounting a persistent volume
    - Check instance ID carefully with 'vastai show instances'
    - Consider using 'vastai stop instance' if you want to pause without data loss

---

## destroy instances

Destroy a list of instances (irreversible, deletes data)

```bash
vastai destroy instances IDS [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `ids` | ids of instances to destroy |

---

## start instance

Start a stopped instance

```bash
vastai start instance ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | ID of instance to start/restart |

**Notes:**

This command attempts to bring an instance from the "stopped" state into the "running" state. This is subject to resource availability on the machine that the instance is located on.
If your instance is stuck in the "scheduling" state for more than 30 seconds after running this, it likely means that the required resources on the machine to run your instance are currently unavailable.

**Examples:**

```bash
    vastai start instances $(vastai show instances -q)
    vastai start instance 329838
```

---

## start instances

Start multiple stopped instances

```bash
vastai start instances IDS [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `ids` | ids of instances to start |

---

## stop instance

Stop a running instance

```bash
vastai stop instance ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to stop |

**Notes:**

This command brings an instance from the "running" state into the "stopped" state. When an instance is "stopped" all of your data on the instance is preserved,
and you can resume use of your instance by starting it again. Once stopped, starting an instance is subject to resource availability on the machine that the instance is located on.
There are ways to move data off of a stopped instance, which are described here: https://vast.ai/docs/gpu-instances/data-movement

---

## stop instances

Stop multiple running instances

```bash
vastai stop instances IDS [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `ids` | ids of instances to stop |

**Examples:**

```bash
    vastai stop instances $(vastai show instances -q)
    vastai stop instances 329838 984849
```

---

## reboot instance

Reboot (stop/start) an instance

```bash
vastai reboot instance ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to reboot |

**Options:**

| Option | Description |
|--------|-------------|
| `--schedule {HOURLY,DAILY,WEEKLY}` | try to schedule a command to run hourly, daily, or monthly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY |
| `--start_date START_DATE` | Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional) |
| `--end_date END_DATE` | End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional) |
| `--day DAY` | Day of week you want scheduled job to run on (0-6, where 0=Sunday) or "*". Default will be 0. For ex. --day 0 |
| `--hour HOUR` | Hour of day you want scheduled job to run on (0-23) or "*" (UTC). Default will be 0. For ex. --hour 16 |

**Notes:**

Stops and starts container without any risk of losing GPU priority.

---

## recycle instance

Destroy and recreate an instance with the same configuration

```bash
vastai recycle instance ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to recycle |

**Notes:**

Destroys and recreates container in place (from newly pulled image) without any risk of losing GPU priority.

---

## label instance

Assign a string label to an instance

```bash
vastai label instance <id> <label>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to label |
| `label` | label to set |

---

## update instance

Update an instance configuration or recreate from a template

```bash
vastai update instance ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to update |

**Options:**

| Option | Description |
|--------|-------------|
| `--template_id TEMPLATE_ID` | new template ID to associate with the instance |
| `--template_hash_id TEMPLATE_HASH_ID` | new template hash ID to associate with the instance |
| `--image IMAGE` | new image UUID for the instance |
| `--args ARGS` | new arguments for the instance |
| `--env ENV` | new environment variables for the instance |
| `--onstart ONSTART` | new onstart script for the instance |

---

## prepay instance

Prepay credits for a reserved instance to prevent interruption

```bash
vastai prepay instance ID AMOUNT
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to prepay for |
| `amount` | amount of instance credit prepayment (default discount func of 0.2 for 1 month, 0.3 for 3 months) |

---

## change bid

Change the bid price for a spot/interruptible instance

```bash
vastai change bid id [--price PRICE]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance type to change bid |

**Options:**

| Option | Description |
|--------|-------------|
| `--price PRICE` | per machine bid price in $/hour |
| `--schedule {HOURLY,DAILY,WEEKLY}` | try to schedule a command to run hourly, daily, or monthly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY |
| `--start_date START_DATE` | Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional) |
| `--end_date END_DATE` | End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional) |
| `--day DAY` | Day of week you want scheduled job to run on (0-6, where 0=Sunday) or "*". Default will be 0. For ex. --day 0 |
| `--hour HOUR` | Hour of day you want scheduled job to run on (0-23) or "*" (UTC). Default will be 0. For ex. --hour 16 |

**Notes:**

Change the current bid price of instance id to PRICE.
If PRICE is not specified, then a winning bid price is used as the default.

---

## show instance

Show details for a specific instance

```bash
vastai show instance ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to show |

---

## show instances

List all your running and stopped instances

```bash
vastai show instances [OPTIONS] [--api-key API_KEY] [--raw]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-q, --quiet` | only display numeric ids |

**Notes:**

Lists all instances owned by the authenticated user, including running, pending, and stopped instances.

**Examples:**

```bash
    vastai show instances                      # List all instances in table format
    vastai show instances --raw                # Output as JSON for scripting
    vastai show instances --raw | jq '.[0]'   # Get first instance details
    vastai show instances -q                   # List only instance IDs
```

!!! tip
    Output includes: instance ID, machine ID, status, GPU info, rental cost, duration, and connection details.

---

## logs

Get the logs for an instance

```bash
vastai logs INSTANCE_ID [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `INSTANCE_ID` | id of instance |

**Options:**

| Option | Description |
|--------|-------------|
| `--tail TAIL` | Number of lines to show from the end of the logs (default '1000') |
| `--filter FILTER` | Grep filter for log entries |
| `--daemon-logs` | Fetch daemon system logs instead of container logs |

---

## execute

Execute a command on a running instance

```bash
vastai execute id COMMAND
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance to execute on |
| `COMMAND` | bash command surrounded by single quotes |

**Options:**

| Option | Description |
|--------|-------------|
| `--schedule {HOURLY,DAILY,WEEKLY}` | try to schedule a command to run hourly, daily, or monthly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY |
| `--start_date START_DATE` | Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional) |
| `--end_date END_DATE` | End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional) |
| `--day DAY` | Day of week you want scheduled job to run on (0-6, where 0=Sunday) or "*". Default will be 0. For ex. --day 0 |
| `--hour HOUR` | Hour of day you want scheduled job to run on (0-23) or "*" (UTC). Default will be 0. For ex. --hour 16 |

**Examples:**

```bash
  vastai execute 99999 'ls -l -o -r'
  vastai execute 99999 'rm -r home/delete_this.txt'
  vastai execute 99999 'du -d2 -h'
```

!!! tip
    available commands:
    ls                 List directory contents
    rm                 Remote files or directories
    du                 Summarize device usage for a set of files

**Return Value:**

```json
Returns the output of the command which was executed on the instance, if successful. May take a few seconds to retrieve the results.
```

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
