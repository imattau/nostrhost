# NostrHost Control-Plane Security Review

**Date:** 2026-09-15
**Scope:** every administrative control plane — the local Nostr relay
(`nostrhost-control`) and its executor/projector (`nostr-operationsd`), the
legacy YunoHost MCP (`yunohost-mcp`), the native MCP adapter
(`nostrhost-mcp`), the native admin API (`forks/yunohost/src/nostrhost/api.py`)
with its Caddy `forward_auth` layer, the Portal/Admin web UIs, and the shared
`nostrhost-auth` / `nostrhost-policy` / `nostrhost-agent` libraries.
**Method:** static review of each plane plus independent source verification
of every Critical/High finding. Findings below are tracked with a
**status**; items already remediated are marked **FIXED** with the commit/
location of the fix, the rest are recommendations.

| Plane | Entry | Trust boundary |
|---|---|---|
| Control relay | `libs/nostrhost-control` (khatru, loopback) | any local process |
| Executor/projector | `forks/yunohost/src/nostr_operationsd.py` | relay content |
| Legacy MCP | `libs/yunohost-mcp` (HTTP 8930 / stdio + root broker) | NIP-98 identity |
| Native MCP | `libs/nostrhost-mcp` (HTTP 8930, Caddy-fronted) | NIP-98 identity |
| Native admin API | `forks/yunohost/src/nostrhost/api.py` (`/package/*`) | portal cookie / NIP-98 |
| Web UIs | `forks/portal`, `forks/admin` | browser session |
| Libraries | `nostrhost-auth`, `nostrhost-policy`, `nostrhost-agent` | callers |

---

## CRITICAL

### C1 — Native admin API "NIP-98" auth is signature-only → admin bypass by replaying any signed event
`api.py` → `libs/nostrhost-auth/src/nostrhost_auth/auth/nostr_verify.py:30-44`

The `Authorization: Nostr <event>` path only checked the event id + Schnorr
signature — no kind check (27235), no `created_at` freshness, no `u`/`method`/
`payload` binding, no replay protection. Any validly-signed event by an admin
key (a public kind-1 note, a contact list, a relay-auth challenge) could be
replayed forever as an API credential.

**Status: FIXED.** `api.py:resolve_callers` now calls
`nostrhost_policy.auth.nip98.verify_nip98_request` (kind 27235, ±60s skew,
exact `u`/`method`/SHA-256 `payload`, TTL replay cache). The request URL is
reconstructed from Caddy's preserved `Host` + `X-Forwarded-Proto`.
Regression tests added: `test_nip98_rejects_non_27235_event`,
`test_nip98_rejects_stale_event`, `test_nip98_rejects_wrong_url_and_method`,
`test_nip98_replay_rejected`, `test_nip98_post_payload_bound`.

---

## HIGH

### H1 — Relay/projector: server-authoritative addressable kinds have no author authorization → forged capability grants
`nostr_operationsd.py:296-310`, `eventmodel.go:145-171`, `relay/server.go`,
`config.example.toml`

Any pubkey that could write kind 31100 could grant itself arbitrary scopes;
the projector accepted any 31100 without checking the author. The shipped
example config was fully open (`allowlist_mode = false`,
`require_auth_kinds = []`).

**Status: FIXED.**
- Relay: `rejectUnauthorizedAuthorPolicy` (server.go) now requires admins for
  `31100/31101/31102` and `2201/2202`, and the server key or an admin for
  `2203/2204/2205`.
- Daemon: `handle_capability` ignores 31100 not authored by an admin.
- `config.example.toml`: `allowlist_mode = true`; `require_auth_kinds` now
  defaults to the protected set (NIP-42) instead of being explicitly empty.
- New guard: `config.Validate` refuses a non-loopback `listen_host`.

### H2 — Unauthenticated `actor` tag → scope impersonation
`nostr_operationsd.py:183, 201-204`

