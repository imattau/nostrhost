# NostrHost MCP Transition

> **Transition from `yunohost-mcp` being a privileged management product into
> `nostrhost-mcp` being a thin protocol adapter over NostrHost's native
> operation model.**

The goal is not "port the MCP server". It is:

> **Preserve the useful client integrations and tool surface, but move
> authority, policy, approvals, execution and state into NostrHost itself.**

The architectural rule kept throughout:

> **MCP is an interface, not an authority boundary.**

This document is the single tracking source for the transition. It contains
the frozen feature inventory of the reference implementation, the tool →
native-operation mapping, the phase plan, and the per-tool migration status
table.

---

## 1. Current state (what already exists)

NostrHost already embodies most of the target architecture. The fork's
operation registry, executor daemon, policy and signed operation chain are
native and proven. `nostrhost-mcp` completes §13 of `ROADMAP.md` and retires
the duplicated legacy integration in `yunohost-mcp`.

Already in place, not to be rebuilt:

- **Operation registry** — `forks/yunohost/src/nostr_operations.py`:
  `TOOLS: dict[str, ToolSpec]` (25 ToolSpecs: name, handler, scope,
  `require_approval`, description). Lines 442–597.
- **Executor daemon** — `src/nostr_operationsd.py`: `OperationEngine`
  subscribes to the control relay (2200–2204/31100/27236/27237), validates
  signer authority, evaluates native policy, executes, and signs terminal
  states with the server key.
- **Operation state machine** — `src/nostr_operations_state.py`:
  `REQUESTED → APPROVED → EXECUTING → SUCCEEDED|FAILED`,
  `REQUESTED → REJECTED`, auto `REQUESTED → EXECUTING`.
- **Signed operation chain** — kinds 2200 request, 2201 approval, 2202
  rejection, 2203 executing, 2204 result, 2205 progress. Correlation is the
  `["e", request-id]` tag. Authoring/publish helpers in `nostr_operations.py`
  (`build_operation_request`, `request_operation`, `approve_operation`,
  `approve_operation_nip46`, `reject_operation`, `grant_capability`,
  `delegate_capability`, `revoke_delegation`).
- **Protocol-neutral MCP adapter** — `src/nostr_mcp_adapter.py`
  (`NostrMCPAdapter`): SDK-free, submits signed kind-2200 requests,
  correlates 2201/2203/2204/2205, no root authority.
- **Result streaming** — `src/nostrhost/events.py`
  `stream_operation_events()` (REQ 2203/2205/2204 by `#e`), consumed by the
  CLI `op follow/status`, the API SSE endpoint, and `NostrMCPAdapter`.
- **Policy** — `libs/nostrhost-policy`: granular `Scope` enum, roles,
  `PolicyRule` gates (confirmation, backup recency, free space, owner
  co-signature), NIP-98 verification, delegation verification, redaction,
  audit. Fork integration: `src/nostrhost_native_policy.py`.
- **Control plane** — `libs/nostrhost-control`: khatru relay on
  `ws://127.0.0.1:4848`, event model, notify service (NIP-17/NIP-59 DMs).
- **Resource Engine** — `src/nostrhost/package_engine.py` + native providers;
  `package.plan` (read) and `package.reconcile` (write, approval-gated) are
  already ToolSpecs.
- **Client integrations** — exist in `yunohost-mcp` (claude-code, codex,
  gemini, hermes, openclaw, opencode) and are ported last (§9).

---

## 2. Frozen reference

`imattau/yunohost-mcp` is held as a **frozen reference implementation**
(added as `libs/yunohost-mcp`, pinned in `baseline/pins.yml`). It keeps
working for stock YunoHost during the migration and serves as the feature
inventory for NostrHost. **No new platform logic is added to it.**

The reference's duplicated modules are retired incrementally as native
equivalents land (see §11):

```text
policy/              -> libs/nostrhost-policy        (already extracted)
auth/                -> libs/nostrhost-policy        (already extracted)
audit/               -> libs/nostrhost-policy audit + signed chain
approve.py           -> fork approve_operation / NIP-46 (control plane)
push_approval.py     -> fork approve_operation_nip46 + nostr-opctl
broker/              -> identityd Unix socket + control relay
notify.py            -> nostrhost-notify (NIP-17/NIP-59)
bridge.py            -> retired
polypack.py          -> deferred (optional memory bridge, not host admin)
yunohost/adapter.py  -> native operation registry + explicit legacy path
```

Kept in `nostrhost-mcp`:

