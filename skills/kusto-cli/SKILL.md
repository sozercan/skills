---
name: kusto-cli
description: kusto-cli operator for safe Azure Data Explorer/Kusto terminal work, including auth, config, KQL, schema discovery, output formats, dry runs, and stdio service mode. Use when the user asks to run, compose, explain, troubleshoot, or automate kusto-cli commands, KQL queries, management commands, table/database exploration, query plans, deeplinks, diagnostics, or API tool calls.
---

# kusto-cli

Kusto work is a **safe query loop**: target the cluster, inspect schema, run the smallest read, then broaden only when safe.

## Safe query loop

1. **Classify the request**:
   - Read query: KQL such as `StormEvents | count`.
   - Metadata: databases, tables, entity schema, samples, diagnostics, query plan, deeplink.
   - Write-capable: inline ingestion or management commands that are not safe `.show` commands.
   - Setup/debug: auth, config, output, stdio service, API explorer.
   Completion: you know whether the command reads data, exposes metadata, or mutates Kusto state.
2. **Protect sensitive data**. Redact private cluster URIs, database/table names, tenant IDs, tokens, customer data, incident data, and result rows unless exact values are required. Use `https://help.kusto.windows.net`, `Samples`, and `StormEvents` in examples.
3. **Put global flags before the command**. `-o`, `--service-uri`, `--database`, `--dry-run`, and `--allow-write` belong before `query`, `command`, `api`, etc. Completion: flags are parseable.
4. **Set the target explicitly**:
   ```bash
   kusto-cli --service-uri https://help.kusto.windows.net --database Samples query 'StormEvents | count'
   kusto-cli config set service-uri https://help.kusto.windows.net
   kusto-cli config set database Samples
   ```
   Completion: cluster and database are known.
5. **Check auth when needed**: run `kusto-cli auth status`. Completion: auth works, or the user knows to provide `KUSTO_ACCESS_TOKEN` or complete `az login` outside the agent run.
6. **Inspect before querying**:
   ```bash
   kusto-cli -o table tables list
   kusto-cli -o table tables describe StormEvents
   kusto-cli -o table tables sample StormEvents 5
   ```
   Completion: query references valid entities and columns.
7. **Run bounded reads first**. Use `take`, `count`, time filters, projections, or `queryplan` before broad scans.
8. **Prove before writes**. Use `--dry-run` first, then `--allow-write` only after explicit live approval.
9. **Report succinctly**. State command, result shape, key finding, and next step. Do not dump tokens, debug logs, or large result sets.

## Command patterns

Use `./bin/kusto-cli` from a local checkout if PATH may be stale.

### Auth and config
```bash
kusto-cli auth status
kusto-cli auth token                  # secret: do not paste token output
kusto-cli --auth env auth status      # token from KUSTO_ACCESS_TOKEN
kusto-cli --auth azcli auth status    # after az login
kusto-cli config show
kusto-cli config set output json
```

With `--auth auto`, token resolution tries the configured token env var, then Azure CLI.

### Read and metadata
```bash
kusto-cli --service-uri https://help.kusto.windows.net --database Samples query 'StormEvents | count'
kusto-cli -o table databases list
kusto-cli -o table tables list
kusto-cli -o table tables describe StormEvents
kusto-cli -o table tables sample StormEvents 5
kusto-cli queryplan 'StormEvents | summarize count() by State'
kusto-cli deeplink 'StormEvents | take 10'
kusto-cli -o json diagnostics
```

### Management and writes
Safe `.show` management command:
```bash
kusto-cli -o table command '.show tables'
```

Write-capable command or inline ingestion:
```bash
kusto-cli --dry-run command '.drop table ExampleTable'
kusto-cli --allow-write command '.drop table ExampleTable'
kusto-cli --dry-run api call kusto_ingest_inline_into_table '{"cluster_uri":"https://help.kusto.windows.net","database":"Samples","table_name":"ExampleTable","data_comma_separator":"a,b"}'
```

### Output and API explorer
```bash
kusto-cli -o json query 'StormEvents | take 5'   # agents/scripts
kusto-cli -o table query 'StormEvents | take 5'  # human review
kusto-cli -o tsv query 'StormEvents | take 5'    # shell pipelines
kusto-cli api tools && kusto-cli api schema kusto_query
```

Use high-level commands first; use `api call` only when a high-level command does not exist or schema details are needed.

## Troubleshooting

- Command unclear: run `kusto-cli help`, `kusto-cli --help`, or an incomplete command to get usage. No target cluster: pass `--service-uri` or configure `service-uri`.
- Auth failure: check `KUSTO_ACCESS_TOKEN`, `--token-env`, `--auth`, and `az login` state.
- Output hard to parse: retry with `-o json` before the command.
- Query error: verify database, entity names, and KQL syntax; run `tables describe` before retrying.
- Slow/risky query: run `queryplan`, add time filters, project fewer columns, or sample first.
- Agent service mode: `kusto-cli --service-uri <cluster> --database <db> serve`.
