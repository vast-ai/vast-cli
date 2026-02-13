# CLI Command Reference

This reference is auto-generated from `vastai --help` output.

!!! tip "Regenerate this page"
    Run `python scripts/generate_cli_docs.py` to update this documentation.

## Overview

```
usage: vast.py [-h] [--url URL] [--retry RETRY] [--explain] [--raw] [--full] [--curl] [--api-key API_KEY] [--version]
               [--no-color]
               command ...

positional arguments:
 command                       command to run. one of:
  help                         print this help message
  attach ssh                   Attach an SSH key to an instance for remote access
  cancel copy                  Cancel an in-progress file copy operation
  cancel sync                  Cancel an in-progress file sync operation
  change bid                   Change the bid price for a spot/interruptible instance
  clone volume                 Create a copy of an existing volume
  copy                         Copy files/directories between instances or between local and instance
  cloud copy                   Copy files between instances and cloud storage (S3, GCS, Azure)
  take snapshot                Create a snapshot of a running container and push to registry
  create api-key               Create a new API key with custom permissions
  create cluster               [Beta] Create a new machine cluster
  create env-var               Create a new account-level environment variable
  create ssh-key               Add an SSH public key to your account
  create workergroup           Create an autoscaling worker group for serverless inference
  create endpoint              Create a serverless inference endpoint
  create instance              Create a new GPU instance from an offer
  create subaccount            Create a subaccount for delegated access
  create team                  Create a new team
  create team-role             Create a custom role with specific permissions
  create template              Create a reusable instance configuration template
  create volume                Create a new persistent storage volume
  create network-volume        [Host] [Beta] Create a new network-attached storage volume
  create overlay               [Beta] Create a virtual overlay network on a cluster
  delete api-key               Delete an API key
  delete ssh-key               Remove an SSH key from your account
  delete scheduled-job         Delete a scheduled job
  delete cluster               [Beta] Delete a machine cluster
  delete workergroup           Delete an autoscaling worker group
  delete endpoint              Delete a serverless inference endpoint
  delete env-var               Delete a user environment variable
  delete overlay               [Beta] Delete an overlay network and its instances
  delete template              Delete a template
  delete volume                Delete a persistent storage volume
  destroy instance             Destroy an instance (irreversible, deletes data)
  destroy instances            Destroy a list of instances (irreversible, deletes data)
  destroy team                 Delete your team and remove all members
  detach ssh                   Remove an SSH key from an instance
  execute                      Execute a command on a running instance
  get endpt-logs               Get logs for a serverless endpoint
  get wrkgrp-logs              Get logs for an autoscaling worker group
  invite member                Invite a user to join your team
  join cluster                 [Beta] Add a machine to an existing cluster
  join overlay                 [Beta] Connect an instance to an overlay network
  label instance               Assign a string label to an instance
  launch instance              Launch a new instance using search parameters to auto-select the best offer
  logs                         Get the logs for an instance
  prepay instance              Prepay credits for a reserved instance to prevent interruption
  reboot instance              Reboot (stop/start) an instance
  recycle instance             Destroy and recreate an instance with the same configuration
  remove member                Remove a team member
  remove team-role             Delete a custom role from your team
  reports                      [Host] Get usage and performance reports for a machine
  reset api-key                Invalidate current API key and generate a new one
  start instance               Start a stopped instance
  start instances              Start multiple stopped instances
  stop instance                Stop a running instance
  stop instances               Stop multiple running instances
  tfa activate                 Activate a new 2FA method by verifying the code
  tfa delete                   Remove a 2FA method from your account
  tfa login                    Complete 2FA login by verifying code
  tfa regen-codes              Regenerate backup codes for 2FA
  tfa resend-sms               Resend SMS 2FA code
  tfa send-sms                 Request a 2FA SMS verification code
  tfa status                   Shows the current 2FA status and configured methods
  tfa totp-setup               Generate TOTP secret and QR code for Authenticator app setup
  tfa update                   Update a 2FA method's settings
  search benchmarks            Search machine benchmark results with filters
  search invoices              Search billing invoices with filters
  search offers                Search available GPU offers with filters
  search templates             Search available templates with filters
  search volumes               Search available volume offers with filters
  search network-volumes       [Host] [Beta] Search available network volume offers with filters
  set api-key                  Set the API key for CLI and SDK authentication
  set user                     Update account settings from a JSON file
  ssh-url                      Generate SSH connection URL for an instance
  scp-url                      Generate SCP file transfer URL for an instance
  show api-key                 Show details for a specific API key
  show api-keys                List all API keys for your account
  show audit-logs              Show account activity and audit logs
  show scheduled-jobs          List all scheduled automation jobs
  show ssh-keys                List all SSH keys registered to your account
  show workergroups            List all your autoscaling worker groups
  show endpoints               List all your serverless endpoints
  show connections             [Beta] Show network connections between instances
  show deposit                 Show prepaid deposit balance for a reserved instance
  show earnings                [Host] Show rental income history for your machines
  show env-vars                List environment variables set for your account
  show invoices                [Deprecated] Get billing history - use show invoices-v1 instead
  show invoices-v1             Get billing history with invoices and charges
  show instance                Show details for a specific instance
  show instances               List all your running and stopped instances
  show ipaddrs                 Show history of IP addresses used by your instances
  show clusters                [Beta] List all your machine clusters
  show overlays                [Beta] List all your overlay networks
  show subaccounts             List all subaccounts under your account
  show members                 List all members in your team
  show team-role               Show details for a specific team role
  show team-roles              List all roles defined for your team
  show user                    Show your account information and balance
  show volumes                 List all your storage volumes and their status
  remove-machine-from-cluster  [Host] [Beta] Remove a machine from a cluster
  transfer credit              Transfer credits to another account
  update workergroup           Update an existing autoscale group
  update endpoint              Update an existing endpoint group
  update env-var               Update an existing user environment variable
  update instance              Update an instance configuration or recreate from a template
  update team-role             Update an existing team role
  update template              Update an existing template
  update ssh-key               Update an SSH key's label or properties
  add network-disk             [Host] [Beta] Attach a network disk to a machine cluster
  cancel maint                 [Host] Cancel a scheduled maintenance window
  cleanup machine              [Host] Clean up expired storage to free disk space
  defrag machines              [Host] Rebuild larger GPU offers from orphaned single GPUs when possible
  delete machine               [Host] Remove a machine from your host account
  list machine                 [Host] List a single machine for rent on the marketplace
  list machines                [Host] List multiple machines for rent on the marketplace
  list network-volume          [Host] [Beta] List disk space as a rentable network volume
  list volume                  [Host] List disk space as a rentable volume
  list volumes                 [Host] List disk space on multiple machines as rentable volumes
  remove defjob                [Host] Remove default background jobs from a machine
  self-test machine            [Host] Run diagnostics on a hosted machine
  set defjob                   [Host] Configure default background jobs for a machine
  set min-bid                  [Host] Set minimum price for interruptible/spot instance rentals
  schedule maint               [Host] Schedule a maintenance window for a machine
  show machine                 [Host] Show details for a specific hosted machine
  show machines                [Host] List all your hosted machines
  show maints                  [Host] List scheduled maintenance windows
  show network-disks           [Host] [Beta] List network disks attached to your machines
  unlist machine               [Host] Remove a machine from the rental marketplace
  unlist network-volume        [Host] [Beta] Remove a network volume offer from the marketplace
  unlist volume                [Host] Remove a volume offer from the marketplace

options:
 -h, --help                    show this help message and exit
 --url URL                     Server REST API URL
 --retry RETRY                 Retry limit
 --explain                     Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                         Output machine-readable json
 --full                        Print full results instead of paging with `less` for commands that support it
 --curl                        Show a curl equivalency to the call
 --api-key API_KEY             API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                     Show CLI version
 --no-color                    Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Use 'vast COMMAND --help' for more info about a command
```

## Client Commands

Commands for renting and managing GPU instances.

### attach ssh

Attach an SSH key to an instance for remote access

```
usage: vastai attach ssh instance_id ssh_key

Attach an SSH key to an instance for remote access

positional arguments:
 instance_id        id of instance to attach to
 ssh_key            ssh key to attach to instance

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Attach an ssh key to an instance. This will allow you to connect to the instance with the ssh key.

Examples:
 vastai attach ssh 12371 ssh-rsa AAAAB3NzaC1yc2EAAA...
 vastai attach ssh 12371 ssh-rsa $(cat ~/.ssh/id_rsa)
```

---

### cancel copy

Cancel an in-progress file copy operation

```
usage: vastai cancel copy DST

Cancel an in-progress file copy operation

positional arguments:
 dst                instance_id:/path to target of copy operation

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Use this command to cancel any/all current remote copy operations copying to a specific named instance, given by DST.

Examples:
 vast cancel copy 12371

The first example cancels all copy operations currently copying data into instance 12371
```

---

### cancel sync

Cancel an in-progress file sync operation

```
usage: vastai cancel sync DST

Cancel an in-progress file sync operation

positional arguments:
 dst                instance_id:/path to target of sync operation

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Use this command to cancel any/all current remote cloud sync operations copying to a specific named instance, given by DST.

Examples:
 vast cancel sync 12371

The first example cancels all copy operations currently copying data into instance 12371
```

---

### change bid

Change the bid price for a spot/interruptible instance

```
usage: vastai change bid id [--price PRICE]

Change the bid price for a spot/interruptible instance

positional arguments:
 id                                id of instance type to change bid

options:
 -h, --help                        show this help message and exit
 --price PRICE                     per machine bid price in $/hour
 --schedule {HOURLY,DAILY,WEEKLY}  try to schedule a command to run hourly, daily, or monthly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY
 --start_date START_DATE           Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional)
 --end_date END_DATE               End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional)
 --day DAY                         Day of week you want scheduled job to run on (0-6, where 0=Sunday) or "*". Default will be 0. For ex. --day 0
 --hour HOUR                       Hour of day you want scheduled job to run on (0-23) or "*" (UTC). Default will be 0. For ex. --hour 16

Global options (available for all commands):
 --url URL                         Server REST API URL
 --retry RETRY                     Retry limit
 --explain                         Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                             Output machine-readable json
 --full                            Print full results instead of paging with `less` for commands that support it
 --curl                            Show a curl equivalency to the call
 --api-key API_KEY                 API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                         Show CLI version
 --no-color                        Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Change the current bid price of instance id to PRICE.
If PRICE is not specified, then a winning bid price is used as the default.
```

---

### clone volume

Create a copy of an existing volume

```
usage: vastai copy volume <source_id> <dest_id> [options]

Create a copy of an existing volume

positional arguments:
 source                     id of volume contract being cloned
 dest                       id of volume offer volume is being copied to

options:
 -h, --help                 show this help message and exit
 -s, --size SIZE            Size of new volume contract, in GB. Must be greater than or equal to the source volume, and less than or equal to the destination offer.
 -d, --disable_compression  Do not compress volume data before copying.

Global options (available for all commands):
 --url URL                  Server REST API URL
 --retry RETRY              Retry limit
 --explain                  Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                      Output machine-readable json
 --full                     Print full results instead of paging with `less` for commands that support it
 --curl                     Show a curl equivalency to the call
 --api-key API_KEY          API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                  Show CLI version
 --no-color                 Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Create a new volume with the given offer, by copying the existing volume.
Size defaults to the size of the existing volume, but can be increased if there is available space.
```

---

### cloud copy

Copy files between instances and cloud storage (S3, GCS, Azure)

```
usage: vastai cloud copy --src SRC --dst DST --instance INSTANCE_ID -connection CONNECTION_ID --transfer TRANSFER_TYPE

Copy files between instances and cloud storage (S3, GCS, Azure)

options:
 -h, --help                        show this help message and exit
 --src SRC                         path to source of object to copy
 --dst DST                         path to target of copy operation
 --instance INSTANCE               id of the instance
 --connection CONNECTION           id of cloud connection on your account (get from calling 'vastai show connections')
 --transfer TRANSFER               type of transfer, possible options include Instance To Cloud and Cloud To Instance
 --dry-run                         show what would have been transferred
 --size-only                       skip based on size only, not mod-time or checksum
 --ignore-existing                 skip all files that exist on destination
 --update                          skip files that are newer on the destination
 --delete-excluded                 delete files on dest excluded from transfer
 --schedule {HOURLY,DAILY,WEEKLY}  try to schedule a command to run hourly, daily, or monthly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY
 --start_date START_DATE           Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional)
 --end_date END_DATE               End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is contract's end. (optional)
 --day DAY                         Day of week you want scheduled job to run on (0-6, where 0=Sunday) or "*". Default will be 0. For ex. --day 0
 --hour HOUR                       Hour of day you want scheduled job to run on (0-23) or "*" (UTC). Default will be 0. For ex. --hour 16

Global options (available for all commands):
 --url URL                         Server REST API URL
 --retry RETRY                     Retry limit
 --explain                         Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                             Output machine-readable json
 --full                            Print full results instead of paging with `less` for commands that support it
 --curl                            Show a curl equivalency to the call
 --api-key API_KEY                 API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                         Show CLI version
 --no-color                        Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Copies a directory from a source location to a target location. Each of source and destination
directories can be either local or remote, subject to appropriate read and write
permissions required to carry out the action. The format for both src and dst is [instance_id:]path.
You can find more information about the cloud copy operation here: https://vast.ai/docs/gpu-instances/cloud-sync

Examples:
 vastai show connections
 ID    NAME      Cloud Type
 1001  test_dir  drive
 1003  data_dir  drive

 vastai cloud copy --src /folder --dst /workspace --instance 6003036 --connection 1001 --transfer "Instance To Cloud"

The example copies all contents of /folder into /workspace on instance 6003036 from gdrive connection 'test_dir'.
```