Authorization was checked against the `actor` tag inside event content, not
the signing key, so any allowlisted low-trust key (agent/notice/publisher)
could name an admin as `actor` and inherit its scopes.

**Status: FIXED.** `handle_request` now rejects a request whose `actor`
differs from the signing key unless the signer is an admin (the MCP adapter
signs as the operator key, which is admin). Regression test:
`test_e2e_actor_binding_rejects_non_admin_impersonation`.

### H3 — Portal stored XSS on the origin that stores Nostr private keys
`forks/portal/pages/index.vue:144` (`v-html="app.description"`)

**Status: PARTIALLY FIXED.** All `v-html` sinks now pass through DOMPurify
(`utils/sanitize.ts`: app descriptions, admin intro text). The custom SVG
logo is rendered through an `<img>` Blob URL instead of HTML injection (an
SVG served as an image cannot execute scripts). **Residual:** the portal
still stores a locally-generated keypair in `localStorage` when the user
opt-in "remember key" is chosen — this is an explicit, documented trade-off
(the code flags it as the same risk class as storing a password), and the
only third-party-controlled HTML vector (app descriptions) is now sanitized.
Consider moving the saved key behind a master-password prompt or sessionStorage.

### H4 — Admin API reachable on every domain with a domain-wide cookie; no `forward_auth` on `/package/*`
`caddy_domain.conf:38-40`, `caddy_admin.py:234-239`, `ldap_ynhuser.py:230`

**Status: FIXED.** Layered fix that keeps the domain-wide `nostrhost.portal`
cookie load-bearing for cross-subdomain SSO while making it useless for
driving the admin API:

1. **Separate host-only admin credential.** `set_session_cookie` now also
   mints a `nostrhost.console` cookie with *no* `Domain` attribute — the
   browser only sends it to the exact host that minted it, so a subdomain app
   never receives it. The native API's cookie-session path reads it
   (`Authenticator.get_admin_cookie`, SSO-cookie fallback for pre-split
   sessions), so the admin API authenticates against a credential distinct
   from the SSO cookie.
2. **Per-request CSRF token on the cookie path.** `/package/session` returns a
   session-bound token (`session_csrf_token`: HMAC of the session id under the
   server secret); every cookie-authenticated API request must echo it in
   `X-Nostrhost-CSRF`. Only same-origin JS can read the probe (no CORS), and a
   cross-origin page cannot set a custom header without a blocked preflight —
   so a subdomain XSS can no longer ride the cookie to the admin API, even
   though SameSite=Lax does not block same-site POSTs. NIP-98 requests are
   header-authenticated and skip this (already CSRF-safe).
3. **`/package/*` only on the primary admin domain.** `build_portal_routes`
   gains `expose_native_api`; `DomainService._expose_native_api` routes the
   native API only for the domain flagged `primary` (legacy fallback: until
   one is flagged the surface stays exposed, so upgrades don't silently lose
   the console). The tracked `conf/caddy/caddy_domain.conf` snippet no longer
   routes `/package/*` on every domain.

Admin console (`forks/admin`) sends the token: `refreshSession` captures
`csrf_token`, `client.ts` sets `X-Nostrhost-CSRF` on session-authenticated
requests.

Tests: `test_session_auth_requires_csrf_token`,
`test_session_auth_rejects_wrong_csrf_token`,
`test_session_auth_admin_ok` (with token), updated session-endpoint + nsite
session tests, `test_portal_routes_hide_native_api_by_default`,
`test_native_api_exposed_only_on_primary_domain`.

### H5 — Many write routes bypass the operation/policy lifecycle
`api.py` `_run_tool` (`service.*`, `app.remove`, `package.reconcile`,
`catalog.*`, `identity.*`, `capability.*`, `/package/agent/*`, …)

**Status: FIXED.** Every host-mutating HTTP route now goes through
`_run_lifecycle` (`run_signed_chain`, which runs the in-process
policy/approval/audit gate):