```text
MCP protocol
generated schema / tool exposure
client setup
redaction
result translation
transport
```

---

## 3. Decisions

1. **Adapter coupling** — `nostrhost-mcp` imports the installed fork package
   (`yunohost.nostr_operations`, `yunohost.nostr_mcp_adapter`,
   `yunohost.nostrhost.events`) exactly as the CLI and `nostr-api` do. No
   duplicated operation client; the registry is the single source of truth.
2. **Schema source** — the fork `ToolSpec` registry is extended with Pydantic
   input/result models; JSON Schemas are derived and drive MCP tool
   generation. The same registry drives CLI, API, Admin forms and MCP.
3. **Registry gap strategy** — the full native surface
   (app/backup/user/system/firewall/diagnosis) is added first, before the
   adapter is built. Un-migrated tools use an explicit legacy path until
   native.
4. **Reference holding** — `imattau/yunohost-mcp` is a pinned frozen
   submodule under `libs/`.

---

## 4. Repository changes

- **Add `libs/yunohost-mcp`** — frozen submodule, pin `1d84c25c` (master),
  plus a `baseline/pins.yml` entry (`component: yunohost-mcp`, frozen).
- **Create `imattau/nostrhost-mcp`** — new repo, Python package
  `nostrhost_mcp`, added as `libs/nostrhost-mcp` + pins.yml entry.
- **This document** is the tracking source.

---

## 5. Feature inventory and tool mapping

Source: `yunohost-mcp` live inventory snapshot (scopes/roles/policy gates)
and the ~70 tool names. Each reference tool maps to a native operation
(existing or to-be-added ToolSpec) or to the explicit legacy path.

Scope vocabulary (reference) — `server.read`, `diagnosis.read`, `apps.read`,
`apps.install`, `apps.upgrade`, `apps.remove`, `apps.config.read/write`,
`services.read`, `services.restart`, `logs.read`, `backups.read/create/
restore/delete`, `users.read/write/delete`, `domains.read/write`,
`system.update/upgrade/migrate`, `firewall.read/write`, `packages.inspect/
test`, `catalog.inspect/verify/publish`, `audit.read`, `owner.approve`,
`memory.read/write/feedback`.

Role bundles (reference, strictly hierarchical):
`readonly < operator < app-admin < package-developer < administrator`.
`system.migrate` and `firewall.write` are administrator-only.

### Mapping table

Legend: ✅ native op exists · ◑ native op planned · ⛔ legacy path (un-migrated)

| Reference tool(s) | Native operation | Status |
|---|---|---|
| `whoami`, `server_identity` | `system.status` (identity introspection) | ◑ add |
| `server_info`, `validate_server`, `health_check` | `system.status` / `system.version` | ◑ add |
| `system_snapshot`, `network_snapshot` | `system.status` / `network.public_ip` | ◑ add |
| `apps_list`, `app_info`, `app_resources` | `app.list` | ✅ |
| `app_install` | `app.install` | ◑ add |
| `app_upgrade`, `plan_app_upgrade`, `execute_plan`, `safe_upgrade` | `app.upgrade` | ◑ add |
| `app_remove` | `app.remove` | ✅ |
| `app_change_url` | `app.change_url` | ◑ add |
| `app_config_get` / `app_config_set` | `app.config.read` / `app.config.set` | ◑ add |
| `updates_check`, `updates_refresh` | `updates.check` / `updates.refresh` | ◑ add |
| `migrations_list`, `migrations_state` | `system.migrations` (read) | ◑ add |
| `migrations_run` | `system.migrate` | ◑ add |
| `services_list`, `service_status`, `service_logs` | `service.status` | ✅ |
| `service_restart` | `service.restart` | ✅ |
| `service_history` | `service.history` | ◑ add |
| `journal_query`, `web_logs` | `logs.read` / `logs.web` | ◑ add |
| `diagnosis_run`, `diagnosis_get`, `diagnose_app` | `diagnosis.run` | ◑ add |
| `ssh_diagnose`, `http_probe`, `incident_snapshot` | `diagnosis.run` (composites) | ◑ add |
| `backups_list`, `backup_create` | `backup.list` / `backup.create` | ◑ add |
| `backup_restore` | `backup.restore` | ◑ add |
| `backups.delete` (scope) | `backup.delete` | ◑ add |
| `domains_list`, `domain_add` | `domain.list` / `domain.add` | ✅ |
| `domain_cert_info`, `domain_cert_install` | `domain.cert.info` / `domain.cert.install` | ◑ add |
| `firewall_is_open`, `firewall_list` | `firewall.list` / `firewall.status` | ◑ add |
| `firewall_open`, `firewall_close`, `firewall_reload` | `firewall.open` / `firewall.close` / `firewall.reload` | ◑ add |
| `users_list`, `user_create`, `user_update`, `user_delete` | `user.list` / `user.create` / `user.update` / `user.delete` | ◑ add |
| `user_group_*`, `user_permission_*` | `user.group.*` / `user.permission.*` | ◑ add |
| `package_inspect`, `package_lint`, `package_logs` | `package.plan` / `package.inspect` | ✅/◑ |
| `package_install_test` … `test_package` | `package.plan` + `package.reconcile` (Resource Engine) | ✅ |
| `catalog_list` | `catalog.list` | ◑ add |
| `catalog_publish_plan`, `catalog_verify`, `catalog_publish` | `catalog.publish` / `catalog.verify` | ◑ add |
| `audit_list`, `audit_get` | `audit.list` / `audit.get` | ◑ add |
| `approve_operation`, `approval_get`, `approval_status` | control-plane NIP-46 / `op status` | ✅ |
| `operations_list`, `operation_status`, `operation_logs` | `op.list` / `op.status` / `op.logs` | ✅ |
| `memory_*` (Polypack) | deferred optional integration | ⛔ defer |

