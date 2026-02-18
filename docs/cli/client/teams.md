# Team Commands

Commands for managing teams and team members.

## create team

Create a new team

```bash
vastai create-team --team_name TEAM_NAME
```

**Options:**

| Option | Description |
|--------|-------------|
| `--team_name TEAM_NAME` | name of the team |

**Notes:**

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

---

## destroy team

Delete your team and remove all members

```bash
vastai destroy team
```

---

## invite member

Invite a user to join your team

```bash
vastai invite member --email EMAIL --role ROLE
```

**Options:**

| Option | Description |
|--------|-------------|
| `--email EMAIL` | email of user to be invited |
| `--role ROLE` | role of user to be invited |

---

## remove member

Remove a team member

```bash
vastai remove member ID
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of user to remove |

---

## show members

List all members in your team

```bash
vastai show members
```

---

## create team-role

Create a custom role with specific permissions

```bash
vastai create team-role --name NAME --permissions PERMISSIONS
```

**Options:**

| Option | Description |
|--------|-------------|
| `--name NAME` | name of the role |
| `--permissions PERMISSIONS` | file path for json encoded permissions, look in the docs for more information |

**Notes:**

Creating a new team role involves understanding how permissions must be sent via json format.
You can find more information about permissions here: https://vast.ai/docs/cli/roles-and-permissions

---

## show team-roles

List all roles defined for your team

```bash
vastai show team-roles
```

---

## show team-role

Show details for a specific team role

```bash
vastai show team-role NAME
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `NAME` | name of the role |

---

## update team-role

Update an existing team role

```bash
vastai update team-role ID --name NAME --permissions PERMISSIONS
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `id` | id of the role |

**Options:**

| Option | Description |
|--------|-------------|
| `--name NAME` | name of the template |
| `--permissions PERMISSIONS` | file path for json encoded permissions, look in the docs for more information |

---

## remove team-role

Delete a custom role from your team

```bash
vastai remove team-role NAME
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `NAME` | name of the role |

---

## See Also

- [Full Command Reference](../commands.md) - Complete help text for all commands