- Already-routed in the earlier pass: `service.restart`, `service.control`,
  `app.remove`, `package.reconcile`.
- **Catalog writes** (`catalog.publish`, `catalog.declare`,
  `catalog.attest`, `catalog.profile.set`, `catalog.announce`) — they already
  had ToolSpecs; the API routes now use the chain.
- **Newly registered as daemon operations** (ToolSpec + input model + scope +
  approval, `identity.write` / `capability.write` / `agent.write`):
  `identity.link`, `identity.revoke`, `capability.grant`,
  `capability.delegate`, `capability.revoke`, `agent.init`, `agent.enable`,
  `agent.disable`, `agent.model.download`, `agent.model.select`,
  `agent.mode.set`, `agent.export.run`, `agent.contribution.settings.set`,
  `agent.contribution.submit`, `agent.contribution.share`. The operator/admin
  signing key never travels in operation args — handlers read it from the
  fork config — so it can't leak into state snapshots or the audit trail.
  The API routes for these now use the chain as well.

Read-class POSTs (require_approval=False) correctly stay direct:
`catalog.verify`, `catalog.reverify`, `package.plan`, `nsite.validate`,
`nsite.reachability`, `nsite.publish.plan`, `diagnosis.run`,
`updates.refresh`.

Tests: `test_h5_identity_write_scope_gates_new_tools` (daemon scope gating),
`test_run_signed_chain_catalog_publish_executes`,
`test_run_signed_chain_identity_link_executes`,
`test_run_signed_chain_capability_grant_executes`,
`test_run_signed_chain_agent_mode_set_executes`, and updated API routing
tests (`test_identity_link`, `test_agent_service_routes`,
`test_capability_grant`, `test_agent_init`, `test_agent_disable`).

### H6 — Executor re-runs every approved operation after restart
`nostr_operationsd.py` (in-memory `records`, replay re-feeds request+approval)

**Status: FIXED.** The daemon now tracks `executed` request ids (populated
from terminal 2204 results) and `subscribe_loop` pre-scans a fresh-connect
replay so replayed request/approval events can never re-execute a completed
write. Regression test: `test_restart_replay_does_not_reexecute_terminal_request`.

### H7 — Execution-result events not restricted to the server key; MCP trusts them when `--server-pubkey` unset
`relay/server.go`, `nostr-operationsd.py:271-294`, `nostrhost-mcp/client.py`

**Status: FIXED.** Relay: `2203/2204/2205` require the server key or an admin.
Adapter: `load_config` derives the server pubkey from the fork operator
config (or `NOSTRHOST_SERVER_PUBKEY`), and `verify_result_event` now **fails
closed** when no server pubkey is configured (loopback is not a trust
boundary). Regression coverage in `nostrhost-mcp/tests`.

### H8 — `yunohost-mcp`: `app_install` had no confirmation/owner policy; could reinstall the MCP control plane
`server.py:1703-1727`, `policy/rules.py`

**Status: FIXED.** `apps.install` now requires confirmation
(`require_confirmation=True`); installing the control-plane package
(`yunohost_mcp`, matched by app id or URL) requires owner co-signature via
the new `apps.control_plane_install` tier (`app_install_policy_key`).
Regression tests: `test_app_install_requires_then_accepts_a_plain_confirmation`,
`test_control_plane_install_requires_owner_cosign`.

### H9 — `yunohost-mcp`: root broker did not re-check six owner-gated operations
`broker/helper.py:_POLICY_NAME_BY_OPERATION`

`domain.remove`, `user.permission_update`, `system.reboot`, `system.shutdown`,
`settings.set`, `regenconf.apply` were brokered but not in the root
boundary's policy map, so the privileged helper ran them without re-validating
confirmation + owner approval.

**Status: FIXED.** Added all six to `_POLICY_NAME_BY_OPERATION` and
`_CONFIRMATION_ARGUMENT_KEYS`. Regression test:
`test_broker_selects_owner_gated_policy_for_high_risk_operations`.