### Policy gates carried over

From the reference policy model (these must hold in the native policy adapter
as the corresponding ops land):

| Operation | Gate |
|---|---|
| `app.change_url`, `app.config.set`, `domain.cert.install`, `catalog.publish` | confirmation |
| `app.upgrade` / `package.reconcile` | recent backup + ≥2 GB free (hard blockers) |
| `app.remove` | confirmation + backup within 24h |
| `backup.restore`, `system.upgrade`, `system.migrate`, `firewall.*`, `user.delete`, `user.group.delete`, `user.permission.add/remove` | confirmation + different administrator identity co-signature |
| `user.create`, `user.update`, `user.group.create`, `user.group.update` | confirmation |
| `audit.read` | owner co-signature per call |

`nostrhost_policy` already models `require_confirmation`,
`require_backup`, `minimum_free_space_bytes`, `max_backup_age_seconds`,
`require_owner_signature`; the fork's `nostrhost_native_policy.py` adapter
must declare the same keys.

---

## 6. Phase 0 — Registry hardening + full native surface (fork)

Correctness and the single-source-of-truth registry before any adapter work:

1. **Vocabulary alignment** — fork ToolSpec scopes drifted to coarse
   `apps.write`/`services.write`/`state.write`/`domains.write`, but the
   policy `Scope` enum and relay `KNOWN_SCOPES` are granular. Align every
   ToolSpec to enum members so 31100 grants / 27236 delegations verify against
   the ops that consume them. (Extend the enum only where a coarse scope is
   genuinely required.)
2. **Extend `ToolSpec`** (`src/nostr_operations.py`) with `input_model`
   (Pydantic), `result_model`, `risk` (low/medium/high), `reversibility`;
   JSON Schema derived via `model_json_schema()`.
3. **Add missing ToolSpecs** with typed `_safe_*` handlers + Pydantic models:
   `app.install`, `app.upgrade`, `app.change_url`, `app.config.read/set`;
   `backup.create/list/restore`; `user.create/update/delete`,
   `user.group.*`, `user.permission.*`; `system.upgrade`, `system.migrate`;
   `firewall.open/close/list/reload`; `diagnosis.run`; `updates.check`;
   `catalog.publish`; `audit.list/get`; `logs.read`.
4. **Fix read-only gating** — `system.version`, `app.list`, `service.status`
   and all new read ops get `require_approval=False`.
5. **`operation_catalog()`** — JSON-serializable
   `{name, scope, approval, risk, reversibility, input_schema, description}`
   introspectable by the adapter; `known_tools()` reads from it.
6. **CLI/API/tests** — extend `_TOOL_HANDLERS`, CLI command groups, API
   handlers, and tests. Keep the suite green.
7. **VM-prove** the new write ops through the full 2200 chain
   (request → approval → execute → result).

---

## 7. Phases 1–8

