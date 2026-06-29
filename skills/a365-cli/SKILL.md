---
name: a365-cli
description: a365 CLI operator for safe Microsoft 365 work through agent365 MCP servers. Use when the user asks to run, compose, explain, troubleshoot, or automate a365 commands for auth, Teams, Mail, Calendar, Planner, SharePoint, OneDrive, Me, Copilot, Word, Excel, Admin, Knowledge, NLWeb, WebSearch, DASearch, or Triggers.
---

# a365 CLI

A365 work is a **safe run**: orient, prove, execute only when intent is clear, then report what happened.

## Safe run

1. **Classify the request** as one branch:
   - Read: list, get, search, inspect, download, summarize.
   - Mutation: send, post, create, update, delete, reply, forward, share, RSVP, admin change.
   - Setup/debug: auth, config, help, verbose logs, API explorer.
   Completion: you know whether the command can change live Microsoft 365 data.
2. **Protect sensitive data**. Redact real emails, user IDs, team IDs, tenant IDs, message IDs, tokens, and file IDs in examples or summaries unless exact values are necessary for the task.
   Completion: shared text uses placeholders such as `alice@contoso.com`, `00000000-0000-0000-0000-000000000000`, or `19:example@thread.v2`.
3. **Discover syntax before guessing**. Run command help for the relevant branch:
   ```bash
   a365 --help
   a365 <service> --help
   a365 <service> <subcommand> --help
   ```
   Completion: required positional args and useful flags are known.
4. **Check auth when needed**. For first use or access errors:
   ```bash
   a365 auth status
   a365 auth login
   ```
   Completion: auth is valid, or the user has the exact next login step.
5. **Prove before mutation**. For any mutation, run `--dry-run` first unless the user explicitly forbids previewing.
   Completion: the user has seen the intended action and validation result.
6. **Execute intentionally**. Remove `--dry-run` only when the user has explicitly asked for the live change. Use `--force` only if they explicitly want to skip prompts.
   Completion: the live command matches the previewed action.
7. **Report succinctly**. State command outcome, important IDs or next steps, and any caveats. Do not dump verbose logs unless troubleshooting.
   Completion: the user can tell what changed or what to run next.

## Command patterns

Use `./a365` instead of `a365` when working from a local checkout and PATH may be stale.

### Auth and config

```bash
a365 auth login
a365 auth status
a365 auth token
a365 auth logout
a365 config set output json
a365 config show
```

Use `--tenant-id` / `A365_TENANT_ID` only when the user needs a specific tenant. Use `--client-id` / `A365_CLIENT_ID` only when their organization requires a custom Entra app registration.

### Read-only examples

```bash
a365 teams list
a365 teams chats list -o json
a365 mail search '?$top=10' -o table
a365 calendar list -o json
a365 sharepoint sites search "project" -o json
a365 me profile
```

Prefer read-only commands before mutation when IDs or context are missing.

### Mutation examples

Always preview first:

```bash
a365 teams chats send "19:example@thread.v2" "Hello" --dry-run
a365 mail draft alice@contoso.com "Subject" "Body" --dry-run -o json
a365 calendar delete 00000000-0000-0000-0000-000000000000 --dry-run
```

Then execute only after explicit live approval:

```bash
a365 teams chats send "19:example@thread.v2" "Hello"
```

### Output formats

```bash
a365 teams list                  # human table
a365 teams list -o json          # structured output for agents/scripts
a365 mail search '?$top=3' -o tsv # shell pipelines
a365 calendar list --output json
```

## Troubleshooting

- Syntax unclear: run the nearest `--help` command.
- Auth failure: run `a365 auth status`, then `a365 auth login`.
- Hard-to-read output: retry with `-o json`.
- Gateway/MCP flake: retry once, then add `-v` for request/response details.
- Raw MCP discovery/debugging: use `a365 api servers --probe`, `a365 api tools <service>`, or `a365 api call <service> <tool> '<json>'`.
