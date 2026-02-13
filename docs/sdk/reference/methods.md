# SDK Method Reference

Complete mapping of SDK methods to CLI commands. Click CLI commands to see full documentation.

## Search Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `search_offers()` | [`search offers`](../../cli/commands.md#search-offers) | Search available GPU offers |
| `search_templates()` | [`search templates`](../../cli/commands.md#search-templates) | Search templates |
| `search_volumes()` | [`search volumes`](../../cli/commands.md#search-volumes) | Search volume offers |
| `search_network_volumes()` | [`search network-volumes`](../../cli/commands.md#search-network-volumes) | Search network volumes |
| `search_benchmarks()` | [`search benchmarks`](../../cli/commands.md#search-benchmarks) | Search benchmarks |
| `search_invoices()` | [`search invoices`](../../cli/commands.md#search-invoices) | Search invoices |

## Instance Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_instances()` | [`show instances`](../../cli/commands.md#show-instances) | List all instances |
| `show_instance(id)` | [`show instance`](../../cli/commands.md#show-instance) | Get instance details |
| `create_instance(id, image, ...)` | [`create instance`](../../cli/commands.md#create-instance) | Create instance |
| `launch_instance(...)` | [`launch instance`](../../cli/commands.md#launch-instance) | Search and launch in one |
| `destroy_instance(id)` | [`destroy instance`](../../cli/commands.md#destroy-instance) | Delete instance |
| `destroy_instances(ids)` | [`destroy instances`](../../cli/commands.md#destroy-instances) | Delete multiple |
| `start_instance(id)` | [`start instance`](../../cli/commands.md#start-instance) | Start stopped instance |
| `start_instances(ids)` | [`start instances`](../../cli/commands.md#start-instances) | Start multiple |
| `stop_instance(id)` | [`stop instance`](../../cli/commands.md#stop-instance) | Stop running instance |
| `stop_instances(ids)` | [`stop instances`](../../cli/commands.md#stop-instances) | Stop multiple |
| `reboot_instance(id)` | [`reboot instance`](../../cli/commands.md#reboot-instance) | Reboot instance |
| `recycle_instance(id)` | [`recycle instance`](../../cli/commands.md#recycle-instance) | Destroy and recreate |
| `label_instance(id, label)` | [`label instance`](../../cli/commands.md#label-instance) | Set instance label |
| `update_instance(id, ...)` | [`update instance`](../../cli/commands.md#update-instance) | Update from template |
| `prepay_instance(id, amount)` | [`prepay instance`](../../cli/commands.md#prepay-instance) | Add reserved credits |
| `logs(id, ...)` | [`logs`](../../cli/commands.md#logs) | Get instance logs |
| `execute(id, command)` | [`execute`](../../cli/commands.md#execute) | Run command on instance |

## Volume Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_volumes()` | [`show volumes`](../../cli/commands.md#show-volumes) | List volumes |
| `create_volume(...)` | [`create volume`](../../cli/commands.md#create-volume) | Create volume |
| `delete_volume(id)` | [`delete volume`](../../cli/commands.md#delete-volume) | Delete volume |
| `clone_volume(id)` | [`clone volume`](../../cli/commands.md#clone-volume) | Clone volume |
| `create_network_volume(...)` | [`create network-volume`](../../cli/commands.md#create-network-volume) | Create network volume |

## SSH & File Transfer Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `ssh_url(id)` | [`ssh-url`](../../cli/commands.md#ssh-url) | Get SSH URL |
| `scp_url(id, path)` | [`scp-url`](../../cli/commands.md#scp-url) | Get SCP URL |
| `copy(src, dst)` | [`copy`](../../cli/commands.md#copy) | Copy files |
| `cloud_copy(src, dst)` | [`cloud copy`](../../cli/commands.md#cloud-copy) | Cloud provider copy |
| `cancel_copy(dst_id)` | [`cancel copy`](../../cli/commands.md#cancel-copy) | Cancel copy |
| `attach_ssh(instance_id, key_id)` | [`attach ssh`](../../cli/commands.md#attach-ssh) | Attach SSH key |
| `detach_ssh(instance_id, key_id)` | [`detach ssh`](../../cli/commands.md#detach-ssh) | Detach SSH key |

## Billing Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_user()` | [`show user`](../../cli/commands.md#show-user) | Get account info |
| `show_invoices()` | [`show invoices`](../../cli/commands.md#show-invoices) | List invoices (deprecated) |
| `show_invoices_v1(...)` | [`show invoices-v1`](../../cli/commands.md#show-invoices-v1) | List invoices/charges |
| `transfer_credit(amount, recipient)` | [`transfer credit`](../../cli/commands.md#transfer-credit) | Transfer credits |
| `show_deposit(id)` | [`show deposit`](../../cli/commands.md#show-deposit) | Show reserve deposit |
| `show_audit_logs()` | [`show audit-logs`](../../cli/commands.md#show-audit-logs) | Show audit history |
| `show_ipaddrs()` | [`show ipaddrs`](../../cli/commands.md#show-ipaddrs) | Show IP history |

## Team Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `create_team(name)` | [`create team`](../../cli/commands.md#create-team) | Create team |
| `destroy_team()` | [`destroy team`](../../cli/commands.md#destroy-team) | Delete team |
| `invite_member(email)` | [`invite member`](../../cli/commands.md#invite-member) | Invite member |
| `remove_member(id)` | [`remove member`](../../cli/commands.md#remove-member) | Remove member |
| `show_members()` | [`show members`](../../cli/commands.md#show-members) | List members |
| `create_team_role(name)` | [`create team-role`](../../cli/commands.md#create-team-role) | Create role |
| `show_team_roles()` | [`show team-roles`](../../cli/commands.md#show-team-roles) | List roles |
| `show_team_role(id)` | [`show team-role`](../../cli/commands.md#show-team-role) | Show role |
| `update_team_role(id, ...)` | [`update team-role`](../../cli/commands.md#update-team-role) | Update role |
| `remove_team_role(id)` | [`remove team-role`](../../cli/commands.md#remove-team-role) | Remove role |

## Autoscaling / Worker Group Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_workergroups()` | [`show workergroups`](../../cli/commands.md#show-workergroups) | List worker groups |
| `create_workergroup(...)` | [`create workergroup`](../../cli/commands.md#create-workergroup) | Create worker group |
| `delete_workergroup(id)` | [`delete workergroup`](../../cli/commands.md#delete-workergroup) | Delete worker group |
| `update_workergroup(id, ...)` | [`update workergroup`](../../cli/commands.md#update-workergroup) | Update worker group |
| `show_autoscalers()` | [`show workergroups`](../../cli/commands.md#show-workergroups) | Alias for workergroups |
| `create_autoscaler(...)` | [`create workergroup`](../../cli/commands.md#create-workergroup) | Alias |
| `delete_autoscaler(id)` | [`delete workergroup`](../../cli/commands.md#delete-workergroup) | Alias |
| `update_autoscaler(id, ...)` | [`update workergroup`](../../cli/commands.md#update-workergroup) | Alias |
| `get_wrkgrp_logs(id)` | [`get wrkgrp-logs`](../../cli/commands.md#get-wrkgrp-logs) | Get worker group logs |

## Endpoint Methods (Serverless)

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_endpoints()` | [`show endpoints`](../../cli/commands.md#show-endpoints) | List endpoints |
| `create_endpoint(...)` | [`create endpoint`](../../cli/commands.md#create-endpoint) | Create endpoint |
| `delete_endpoint(id)` | [`delete endpoint`](../../cli/commands.md#delete-endpoint) | Delete endpoint |
| `update_endpoint(id, ...)` | [`update endpoint`](../../cli/commands.md#update-endpoint) | Update endpoint |
| `get_endpt_logs(id)` | [`get endpt-logs`](../../cli/commands.md#get-endpt-logs) | Get endpoint logs |

## API Key Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_api_keys()` | [`show api-keys`](../../cli/commands.md#show-api-keys) | List API keys |
| `show_api_key(id)` | [`show api-key`](../../cli/commands.md#show-api-key) | Show key details |
| `create_api_key(name, ...)` | [`create api-key`](../../cli/commands.md#create-api-key) | Create API key |
| `delete_api_key(id)` | [`delete api-key`](../../cli/commands.md#delete-api-key) | Delete API key |
| `reset_api_key()` | [`reset api-key`](../../cli/commands.md#reset-api-key) | Reset primary key |
| `set_api_key(key)` | [`set api-key`](../../cli/commands.md#set-api-key) | Store API key |

## SSH Key Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_ssh_keys()` | [`show ssh-keys`](../../cli/commands.md#show-ssh-keys) | List SSH keys |
| `create_ssh_key(name, key)` | [`create ssh-key`](../../cli/commands.md#create-ssh-key) | Add SSH key |
| `delete_ssh_key(id)` | [`delete ssh-key`](../../cli/commands.md#delete-ssh-key) | Delete SSH key |
| `update_ssh_key(id, ...)` | [`update ssh-key`](../../cli/commands.md#update-ssh-key) | Update SSH key |

## Environment Variable Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_env_vars()` | [`show env-vars`](../../cli/commands.md#show-env-vars) | List env vars |
| `create_env_var(key, value)` | [`create env-var`](../../cli/commands.md#create-env-var) | Create env var |
| `update_env_var(key, value)` | [`update env-var`](../../cli/commands.md#update-env-var) | Update env var |
| `delete_env_var(key)` | [`delete env-var`](../../cli/commands.md#delete-env-var) | Delete env var |

## Template Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `create_template(...)` | [`create template`](../../cli/commands.md#create-template) | Create template |
| `delete_template(id)` | [`delete template`](../../cli/commands.md#delete-template) | Delete template |
| `update_template(id, ...)` | [`update template`](../../cli/commands.md#update-template) | Update template |

## Subaccount Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `create_subaccount(...)` | [`create subaccount`](../../cli/commands.md#create-subaccount) | Create subaccount |
| `show_subaccounts()` | [`show subaccounts`](../../cli/commands.md#show-subaccounts) | List subaccounts |

## Scheduled Job Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_scheduled_jobs()` | [`show scheduled-jobs`](../../cli/commands.md#show-scheduled-jobs) | List scheduled jobs |
| `delete_scheduled_job(id)` | [`delete scheduled-job`](../../cli/commands.md#delete-scheduled-job) | Delete scheduled job |

## Snapshot Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `take_snapshot(...)` | [`take snapshot`](../../cli/commands.md#take-snapshot) | Schedule container snapshot |

## Connection Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_connections(id)` | [`show connections`](../../cli/commands.md#show-connections) | Show peer connections |

## Two-Factor Authentication Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `tfa_status()` | [`tfa status`](../../cli/commands.md#tfa-status) | Show 2FA status |
| `tfa_totp_setup()` | [`tfa totp-setup`](../../cli/commands.md#tfa-totp-setup) | Set up TOTP authenticator |
| `tfa_send_sms()` | [`tfa send-sms`](../../cli/commands.md#tfa-send-sms) | Request SMS code |
| `tfa_activate(...)` | [`tfa activate`](../../cli/commands.md#tfa-activate) | Activate 2FA method |
| `tfa_login(...)` | [`tfa login`](../../cli/commands.md#tfa-login) | Complete 2FA login |
| `tfa_delete(...)` | [`tfa delete`](../../cli/commands.md#tfa-delete) | Remove 2FA method |
| `tfa_update(...)` | [`tfa update`](../../cli/commands.md#tfa-update) | Update 2FA settings |
| `tfa_regen_codes(...)` | [`tfa regen-codes`](../../cli/commands.md#tfa-regen-codes) | Regenerate backup codes |
| `tfa_resend_sms(...)` | [`tfa resend-sms`](../../cli/commands.md#tfa-resend-sms) | Resend SMS code |

## Host Methods

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `show_machines()` | [`show machines`](../../cli/commands.md#show-machines) | List hosted machines |
| `show_machine(id)` | [`show machine`](../../cli/commands.md#show-machine) | Show machine details |
| `list_machine(id)` | [`list machine`](../../cli/commands.md#list-machine) | List for rent |
| `unlist_machine(id)` | [`unlist machine`](../../cli/commands.md#unlist-machine) | Remove from market |
| `delete_machine(id)` | [`delete machine`](../../cli/commands.md#delete-machine) | Delete machine |
| `set_min_bid(id, price)` | [`set min-bid`](../../cli/commands.md#set-min-bid) | Set min price |
| `self_test_machine(id)` | [`self-test machine`](../../cli/commands.md#self-test-machine) | Run diagnostics |
| `show_earnings(...)` | [`show earnings`](../../cli/commands.md#show-earnings) | Show earnings |
| `reports(id)` | [`reports`](../../cli/commands.md#reports) | Get machine reports |
| `schedule_maint(id, ...)` | [`schedule maint`](../../cli/commands.md#schedule-maint) | Schedule maintenance |
| `cancel_maint(id)` | [`cancel maint`](../../cli/commands.md#cancel-maint) | Cancel maintenance |
| `show_maints()` | [`show maints`](../../cli/commands.md#show-maints) | Show maintenance |
| `cleanup_machine(id)` | [`cleanup machine`](../../cli/commands.md#cleanup-machine) | Clean expired storage |
| `defrag_machines()` | [`defrag machines`](../../cli/commands.md#defrag-machines) | Defragment storage |

## Cluster Methods (Beta)

| SDK Method | CLI Command | Description |
|------------|-------------|-------------|
| `create_cluster(...)` | [`create cluster`](../../cli/commands.md#create-cluster) | Create cluster |
| `delete_cluster(id)` | [`delete cluster`](../../cli/commands.md#delete-cluster) | Delete cluster |
| `join_cluster(id, machines)` | [`join cluster`](../../cli/commands.md#join-cluster) | Join machines |
| `show_clusters()` | [`show clusters`](../../cli/commands.md#show-clusters) | List clusters |
| `remove_machine_from_cluster(...)` | [`remove-machine-from-cluster`](../../cli/commands.md#remove-machine-from-cluster) | Remove from cluster |
| `create_overlay(...)` | [`create overlay`](../../cli/commands.md#create-overlay) | Create overlay network |
| `delete_overlay(id)` | [`delete overlay`](../../cli/commands.md#delete-overlay) | Delete overlay |
| `show_overlays()` | [`show overlays`](../../cli/commands.md#show-overlays) | List overlays |
| `join_overlay(...)` | [`join overlay`](../../cli/commands.md#join-overlay) | Join overlay |
| `add_network_disk(...)` | [`add network-disk`](../../cli/commands.md#add-network-disk) | Add network disk |
| `show_network_disks()` | [`show network-disks`](../../cli/commands.md#show-network-disks) | List network disks |

---

## See Also

- [VastAI Class Reference](vastai.md) - Constructor and patterns
- [Quick Start Guide](../quickstart.md) - Working examples
- [CLI Command Reference](../../cli/commands.md) - Full CLI documentation