---

### copy

Copy files/directories between instances or between local and instance

```
usage: vastai copy SRC DST

Copy files/directories between instances or between local and instance

positional arguments:
 src                      Source location for copy operation (supports multiple formats)
 dst                      Target location for copy operation (supports multiple formats)

options:
 -h, --help               show this help message and exit
 -i, --identity IDENTITY  Location of ssh private key

Global options (available for all commands):
 --url URL                Server REST API URL
 --retry RETRY            Retry limit
 --explain                Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                    Output machine-readable json
 --full                   Print full results instead of paging with `less` for commands that support it
 --curl                   Show a curl equivalency to the call
 --api-key API_KEY        API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                Show CLI version
 --no-color               Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Copies a directory from a source location to a target location. Each of source and destination
directories can be either local or remote, subject to appropriate read and write
permissions required to carry out the action.

Supported location formats:
- [instance_id:]path               (legacy format, still supported)
- C.instance_id:path              (container copy format)
- cloud_service:path              (cloud service format)
- cloud_service.cloud_service_id:path  (cloud service with ID)
- local:path                      (explicit local path)
- V.volume_id:path                (volume copy, see restrictions)

You should not copy to /root or / as a destination directory, as this can mess up the permissions on your instance ssh folder, breaking future copy operations (as they use ssh authentication)
You can see more information about constraints here: https://vast.ai/docs/gpu-instances/data-movement#constraints
Volume copy is currently only supported for copying to other volumes or instances, not cloud services or local.

Examples:
 vast copy 6003036:/workspace/ 6003038:/workspace/
 vast copy C.11824:/data/test local:data/test
 vast copy local:data/test C.11824:/data/test
 vast copy drive:/folder/file.txt C.6003036:/workspace/
 vast copy s3.101:/data/ C.6003036:/workspace/
 vast copy V.1234:/file C.5678:/workspace/

The first example copy syncs all files from the absolute directory '/workspace' on instance 6003036 to the directory '/workspace' on instance 6003038.
The second example copy syncs files from container 11824 to the local machine using structured syntax.
The third example copy syncs files from local to container 11824 using structured syntax.
The fourth example copy syncs files from Google Drive to an instance.
The fifth example copy syncs files from S3 bucket with id 101 to an instance.
```

---

### create api-key

Create a new API key with custom permissions

```
usage: vastai create api-key --name NAME --permission_file PERMISSIONS

Create a new API key with custom permissions

options:
 -h, --help                         show this help message and exit
 --name NAME                        name of the api-key
 --permission_file PERMISSION_FILE  file path for json encoded permissions, see https://vast.ai/docs/cli/roles-and-permissions for more information
 --key_params KEY_PARAMS            optional wildcard key params for advanced keys

Global options (available for all commands):
 --url URL                          Server REST API URL
 --retry RETRY                      Retry limit
 --explain                          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                              Output machine-readable json
 --full                             Print full results instead of paging with `less` for commands that support it
 --curl                             Show a curl equivalency to the call
 --api-key API_KEY                  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                          Show CLI version
 --no-color                         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

In order to create api keys you must understand how permissions must be sent via json format.
You can find more information about permissions here: https://vast.ai/docs/cli/roles-and-permissions
```

---

### create cluster

[Beta] Create a new machine cluster

```
usage: vastai create cluster SUBNET MANAGER_ID

[Beta] Create a new machine cluster

positional arguments:
 subnet             local subnet for cluster, ex: '0.0.0.0/24'
 manager_id         Machine ID of manager node in cluster. Must exist already.

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Create Vast Cluster by defining a local subnet and manager id.
```

---

### create endpoint

Create a serverless inference endpoint

```
usage: vastai create endpoint [OPTIONS]

Create a serverless inference endpoint

options:
 -h, --help                     show this help message and exit
 --min_load MIN_LOAD            minimum floor load in perf units/s  (token/s for LLms)
 --min_cold_load MIN_COLD_LOAD  minimum floor load in perf units/s (token/s for LLms), but allow handling with cold workers
 --target_util TARGET_UTIL      target capacity utilization (fraction, max 1.0, default 0.9)
 --cold_mult COLD_MULT          cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)
 --cold_workers COLD_WORKERS    min number of workers to keep 'cold' when you have no load (default 5)
 --max_workers MAX_WORKERS      max number of workers your endpoint group can have (default 20)
 --endpoint_name ENDPOINT_NAME  deployment endpoint name (allows multiple autoscale groups to share same deployment endpoint)

Global options (available for all commands):
 --url URL                      Server REST API URL
 --retry RETRY                  Retry limit
 --explain                      Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                          Output machine-readable json
 --full                         Print full results instead of paging with `less` for commands that support it
 --curl                         Show a curl equivalency to the call
 --api-key API_KEY              API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                      Show CLI version
 --no-color                     Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Create a new endpoint group to manage many autoscaling groups

Example: vastai create endpoint --target_util 0.9 --cold_mult 2.0 --endpoint_name "LLama"
```

---

### create env-var

Create a new account-level environment variable

```
usage: vastai create env-var <name> <value>

Create a new account-level environment variable

positional arguments:
 name               Environment variable name
 value              Environment variable value

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### create instance

Create a new GPU instance from an offer

```
usage: vastai create instance ID [OPTIONS] [--args ...]

Create a new GPU instance from an offer

positional arguments:
 id                                id of instance type to launch (returned from search offers)

options:
 -h, --help                        show this help message and exit
 --template_hash TEMPLATE_HASH     Create instance from template info
 --user USER                       User to use with docker create. This breaks some images, so only use this if you are certain you need it.
 --disk DISK                       size of local disk partition in GB
 --image IMAGE                     docker container image to launch
 --login LOGIN                     docker login arguments for private repo authentication, surround with '' 
 --label LABEL                     label to set on the instance
 --onstart ONSTART                 filename to use as onstart script
 --onstart-cmd ONSTART_CMD         contents of onstart script as single argument
 --entrypoint ENTRYPOINT           override entrypoint for args launch instance
 --ssh                             Launch as an ssh instance type
 --jupyter                         Launch as a jupyter instance instead of an ssh instance
 --direct                          Use (faster) direct connections for jupyter & ssh
 --jupyter-dir JUPYTER_DIR         For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory
 --jupyter-lab                     For runtype 'jupyter', Launch instance with jupyter lab
 --lang-utf8                       Workaround for images with locale problems: install and generate locales before instance launch, and set locale to C.UTF-8
 --python-utf8                     Workaround for images with locale problems: set python's locale to C.UTF-8
 --env ENV                         env variables and port mapping options, surround with '' 
 --args ...                        list of arguments passed to container ENTRYPOINT. Onstart is recommended for this purpose. (must be last argument)
 --force                           Skip sanity checks when creating from an existing instance
 --cancel-unavail                  Return error if scheduling fails (rather than creating a stopped instance)
 --bid_price BID_PRICE             (OPTIONAL) create an INTERRUPTIBLE instance with per machine bid price in $/hour
 --create-volume VOLUME_ASK_ID     Create a new local volume using an ID returned from the "search volumes" command and link it to the new instance
 --link-volume EXISTING_VOLUME_ID  ID of an existing rented volume to link to the instance during creation. (returned from "show volumes" cmd)
 --volume-size VOLUME_SIZE         Size of the volume to create in GB. Only usable with --create-volume (default 15GB)
 --mount-path MOUNT_PATH           The path to the volume from within the new instance container. e.g. /root/volume
 --volume-label VOLUME_LABEL       (optional) A name to give the new volume. Only usable with --create-volume

Global options (available for all commands):
 --url URL                         Server REST API URL
 --retry RETRY                     Retry limit
 --explain                         Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                             Output machine-readable json
 --full                            Print full results instead of paging with `less` for commands that support it
 --curl                            Show a curl equivalency to the call
 --api-key API_KEY                 API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                         Show CLI version
 --no-color                        Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Performs the same action as pressing the "RENT" button on the website at https://console.vast.ai/create/
Creates an instance from an offer ID (which is returned from "search offers"). Each offer ID can only be used to create one instance.
Besides the offer ID, you must pass in an '--image' argument as a minimum.

If you use args/entrypoint launch mode, we create a container from your image as is, without attempting to inject ssh and or jupyter.
If you use the args launch mode, you can override the entrypoint with --entrypoint, and pass arguments to the entrypoint with --args.
If you use --args, that must be the last argument, as any following tokens are consumed into the args string.
For ssh/jupyter launch types, use --onstart-cmd to pass in startup script, instead of --entrypoint and --args.

Examples:

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

Return value:
Returns a json reporting the instance ID of the newly created instance:
{'success': True, 'new_contract': 7835610}
```

---

### create overlay

[Beta] Create a virtual overlay network on a cluster

```
usage: vastai create overlay CLUSTER_ID OVERLAY_NAME

[Beta] Create a virtual overlay network on a cluster

positional arguments:
 cluster_id         ID of cluster to create overlay on top of
 name               overlay network name

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Creates an overlay network to allow local networking between instances on a physical cluster
```

---

### create ssh-key

Add an SSH public key to your account

```
usage: vastai create ssh-key [ssh_public_key] [-y]

Add an SSH public key to your account

positional arguments:
 ssh_key            add your existing ssh public key to your account (from the .pub file). If no public key is provided, a new key pair will be generated.

options:
 -h, --help         show this help message and exit
 -y, --yes          automatically answer yes to prompts

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

You may use this command to add an existing public key, or create a new ssh key pair and add that public key, to your Vast account.

If you provide an ssh_public_key.pub argument, that public key will be added to your Vast account. All ssh public keys should be in OpenSSH format.

        Example: $vastai create ssh-key 'ssh_public_key.pub'

If you don't provide an ssh_public_key.pub argument, a new Ed25519 key pair will be generated.

        Example: $vastai create ssh-key

The generated keys are saved as ~/.ssh/id_ed25519 (private) and ~/.ssh/id_ed25519.pub (public). Any existing id_ed25519 keys are backed up as .backup_<timestamp>.
The public key will be added to your Vast account.

All ssh public keys are stored in your Vast account and can be used to connect to instances they've been added to.
```

---

### create subaccount

Create a subaccount for delegated access

```
usage: vastai create subaccount --email EMAIL --username USERNAME --password PASSWORD --type TYPE

Create a subaccount for delegated access

options:
 -h, --help           show this help message and exit
 --email EMAIL        email address to use for login
 --username USERNAME  username to use for login
 --password PASSWORD  password to use for login
 --type TYPE          host/client

Global options (available for all commands):
 --url URL            Server REST API URL
 --retry RETRY        Retry limit
 --explain            Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                Output machine-readable json
 --full               Print full results instead of paging with `less` for commands that support it
 --curl               Show a curl equivalency to the call
 --api-key API_KEY    API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version            Show CLI version
 --no-color           Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Creates a new account that is considered a child of your current account as defined via the API key.

vastai create subaccount --email bob@gmail.com --username bob --password password --type host

vastai create subaccount --email vast@gmail.com --username vast --password password --type host
```

---

### create team

Create a new team

```
usage: vastai create-team --team_name TEAM_NAME

Create a new team

options:
 -h, --help             show this help message and exit
 --team_name TEAM_NAME  name of the team

Global options (available for all commands):
 --url URL              Server REST API URL
 --retry RETRY          Retry limit
 --explain              Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                  Output machine-readable json
 --full                 Print full results instead of paging with `less` for commands that support it
 --curl                 Show a curl equivalency to the call
 --api-key API_KEY      API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version              Show CLI version
 --no-color             Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Creates a new team under your account.

Unlike legacy teams, this command does NOT convert your personal account into a team.
Each team is created as a separate account, and you can be a member of multiple teams.

When you create a team:
  - You become the team owner.
  - The team starts as an independent account with its own billing, credits, and resources.
  - Default roles (owner, manager, member) are automatically created.
  - You can invite others, assign roles, and manage resources within the team.

Notes:
  - You cannot create a team from within another team account.
  - To transfer credits to a team, use `vastai transfer credit <team_email> <amount>` after team creation.

For more details, see:
https://vast.ai/docs/teams-quickstart
```

---

### create team-role

Create a custom role with specific permissions

```
usage: vastai create team-role --name NAME --permissions PERMISSIONS

Create a custom role with specific permissions

options:
 -h, --help                 show this help message and exit
 --name NAME                name of the role
 --permissions PERMISSIONS  file path for json encoded permissions, look in the docs for more information