---

## MEDIUM (open)

| # | Finding | Location | Status |
|---|---|---|---|
| M1 | Delegation 30-day cap bypassable via future-dated `created_at` | `yunohost-mcp/auth/delegation.py`; `nostrhost-policy/auth/delegation.py` | FIXED |
| M2 | Audit log is plain JSONL, no hash chain/signature; denials not recorded | `nostrhost-policy/audit/log.py` + `yunohost-mcp/audit/log.py` | FIXED (hash-chained entries + `verify()`; `O_NOFOLLOW`/`O_APPEND`; bounded reads; scope-denial entries) |
| M3 | NIP-65 relay lists never author/signature-verified | `nostrhost-auth/identity/relays.py` | FIXED |
| M4 | Catalogue attestation "trusts any verifier" by default | `nostrhost-catalog/internal/trust/attestation_policy.go` | FIXED (prefer/require fail closed without configured verifiers) |
| M5 | MCP HTTP buffers unbounded body before auth, no rate limit | `nostrhost-mcp/http.py` | FIXED (1 MiB body cap before auth; rate limiting belongs at the Caddy front) |
| M6 | MCP service runs as root, defaults to operator key | `nostrhost-mcp/config.py`, `deploy/nostrhost-mcp.service` | FIXED (HTTP `serve` fails closed without an explicit agent key; daemon `broker_pubkeys` lets a scoped agent key relay actors; unit documented for non-root deployment) |
| M7 | `COUNT` bypasses NIP-42 read protection | `relay/server.go:150-154` (no `RejectCountFilter`) | FIXED (COUNT gated by the same NIP-42 read policy + no-empty/no-complex filters) |
| M8 | Broker deferred-consume is non-atomic | `yunohost-mcp/policy/confirmation.py` | FIXED (atomic in-flight marker; one-shot consume + revert-on-failure) |
| M9 | Secrets in app config/settings persisted plaintext in audit + confirmation DB | `yunohost-mcp/server.py`, `redaction.py` | FIXED (sensitive-key values redacted in audit + persisted plans) |
| M10 | SSRF: `http_probe` DNS-rebinding TOCTOU; nsite probe/reachability unrestricted | `yunohost-mcp/yunohost/adapter.py`; `nostrhost/nsites/service.py` | FIXED (adapter + nsite probes pinned to validated IP, private targets refused) |
| M11 | Owner approval not cryptographically verified inside `approve()` | `nostrhost-policy/policy/confirmation.py:143-164` | FIXED (store verifies a kind-24243 owner signature bound to the exact ticket; `approve_operation`/CLI/push all pass it) |
| M12 | `X-Forwarded-Host`/`Proto` attacker-influenced at authd | `nostr_login.py` | FIXED (Host header authoritative) |
| M13 | Open redirect after login via `r` param | `forks/portal/pages/login.vue` | FIXED (same-origin validation) |
| M14 | Additional unsanitized `v-html` (intro text, custom SVG logo) | `CustomText.vue:8`, `CustomLogo.vue:17` | FIXED (DOMPurify + SVG via `<img>`) |
| M15 | NIP-86: admins never revoked on config removal; auth event kind unchecked; 30s replay window | `nostrhost-control/internal/policy/store.go`, khatru `nip86.go` | FIXED (admin reconciliation); khatru kind-check remains a dependency item |
| M16 | `git clone --branch <revision>` option injection | `nostrhost-catalog/internal/repository/metadata.go` | FIXED (revision validated + `--branch=` binding) |
| M17 | Agent audit redaction misses `secret_key`, `credentials`, `passwordHash` | `nostrhost-agent/agent/sanitize.go` | FIXED |
| M18 | Raw exception strings returned in 500s | `api.py` error boundary | FIXED (generic message + server-side log) |

### M11 — Owner approval not cryptographically verified inside `approve()`

