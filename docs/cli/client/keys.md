# API & SSH Key Commands

Commands for managing API keys, SSH keys, and environment variables.

## set api-key

Set the API key for CLI and SDK authentication

```bash
vastai set api-key API_KEY
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `api_key` | API key to set as currently logged in user |

**Notes:**

Stores your Vast.ai API key locally for authentication with all CLI commands.
Get your API key from the Vast.ai console: https://console.vast.ai/account/

**Examples:**

```bash
    vastai set api-key abc123def456...         # Set your API key
```

!!! tip
    Security notes:
    - API key is stored in ~/.config/vastai/vast_api_key
    - Permissions are set to user-read-only (600)
    - Do NOT share your API key or commit it to version control
    - Regenerate your key at https://console.vast.ai/account/ if compromised
    - You can also use the VAST_API_KEY environment variable instead
    The legacy location ~/.vast_api_key is automatically removed when you set a new key.

---

## show api-key

Show details for a specific API key

```bash
vastai show api-key ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of API key to show |

---

## show api-keys

List all API keys for your account

```bash
vastai show api-keys
```

---

## create api-key

Create a new API key with custom permissions

```bash
vastai create api-key --name NAME --permission_file PERMISSIONS
```

**Options:**

| Option | Description |
|--------|-------------|
| `--name NAME` | name of the api-key |
| `--permission_file PERMISSION_FILE` | file path for json encoded permissions, see https://vast.ai/docs/cli/roles-and-permissions for more information |
| `--key_params KEY_PARAMS` | optional wildcard key params for advanced keys |

**Notes:**

In order to create api keys you must understand how permissions must be sent via json format.
You can find more information about permissions here: https://vast.ai/docs/cli/roles-and-permissions

---

## delete api-key

Delete an API key

```bash
vastai delete api-key ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of apikey to remove |

---

## reset api-key

Invalidate current API key and generate a new one

```bash
vastai reset api-key
```

---

## show ssh-keys

List all SSH keys registered to your account

```bash
vastai show ssh-keys
```

---

## create ssh-key

Add an SSH public key to your account

```bash
vastai create ssh-key [ssh_public_key] [-y]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `ssh_key` | add your existing ssh public key to your account (from the .pub file). If no public key is provided, a new key pair will be generated. |

**Options:**

| Option | Description |
|--------|-------------|
| `-y, --yes` | automatically answer yes to prompts |

**Notes:**

You may use this command to add an existing public key, or create a new ssh key pair and add that public key, to your Vast account.
If you provide an ssh_public_key.pub argument, that public key will be added to your Vast account. All ssh public keys should be in OpenSSH format.

!!! tip
    If you don't provide an ssh_public_key.pub argument, a new Ed25519 key pair will be generated.
    The generated keys are saved as ~/.ssh/id_ed25519 (private) and ~/.ssh/id_ed25519.pub (public). Any existing id_ed25519 keys are backed up as .backup_<timestamp>.
    The public key will be added to your Vast account.
    All ssh public keys are stored in your Vast account and can be used to connect to instances they've been added to.

---

## delete ssh-key

Remove an SSH key from your account

```bash
vastai delete ssh-key ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id ssh key to delete |

---

## update ssh-key

Update an SSH key's label or properties

```bash
vastai update ssh-key ID SSH_KEY
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of the ssh key to update |
| `ssh_key` | new public key value |

---

## show env-vars

List environment variables set for your account

```bash
vastai show env-vars [-s]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-s, --show-values` | Show the values of environment variables |

---

## create env-var

Create a new account-level environment variable

```bash
vastai create env-var <name> <value>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Environment variable name |
| `value` | Environment variable value |

---

## update env-var

Update an existing user environment variable

```bash
vastai update env-var <name> <value>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Environment variable name to update |
| `value` | New environment variable value |

---

## delete env-var

Delete a user environment variable

```bash
vastai delete env-var <name>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `name` | Environment variable name to delete |

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