Global options (available for all commands):
 --url URL                  Server REST API URL
 --retry RETRY              Retry limit
 --explain                  Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                      Output machine-readable json
 --full                     Print full results instead of paging with `less` for commands that support it
 --curl                     Show a curl equivalency to the call
 --api-key API_KEY          API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                  Show CLI version
 --no-color                 Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Creating a new team role involves understanding how permissions must be sent via json format.
You can find more information about permissions here: https://vast.ai/docs/cli/roles-and-permissions
```

---

### create template

Create a reusable instance configuration template

```
usage: vastai create template

Create a reusable instance configuration template

options:
 -h, --help                     show this help message and exit
 --name NAME                    name of the template
 --image IMAGE                  docker container image to launch
 --image_tag IMAGE_TAG          docker image tag (can also be appended to end of image_path)
 --href HREF                    link you want to provide
 --repo REPO                    link to repository
 --login LOGIN                  docker login arguments for private repo authentication, surround with ''
 --env ENV                      Contents of the 'Docker options' field
 --ssh                          Launch as an ssh instance type
 --jupyter                      Launch as a jupyter instance instead of an ssh instance
 --direct                       Use (faster) direct connections for jupyter & ssh
 --jupyter-dir JUPYTER_DIR      For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory
 --jupyter-lab                  For runtype 'jupyter', Launch instance with jupyter lab
 --onstart-cmd ONSTART_CMD      contents of onstart script as single argument
 --search_params SEARCH_PARAMS  search offers filters
 -n, --no-default               Disable default search param query args
 --disk_space DISK_SPACE        disk storage space, in GB
 --readme README                readme string
 --hide-readme                  hide the readme from users
 --desc DESC                    description string
 --public                       make template available to public

Global options (available for all commands):
 --url URL                      Server REST API URL
 --retry RETRY                  Retry limit
 --explain                      Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                          Output machine-readable json
 --full                         Print full results instead of paging with `less` for commands that support it
 --curl                         Show a curl equivalency to the call
 --api-key API_KEY              API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                      Show CLI version
 --no-color                     Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Create a template that can be used to create instances with

Example:
    vastai create template --name "tgi-llama2-7B-quantized" --image "ghcr.io/huggingface/text-generation-inference:1.0.3"
                            --env "-p 3000:3000 -e MODEL_ARGS='--model-id TheBloke/Llama-2-7B-chat-GPTQ --quantize gptq'"
                            --onstart-cmd 'wget -O - https://raw.githubusercontent.com/vast-ai/vast-pyworker/main/scripts/launch_tgi.sh | bash'
                            --search_params "gpu_ram>=23 num_gpus=1 gpu_name=RTX_3090 inet_down>128 direct_port_count>3 disk_space>=192 driver_version>=535086005 rented=False"
                            --disk_space 8.0 --ssh --direct
```

---

### create volume

Create a new persistent storage volume

```
usage: vastai create volume ID [options]

Create a new persistent storage volume

positional arguments:
 id                 id of volume offer

options:
 -h, --help         show this help message and exit
 -s, --size SIZE    size in GB of volume. Default 15 GB.
 -n, --name NAME    Optional name of volume.

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Creates a volume from an offer ID (which is returned from "search volumes"). Each offer ID can be used to create multiple volumes,
provided the size of all volumes does not exceed the size of the offer.
```

---

### create workergroup

Create an autoscaling worker group for serverless inference

```
usage: vastai workergroup create [OPTIONS]

Create an autoscaling worker group for serverless inference

