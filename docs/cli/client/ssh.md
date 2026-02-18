# SSH & File Transfer Commands

Commands for connecting to instances and transferring files.

## ssh-url

Generate SSH connection URL for an instance

```bash
vastai ssh-url ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of instance |

**Notes:**

Retrieves the SSH connection URL for an instance. Use this to get the host and port
information needed to connect via SSH.

**Examples:**

```bash
    vastai ssh-url 12345                       # Get SSH URL for instance 12345
```

!!! tip
    Output format:
    ssh://root@<ip_address>:<port>
    Use with ssh command:
    ssh -p <port> root@<ip_address>
    See also: 'vastai scp-url' for SCP file transfer URLs

---

## scp-url

Generate SCP file transfer URL for an instance

```bash
vastai scp-url ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id |

**Notes:**

Retrieves the SCP connection URL for an instance. Use this to get the host and port
information needed to transfer files via SCP.

**Examples:**

```bash
    vastai scp-url 12345                       # Get SCP URL for instance 12345
```

!!! tip
    Output format:
    scp://root@<ip_address>:<port>
    Use with scp command:
    scp -P <port> local_file root@<ip_address>:/remote/path
    scp -P <port> root@<ip_address>:/remote/file ./local_path
    See also: 'vastai ssh-url' for SSH connection URLs, 'vastai copy' for simplified file transfers

---

## copy

Copy files/directories between instances or between local and instance

```bash
vastai copy SRC DST
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `src` | Source location for copy operation (supports multiple formats) |
| `dst` | Target location for copy operation (supports multiple formats) |

**Options:**

| Option | Description |
|--------|-------------|
| `-i, --identity IDENTITY` | Location of ssh private key |

**Notes:**

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

**Examples:**

```bash
 vastai copy 6003036:/workspace/ 6003038:/workspace/
 vastai copy C.11824:/data/test local:data/test
 vastai copy local:data/test C.11824:/data/test
 vastai copy drive:/folder/file.txt C.6003036:/workspace/
 vastai copy s3.101:/data/ C.6003036:/workspace/
 vastai copy V.1234:/file C.5678:/workspace/
```

!!! tip
    The first example copy syncs all files from the absolute directory '/workspace' on instance 6003036 to the directory '/workspace' on instance 6003038.
    The second example copy syncs files from container 11824 to the local machine using structured syntax.
    The third example copy syncs files from local to container 11824 using structured syntax.
    The fourth example copy syncs files from Google Drive to an instance.
    The fifth example copy syncs files from S3 bucket with id 101 to an instance.

---

## cloud copy

Copy files between instances and cloud storage (S3, GCS, Azure)

```bash
vastai cloud copy --src SRC --dst DST --instance INSTANCE_ID -connection CONNECTION_ID --transfer TRANSFER_TYPE
```

**Options:**

| Option | Description |
|--------|-------------|
| `--src SRC` | path to source of object to copy |
| `--dst DST` | path to target of copy operation |
| `--instance INSTANCE` | id of the instance |
| `--connection CONNECTION` | id of cloud connection on your account (get from calling 'vastai show connections') |
| `--transfer TRANSFER` | type of transfer, possible options include Instance To Cloud and Cloud To Instance |
| `--dry-run` | show what would have been transferred |
| `--size-only` | skip based on size only, not mod-time or checksum |
| `--ignore-existing` | skip all files that exist on destination |
| `--update` | skip files that are newer on the destination |
| `--delete-excluded` | delete files on dest excluded from transfer |
| `--schedule {HOURLY,DAILY,WEEKLY}` | try to schedule a command to run hourly, daily, or monthly. Valid values are HOURLY, DAILY, WEEKLY  For ex. --schedule DAILY |
| `--start_date START_DATE` | Start date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is now. (optional) |
| `--end_date END_DATE` | End date/time in format 'YYYY-MM-DD HH:MM:SS PM' (UTC). Default is contract's end. (optional) |
| `--day DAY` | Day of week you want scheduled job to run on (0-6, where 0=Sunday) or "*". Default will be 0. For ex. --day 0 |
| `--hour HOUR` | Hour of day you want scheduled job to run on (0-23) or "*" (UTC). Default will be 0. For ex. --hour 16 |

**Notes:**

Copies a directory from a source location to a target location. Each of source and destination
directories can be either local or remote, subject to appropriate read and write
permissions required to carry out the action. The format for both src and dst is [instance_id:]path.
You can find more information about the cloud copy operation here: https://vast.ai/docs/gpu-instances/cloud-sync

**Examples:**

```bash
 vastai show connections
 vastai cloud copy --src /folder --dst /workspace --instance 6003036 --connection 1001 --transfer "Instance To Cloud"
```

!!! tip
    ID    NAME      Cloud Type
    1001  test_dir  drive
    1003  data_dir  drive
    The example copies all contents of /folder into /workspace on instance 6003036 from gdrive connection 'test_dir'.

---

## cancel copy

Cancel an in-progress file copy operation

```bash
vastai cancel copy DST
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `dst` | instance_id:/path to target of copy operation |

**Notes:**

Use this command to cancel any/all current remote copy operations copying to a specific named instance, given by DST.

**Examples:**

```bash
 vastai cancel copy 12371
```

!!! tip
    The first example cancels all copy operations currently copying data into instance 12371

---

## cancel sync

Cancel an in-progress file sync operation

```bash
vastai cancel sync DST
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `dst` | instance_id:/path to target of sync operation |

**Notes:**

Use this command to cancel any/all current remote cloud sync operations copying to a specific named instance, given by DST.

**Examples:**

```bash
 vastai cancel sync 12371
```

!!! tip
    The first example cancels all copy operations currently copying data into instance 12371

---

## attach ssh

Attach an SSH key to an instance for remote access

```bash
vastai attach ssh instance_id ssh_key
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `instance_id` | id of instance to attach to |
| `ssh_key` | ssh key to attach to instance |

**Notes:**

Attach an ssh key to an instance. This will allow you to connect to the instance with the ssh key.

**Examples:**

```bash
 vastai attach ssh 12371 ssh-rsa AAAAB3NzaC1yc2EAAA...
 vastai attach ssh 12371 ssh-rsa $(cat ~/.ssh/id_rsa)
```

---

## detach ssh

Remove an SSH key from an instance

```bash
vastai detach instance_id ssh_key_id
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `instance_id` | id of the instance |
| `ssh_key_id` | id of the key to detach to the instance |

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