### Phase 1 — `nostrhost-mcp` skeleton (health + read-only)
Scaffold `imattau/nostrhost-mcp` (Python, `mcp[cli]`, `nostrhost-policy`;
fork as installed package). `nostrhost-mcp serve --stdio` and
`--http 127.0.0.1:<port>` (streamable HTTP for OpenCode Web → localhost,
never public). Systemd unit as an **unprivileged** user with no host write
authority. Tools generated from `operation_catalog()`; read ops immediate;
mutations return `status: submitted, operation_id` and stream 2203/2205 as
MCP progress, 2204 as the result (via the installed fork's
`NostrMCPAdapter` + `stream_operation_events`).

### Phase 2 — native identity + capabilities
HTTP transport verifies client NIP-98 (`nostrhost_policy.auth.nip98`); stdio
bound to the owner. Client npub rides as the `actor` tag. Migration tool
`nostrhost identity import-mcp-agents`: translate old `yunohost-mcp`
identity.toml roles → 31100 capability grants / 27236 delegations for the
same agent npubs. No separate "MCP user" class.

### Phase 3 — signed mutations + streaming
Wire `service.restart/control`, `backup.create`, `dns.apply/subscribe/
unsubscribe`, `credential.set/remove`, `domain.add/remove`,
`app.install/upgrade/remove`, `package.reconcile`, `state.reconcile`,
`rollback.apply`.

### Phase 4 — approval flow (out of MCP)
Already native: 2201 by admin or NIP-46. The adapter only surfaces
`approval_required` + `operation_id` and later the final result. Push
approval stays a control-plane utility (`nostr-opctl approve` /
`approve_operation_nip46`), not part of the MCP server.

### Phase 5 — Resource Engine integration
`package.plan`/`package.reconcile` are native. Map old `package_*` test
tools → plan/reconcile + `catalog.publish`. Legacy-only tools fall to the
explicit compat path.

### Phase 6 — client integrations
Port claude-code/codex/gemini/hermes/openclaw/opencode configs to point at
`nostrhost-mcp`; rename the `yunohost-mcp-operations` skill →
`nostrhost-mcp-operations`. OpenCode Web → localhost streamable HTTP.
Package + publish (`python3-nostrhost-mcp` deb + PyPI entry in
`packaging/packages.yml`; add to the `nostrhost-core-system` meta when ready).

### Phase 7 — multi-host / fleet projection
Per-node adapter; a fleet projection maps a client to the right node's relay.
Detail deferred until Phases 1–6 are proven.

### Phase 8 — retire duplicated `yunohost-mcp` logic
With `libs/yunohost-mcp` frozen, retire the modules listed in §2 as native
equivalents land. Keep in `nostrhost-mcp`: protocol, generated schema/tool
exposure, client setup, redaction, result translation, transport.

---

## 8. Verification

- **Local**: fork tests (existing 477+), new `nostrhost-mcp` unit tests
  (schema generation, chain correlation, redaction), flake8 clean.
- **VM**: real MCP client (opencode/codex) → `nostrhost-mcp` (unprivileged)
  → submit → approve → execute → streamed result; assert the MCP process has
  no host write authority.
- **Phase 4 success criterion** (VM gate):

```text
OpenCode → nostrhost-mcp → read server status → list apps →
request app install → owner approval → install executes →
health check → result returned
```

---

## 9. Status tracking

Updated as each row lands. `Done` = native op VM-proven through the chain and
the reference tool retired from the legacy path.

| Reference capability | Native op | Status |
|---|---|---|
| host reads | `system.status` / `system.version` | ◑ |
| app lifecycle | `app.list` / `app.install` / `app.upgrade` / `app.remove` | ◑ |
| services | `service.status` / `service.restart` / `service.control` | ◑ |
| backup | `backup.create` / `backup.list` / `backup.restore` | ◑ |
| domains/DNS | `domain.*` / `dns.*` / `network.public_ip` | ✅ |
| package lifecycle | `package.plan` / `package.reconcile` | ✅ |
| users/groups/permissions | `user.*` / `user.group.*` / `user.permission.*` | ◑ |
| system upgrade/migrate | `system.upgrade` / `system.migrate` | ◑ |
| firewall | `firewall.*` | ◑ |
| diagnosis/logs | `diagnosis.run` / `logs.read` | ◑ |
| catalog | `catalog.list` / `catalog.publish` | ◑ |
| audit | `audit.list` / `audit.get` | ◑ |
| approvals | NIP-46 / `op status` (control plane) | ✅ |
| identity/roles | 31100 / 27236 (control plane) | ✅ |
| client integrations | `nostrhost-mcp` setup | ◑ |
| memory (Polypack) | deferred optional | ⛔ |