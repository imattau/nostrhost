# MCP diagnosis tools

The diagnosis-related tools exposed by `libs/yunohost-mcp` to MCP clients
(an LLM agent, most commonly). Two are thin wrappers around the [core
diagnosis engine](diagnosis-engine.md); the rest are new composite
evidence-gathering tools built *around* it, reading raw OS state
(`/proc`, `ps`, `ss`, `fail2ban-client`, journald) that the stock engine
doesn't expose. None of this currently has a UI equivalent — see
[`../ADMIN-FEATURE-MATRIX.md`](../ADMIN-FEATURE-MATRIX.md).

Every tool is defined in
[`../../libs/yunohost-mcp/src/yunohost_mcp/server.py`](../../libs/yunohost-mcp/src/yunohost_mcp/server.py)
and backed by
[`.../yunohost_mcp/yunohost/adapter.py`](../../libs/yunohost-mcp/src/yunohost_mcp/yunohost/adapter.py).
All responses carry a `"fake": bool` field — `true` when the server is
running against `fake_yunohost` fixtures rather than a real host, so a
client can tell canned data from live data.

## `health_check()`

**Scope:** `DIAGNOSIS_READ`

Thin wrapper: calls the engine's `diagnosis_show()` in-process (or the
`fake_yunohost` stub below) and returns it unmodified except for the
`fake` flag.

```jsonc
// call
health_check()

// response (fake_yunohost=true)
{
  "fake": true,
  "categories": [
    { "id": "ip", "status": "SUCCESS", "summary": "IPv4 and IPv6 reachable" },
    { "id": "dnsrecords", "status": "SUCCESS", "summary": "DNS records look good" },
    { "id": "services", "status": "SUCCESS", "summary": "All services running" }
  ]
}
// response (real): { "fake": false, "reports": [ ...diagnosis_show() report shape... ] }
```

## `diagnosis_get()`

**Scope:** `DIAGNOSIS_READ`

A literal alias for `health_check()`. Kept as a distinct MCP tool
"so the two MCP tools stay independently scope-checked even though they
call the same YunoHost primitive" (adapter.py comment) — there's no
behavioral difference to expect between the two today.

## `diagnosis_run(categories=None, force=False)`

**Scope:** `DIAGNOSIS_READ`

Triggers a fresh run, same semantics as `yunohost diagnosis run`. Can
take real time — network and port checks are not instant.

```jsonc
diagnosis_run(categories=["ip", "mail"], force=true)
// { "fake": false, "operation_id": "20260914-...-diagnosis_run", ...report fields... }
```

