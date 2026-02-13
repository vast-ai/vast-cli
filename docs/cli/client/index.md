# Client Commands

Commands for renting and managing GPU instances on Vast.ai.

## Command Categories

### Instance Management

| Command | Description |
|---------|-------------|
| [`create instance`](instances.md#create-instance) | Create a new instance |
| [`destroy instance`](instances.md#destroy-instance) | Destroy an instance |
| [`start instance`](instances.md#start-instance) | Start a stopped instance |
| [`stop instance`](instances.md#stop-instance) | Stop a running instance |
| [`reboot instance`](instances.md#reboot-instance) | Reboot an instance |
| [`label instance`](instances.md#label-instance) | Assign a label to an instance |
| [`show instances`](instances.md#show-instances) | List your instances |
| [`show instance`](instances.md#show-instance) | Show instance details |
| [`logs`](instances.md#logs) | Get instance logs |
| [`execute`](instances.md#execute) | Execute command on instance |

### Search

| Command | Description |
|---------|-------------|
| [`search offers`](search.md#search-offers) | Search available GPU offers |
| [`search templates`](search.md#search-templates) | Search templates |
| [`search volumes`](search.md#search-volumes) | Search volume offers |
| [`search benchmarks`](search.md#search-benchmarks) | Search benchmark results |

### SSH & File Transfer

| Command | Description |
|---------|-------------|
| [`ssh-url`](ssh.md#ssh-url) | Get SSH connection URL |
| [`scp-url`](ssh.md#scp-url) | Get SCP URL for file transfer |
| [`copy`](ssh.md#copy) | Copy files to/from instances |
| [`attach ssh`](ssh.md#attach-ssh) | Attach SSH key to instance |
| [`detach ssh`](ssh.md#detach-ssh) | Detach SSH key from instance |

### Billing & Account

| Command | Description |
|---------|-------------|
| [`show invoices-v1`](billing.md#show-invoices-v1) | List invoices and charges |
| [`show user`](billing.md#show-user) | Get account info |
| [`transfer credit`](billing.md#transfer-credit) | Transfer credits |
| [`add credit`](billing.md#add-credit) | Add credit to account |

### Volumes

| Command | Description |
|---------|-------------|
| [`create volume`](volumes.md#create-volume) | Create a new volume |
| [`delete volume`](volumes.md#delete-volume) | Delete a volume |
| [`show volumes`](volumes.md#show-volumes) | List your volumes |
| [`clone volume`](volumes.md#clone-volume) | Clone an existing volume |

### Teams

| Command | Description |
|---------|-------------|
| [`create team`](teams.md#create-team) | Create a new team |
| [`destroy team`](teams.md#destroy-team) | Delete a team |
| [`invite member`](teams.md#invite-member) | Invite team member |
| [`remove member`](teams.md#remove-member) | Remove team member |
| [`show members`](teams.md#show-members) | List team members |

### Autoscaling / Worker Groups

| Command | Description |
|---------|-------------|
| [`create workergroup`](autoscaling.md#create-workergroup) | Create worker group |
| [`delete workergroup`](autoscaling.md#delete-workergroup) | Delete worker group |
| [`update workergroup`](autoscaling.md#update-workergroup) | Update worker group |
| [`show workergroups`](autoscaling.md#show-workergroups) | List worker groups |

### API & SSH Keys

| Command | Description |
|---------|-------------|
| [`set api-key`](keys.md#set-api-key) | Set your API key |
| [`show api-keys`](keys.md#show-api-keys) | List API keys |
| [`create api-key`](keys.md#create-api-key) | Create restricted API key |
| [`create ssh-key`](keys.md#create-ssh-key) | Add SSH key |
| [`show ssh-keys`](keys.md#show-ssh-keys) | List SSH keys |

## Quick Reference

```bash
# Find a GPU and launch an instance
vastai search offers --query "num_gpus >= 1 gpu_ram >= 16" --order dph_total
vastai create instance 12345 --image pytorch/pytorch:latest --disk 20

# Manage instances
vastai show instances
vastai logs 67890
vastai stop instance 67890
vastai destroy instance 67890

# File transfer
vastai copy /local/file.txt 67890:/remote/path/
vastai copy 67890:/remote/results/ /local/path/
```

## See Also

- [Full Command Reference](../commands.md) - Complete command list with help text
- [CLI Overview](../index.md) - Query syntax and global options
- [Host Commands](../host/index.md) - Commands for GPU providers