options:
 -h, --help                     show this help message and exit
 --template_hash TEMPLATE_HASH  template hash (required, but **Note**: if you use this field, you can skip search_params, as they are automatically inferred from the template)
 --template_id TEMPLATE_ID      template id (optional)
 -n, --no-default               Disable default search param query args
 --launch_args LAUNCH_ARGS      launch args  string for create instance  ex: "--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64"
 --endpoint_name ENDPOINT_NAME  deployment endpoint name (allows multiple workergroups to share same deployment endpoint)
 --endpoint_id ENDPOINT_ID      deployment endpoint id (allows multiple workergroups to share same deployment endpoint)
 --test_workers TEST_WORKERS    number of workers to create to get an performance estimate for while initializing workergroup (default 3)
 --gpu_ram GPU_RAM              estimated GPU RAM req  (independent of search string)
 --search_params SEARCH_PARAMS  search param string for search offers    ex: "gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64"
 --min_load MIN_LOAD            [NOTE: this field isn't currently used at the workergroup level] minimum floor load in perf units/s  (token/s for LLms)
 --target_util TARGET_UTIL      [NOTE: this field isn't currently used at the workergroup level] target capacity utilization (fraction, max 1.0, default 0.9)
 --cold_mult COLD_MULT          [NOTE: this field isn't currently used at the workergroup level]cold/stopped instance capacity target as multiple of hot capacity target (default 2.0)
 --cold_workers COLD_WORKERS    min number of workers to keep 'cold' for this workergroup

Global options (available for all commands):
 --url URL                      Server REST API URL
 --retry RETRY                  Retry limit
 --explain                      Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                          Output machine-readable json
 --full                         Print full results instead of paging with `less` for commands that support it
 --curl                         Show a curl equivalency to the call
 --api-key API_KEY              API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                      Show CLI version
 --no-color                     Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Create a new autoscaling group to manage a pool of worker instances.

Example: vastai create workergroup --template_hash HASH  --endpoint_name "LLama" --test_workers 5
```

---

### delete api-key

Delete an API key

```
usage: vastai delete api-key ID

Delete an API key

positional arguments:
 id                 id of apikey to remove

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### delete cluster

[Beta] Delete a machine cluster

```
usage: vastai delete cluster CLUSTER_ID

[Beta] Delete a machine cluster

positional arguments:
 cluster_id         ID of cluster to delete

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Delete Vast Cluster
```

---

### delete endpoint

Delete a serverless inference endpoint

```
usage: vastai delete endpoint ID 

Delete a serverless inference endpoint

positional arguments:
 id                 id of endpoint group to delete

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai delete endpoint 4242
```

---

### delete env-var

Delete a user environment variable

```
usage: vastai delete env-var <name>

Delete a user environment variable

positional arguments:
 name               Environment variable name to delete

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### delete overlay

[Beta] Delete an overlay network and its instances

```
usage: vastai delete overlay OVERLAY_IDENTIFIER

[Beta] Delete an overlay network and its instances

positional arguments:
 overlay_identifier  ID (int) or name (str) of overlay to delete

options:
 -h, --help          show this help message and exit

Global options (available for all commands):
 --url URL           Server REST API URL
 --retry RETRY       Retry limit
 --explain           Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw               Output machine-readable json
 --full              Print full results instead of paging with `less` for commands that support it
 --curl              Show a curl equivalency to the call
 --api-key API_KEY   API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version           Show CLI version
 --no-color          Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### delete scheduled-job

Delete a scheduled job

```
usage: vastai delete scheduled-job ID

Delete a scheduled job

positional arguments:
 id                 id of scheduled job to remove

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### delete ssh-key

Remove an SSH key from your account

```
usage: vastai delete ssh-key ID

Remove an SSH key from your account

positional arguments:
 id                 id ssh key to delete

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### delete template

Delete a template

```
usage: vastai delete template [--template-id <id> | --hash-id <hash_id>]

Delete a template

options:
 -h, --help                 show this help message and exit
 --template-id TEMPLATE_ID  Template ID of Template to Delete
 --hash-id HASH_ID          Hash ID of Template to Delete

Global options (available for all commands):
 --url URL                  Server REST API URL
 --retry RETRY              Retry limit
 --explain                  Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                      Output machine-readable json
 --full                     Print full results instead of paging with `less` for commands that support it
 --curl                     Show a curl equivalency to the call
 --api-key API_KEY          API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                  Show CLI version
 --no-color                 Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Note: Deleting a template only removes the user's replationship to a template. It does not get destroyed
Example: vastai delete template --template-id 12345
Example: vastai delete template --hash-id 49c538d097ad6437413b83711c9f61e8
```

---

### delete volume

Delete a persistent storage volume

```
usage: vastai delete volume ID

Delete a persistent storage volume

positional arguments:
 id                 id of volume contract

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Deletes volume with the given ID. All instances using the volume must be destroyed before the volume can be deleted.
```

---

### delete workergroup

Delete an autoscaling worker group

```
usage: vastai delete workergroup ID 

Delete an autoscaling worker group

positional arguments:
 id                 id of group to delete

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Note that deleting a workergroup doesn't automatically destroy all the instances that are associated with your workergroup.
Example: vastai delete workergroup 4242
```

---

### destroy instance

Destroy an instance (irreversible, deletes data)

```
usage: vastai destroy instance id [-h] [--api-key API_KEY] [--raw]

Destroy an instance (irreversible, deletes data)

positional arguments:
 id                 id of instance to delete

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Performs the same action as pressing the "DESTROY" button on the website at https://console.vast.ai/instances/

WARNING: This action is IMMEDIATE and IRREVERSIBLE. All data on the instance will be permanently
deleted unless you have saved it to a persistent volume or external storage.

Examples:
    vastai destroy instance 12345              # Destroy instance with ID 12345

Before destroying:
  - Save any important data using 'vastai copy' or by mounting a persistent volume
  - Check instance ID carefully with 'vastai show instances'
  - Consider using 'vastai stop instance' if you want to pause without data loss
```

---

### destroy instances

Destroy a list of instances (irreversible, deletes data)

```
usage: vastai destroy instances IDS [OPTIONS]

Destroy a list of instances (irreversible, deletes data)

positional arguments:
 ids                ids of instances to destroy

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### destroy team

Delete your team and remove all members

```
usage: vastai destroy team

Delete your team and remove all members

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### detach ssh

Remove an SSH key from an instance

```
usage: vastai detach instance_id ssh_key_id

Remove an SSH key from an instance

positional arguments:
 instance_id        id of the instance
 ssh_key_id         id of the key to detach to the instance

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai detach 99999 12345
```

---

### execute

Execute a command on a running instance

```
usage: vastai execute id COMMAND

Execute a command on a running instance

positional arguments:
 id                                id of instance to execute on
 COMMAND                           bash command surrounded by single quotes

options:
 -h, --help                        show this help message and exit
 --schedule {HOURLY,DAILY,WEEKLY}  try to schedule a command to run hourly, daily, or monthly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY
 --start_date START_DATE           Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional)
 --end_date END_DATE               End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional)
 --day DAY                         Day of week you want scheduled job to run on (0-6, where 0=Sunday) or "*". Default will be 0. For ex. --day 0
 --hour HOUR                       Hour of day you want scheduled job to run on (0-23) or "*" (UTC). Default will be 0. For ex. --hour 16

Global options (available for all commands):
 --url URL                         Server REST API URL
 --retry RETRY                     Retry limit
 --explain                         Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                             Output machine-readable json
 --full                            Print full results instead of paging with `less` for commands that support it
 --curl                            Show a curl equivalency to the call
 --api-key API_KEY                 API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                         Show CLI version
 --no-color                        Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Examples:
  vastai execute 99999 'ls -l -o -r'
  vastai execute 99999 'rm -r home/delete_this.txt'
  vastai execute 99999 'du -d2 -h'

available commands:
  ls                 List directory contents
  rm                 Remote files or directories
  du                 Summarize device usage for a set of files

Return value:
Returns the output of the command which was executed on the instance, if successful. May take a few seconds to retrieve the results.
```

---

### get endpt-logs

Get logs for a serverless endpoint

```
usage: vastai get endpt-logs ID [--api-key API_KEY]

Get logs for a serverless endpoint

positional arguments:
 id                 id of endpoint group to fetch logs from

options:
 -h, --help         show this help message and exit
 --level LEVEL      log detail level (0 to 3)
 --tail TAIL

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai get endpt-logs 382
```

---

### get wrkgrp-logs

Get logs for an autoscaling worker group

```
usage: vastai get wrkgrp-logs ID [--api-key API_KEY]

Get logs for an autoscaling worker group

positional arguments:
 id                 id of endpoint group to fetch logs from

options:
 -h, --help         show this help message and exit
 --level LEVEL      log detail level (0 to 3)
 --tail TAIL

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai get endpt-logs 382
```

---

### help

print this help message

```
usage: vast.py help [-h] [--url URL] [--retry RETRY] [--explain] [--raw] [--full] [--curl] [--api-key API_KEY] [--version]
                    [--no-color]
                    [subcommand]

positional arguments:
 subcommand

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### invite member

Invite a user to join your team

```
usage: vastai invite member --email EMAIL --role ROLE

Invite a user to join your team

options:
 -h, --help         show this help message and exit
 --email EMAIL      email of user to be invited
 --role ROLE        role of user to be invited

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### join cluster

[Beta] Add a machine to an existing cluster

```
usage: vastai join cluster CLUSTER_ID MACHINE_IDS

[Beta] Add a machine to an existing cluster

positional arguments:
 cluster_id         ID of cluster to add machine to
 machine_ids        machine id(s) to join cluster

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Join's Machine to Vast Cluster
```

---

### join overlay

[Beta] Connect an instance to an overlay network

```
usage: vastai join overlay OVERLAY_NAME INSTANCE_ID

[Beta] Connect an instance to an overlay network

positional arguments:
 name               Overlay network name to join instance to.
 instance_id        Instance ID to add to overlay.

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Adds an instance to a compatible overlay network.
```

---

### label instance

Assign a string label to an instance

```
usage: vastai label instance <id> <label>

Assign a string label to an instance

positional arguments:
 id                 id of instance to label
 label              label to set

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### launch instance

Launch a new instance using search parameters to auto-select the best offer

```
usage: vastai launch instance [--help] [--api-key API_KEY] <gpu_name> <num_gpus> <image> [geolocation] [disk_space]

Launch a new instance using search parameters to auto-select the best offer

options:
 -h, --help                                       show this help message and exit
 -g, --gpu-name {A10,A100_PCIE,A100_SXM4,A100X,A40,A800_PCIE,B200,GTX_1050,GTX_1050_Ti,GTX_1060,GTX_1070,GTX_1070_Ti,GTX_1080,GTX_1080_Ti,GTX_1650,GTX_1660,GTX_1660_S,GTX_1660_Ti,GTX_TITAN_X,H100_NVL,H100_PCIE,H100_SXM,H200,H200_NVL,L4,L40,L40S,Q_RTX_4000,Q_RTX_6000,Q_RTX_8000,Quadro_K2200,Quadro_P4000,Radeon_VII,RTX_2060,RTX_2060S,RTX_2070,RTX_2070S,RTX_2080,RTX_2080_Ti,RTX_3050,RTX_3060,RTX_3060_laptop,RTX_3060_Ti,RTX_3070,RTX_3070_laptop,RTX_3070_Ti,RTX_3080,RTX_3080_Ti,RTX_3090,RTX_3090_Ti,RTX_4000Ada,RTX_4060,RTX_4060_Ti,RTX_4070,RTX_4070S,RTX_4070S_Ti,RTX_4070_Ti,RTX_4080,RTX_4080_laptop,RTX_4080S,RTX_4090,RTX_4090D,RTX_4500Ada,RTX_5000Ada,RTX_5060,RTX_5060_Ti,RTX_5070,RTX_5070_Ti,RTX_5080,RTX_5090,RTX_5880Ada,RTX_6000Ada,RTX_A2000,RTX_A4000,RTX_A4500,RTX_A5000,RTX_A6000,RTX_PRO_4000,RTX_PRO_4500,RTX_PRO_6000_S,RTX_PRO_6000_WS,RX_6950_XT,Tesla_P100,Tesla_P4,Tesla_P40,Tesla_T4,Tesla_V100,Titan_RTX,Titan_V,Titan_Xp}
                                                  Name of the GPU model, replace spaces with underscores
 -n, --num-gpus {1,2,4,8,12,14}                   Number of GPUs required
 -r, --region REGION                              Geographical location of the instance
 -i, --image IMAGE                                Name of the image to use for instance
 -d, --disk DISK                                  Disk space required in GB
 --limit LIMIT
 -o, --order ORDER                                Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'num_gpus,total_flops-'.  default='score-'
 --login LOGIN                                    docker login arguments for private repo authentication, surround with '' 
 --label LABEL                                    label to set on the instance
 --onstart ONSTART                                filename to use as onstart script
 --onstart-cmd ONSTART_CMD                        contents of onstart script as single argument
 --entrypoint ENTRYPOINT                          override entrypoint for args launch instance
 --ssh                                            Launch as an ssh instance type
 --jupyter                                        Launch as a jupyter instance instead of an ssh instance
 --direct                                         Use (faster) direct connections for jupyter & ssh
 --jupyter-dir JUPYTER_DIR                        For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory
 --jupyter-lab                                    For runtype 'jupyter', Launch instance with jupyter lab
 --lang-utf8                                      Workaround for images with locale problems: install and generate locales before instance launch, and set locale to C.UTF-8
 --python-utf8                                    Workaround for images with locale problems: set python's locale to C.UTF-8
 --env ENV                                        env variables and port mapping options, surround with '' 
 --args ...                                       list of arguments passed to container ENTRYPOINT. Onstart is recommended for this purpose. (must be last argument)
 --force                                          Skip sanity checks when creating from an existing instance
 --cancel-unavail                                 Return error if scheduling fails (rather than creating a stopped instance)
 --template_hash TEMPLATE_HASH                    template hash which contains all relevant information about an instance. This can be used as a replacement for other parameters describing the instance configuration

Global options (available for all commands):
 --url URL                                        Server REST API URL
 --retry RETRY                                    Retry limit
 --explain                                        Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                                            Output machine-readable json
 --full                                           Print full results instead of paging with `less` for commands that support it
 --curl                                           Show a curl equivalency to the call
 --api-key API_KEY                                API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                                        Show CLI version
 --no-color                                       Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Launches an instance based on the given parameters. The instance will be created with the top offer from the search results.
Besides the gpu_name and num_gpus, you must pass in an '--image' argument as a minimum.

If you use args/entrypoint launch mode, we create a container from your image as is, without attempting to inject ssh and or jupyter.
If you use the args launch mode, you can override the entrypoint with --entrypoint, and pass arguments to the entrypoint with --args.
If you use --args, that must be the last argument, as any following tokens are consumed into the args string.
For ssh/jupyter launch types, use --onstart-cmd to pass in startup script, instead of --entrypoint and --args.

Examples:

    # launch a single RTX 3090 instance with the pytorch image and 16 GB of disk space located anywhere
    python vast.py launch instance -g RTX_3090 -n 1 -i pytorch/pytorch

    # launch a 4x RTX 3090 instance with the pytorch image and 32 GB of disk space located in North America
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
```

---

### logs

Get the logs for an instance

```
usage: vastai logs INSTANCE_ID [OPTIONS] 

Get the logs for an instance

positional arguments:
 INSTANCE_ID        id of instance

options:
 -h, --help         show this help message and exit
 --tail TAIL        Number of lines to show from the end of the logs (default '1000')
 --filter FILTER    Grep filter for log entries
 --daemon-logs      Fetch daemon system logs instead of container logs

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### prepay instance

Prepay credits for a reserved instance to prevent interruption

```
usage: vastai prepay instance ID AMOUNT

Prepay credits for a reserved instance to prevent interruption

positional arguments:
 id                 id of instance to prepay for
 amount             amount of instance credit prepayment (default discount func of 0.2 for 1 month, 0.3 for 3 months)

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### reboot instance

Reboot (stop/start) an instance

```
usage: vastai reboot instance ID [OPTIONS]

Reboot (stop/start) an instance

positional arguments:
 id                                id of instance to reboot

options:
 -h, --help                        show this help message and exit
 --schedule {HOURLY,DAILY,WEEKLY}  try to schedule a command to run hourly, daily, or monthly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY
 --start_date START_DATE           Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional)
 --end_date END_DATE               End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is 7 days from now. (optional)
 --day DAY                         Day of week you want scheduled job to run on (0-6, where 0=Sunday) or "*". Default will be 0. For ex. --day 0
 --hour HOUR                       Hour of day you want scheduled job to run on (0-23) or "*" (UTC). Default will be 0. For ex. --hour 16

Global options (available for all commands):
 --url URL                         Server REST API URL
 --retry RETRY                     Retry limit
 --explain                         Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                             Output machine-readable json
 --full                            Print full results instead of paging with `less` for commands that support it
 --curl                            Show a curl equivalency to the call
 --api-key API_KEY                 API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                         Show CLI version
 --no-color                        Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Stops and starts container without any risk of losing GPU priority.
```

---

### recycle instance

Destroy and recreate an instance with the same configuration

```
usage: vastai recycle instance ID [OPTIONS]

Destroy and recreate an instance with the same configuration

positional arguments:
 id                 id of instance to recycle

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Destroys and recreates container in place (from newly pulled image) without any risk of losing GPU priority.
```

---

### remove member

Remove a team member

```
usage: vastai remove member ID

Remove a team member

positional arguments:
 id                 id of user to remove

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### remove team-role

Delete a custom role from your team

```
usage: vastai remove team-role NAME

Delete a custom role from your team

positional arguments:
 NAME               name of the role

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### reset api-key

Invalidate current API key and generate a new one

```
usage: vastai reset api-key

Invalidate current API key and generate a new one

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### scp-url

Generate SCP file transfer URL for an instance

```
usage: vastai scp-url ID

Generate SCP file transfer URL for an instance

positional arguments:
 id                 id

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Retrieves the SCP connection URL for an instance. Use this to get the host and port
information needed to transfer files via SCP.

Examples:
    vastai scp-url 12345                       # Get SCP URL for instance 12345

Output format:
    scp://root@<ip_address>:<port>

Use with scp command:
    scp -P <port> local_file root@<ip_address>:/remote/path
    scp -P <port> root@<ip_address>:/remote/file ./local_path

See also: 'vastai ssh-url' for SSH connection URLs, 'vastai copy' for simplified file transfers
```

---

### search benchmarks

Search machine benchmark results with filters

```
usage: vastai search benchmarks [--help] [--api-key API_KEY] [--raw] <query>

Search machine benchmark results with filters

positional arguments:
 query              Search query in simple query syntax (see below)

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Query syntax:

    query = comparison comparison...
    comparison = field op value
    field = <name of a field>
    op = one of: <, <=, ==, !=, >=, >, in, notin
    value = <bool, int, float, string> | 'any' | [value0, value1, ...]
    bool: True, False

note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

Examples:

    # search for benchmarks with score > 100 for llama2_70B model on 2 specific machines
    vastai search benchmarks 'score > 100.0  model=llama2_70B  machine_id in [302,402]'

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
```

---

### search invoices

Search billing invoices with filters

```
usage: vastai search invoices [--help] [--api-key API_KEY] [--raw] <query>

Search billing invoices with filters

positional arguments:
 query              Search query in simple query syntax (see below)

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Query syntax:

        query = comparison comparison...
        comparison = field op value
        field = <name of a field>
        op = one of: <, <=, ==, !=, >=, >, in, notin
        value = <bool, int, float, string> | 'any' | [value0, value1, ...]
        bool: True, False

    note: to pass '>' and '<' on the command line, make sure to use quotes
    note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

    Examples:

        # search for somewhat reliable single RTX 3090 instances, filter out any duplicates or offers that conflict with our existing stopped instances
        vastai search invoices 'amount_cents>3000  '

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
```

---

### search offers

Search available GPU offers with filters

```
usage: vastai search offers [--help] [--api-key API_KEY] [--raw] <query>

Search available GPU offers with filters

positional arguments:
 query                Query to search for. default: 'external=false rentable=true verified=true', pass -n to ignore default

options:
 -h, --help           show this help message and exit
 -t, --type TYPE      Show 'on-demand', 'reserved', or 'bid'(interruptible) pricing. default: on-demand
 -i, --interruptible  Alias for --type=bid
 -b, --bid            Alias for --type=bid
 -r, --reserved       Alias for --type=reserved
 -d, --on-demand      Alias for --type=on-demand
 -n, --no-default     Disable default query
 --new                New search exp
 --limit LIMIT
 --disable-bundling   Deprecated
 --storage STORAGE    Amount of storage to use for pricing, in GiB. default=5.0GiB
 -o, --order ORDER    Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'num_gpus,total_flops-'.  default='score-'

Global options (available for all commands):
 --url URL            Server REST API URL
 --retry RETRY        Retry limit
 --explain            Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                Output machine-readable json
 --full               Print full results instead of paging with `less` for commands that support it
 --curl               Show a curl equivalency to the call
 --api-key API_KEY    API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version            Show CLI version
 --no-color           Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Query syntax:

    query = comparison comparison...
    comparison = field op value
    field = <name of a field>
    op = one of: <, <=, ==, !=, >=, >, in, notin
    value = <bool, int, float, string> | 'any' | [value0, value1, ...]
    bool: True, False

note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

Examples:

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
```

---

### search templates

Search available templates with filters

```
usage: vastai search templates [--help] [--api-key API_KEY] [--raw] <query>

Search available templates with filters

positional arguments:
 query              Search query in simple query syntax (see below)

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Query syntax:

        query = comparison comparison...
        comparison = field op value
        field = <name of a field>
        op = one of: <, <=, ==, !=, >=, >, in, notin
        value = <bool, int, float, string> | 'any' | [value0, value1, ...]
        bool: True, False

    note: to pass '>' and '<' on the command line, make sure to use quotes
    note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

    Examples:

        # search for somewhat reliable single RTX 3090 instances, filter out any duplicates or offers that conflict with our existing stopped instances
        vastai search templates 'count_created > 100  creator_id in [38382,48982]'

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
```

---

### search volumes

Search available volume offers with filters

```
usage: vastai search volumes [--help] [--api-key API_KEY] [--raw] <query>

Search available volume offers with filters

positional arguments:
 query              Query to search for. default: 'external=false verified=true disk_space>=1', pass -n to ignore default

options:
 -h, --help         show this help message and exit
 -n, --no-default   Disable default query
 --limit LIMIT
 --storage STORAGE  Amount of storage to use for pricing, in GiB. default=1.0GiB
 -o, --order ORDER  Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'disk_space,inet_up-'.  default='score-'

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Query syntax:

    query = comparison comparison...
    comparison = field op value
    field = <name of a field>
    op = one of: <, <=, ==, !=, >=, >, in, notin
    value = <bool, int, float, string> | 'any' | [value0, value1, ...]
    bool: True, False

note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

Examples:

    # search for volumes with greater than 50GB of available storage and greater than 500 Mb/s upload and download speed
    vastai search volumes "disk_space>50 inet_up>500 inet_down>500"

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
```

---

### set api-key

Set the API key for CLI and SDK authentication

```
usage: vastai set api-key API_KEY

Set the API key for CLI and SDK authentication

positional arguments:
 api_key            API key to set as currently logged in user

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Stores your Vast.ai API key locally for authentication with all CLI commands.
Get your API key from the Vast.ai console: https://console.vast.ai/account/

Examples:
    vastai set api-key abc123def456...         # Set your API key

Security notes:
  - API key is stored in ~/.config/vastai/vast_api_key
  - Permissions are set to user-read-only (600)
  - Do NOT share your API key or commit it to version control
  - Regenerate your key at https://console.vast.ai/account/ if compromised
  - You can also use the VAST_API_KEY environment variable instead

The legacy location ~/.vast_api_key is automatically removed when you set a new key.
```

---

### set user

Update account settings from a JSON file

```
usage: vastai set user --file FILE

Update account settings from a JSON file

options:
 -h, --help         show this help message and exit
 --file FILE        file path for params in json format

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Available fields:

Name                            Type       Description

ssh_key                         string
paypal_email                    string
wise_email                      string
email                           string
normalized_email                string
username                        string
fullname                        string
billaddress_line1               string
billaddress_line2               string
billaddress_city                string
billaddress_zip                 string
billaddress_country             string
billaddress_taxinfo             string
balance_threshold_enabled       string
balance_threshold               string
autobill_threshold              string
phone_number                    string
tfa_enabled                     bool
```

---

### show api-key

Show details for a specific API key

```
usage: vastai show api-key ID

Show details for a specific API key

positional arguments:
 id                 id of API key to show

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show api-keys

List all API keys for your account

```
usage: vastai show api-keys

List all API keys for your account

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show audit-logs

Show account activity and audit logs

```
usage: vastai show audit-logs [--api-key API_KEY] [--raw]

Show account activity and audit logs

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show clusters

[Beta] List all your machine clusters

```
usage: vastai show clusters

[Beta] List all your machine clusters

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Show clusters associated with your account.
```

---

### show connections

[Beta] Show network connections between instances

```
usage: vastai show connections [--api-key API_KEY] [--raw]

[Beta] Show network connections between instances

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show deposit

Show prepaid deposit balance for a reserved instance

```
usage: vastai show deposit ID [options]

Show prepaid deposit balance for a reserved instance

positional arguments:
 id                 id of instance to get info for

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show endpoints

List all your serverless endpoints

```
usage: vastai show endpoints [--api-key API_KEY]

List all your serverless endpoints

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai show endpoints
```

---

### show env-vars

List environment variables set for your account

```
usage: vastai show env-vars [-s]

List environment variables set for your account

options:
 -h, --help         show this help message and exit
 -s, --show-values  Show the values of environment variables

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show instance

Show details for a specific instance

```
usage: vastai show instance ID [OPTIONS]

Show details for a specific instance

positional arguments:
 id                 id of instance to show

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show instances

List all your running and stopped instances

```
usage: vastai show instances [OPTIONS] [--api-key API_KEY] [--raw]

List all your running and stopped instances

options:
 -h, --help         show this help message and exit
 -q, --quiet        only display numeric ids

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Lists all instances owned by the authenticated user, including running, pending, and stopped instances.

Examples:
    vastai show instances                      # List all instances in table format
    vastai show instances --raw                # Output as JSON for scripting
    vastai show instances --raw | jq '.[0]'   # Get first instance details
    vastai show instances -q                   # List only instance IDs

Output includes: instance ID, machine ID, status, GPU info, rental cost, duration, and connection details.
```

---

### show invoices

[Deprecated] Get billing history - use show invoices-v1 instead

```
usage: (DEPRECATED) vastai show invoices [OPTIONS]

[Deprecated] Get billing history - use show invoices-v1 instead

options:
 -h, --help                       show this help message and exit
 -q, --quiet                      only display numeric ids
 -s, --start_date START_DATE      start date and time for report. Many formats accepted (optional)
 -e, --end_date END_DATE          end date and time for report. Many formats accepted (optional)
 -c, --only_charges               Show only charge items
 -p, --only_credits               Show only credit items
 --instance_label INSTANCE_LABEL  Filter charges on a particular instance label (useful for autoscaler groups)

Global options (available for all commands):
 --url URL                        Server REST API URL
 --retry RETRY                    Retry limit
 --explain                        Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                            Output machine-readable json
 --full                           Print full results instead of paging with `less` for commands that support it
 --curl                           Show a curl equivalency to the call
 --api-key API_KEY                API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                        Show CLI version
 --no-color                       Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show invoices-v1

Get billing history with invoices and charges

```
usage: vastai show invoices-v1 [OPTIONS]

Get billing history with invoices and charges

options:
 -h, --help                           show this help message and exit
 -i, --invoices                       Show invoices instead of charges
 -it, --invoice-type type [type ...]  Filter which types of invoices to show: {transfers, stripe, bitpay, coinbase, crypto.com, reserved, payout_paypal, payout_wise}
 -c, --charges                        Show charges instead of invoices
 -ct, --charge-type type [type ...]   Filter which types of charges to show: {i|instance, v|volume, s|serverless}
 -s, --start-date START_DATE          Start date (YYYY-MM-DD or timestamp)
 -e, --end-date END_DATE              End date (YYYY-MM-DD or timestamp)
 -l, --limit LIMIT                    Number of results per page (default: 20, max: 100)
 -t, --next-token NEXT_TOKEN          Pagination token for next page
 -f, --format {table,tree}            Output format for charges (default: table)
 -v, --verbose                        Include full Instance Charge details and Invoice Metadata (tree view only)
 --latest-first                       Sort by latest first

Global options (available for all commands):
 --url URL                            Server REST API URL
 --retry RETRY                        Retry limit
 --explain                            Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                                Output machine-readable json
 --full                               Print full results instead of paging with `less` for commands that support it
 --curl                               Show a curl equivalency to the call
 --api-key API_KEY                    API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                            Show CLI version
 --no-color                           Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

This command supports colored output and rich formatting if the 'rich' python module is installed!

Examples:
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

### show ipaddrs

Show history of IP addresses used by your instances

```
usage: vastai show ipaddrs [--api-key API_KEY] [--raw]

Show history of IP addresses used by your instances

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show members

List all members in your team

```
usage: vastai show members

List all members in your team

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show overlays

[Beta] List all your overlay networks

```
usage: vastai show overlays

[Beta] List all your overlay networks

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Show overlays associated with your account.
```

---

### show scheduled-jobs

List all scheduled automation jobs

```
usage: vastai show scheduled-jobs [--api-key API_KEY] [--raw]

List all scheduled automation jobs

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show ssh-keys

List all SSH keys registered to your account

```
usage: vastai show ssh-keys

List all SSH keys registered to your account

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show subaccounts

List all subaccounts under your account

```
usage: vastai show subaccounts [OPTIONS]

List all subaccounts under your account

options:
 -h, --help         show this help message and exit
 -q, --quiet        display subaccounts from current user

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show team-role

Show details for a specific team role

```
usage: vastai show team-role NAME

Show details for a specific team role

positional arguments:
 NAME               name of the role

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show team-roles

List all roles defined for your team

```
usage: vastai show team-roles

List all roles defined for your team

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show user

Show your account information and balance

```
usage: vastai show user [OPTIONS]

Show your account information and balance

options:
 -h, --help         show this help message and exit
 -q, --quiet        display information about user

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Displays account information for the authenticated user.

Examples:
    vastai show user                           # Show user info in table format
    vastai show user --raw                     # Output as JSON for scripting

Information displayed:
  - Account balance and credit
  - Email address
  - Username
  - SSH public key (if configured)
  - Account settings

Note: API key is NOT displayed for security reasons.
Use 'vastai set api-key' to update your stored API key.
```

---

### show volumes

List all your storage volumes and their status

```
usage: vastai show volumes [OPTIONS]

List all your storage volumes and their status

options:
 -h, --help         show this help message and exit
 -t, --type TYPE    volume type to display. Default to all. Possible values are "local", "all", "network"

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Show stats on owned volumes
```

---

### show workergroups

List all your autoscaling worker groups

```
usage: vastai show workergroups [--api-key API_KEY]

List all your autoscaling worker groups

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai show workergroups
```

---

### ssh-url

Generate SSH connection URL for an instance

```
usage: vastai ssh-url ID

Generate SSH connection URL for an instance

positional arguments:
 id                 id of instance

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Retrieves the SSH connection URL for an instance. Use this to get the host and port
information needed to connect via SSH.

Examples:
    vastai ssh-url 12345                       # Get SSH URL for instance 12345

Output format:
    ssh://root@<ip_address>:<port>

Use with ssh command:
    ssh -p <port> root@<ip_address>

See also: 'vastai scp-url' for SCP file transfer URLs
```

---

### start instance

Start a stopped instance

```
usage: vastai start instance ID [OPTIONS]

Start a stopped instance

positional arguments:
 id                 ID of instance to start/restart

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

This command attempts to bring an instance from the "stopped" state into the "running" state. This is subject to resource availability on the machine that the instance is located on.
If your instance is stuck in the "scheduling" state for more than 30 seconds after running this, it likely means that the required resources on the machine to run your instance are currently unavailable.
Examples:
    vastai start instances $(vastai show instances -q)
    vastai start instance 329838
```

---

### start instances

Start multiple stopped instances

```
usage: vastai start instances IDS [OPTIONS]

Start multiple stopped instances

positional arguments:
 ids                ids of instances to start

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### stop instance

Stop a running instance

```
usage: vastai stop instance ID [OPTIONS]

Stop a running instance

positional arguments:
 id                 id of instance to stop

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

This command brings an instance from the "running" state into the "stopped" state. When an instance is "stopped" all of your data on the instance is preserved,
and you can resume use of your instance by starting it again. Once stopped, starting an instance is subject to resource availability on the machine that the instance is located on.
There are ways to move data off of a stopped instance, which are described here: https://vast.ai/docs/gpu-instances/data-movement
```

---

### stop instances

Stop multiple running instances

```
usage: vastai stop instances IDS [OPTIONS]

Stop multiple running instances

positional arguments:
 ids                ids of instances to stop

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Examples:
    vastai stop instances $(vastai show instances -q)
    vastai stop instances 329838 984849
```

---

### take snapshot

Create a snapshot of a running container and push to registry

```
usage: vastai take snapshot INSTANCE_ID --repo REPO --docker_login_user USER --docker_login_pass PASS[--container_registry REGISTRY] [--pause true|false]

Create a snapshot of a running container and push to registry

positional arguments:
 instance_id                              instance_id of the container instance to snapshot

options:
 -h, --help                               show this help message and exit
 --container_registry CONTAINER_REGISTRY  Container registry to push the snapshot to. Default will be docker.io
 --repo REPO                              repo to push the snapshot to
 --docker_login_user DOCKER_LOGIN_USER    Username for container registry with repo
 --docker_login_pass DOCKER_LOGIN_PASS    Password or token for container registry with repo
 --pause PAUSE                            Pause container's processes being executed by the CPU to take snapshot (true/false). Default will be true

Global options (available for all commands):
 --url URL                                Server REST API URL
 --retry RETRY                            Retry limit
 --explain                                Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                                    Output machine-readable json
 --full                                   Print full results instead of paging with `less` for commands that support it
 --curl                                   Show a curl equivalency to the call
 --api-key API_KEY                        API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                                Show CLI version
 --no-color                               Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Takes a snapshot of a running container instance and pushes snapshot to the specified repository in container registry.

Use pause=true to pause the container during commit (safer but slower),
or pause=false to leave it running (faster but may produce a filesystem-
// safer snapshot).
```

---

### tfa activate

Activate a new 2FA method by verifying the code

```
usage: vastai tfa activate CODE --secret SECRET [--sms] [--phone-number PHONE_NUMBER] [--label LABEL]

Activate a new 2FA method by verifying the setup code

positional arguments:
 code                         6-digit verification code from SMS or Authenticator app

options:
 -h, --help                   show this help message and exit
 --sms                        Use SMS 2FA method instead of TOTP
 --secret SECRET              Secret token from setup process (required)
 --phone-number PHONE_NUMBER  Phone number for SMS method (E.164 format)
 -l, --label LABEL            Label for the new 2FA method

Global options (available for all commands):
 --url URL                    Server REST API URL
 --retry RETRY                Retry limit
 --explain                    Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                        Output machine-readable json
 --full                       Print full results instead of paging with `less` for commands that support it
 --curl                       Show a curl equivalency to the call
 --api-key API_KEY            API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                    Show CLI version
 --no-color                   Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Complete the 2FA setup process by verifying your code.

For TOTP (Authenticator app):
 1. Run 'vastai tfa totp-setup' to get the manual key/QR code and secret
 2. Enter the manual key or scan the QR code with your Authenticator app
 3. Run this command with the 6-digit code from your app and the secret token from step 1

For SMS:
 1. Run 'vastai tfa send-sms --phone-number <PHONE_NUMBER>' to receive SMS and get secret token
 2. Run this command with the code you received via SMS and the phone number it was sent to

If this is your first 2FA method, backup codes will be generated and displayed.
Save these backup codes in a secure location!

Examples:
 vastai tfa activate --secret abc123def456 123456
 vastai tfa activate --secret abc123def456 --sms --phone-number +12345678901 123456
 vastai tfa activate --secret abc123def456 --sms --phone-number +12345678901 --label "Work Phone" 123456
```

---

### tfa delete

Remove a 2FA method from your account

```
usage: vastai tfa delete [--id-to-delete ID] [--code CODE] [--sms] [--secret SECRET] [--backup-code BACKUP_CODE] [--method-id ID]

Remove a 2FA method from your account

options:
 -h, --help                        show this help message and exit
 -id, --id-to-delete ID_TO_DELETE  ID of the 2FA method to delete (see `vastai tfa status`)
 -c, --code CODE                   2FA code from your Authenticator app or SMS to authorize deletion
 --sms                             Use SMS 2FA method instead of TOTP
 -s, --secret SECRET               Secret token (required for SMS authorization)
 -bc, --backup-code BACKUP_CODE    One-time backup code (alternative to regular 2FA code)
 --method-id METHOD_ID             2FA Method ID if you have more than one of the same type ('id' from `tfa status`)

Global options (available for all commands):
 --url URL                         Server REST API URL
 --retry RETRY                     Retry limit
 --explain                         Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                             Output machine-readable json
 --full                            Print full results instead of paging with `less` for commands that support it
 --curl                            Show a curl equivalency to the call
 --api-key API_KEY                 API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                         Show CLI version
 --no-color                        Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Remove a 2FA method from your account.

This action requires 2FA verification to prevent unauthorized removals.

NOTE: If you do not specify --id-to-delete, the system will attempt to delete the method
you are using to authenticate. However, it is much safer to specify the ID to avoid
confusion if you have multiple methods.

Use `vastai tfa status` to see your active methods and their IDs.

Examples:
 # Delete method #123, authorize with TOTP/Authenticator code
 vastai tfa delete --id-to-delete 123 --code 456789

 # Delete method #123, authorize with SMS and secret from `tfa send-sms`
 vastai tfa delete -id 123 --sms --secret abc123def456 -c 456789

 # Delete method #123, authorize with backup code
 vastai tfa delete --id-to-delete 123 --backup-code ABCD-EFGH-IJKL

 # Delete method #123, specify which TOTP method to use if you have multiple
 vastai tfa delete -id 123 --method-id 456 -c 456789

 # Delete the TOTP method you are using to authenticate (use with caution)
 vastai tfa delete -c 456789
```

---

### tfa login

Complete 2FA login by verifying code

```
usage: vastai tfa login [--code CODE] [--sms] [--secret SECRET] [--backup-code BACKUP_CODE]

Complete 2FA login by verifying code and obtaining session key

options:
 -h, --help                      show this help message and exit
 -c, --code CODE                 2FA code from Authenticator app (default) or SMS
 --sms                           Use SMS 2FA method instead of TOTP
 -s, --secret SECRET             Secret token from previous login step (required for SMS)
 -bc, --backup-code BACKUP_CODE  One-time backup code (alternative to regular 2FA code)
 -id, --method-id METHOD_ID      2FA Method ID if you have more than one of the same type ('id' from `tfa status`)

Global options (available for all commands):
 --url URL                       Server REST API URL
 --retry RETRY                   Retry limit
 --explain                       Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                           Output machine-readable json
 --full                          Print full results instead of paging with `less` for commands that support it
 --curl                          Show a curl equivalency to the call
 --api-key API_KEY               API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                       Show CLI version
 --no-color                      Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Complete Two-Factor Authentication login by providing the 2FA code.

For TOTP (default): Provide the 6-digit code from your Authenticator app
For SMS: Include the --sms flag and provide -s/--secret from the `tfa send-sms` command response
For backup code: Use --backup-code instead of code (codes may only be used once)

Examples:
 vastai tfa login -c 123456
 vastai tfa login --code 123456 --sms --secret abc123def456
 vastai tfa login --backup-code ABCD-EFGH-IJKL
```

---

### tfa regen-codes

Regenerate backup codes for 2FA

```
usage: vastai tfa regen-codes [--code CODE] [--sms] [--secret SECRET] [--backup-code BACKUP_CODE] [--method-id ID]

Regenerate backup codes for 2FA recovery

options:
 -h, --help                      show this help message and exit
 -c, --code CODE                 2FA code from Authenticator app (default) or SMS
 --sms                           Use SMS 2FA method instead of TOTP
 -s, --secret SECRET             Secret token from previous login step (required for SMS)
 -bc, --backup-code BACKUP_CODE  One-time backup code (alternative to regular 2FA code)
 -id, --method-id METHOD_ID      2FA Method ID if you have more than one of the same type ('id' from `tfa status`)

Global options (available for all commands):
 --url URL                       Server REST API URL
 --retry RETRY                   Retry limit
 --explain                       Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                           Output machine-readable json
 --full                          Print full results instead of paging with `less` for commands that support it
 --curl                          Show a curl equivalency to the call
 --api-key API_KEY               API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                       Show CLI version
 --no-color                      Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Generate a new set of backup codes for your account.

This action requires 2FA verification to prevent unauthorized regeneration.

WARNING: This will invalidate all existing backup codes!
Any previously generated codes will no longer work.

Backup codes are one-time use codes that allow you to log in
if you lose access to your primary 2FA method (lost phone, etc).

You should regenerate your backup codes if:
- You've used several codes and are running low
- You think your codes may have been compromised
- You lost your saved codes and need new ones

Important: Save the new codes in a secure location immediately!
They will not be shown again.

Examples:
 vastai tfa regen-codes --code 123456
 vastai tfa regen-codes -c 123456 --sms --secret abc123def456
 vastai tfa regen-codes --backup-code ABCD-EFGH-IJKL
```

---

### tfa resend-sms

Resend SMS 2FA code

```
usage: vastai tfa resend-sms --secret SECRET [--phone-number PHONE_NUMBER]

Resend SMS 2FA verification code

options:
 -h, --help                       show this help message and exit
 -p, --phone-number PHONE_NUMBER  Phone number to receive SMS code (E.164 format, e.g., +1234567890)
 -s, --secret SECRET              Secret token from the original 2FA login attempt

Global options (available for all commands):
 --url URL                        Server REST API URL
 --retry RETRY                    Retry limit
 --explain                        Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                            Output machine-readable json
 --full                           Print full results instead of paging with `less` for commands that support it
 --curl                           Show a curl equivalency to the call
 --api-key API_KEY                API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                        Show CLI version
 --no-color                       Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Resend the SMS verification code to your phone.

This is useful if:
- You didn't receive the original SMS
- The code expired before you could use it
- You accidentally deleted the message

You must provide the same secret token from the original request.

Example:
 vastai tfa resend-sms --secret abc123def456
```

---

### tfa send-sms

Request a 2FA SMS verification code

```
usage: vastai tfa send-sms [--phone-number PHONE_NUMBER]

Request a 2FA SMS verification code to be sent

options:
 -h, --help                       show this help message and exit
 -p, --phone-number PHONE_NUMBER  Phone number to receive SMS code (E.164 format, e.g., +1234567890)

Global options (available for all commands):
 --url URL                        Server REST API URL
 --retry RETRY                    Retry limit
 --explain                        Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                            Output machine-readable json
 --full                           Print full results instead of paging with `less` for commands that support it
 --curl                           Show a curl equivalency to the call
 --api-key API_KEY                API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                        Show CLI version
 --no-color                       Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Request a two-factor authentication code to be sent via SMS.

If --phone-number is not provided, uses the phone number on your account.
The secret token will be returned and must be used with 'vastai tfa activate'.

Examples:
 vastai tfa send-sms
 vastai tfa send-sms --phone-number +12345678901
```

---

### tfa status

Shows the current 2FA status and configured methods

```
usage: vast.py tfa status [-h] [--url URL] [--retry RETRY] [--explain] [--raw] [--full] [--curl] [--api-key API_KEY] [--version]
                          [--no-color]

Show the current 2FA status and configured methods for your account

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Show the current 2FA status for your account, including:
 - Whether or not 2FA is enabled
 - A list of active 2FA methods
 - The number of backup codes remaining (if 2FA is enabled)
```

---

### tfa totp-setup

Generate TOTP secret and QR code for Authenticator app setup

```
usage: vastai tfa totp-setup

Generate TOTP secret and QR code for Authenticator app setup

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Set up TOTP (Time-based One-Time Password) 2FA using an Authenticator app.

This command generates a new TOTP secret and displays:
- A QR code (for scanning with your app)
- A manual entry key (for typing into your app)
- A secret token (needed for the next step)

Workflow:
 1. Run this command to generate the TOTP secret
 2. Add the account to your Authenticator app by either:
    - Scanning the displayed QR code, OR
    - Manually entering the key shown
 3. Once added, your app will display a 6-digit code
 4. Complete setup by running:
    vastai tfa activate --secret <SECRET> <CODE>

Supported Authenticator Apps:
 - Google Authenticator
 - Microsoft Authenticator
 - Authy
 - 1Password
 - Any TOTP-compatible app

Example:
 vastai tfa totp-setup
```

---

### tfa update

Update a 2FA method's settings

```
usage: vastai tfa update METHOD_ID [--label LABEL] [--set-primary]

Update a 2FA method's settings (label or primary status)

positional arguments:
 METHOD_ID                      ID of the 2FA method to update (see `vastai tfa status`)

options:
 -h, --help                     show this help message and exit
 -l, --label LABEL              New label/name for this 2FA method
 -p, --set-primary SET_PRIMARY  Set this method as the primary/default 2FA method

Global options (available for all commands):
 --url URL                      Server REST API URL
 --retry RETRY                  Retry limit
 --explain                      Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                          Output machine-readable json
 --full                         Print full results instead of paging with `less` for commands that support it
 --curl                         Show a curl equivalency to the call
 --api-key API_KEY              API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                      Show CLI version
 --no-color                     Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Update the label or primary status of a 2FA method.

The label is a friendly name to help you identify different methods
(e.g. "Work Phone", "Personal Authenticator").

The primary method is your preferred/default 2FA method.

Examples:
 vastai tfa update 123 --label "Work Phone"
 vastai tfa update 456 --set-primary
 vastai tfa update 789 --label "Backup Authenticator" --set-primary
```

---

### transfer credit

Transfer credits to another account

```
usage: vastai transfer credit [--recipient EMAIL] [--amount DOLLARS] [RECIPIENT AMOUNT]

Transfer credits to another account

options:
 -h, --help                 show this help message and exit
 --recipient, -r RECIPIENT  email (or id) of recipient account
 --amount, -a AMOUNT        dollars of credit to transfer
 --skip                     skip confirmation

Global options (available for all commands):
 --url URL                  Server REST API URL
 --retry RETRY              Retry limit
 --explain                  Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                      Output machine-readable json
 --full                     Print full results instead of paging with `less` for commands that support it
 --curl                     Show a curl equivalency to the call
 --api-key API_KEY          API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                  Show CLI version
 --no-color                 Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Transfer credits to another account. This action is irreversible.

Supports two syntax styles (named flags recommended):
  vastai transfer credit --recipient user@example.com --amount 10.00
  vastai transfer credit user@example.com 10.00  (legacy positional)

Examples:
  vastai transfer credit --recipient user@example.com --amount 25.50
  vastai transfer credit -r user@example.com -a 25.50
  vastai transfer credit user@example.com 25.50
```

---

### update endpoint

Update an existing endpoint group

```
usage: vastai update endpoint ID [OPTIONS]

Update an existing endpoint group

positional arguments:
 id                               id of endpoint group to update

options:
 -h, --help                       show this help message and exit
 --min_load MIN_LOAD              minimum floor load in perf units/s  (token/s for LLms)
 --min_cold_load MIN_COLD_LOAD    minimum floor load in perf units/s  (token/s for LLms), but allow handling with cold workers
 --endpoint_state ENDPOINT_STATE  active, suspended, or stopped
 --target_util TARGET_UTIL        target capacity utilization (fraction, max 1.0, default 0.9)
 --cold_mult COLD_MULT            cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)
 --cold_workers COLD_WORKERS      min number of workers to keep 'cold' when you have no load (default 5)
 --max_workers MAX_WORKERS        max number of workers your endpoint group can have (default 20)
 --endpoint_name ENDPOINT_NAME    deployment endpoint name (allows multiple workergroups to share same deployment endpoint)

Global options (available for all commands):
 --url URL                        Server REST API URL
 --retry RETRY                    Retry limit
 --explain                        Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                            Output machine-readable json
 --full                           Print full results instead of paging with `less` for commands that support it
 --curl                           Show a curl equivalency to the call
 --api-key API_KEY                API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                        Show CLI version
 --no-color                       Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai update endpoint 4242 --min_load 100 --target_util 0.9 --cold_mult 2.0 --endpoint_name "LLama"
```

---

### update env-var

Update an existing user environment variable

```
usage: vastai update env-var <name> <value>

Update an existing user environment variable

positional arguments:
 name               Environment variable name to update
 value              New environment variable value

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### update instance

Update an instance configuration or recreate from a template

```
usage: vastai update instance ID [OPTIONS]

Update an instance configuration or recreate from a template

positional arguments:
 id                                   id of instance to update

options:
 -h, --help                           show this help message and exit
 --template_id TEMPLATE_ID            new template ID to associate with the instance
 --template_hash_id TEMPLATE_HASH_ID  new template hash ID to associate with the instance
 --image IMAGE                        new image UUID for the instance
 --args ARGS                          new arguments for the instance
 --env ENV                            new environment variables for the instance
 --onstart ONSTART                    new onstart script for the instance

Global options (available for all commands):
 --url URL                            Server REST API URL
 --retry RETRY                        Retry limit
 --explain                            Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                                Output machine-readable json
 --full                               Print full results instead of paging with `less` for commands that support it
 --curl                               Show a curl equivalency to the call
 --api-key API_KEY                    API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                            Show CLI version
 --no-color                           Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai update instance 1234 --template_hash_id 661d064bbda1f2a133816b6d55da07c3
```

---

### update ssh-key

Update an SSH key's label or properties

```
usage: vastai update ssh-key ID SSH_KEY

Update an SSH key's label or properties

positional arguments:
 id                 id of the ssh key to update
 ssh_key            new public key value

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### update team-role

Update an existing team role

```
usage: vastai update team-role ID --name NAME --permissions PERMISSIONS

Update an existing team role

positional arguments:
 id                         id of the role

options:
 -h, --help                 show this help message and exit
 --name NAME                name of the template
 --permissions PERMISSIONS  file path for json encoded permissions, look in the docs for more information

Global options (available for all commands):
 --url URL                  Server REST API URL
 --retry RETRY              Retry limit
 --explain                  Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                      Output machine-readable json
 --full                     Print full results instead of paging with `less` for commands that support it
 --curl                     Show a curl equivalency to the call
 --api-key API_KEY          API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                  Show CLI version
 --no-color                 Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### update template

Update an existing template

```
usage: vastai update template HASH_ID

Update an existing template

positional arguments:
 HASH_ID                        hash id of the template

options:
 -h, --help                     show this help message and exit
 --name NAME                    name of the template
 --image IMAGE                  docker container image to launch
 --image_tag IMAGE_TAG          docker image tag (can also be appended to end of image_path)
 --href HREF                    link you want to provide
 --repo REPO                    link to repository
 --login LOGIN                  docker login arguments for private repo authentication, surround with ''
 --env ENV                      Contents of the 'Docker options' field
 --ssh                          Launch as an ssh instance type
 --jupyter                      Launch as a jupyter instance instead of an ssh instance
 --direct                       Use (faster) direct connections for jupyter & ssh
 --jupyter-dir JUPYTER_DIR      For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory
 --jupyter-lab                  For runtype 'jupyter', Launch instance with jupyter lab
 --onstart-cmd ONSTART_CMD      contents of onstart script as single argument
 --search_params SEARCH_PARAMS  search offers filters
 -n, --no-default               Disable default search param query args
 --disk_space DISK_SPACE        disk storage space, in GB
 --readme README                readme string
 --hide-readme                  hide the readme from users
 --desc DESC                    description string
 --public                       make template available to public

Global options (available for all commands):
 --url URL                      Server REST API URL
 --retry RETRY                  Retry limit
 --explain                      Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                          Output machine-readable json
 --full                         Print full results instead of paging with `less` for commands that support it
 --curl                         Show a curl equivalency to the call
 --api-key API_KEY              API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                      Show CLI version
 --no-color                     Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Update a template

Example:
    vastai update template c81e7ab0e928a508510d1979346de10d --name "tgi-llama2-7B-quantized" --image "ghcr.io/huggingface/text-generation-inference:1.0.3"
                            --env "-p 3000:3000 -e MODEL_ARGS='--model-id TheBloke/Llama-2-7B-chat-GPTQ --quantize gptq'"
                            --onstart-cmd 'wget -O - https://raw.githubusercontent.com/vast-ai/vast-pyworker/main/scripts/launch_tgi.sh | bash'
                            --search_params "gpu_ram>=23 num_gpus=1 gpu_name=RTX_3090 inet_down>128 direct_port_count>3 disk_space>=192 driver_version>=535086005 rented=False"
                            --disk 8.0 --ssh --direct
```

---

### update workergroup

Update an existing autoscale group

```
usage: vastai update workergroup WORKERGROUP_ID --endpoint_id ENDPOINT_ID [options]

Update an existing autoscale group

positional arguments:
 id                             id of autoscale group to update

options:
 -h, --help                     show this help message and exit
 --min_load MIN_LOAD            minimum floor load in perf units/s  (token/s for LLms)
 --target_util TARGET_UTIL      target capacity utilization (fraction, max 1.0, default 0.9)
 --cold_mult COLD_MULT          cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)
 --cold_workers COLD_WORKERS    min number of workers to keep 'cold' for this workergroup
 --test_workers TEST_WORKERS    number of workers to create to get an performance estimate for while initializing workergroup (default 3)
 --gpu_ram GPU_RAM              estimated GPU RAM req  (independent of search string)
 --template_hash TEMPLATE_HASH  template hash (**Note**: if you use this field, you can skip search_params, as they are automatically inferred from the template)
 --template_id TEMPLATE_ID      template id
 --search_params SEARCH_PARAMS  search param string for search offers    ex: "gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64"
 -n, --no-default               Disable default search param query args
 --launch_args LAUNCH_ARGS      launch args  string for create instance  ex: "--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/public.vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64"
 --endpoint_name ENDPOINT_NAME  deployment endpoint name (allows multiple workergroups to share same deployment endpoint)
 --endpoint_id ENDPOINT_ID      deployment endpoint id (allows multiple workergroups to share same deployment endpoint)

Global options (available for all commands):
 --url URL                      Server REST API URL
 --retry RETRY                  Retry limit
 --explain                      Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                          Output machine-readable json
 --full                         Print full results instead of paging with `less` for commands that support it
 --curl                         Show a curl equivalency to the call
 --api-key API_KEY              API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                      Show CLI version
 --no-color                     Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Example: vastai update workergroup 4242 --min_load 100 --target_util 0.9 --cold_mult 2.0 --search_params "gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64" --launch_args "--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/public.vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64" --gpu_ram 32.0 --endpoint_name "LLama" --endpoint_id 2
```

---

## Host Commands

Commands for GPU providers hosting machines on Vast.ai.

### add network-disk

[Beta] Attach a network disk to a machine cluster

```
usage: vastai add network-disk MACHINES MOUNT_PATH [options]

[Host] [Beta] Attach a network disk to a machine cluster

positional arguments:
 machines                 ids of machines to add disk to, that is networked to be on the same LAN as machine
 mount_point              mount path of disk to add

options:
 -h, --help               show this help message and exit
 -d, --disk_id [DISK_ID]  id of network disk to attach to machines in the cluster

Global options (available for all commands):
 --url URL                Server REST API URL
 --retry RETRY            Retry limit
 --explain                Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                    Output machine-readable json
 --full                   Print full results instead of paging with `less` for commands that support it
 --curl                   Show a curl equivalency to the call
 --api-key API_KEY        API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                Show CLI version
 --no-color               Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

This variant can be used to add a network disk to a physical cluster.
When you add a network disk for the first time, you just need to specify the machine(s) and mount_path.
When you add a network disk for the second time, you need to specify the disk_id.
Example:
vastai add network-disk 1 /mnt/disk1
vastai add network-disk 1 /mnt/disk1 -d 12345
```

---

### cancel maint

Cancel a scheduled maintenance window

```
usage: vastai cancel maint id

[Host] Cancel a scheduled maintenance window

positional arguments:
 id                 id of machine to cancel maintenance(s) for

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

For deleting a machine's scheduled maintenance window(s), use this cancel maint command.
Example: vastai cancel maint 8207
```

---

### cleanup machine

Clean up expired storage to free disk space

```
usage: vastai cleanup machine ID [options]

[Host] Clean up expired storage to free disk space

positional arguments:
 id                 id of machine to cleanup

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Instances expire on their end date. Expired instances still pay storage fees, but can not start.
Since hosts are still paid storage fees for expired instances, we do not auto delete them.
Instead you can use this CLI/API function to delete all expired storage instances for a machine.
This is useful if you are running low on storage, want to do maintenance, or are subsidizing storage, etc.
```

---

### create network-volume

[Beta] Create a new network-attached storage volume

```
usage: vastai create network volume ID [options]

[Host] [Beta] Create a new network-attached storage volume

positional arguments:
 id                 id of network volume offer

options:
 -h, --help         show this help message and exit
 -s, --size SIZE    size in GB of network volume. Default 15 GB.
 -n, --name NAME    Optional name of network volume.

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Creates a network volume from an offer ID (which is returned from "search network volumes"). Each offer ID can be used to create multiple volumes,
provided the size of all volumes does not exceed the size of the offer.
```

---

### defrag machines

Rebuild larger GPU offers from orphaned single GPUs when possible

```
usage: vastai defragment machines IDs 

[Host] Rebuild larger GPU offers from orphaned single GPUs when possible

positional arguments:
 IDs                ids of machines

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Defragment some of your machines. This will rearrange GPU assignments to try and make more multi-gpu offers available.
```

---

### delete machine

Remove a machine from your host account

```
usage: vastai delete machine <id>

[Host] Remove a machine from your host account

positional arguments:
 id                 id of machine to delete

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### list machine

List a single machine for rent on the marketplace

```
usage: vastai list machine ID [options]

[Host] List a single machine for rent on the marketplace

positional arguments:
 id                                 id of machine to list

options:
 -h, --help                         show this help message and exit
 -g, --price_gpu PRICE_GPU          per gpu rental price in $/hour  (price for active instances)
 -s, --price_disk PRICE_DISK        storage price in $/GB/month (price for inactive instances), default: $0.10/GB/month
 -u, --price_inetu PRICE_INETU      price for internet upload bandwidth in $/GB
 -d, --price_inetd PRICE_INETD      price for internet download bandwidth in $/GB
 -b, --price_min_bid PRICE_MIN_BID  per gpu minimum bid price floor in $/hour
 -r, --discount_rate DISCOUNT_RATE  Max long term prepay discount rate fraction, default: 0.4 
 -m, --min_chunk MIN_CHUNK          minimum amount of gpus
 -e, --end_date END_DATE            contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format)
 -l, --duration DURATION            Updates end_date daily to be duration from current date. Cannot be combined with end_date. Format is: `n days`, `n weeks`, `n months`, `n years`, or total intended duration in seconds.
 -v, --vol_size VOL_SIZE            Size for volume contract offer. Defaults to half of available disk. Set 0 to not create a volume contract offer.
 -z, --vol_price VOL_PRICE          Price for disk on volume contract offer. Defaults to price_disk. Invalid if vol_size is 0.

Global options (available for all commands):
 --url URL                          Server REST API URL
 --retry RETRY                      Retry limit
 --explain                          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                              Output machine-readable json
 --full                             Print full results instead of paging with `less` for commands that support it
 --curl                             Show a curl equivalency to the call
 --api-key API_KEY                  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                          Show CLI version
 --no-color                         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Performs the same action as pressing the "LIST" button on the site https://cloud.vast.ai/host/machines.
On the end date the listing will expire and your machine will unlist. However any existing client jobs will still remain until ended by their owners.
Once you list your machine and it is rented, it is extremely important that you don't interfere with the machine in any way.
If your machine has an active client job and then goes offline, crashes, or has performance problems, this could permanently lower your reliability rating.
We strongly recommend you test the machine first and only list when ready.
```

---

### list machines

List multiple machines for rent on the marketplace

```
usage: vastai list machines IDS [OPTIONS]

[Host] List multiple machines for rent on the marketplace

positional arguments:
 ids                                ids of machines to list

options:
 -h, --help                         show this help message and exit
 -g, --price_gpu PRICE_GPU          per gpu on-demand rental price in $/hour (base price for active instances)
 -s, --price_disk PRICE_DISK        storage price in $/GB/month (price for inactive instances), default: $0.10/GB/month
 -u, --price_inetu PRICE_INETU      price for internet upload bandwidth in $/GB
 -d, --price_inetd PRICE_INETD      price for internet download bandwidth in $/GB
 -b, --price_min_bid PRICE_MIN_BID  per gpu minimum bid price floor in $/hour
 -r, --discount_rate DISCOUNT_RATE  Max long term prepay discount rate fraction, default: 0.4 
 -m, --min_chunk MIN_CHUNK          minimum amount of gpus
 -e, --end_date END_DATE            contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format)
 -l, --duration DURATION            Updates end_date daily to be duration from current date. Cannot be combined with end_date. Format is: `n days`, `n weeks`, `n months`, `n years`, or total intended duration in seconds.
 -v, --vol_size VOL_SIZE            Size for volume contract offer. Defaults to half of available disk. Set 0 to not create a volume contract offer.
 -z, --vol_price VOL_PRICE          Price for disk on volume contract offer. Defaults to price_disk. Invalid if vol_size is 0.

