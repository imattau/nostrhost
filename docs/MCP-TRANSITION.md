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
| `server_info`, `validate_server`, `health_check` | `system.status` / `system.version` | ✅ `system.status` |
| `system_snapshot`, `network_snapshot` | `system.status` / `network.public_ip` | ✅ |
| `apps_list`, `app_info`, `app_resources` | `app.list` | ✅ |
| `app_install` | `app.install` | ✅ |
| `app_upgrade`, `plan_app_upgrade`, `execute_plan`, `safe_upgrade` | `app.upgrade` | ✅ |
| `app_remove` | `app.remove` | ✅ |
| `app_change_url` | `app.change_url` | ✅ |
| `app_config_get` / `app_config_set` | `app.config.read` / `app.config.set` | ✅ |
| `updates_check`, `updates_refresh` | `updates.check` / `updates.refresh` | ⛔ pending |
| `migrations_list`, `migrations_state` | `system.migrations` (read) | ⛔ pending |
| `migrations_run` | `system.migrate` | ⛔ pending |
| `services_list`, `service_status`, `service_logs` | `service.status` | ✅ |
| `service_restart` | `service.restart` | ✅ |
| `service_history` | `service.history` | ⛔ pending |
| `journal_query`, `web_logs` | `logs.read` / `logs.web` | ⛔ pending |
| `diagnosis_run`, `diagnosis_get`, `diagnose_app` | `diagnosis.run` | ✅ |
| `ssh_diagnose`, `http_probe`, `incident_snapshot` | `diagnosis.run` (composites) | ◑ compose |
| `backups_list`, `backup_create` | `backup.list` / `backup.create` | ✅ |
| `backup_restore` | `backup.restore` | ✅ |
| `backups.delete` (scope) | `backup.delete` | ⛔ pending |
| `domains_list`, `domain_add` | `domain.list` / `domain.add` | ✅ |
| `domain_cert_info`, `domain_cert_install` | `domain.cert.info` / `domain.cert.install` | ⛔ pending |
| `firewall_is_open`, `firewall_list` | `firewall.list` / `firewall.status` | ✅ `firewall.list` |
| `firewall_open`, `firewall_close`, `firewall_reload` | `firewall.open` / `firewall.close` / `firewall.reload` | ✅ |
| `users_list`, `user_create`, `user_update`, `user_delete` | `user.list` / `user.create` / `user.update` / `user.delete` | ✅ (user.update ⛔) |
| `user_group_*`, `user_permission_*` | `user.group.*` / `user.permission.*` | ⛔ pending |
| `package_inspect`, `package_lint`, `package_logs` | `package.plan` / `package.inspect` | ✅/◑ |
| `package_install_test` … `test_package` | `package.plan` + `package.reconcile` (Resource Engine) | ✅ |
| `catalog_list` | `catalog.list` | ⛔ pending |
| `catalog_publish_plan`, `catalog_verify`, `catalog_publish` | `catalog.publish` / `catalog.verify` | ⛔ pending |
| `audit_list`, `audit_get` | `audit.list` / `audit.get` | ⛔ pending |
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
bound to the owner. Client npub rides as the `actor` tag. No separate "MCP
user" class: agents are native capabilities, granted with
`nostrhost capability grant <npub> <scopes>` (kind 31100) or
`nostrhost capability delegate <npub> <scopes> --expires-at` (kind 27236),
and `nostr-operationsd` authorizes their requests exactly like any other
identity. No migration tool is built — the only identity.toml in the tree is
the frozen reference's example file and no legacy deployment exists, so there
is nothing to translate.

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

**Phase 0 (registry hardening + full native surface) is complete as of the
first commit**: the registry carries input schemas + risk/reversibility
(`operation_catalog()`), scopes are aligned to the shared policy enum, the
broadened native surface is registered (18 new ops) and policy-gated.

**Phase 1 (`nostrhost-mcp` skeleton) is complete**: the adapter repo
(`libs/nostrhost-mcp`, imattau/nostrhost-mcp) is scaffolded — a thin MCP
server over the installed fork (mcp SDK v2) whose tools are generated from
`operation_catalog()`; read ops stream to the terminal 2204, write ops return
`approval_required` + `operation_id` (with an `op_status` helper to poll),
streamable HTTP verifies NIP-98 per request (loopback only, `/mcp`), and a
deploy unit runs it unprivileged. VM-proven on clean6: 44 tools, read op to
result, write op approval_required → control-plane approval → `op_status`
SUCCEEDED; HTTP valid NIP-98 → 200, missing/garbage → 401.

**Phase 2 (native identity + capabilities) is complete**: the HTTP transport
verifies the client's NIP-98 and the client npub rides as the operation
`actor`; agents are native 31100/27236 capabilities with no separate MCP user
class, and the migration tool from the original plan was dropped — there is no
legacy identity.toml to translate (only the frozen reference's example file).
The daemon now authorizes the **actor** (defaults to the requester) for the
tool scope, so the MCP client's grants — not the server's signing key —
decide what it may do. VM-proven on clean6: a fresh client key is rejected
`unauthorized`, runs read ops after `nostrhost capability grant server.read`,
a write without its scope is rejected, and after granting `services.restart`
the write proceeds approval_required → control-plane approval → SUCCEEDED.
Also fixed en route: the operationsd's subscribe loop now runs
`handle_event` in a worker thread — the synchronous publish/state-snapshot
round-trips were stalling the asyncio loop on replay, so the relay timed out
the websocket (close 1011) and the daemon never got past the accumulated
event replay on restart.

| Reference capability | Native op | Status |
|---|---|---|
| host reads | `system.status` / `system.version` | ✅ |
| app lifecycle | `app.list` / `app.install` / `app.upgrade` / `app.remove` / `app.change_url` / `app.config.read/set` | ✅ |
| services | `service.status` / `service.restart` / `service.control` | ✅ |
| backup | `backup.create` / `backup.list` / `backup.restore` | ✅ |
| domains/DNS | `domain.*` / `dns.*` / `network.public_ip` | ✅ |
| package lifecycle | `package.plan` / `package.reconcile` | ✅ |
| users/groups/permissions | `user.list` / `user.create` / `user.delete` (groups/permissions ⛔) | ◑ |
| system upgrade/migrate | `system.upgrade` (migrate ⛔) | ◑ |
| firewall | `firewall.list` / `firewall.open` / `firewall.close` / `firewall.reload` | ✅ |
| diagnosis/logs | `diagnosis.run` (logs ⛔) | ◑ |
| catalog | `catalog.list` / `catalog.publish` | ⛔ |
| audit | `audit.list` / `audit.get` | ⛔ |
| approvals | NIP-46 / `op status` (control plane) | ✅ |
| identity/roles | 31100 / 27236 (control plane) | ✅ |
| client integrations | `nostrhost-mcp` setup | ◑ |
| memory (Polypack) | deferred optional | ⛔ |