**Implementation note worth knowing before changing anything nearby:**
the engine's `diagnosis_run` is wrapped by `@is_unit_operation` (see
[diagnosis-engine.md](diagnosis-engine.md#cli--api-surface)), whose SSE
registration reads a Bottle request header. That header doesn't exist
when this is called in-process from the MCP broker — a plain in-process
call raises `RuntimeError("Request context not initialized.")` every
time. The adapter works around this by shelling out to a **separate
system-Python subprocess** with a CLI-style headless context
(`_call_via_system_python(..., interface_type="cli")`), then recovers an
`operation_id` afterward by re-reading the operation-log directory
(`_latest_operation_id()`) rather than from any in-process handle,
since the subprocess's return value doesn't carry one either.

> If `@is_unit_operation` or its SSE registration is ever refactored in
> the YunoHost fork, this is the one diagnosis MCP tool that can silently
> break without a code change here — there's no compile-time link between
> the two. Grep both together before touching `src/log.py`'s
> `is_unit_operation`.

## `system_snapshot()`

**Scope:** `SERVER_READ`

Not part of the diagnosis engine at all. Reads `/proc/uptime`,
`/proc/meminfo`, `shutil.disk_usage("/")`, the top-20 `ps` processes
sorted by CPU, and OOM-related journal entries (`journal_query`,
`kernel`/`systemd-oomd`, `err..emerg`) directly — richer and more
granular than `50-systemresources.py`'s pass/fail checks, but computed
independently of them rather than reusing that diagnoser's logic.

```jsonc
system_snapshot()
// {
//   "fake": false, "uptime_seconds": 86400.0, "boot_id": "...",
//   "load_average": [0.1, 0.1, 0.1],
//   "memory": { "total_bytes": ..., "available_bytes": ..., "free_bytes": ..., "cached_bytes": ... },
//   "swap": { "total_bytes": ..., "free_bytes": ... },
//   "disk": { "/": { "total_bytes": ..., "free_bytes": ..., "used_bytes": ... } },
//   "processes": [ { "pid": "...", "command": "...", "state": "...", "cpu_percent": "...", "memory_percent": "..." } ],
//   "oom_events": [ ... ]
// }
```

## `ssh_diagnose(since="-24h", lines=200)`

**Scope:** `DIAGNOSIS_READ`

Entirely new capability — no diagnosis-engine equivalent. Gathers
`service_status(["ssh", "fail2ban", "nftables"])`, `ss -H -lnt`
listeners, `fail2ban-client status` plus per-jail status, and
error-level journal entries for ssh/sshd/fail2ban/nftables.

```jsonc
ssh_diagnose(since="-1h", lines=50)
// {
//   "fake": false,
//   "services": { "ssh": {...}, "fail2ban": {...}, "nftables": {...} },
//   "listeners": ["LISTEN 0 128 0.0.0.0:22 ...", ...],
//   "fail2ban": { "status_command_ok": true, "jails": { "sshd": "..." }, "error": null },
//   "logs": [ ...journal entries... ]
// }
```

## `incident_snapshot(since="-24h", until=None, lines=100)`

**Scope:** `DIAGNOSIS_READ`

Composite: aggregates `system_snapshot()`, `service_history()` for
`[nginx, ssh, fail2ban, nftables, yunohost-api, yunohost_mcp]`,
`web_logs(status=500, ...)`, `journal_query(...)` across the same
service set at `err..emerg`, `ssh_diagnose()`, and `network_snapshot()`
into one incident-window report. No stock equivalent — this is the tool
meant for "something broke around time X, what do we know."

```jsonc
incident_snapshot(since="-2h")
// {
//   "fake": false,
//   "window": { "since": "-2h", "until": null },
//   "system": { ...system_snapshot()... },
//   "service_history": { ...service_history()... },
//   "web": { ...web_logs(status=500)... },
//   "journal": { ...journal_query()... },
//   "ssh": { ...ssh_diagnose()... },
//   "network": { ...network_snapshot()... }
// }
```

## `diagnose_app(app)`

**Scope:** `APPS_READ`

App-scoped triage the diagnosis engine has no mode for — it's server-wide
only. Combines `app_info(app, full=True)`, `health_check()` (the whole
server's report, not filtered to this app), and recent
`operations_list()` entries whose `name`/`description` mention the app.

```jsonc
diagnose_app("nextcloud")
// { "fake": false, "app": "nextcloud", "app_info": {...}, "diagnosis": {...}, "related_operations": [...] }
```

## `validate_server()`

**Scope:** `SERVER_READ`

Pre-flight aggregation: `server_info()` + `health_check()` +
`updates_check()` + `services_list()` + `backups_list()`, one call. New —
not a diagnosis-engine feature.

## `safe_upgrade(app, confirmation_id=None)`

**Scope:** `APPS_UPGRADE`, requires confirmation/co-signature

The flagship composite workflow: diagnosis → inspect app → fresh backup →
upgrade → post-upgrade checks → re-diagnose → one report. Its first step
is a `health_check()` call (referred to as `pre_diagnosis` in the
implementation). Disk-space and backup-recency policy checks happen
around this call in `server.py`, not inside the adapter method itself.

## What's not documented here

`diagnosis://` is also registered as an MCP **resource**
(`@mcp.resource("yunohost://diagnosis")`), returning the same payload as
`health_check()`, for clients that prefer resource reads over tool calls.

## Related

- [Diagnosis engine](diagnosis-engine.md) — what every `health_check` /
  `diagnosis_run` / `diagnosis_get` call underneath these tools actually
  does.
- [MCP integration](mcp-integration.md) — how a client connects and
  authenticates in the first place; this page assumes that's done.