Global options (available for all commands):
 --url URL                          Server REST API URL
 --retry RETRY                      Retry limit
 --explain                          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                              Output machine-readable json
 --full                             Print full results instead of paging with `less` for commands that support it
 --curl                             Show a curl equivalency to the call
 --api-key API_KEY                  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                          Show CLI version
 --no-color                         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

This variant can be used to list or update the listings for multiple machines at once with the same args.
You could extend the end dates of all your machines using a command combo like this:
./vast.py list machines $(./vast.py show machines -q) -e 12/31/2024 --retry 6
```

---

### list network-volume

[Beta] List disk space as a rentable network volume

```
usage: vastai list network volume DISK_ID [options]

[Host] [Beta] List disk space as a rentable network volume

positional arguments:
 disk_id                      id of network disk to list

options:
 -h, --help                   show this help message and exit
 -p, --price_disk PRICE_DISK  storage price in $/GB/month, default: $0.15/GB/month
 -e, --end_date END_DATE      contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format), default 1 month
 -s, --size SIZE              size of disk space allocated to offer in GB, default 15 GB

Global options (available for all commands):
 --url URL                    Server REST API URL
 --retry RETRY                Retry limit
 --explain                    Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                        Output machine-readable json
 --full                       Print full results instead of paging with `less` for commands that support it
 --curl                       Show a curl equivalency to the call
 --api-key API_KEY            API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                    Show CLI version
 --no-color                   Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### list volume