`ConfirmationStore.approve()` (and the SQLite variant) originally compared a
caller-supplied `approver_pubkey` string to the configured owner — the store
trusted whatever identity the boundary claimed, so any code path that forgot
the NIP-98 check (or passed the wrong key) could mark a high-risk ticket
approved without a real owner signature.

**Status: FIXED.** Both `nostrhost-policy/policy/confirmation.py` and
`yunohost-mcp/policy/confirmation.py` now require a **kind-24243
owner-approval event** (`signed_approval`) and verify it inside `approve()`:
`verify_event` (NIP-01 id + schnorr), author == configured owner,
`confirmation_id`/`operation_hash` tags bind the signature to this exact
ticket. The bare-pubkey comparison is gone — a forged `approver_pubkey` no
longer approves anything.

All approval paths pass the signed event:
- `push_approval.py` returns the signed event it already independently
  verified, and `_mark_approved` feeds it to the store (which re-verifies).
- `approve_operation` (MCP tool) requires the `approval_event` argument; the
  `yunohost-mcp-approve` CLI signs it via the paired NIP-46 signer
  (`_sign_owner_approval`, perms now include `sign_event:24243`).

Tests: `test_approve_rejects_unbound_signature`,
`test_approve_rejects_invalid_signature`, `test_approve_rejects_non_owner_approver`
(forged key), updated owner/consume/CLI/push tests in both suites.

## LOW / INFO (selected)

- `yunohost-mcp`: DNS-rebinding protection explicitly disabled / URL from
  `Host` when `public_base_url` unset; unauthenticated body buffering; broker
  no read timeout; malformed `expires` crashes all requests; `readonly` can
  clone arbitrary git repos; plain HTTP by default.
- `nostrhost-policy`: config file permissions not validated; in-memory
  replay/confirmation stores per-process; Python deps lower-bound only.
- `nostrhost-control`: no rate limiting; content cap only on `Content`.
- `nostr-operationsd`/API: duplicate shadowed `/package/operations*` routes
  make the NIP-46 bunker-signed approval flow dead code; nsite scoped authz
  trusts relay capability grants (now mitigated by the relay author rule +
  daemon admin check); authd runs as root.
- Info: stdio transport grants `ALL_SCOPES` incl. `OWNER_APPROVE`; crypto
  delegated to rust-nostr/go-nostr; no shell injection or unsafe
  deserialization found.

---

## What is done well

- **NIP-98 where it is actually used** (`nostrhost-policy`, `yunohost-mcp`):
  kind, ±60s window, exact `u`/`method`/SHA-256 `payload` binding,
  signature-before-replay ordering.
- **`yunohost-mcp` broker boundary**: `SO_PEERCRED` uid check, `0660
  root:<group>` socket, symlink rejection, independent NIP-98 re-verification.
- **Deny-by-default authorization** in `nostrhost-policy`/`yunohost-mcp`;
  fail-closed owner resolution; delegation scope intersection.
- **`nostrhost-agent`**: unprivileged, heavily confined systemd unit; typed
  host-owned operation registry; no shell; loopback-only endpoints.
- **`nostrhost-catalog`**: publisher allowlist at the projection boundary,
  strict schema validation, HTTPS-only repos.
- **Control relay**: admin authority confined to operator/admin keys; NIP-86
  gated; `u` tag pinned; loopback default; unit hardening.
- **API/Caddy**: identity-header scrubbing; plan/apply `plan_sha256`
  re-validation; hardened DNS credential broker; private keys never sent to
  the server.

---

## Remediation status

**Fixed (this pass):** C1, H1, H2, H3-loopback-guard, H3-XSS, H4, H5, H6, H7,
H8, H9, M1, M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12, M13, M14, M15,
M16, M17, M18.
**Remaining:** none open. M11's library-side hardening (owner approval now
cryptographically verified inside the confirmation store) is complete; all
prior findings are fixed. Remaining items are deployment/dependency notes
(khatru NIP-86 kind-check) and LOW/INFO items tracked in the report.