List disk space as a rentable volume

```
usage: vastai list volume ID [options]

[Host] List disk space as a rentable volume

positional arguments:
 id                           id of machine to list

options:
 -h, --help                   show this help message and exit
 -p, --price_disk PRICE_DISK  storage price in $/GB/month, default: $0.10/GB/month
 -e, --end_date END_DATE      contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format), default 3 months
 -s, --size SIZE              size of disk space allocated to offer in GB, default 15 GB

Global options (available for all commands):
 --url URL                    Server REST API URL
 --retry RETRY                Retry limit
 --explain                    Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                        Output machine-readable json
 --full                       Print full results instead of paging with `less` for commands that support it
 --curl                       Show a curl equivalency to the call
 --api-key API_KEY            API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                    Show CLI version
 --no-color                   Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Allocates a section of disk on a machine to be used for volumes.
```

---

### list volumes

List disk space on multiple machines as rentable volumes

```
usage: vastai list volumes IDS [OPTIONS]

[Host] List disk space on multiple machines as rentable volumes

positional arguments:
 ids                          ids of machines to list volumes on

options:
 -h, --help                   show this help message and exit
 -p, --price_disk PRICE_DISK  storage price in $/GB/month, default: $0.10/GB/month
 -e, --end_date END_DATE      contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format), default 3 months
 -s, --size SIZE              size of disk space allocated to offer in GB, default 15 GB

Global options (available for all commands):
 --url URL                    Server REST API URL
 --retry RETRY                Retry limit
 --explain                    Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                        Output machine-readable json
 --full                       Print full results instead of paging with `less` for commands that support it
 --curl                       Show a curl equivalency to the call
 --api-key API_KEY            API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                    Show CLI version
 --no-color                   Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Allocates a section of disk on machines to be used for volumes.
```

---

### remove defjob

Remove default background jobs from a machine

```
usage: vastai remove defjob id

[Host] Remove default background jobs from a machine

positional arguments:
 id                 id of machine to remove default instance from

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### remove-machine-from-cluster

[Beta] Remove a machine from a cluster

```
usage: vastai remove-machine-from-cluster CLUSTER_ID MACHINE_ID NEW_MANAGER_ID

[Host] [Beta] Remove a machine from a cluster

positional arguments:
 cluster_id         ID of cluster you want to remove machine from.
 machine_id         ID of machine to remove from cluster.
 new_manager_id     ID of machine to promote to manager. Must already be in cluster

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Removes machine from cluster and also reassigns manager ID,
if we're removing the manager node
```

---

### reports

Get usage and performance reports for a machine

```
usage: vastai reports ID

[Host] Get usage and performance reports for a machine

positional arguments:
 id                 machine id

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### schedule maint

Schedule a maintenance window for a machine

```
usage: vastai schedule maintenance id [--sdate START_DATE --duration DURATION --maintenance_category MAINTENANCE_CATEGORY]

[Host] Schedule a maintenance window for a machine

positional arguments:
 id                                           id of machine to schedule maintenance for

options:
 -h, --help                                   show this help message and exit
 --sdate SDATE                                maintenance start date in unix epoch time (UTC seconds)
 --duration DURATION                          maintenance duration in hours
 --maintenance_category MAINTENANCE_CATEGORY  (optional) can be one of [power, internet, disk, gpu, software, other]

Global options (available for all commands):
 --url URL                                    Server REST API URL
 --retry RETRY                                Retry limit
 --explain                                    Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                                        Output machine-readable json
 --full                                       Print full results instead of paging with `less` for commands that support it
 --curl                                       Show a curl equivalency to the call
 --api-key API_KEY                            API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                                    Show CLI version
 --no-color                                   Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

The proper way to perform maintenance on your machine is to wait until all active contracts have expired or the machine is vacant.
For unplanned or unscheduled maintenance, use this schedule maint command. That will notify the client that you have to take the machine down and that they should save their work.
You can specify a date, duration, reason and category for the maintenance.

Example: vastai schedule maint 8207 --sdate 1677562671 --duration 0.5 --maintenance_category "power"
```

---

### search network-volumes

[Beta] Search available network volume offers with filters

```
usage: vastai search network volumes [--help] [--api-key API_KEY] [--raw] <query>

[Host] [Beta] Search available network volume offers with filters

positional arguments:
 query              Query to search for. default: 'external=false verified=true disk_space>=1', pass -n to ignore default

options:
 -h, --help         show this help message and exit
 -n, --no-default   Disable default query
 --limit LIMIT
 --storage STORAGE  Amount of storage to use for pricing, in GiB. default=1.0GiB
 -o, --order ORDER  Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'disk_space,inet_up-'.  default='score-'

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Query syntax:

    query = comparison comparison...
    comparison = field op value
    field = <name of a field>
    op = one of: <, <=, ==, !=, >=, >, in, notin
    value = <bool, int, float, string> | 'any' | [value0, value1, ...]
    bool: True, False

note: to pass '>' and '<' on the command line, make sure to use quotes
note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

Examples:

    # search for volumes with greater than 50GB of available storage and greater than 500 Mb/s upload and download speed
    vastai search volumes "disk_space>50 inet_up>500 inet_down>500"

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
```

---

### self-test machine

Run diagnostics on a hosted machine

```
usage: vastai self-test machine <machine_id> [--debugging] [--explain] [--api_key API_KEY] [--url URL] [--retry RETRY] [--raw] [--ignore-requirements]

[Host] Run diagnostics on a hosted machine

positional arguments:
 machine_id             Machine ID

options:
 -h, --help             show this help message and exit
 --debugging            Enable debugging output
 --explain              Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                  Output machine-readable JSON
 --url URL              Server REST API URL
 --retry RETRY          Retry limit
 --ignore-requirements  Ignore the minimum system requirements and run the self test regardless

Global options (available for all commands):
 --full                 Print full results instead of paging with `less` for commands that support it
 --curl                 Show a curl equivalency to the call
 --api-key API_KEY      API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version              Show CLI version
 --no-color             Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

This command tests if a machine meets specific requirements and
runs a series of tests to ensure it's functioning correctly.

Examples:
 vast self-test machine 12345
 vast self-test machine 12345 --debugging
 vast self-test machine 12345 --explain
 vast self-test machine 12345 --api_key <YOUR_API_KEY>
```

---

### set defjob

Configure default background jobs for a machine

```
usage: vastai set defjob id [--api-key API_KEY] [--price_gpu PRICE_GPU] [--price_inetu PRICE_INETU] [--price_inetd PRICE_INETD] [--image IMAGE] [--args ...]

[Host] Configure default background jobs for a machine

positional arguments:
 id                         id of machine to launch default instance on

options:
 -h, --help                 show this help message and exit
 --price_gpu PRICE_GPU      per gpu rental price in $/hour
 --price_inetu PRICE_INETU  price for internet upload bandwidth in $/GB
 --price_inetd PRICE_INETD  price for internet download bandwidth in $/GB
 --image IMAGE              docker container image to launch
 --args ...                 list of arguments passed to container launch

Global options (available for all commands):
 --url URL                  Server REST API URL
 --retry RETRY              Retry limit
 --explain                  Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                      Output machine-readable json
 --full                     Print full results instead of paging with `less` for commands that support it
 --curl                     Show a curl equivalency to the call
 --api-key API_KEY          API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                  Show CLI version
 --no-color                 Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Performs the same action as creating a background job at https://cloud.vast.ai/host/create.
```

---

### set min-bid

Set minimum price for interruptible/spot instance rentals

```
usage: vastai set min_bid id [--price PRICE]

[Host] Set minimum price for interruptible/spot instance rentals

positional arguments:
 id                 id of machine to set min bid price for

options:
 -h, --help         show this help message and exit
 --price PRICE      per gpu min bid price in $/hour

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Change the current min bid price of machine id to PRICE.
```

---

### show earnings

Show rental income history for your machines

```
usage: vastai show earnings [OPTIONS]

[Host] Show rental income history for your machines

options:
 -h, --help                   show this help message and exit
 -q, --quiet                  only display numeric ids
 -s, --start_date START_DATE  start date and time for report. Many formats accepted
 -e, --end_date END_DATE      end date and time for report. Many formats accepted 
 -m, --machine_id MACHINE_ID  Machine id (optional)

Global options (available for all commands):
 --url URL                    Server REST API URL
 --retry RETRY                Retry limit
 --explain                    Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw                        Output machine-readable json
 --full                       Print full results instead of paging with `less` for commands that support it
 --curl                       Show a curl equivalency to the call
 --api-key API_KEY            API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version                    Show CLI version
 --no-color                   Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show machine

Show details for a specific hosted machine

```
usage: vastai show machine ID [OPTIONS]

[Host] Show details for a specific hosted machine

positional arguments:
 id                 id of machine to display

options:
 -h, --help         show this help message and exit
 -q, --quiet        only display numeric ids

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show machines

List all your hosted machines

```
usage: vastai show machines [OPTIONS]

[Host] List all your hosted machines

options:
 -h, --help         show this help message and exit
 -q, --quiet        only display numeric ids

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show maints

List scheduled maintenance windows

```
usage: vastai show maints --ids MACHINE_IDS [OPTIONS]

[Host] List scheduled maintenance windows

options:
 -h, --help         show this help message and exit
 -i, --ids IDS      comma separated string of machine_ids for which to get maintenance information
 -q, --quiet        only display numeric ids of the machines in maintenance

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### show network-disks

[Beta] List network disks attached to your machines

```
usage: vastai show network-disks

[Host] [Beta] List network disks attached to your machines

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)

Show network disks associated with your account.
```

---

### unlist machine

Remove a machine from the rental marketplace

```
usage: vastai unlist machine <id>

[Host] Remove a machine from the rental marketplace

positional arguments:
 id                 id of machine to unlist

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### unlist network-volume

[Beta] Remove a network volume offer from the marketplace

```
usage: vastai unlist network volume OFFER_ID

[Host] [Beta] Remove a network volume offer from the marketplace

positional arguments:
 id                 id of network volume offer to unlist

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---

### unlist volume

Remove a volume offer from the marketplace

```
usage: vastai unlist volume ID

[Host] Remove a volume offer from the marketplace

positional arguments:
 id                 volume ID you want to unlist

options:
 -h, --help         show this help message and exit

Global options (available for all commands):
 --url URL          Server REST API URL
 --retry RETRY      Retry limit
 --explain          Output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --raw              Output machine-readable json
 --full             Print full results instead of paging with `less` for commands that support it
 --curl             Show a curl equivalency to the call
 --api-key API_KEY  API Key to use. defaults to using the one stored in C:\Users\begna112\.config\vastai\vast_api_key
 --version          Show CLI version
 --no-color         Disable colored output for commands that support it (Note: the 'rich' python module is required for colored output)
```

---
