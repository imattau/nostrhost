# NostrHost
## Platform Roadmap

### Objective

> **NostrHost is a Debian-based self-hosting platform derived from YunoHost.
> Nostr provides its native identity, authority, control, software-trust and
> audit layers. Applications are managed through declarative resources and
> bounded execution, Caddy provides the web and TLS layer, CrowdSec provides
> intrusion detection, and ngit plus Restic provide state and data recovery.
> YunoHost compatibility is retained temporarily for existing applications
> and selected mature Linux-management functionality.**

The early framing — "a Nostr-native YunoHost derivative: keep the proven
machinery, replace the layers around it" — is now largely realised. The
replacement work is mostly done or under way (native package lifecycle,
Caddy, Caddy automatic TLS, native state + Restic, CrowdSec). The goal is
therefore **no longer "replace YunoHost"**. It is to close NostrHost's own
platform loops — native bootstrap, package migration, DNS, secrets and
release/update — so that YunoHost becomes purely a compatibility and
migration source.

NostrHost retains selected mature YunoHost Linux-management functionality:

- domains
- services
- firewall (nftables)
- diagnosis
- Debian packaging
- user/group compatibility (temporary, projected via LDAP)

The layers formerly inherited are now native:

- application installation / removal / upgrades → native package lifecycle (§21)
- Nginx configuration → Caddy (§12)
- certificates → Caddy automatic TLS (§12)
- backups → native state + Restic (§7, §9)

Nostr is the primary control-plane technology for:

- identity
- authentication
- delegated authority
- agent access
- approvals
- catalogue discovery
- publisher trust
- software attestations
- remote administration
- repository identity and state provenance (ngit / NIP-34)
- outbound publication to external relays

### Status legend

```text
✅  done and proven        ◑  partial / in progress        ⏳  pending
```

The roadmap is reconciled from two lineages: the relay-centric **control-plane**
architecture (this document, `docs/CONTROL-PLANE.md`, `docs/NIP-MAPPING.md`) and
the **state-history / recovery** extension (`docs/STATELAYER.md`, ngit / NIP-34
configuration-state with Restic data linkage). The state layer is gated: it is
authoritative only once identity, policy and execution semantics exist — those
gates are now met on the local testbed.

---

## Consolidated plan status — what is done, what is left

This document is the **single plan tracker** for the platform. All workstream
plans are consolidated here: the roadmap sections below, the MCP transition
(Phases 0–8), the alpha execution plan, the agent distribution plan and the
resource-engine cutover. The documents under `docs/` referenced throughout are
the **working specifications**; the plan, its phases and its status live here.

### Master status

| # | Workstream | Status | Remaining |
|---|---|---|---|
| §1–§6 | Fork baseline, extraction, control plane, identity, authorisation, operations | ✅ | — |
| §7 | State history + recovery (ngit/NIP-34, Stages A–D) | ◑ | Stage C (ngit replication/DR, §15), Stage D tail (reconcile auto-apply hardening) |
| §8 | Portal Nostr authentication | ✓ | real-browser passkey attestation + visual app-grid pass (headless limit only) |
| §9 | Restic linkage + assisted rollback (Stage B) | ✅ | reverse steps for app reinstall/upgrade stay manual pending install-arg provenance |
| §10 | Admin interface (native management views) | ⏳ | identities/agents/delegations/approvals/catalogue/trust/audit views |
| §11 | Native Nostr catalogue | ✓ | `catalog.list/get/publish/verify` native ops landed (MCP Phase 5); Admin catalogue UI ⏳ |
| §12 | Web-layer auth (Caddy `forward_auth`, SSOwat retired) | ✓ | P7 residual-reference cleanup (§20) |
| §13 | MCP adapter | ✅ | MCP transition Phases 5–8 (below) |
| §14 | OIDC compatibility | ◑ | client management + signing-key rotation (bridge live/VM-proven) |
| §15 | ngit replication / DR (Stage C) | ◑ | repository/object replication to external relays |
| §16 | Declarative reconciliation (Stage D) | ✓ | — |
| §17 | Distribution + release tooling / native self-update | ⏳ | Debian repo, installer image, signed self-update |
| §18 | Platform simplification (messaging, mail, security) | ◑ | mail identity/UI cleanup; security-state digest cadence (§18.6) |
| §19 | Native bootstrap / postinstall | ◑ | five-key bootstrap + recovery bundle + `--restore` CLI landed (POSTINSTALL-KEYS); blank-VM acceptance loop + legacy postinstall bypass ⏳ |
| §20 | Web cutover completion (Caddy P7) | ⏳ | Caddy storage in backup, cert state in ngit, residual nginx helpers/migrations |
| §21 | End-to-end native app lifecycle | ◑ | `package.plan`/`reconcile` proven on nostrhost-test; the §21 vertical loop on one **real** app ⏳ |
| §22 | YNH package migration analyser | ⏳ | manifest + Bash-AST analyser, deterministic migration, AI repair loop |
| §23 | Behavioural equivalence testing | ⏳ | VM A/B comparison + confidence attestation |
| §24 | Native vs compatibility boundary | ⏳ | measurable shrink (122→87→41→0 helpers) |
| §25 | LDAP dependency inventory / reduction | ⏳ | later phase (alpha) |
| §26 | Native DNS management | ⏳ | later phase (alpha) |
| §27 | Secrets / key lifecycle | ◑ | node-key inventory + safe keeping landed (POSTINSTALL-KEYS); rotation + Restic/DB/external/DNS/Caddy/agent secret classes remain |
| MCP 0–4 | MCP transition: registry, skeleton, identity, signed mutations, approval flow | ✅ | — |
| MCP 5 | Resource Engine integration (catalog surface) | ✓ | `catalog.list/get/publish/verify` + the full backlog landed (updates/migrations/service.history/logs/backup.delete/domain.cert/users/groups/permissions/audit) — 69 ops; legacy `package_*` mapping + compat path dropped by direction |
| MCP 6 | Client integrations + packaging | ⏳ | port claude-code/codex/gemini/hermes/openclaw/opencode configs, skill rename, deb + PyPI |
| MCP 7 | Multi-host / fleet projection | ⏳ | deferred until MCP 1–6 proven |
| MCP 8 | Retire duplicated `yunohost-mcp` logic | ⏳ | gated on MCP 5–6 |
| Alpha W0 | Documentation truth | ✅ | — |
| Alpha W1 | `nostrhost-runtime` deb (private venv, bundled wheels) | ✅ | in `packaging/packages.yml`; verify clean-VM install |
| Alpha W2 | Native bootstrap / postinstall | ◑ | five-key bootstrap + recovery bundle landed (POSTINSTALL-KEYS); blank-VM acceptance loop + legacy postinstall bypass |
| Alpha W3 | End-to-end native app lifecycle | ⏳ | `app install <coordinate>` CLI + native backup/restore + real-app proof |
| Agent 1–2 | Agent daemon packaging (optional APT, disabled by default) | ⏳ | systemd unit, first-run, secret handoff, VM acceptance |
| Agent 3–4 | Model artifacts on Hugging Face + evaluation Space | ⏳ | blocked on a candidate passing the training-regime gates |
| Cutover 1–6 | Resource engine cutover / plane integration | ◑ | step 3 tail (Restic snapshot into native plan result); steps 4–6 (Admin/catalog wiring, package migration) |
| Notify | Native notification service (§18.1) | ✅ | — |
| Mail | Mail-stack retirement | ◑ | §18.7/18.8 identity + UI consequences |
| CrowdSec | Intrusion protection migration | ✅ | — |
| Caddy | Web/TLS migration (P0–P6) | ✅ | P7 (§20) |

### The focused remaining work

The near-term path to a shippable 0.1 alpha is the **alpha plan** (docs truth →
runtime deb → native bootstrap → end-to-end native app lifecycle), then the
**MCP transition tail** (catalog surface, client integrations), then the
**platform-close** items (§19–§27) that turn YunoHost into a pure
compatibility/migration source:

```text
1.  Alpha W2  native postinstall --new / --restore          (§19)
2.  Alpha W3  end-to-end native app lifecycle               (§21)
3.  MCP 5     catalog.list / catalog.publish / catalog.verify + package_* mapping — ✅ done (69 ops; legacy mapping dropped)
4.  MCP 6     client integrations (configs, skill rename, deb + PyPI)
5.  §20       Caddy P7 residual cleanup
6.  §17/§19   distribution + native self-update
7.  §22–§24   package migration analyser + behavioural equivalence + boundary shrink
8.  §25–§27   LDAP demotion, native DNS, secrets lifecycle   (later phase)
```

---

## Architectural Control and State Layers

NostrHost separates control, configuration state, data recovery and runtime truth.

```text
Nostr events
= identity, authority, requests, approvals and audit provenance

ngit / NIP-34 + Git objects
= durable semantic configuration state and history

Restic
= application and filesystem data recovery points

Linux / YunoHost
= actual runtime state and execution
```

A useful rule is:

```text
WHO changed it?        -> Nostr
WHAT should exist?     -> ngit / Git state
WHAT data existed?     -> Restic
WHAT is running now?   -> Linux / YunoHost
```

The NostrHost relay remains private/local by default. It acts as the local system event bus and publication staging point. Public catalogue, software, CI and ngit events are published **outbound** to multiple configured external relays. Private identity, policy and control events remain local-only.

```text
local producers
      |
      v
private NostrHost relay
      |
      +--> local-only control / identity / policy events
      |
      +--> outbound publisher
                 |
                 +--> external relay A
                 +--> external relay B
                 +--> external relay C
```

No inbound public relay port is required for normal operation.

---

# 1. Fork Baseline — ✅

Create an umbrella repository (implemented as `imattau/nostrhost`):

```text
nostrhost/
```

This repository owns:

- architecture
- integration tests
- dependency/version pins
- release tooling
- packaging metadata
- derivative documentation

Fork the main upstream components (implemented as the source-identical
`imattau/nostrhost-*` forks):

```text
YunoHost/yunohost
    -> imattau/nostrhost-yunohost

YunoHost/yunohost-portal
    -> imattau/nostrhost-portal

YunoHost/yunohost-admin
    -> imattau/nostrhost-admin

YunoHost/SSOwat
    -> imattau/nostrhost-ssowat
```

Do not change behaviour immediately.

The fifth foundational component — `nostrhost-control` (the internal relay
control plane) — is added in roadmap §3 without touching these forks.

## Baseline milestone

The first milestone is:

> The derivative installs, boots and behaves identically to standard YunoHost.

This creates a known-good baseline before any Nostr-native changes are introduced. Achieved: forks source-identical to their pins, verified by `scripts/verify-clean.sh` and CI.

---

# 2. Extract the Existing Nostr Work — ✅

The existing projects are treated as reference implementations and implementation bases, not discarded prototypes.

## 2.1 From `yunohost-nostr-auth`

Extract reusable components for:

```text
Nostr identity
challenge generation
signature verification
NIP-07
NIP-46
passkey signer support
npub conversion
identity linking
revocation
NIP-05
```

Create a reusable authentication/identity library (implemented as `imattau/nostrhost-auth`).

The existing standalone implementation continues working during the migration.

## 2.2 From `yunohost-mcp`

Extract reusable components for:

```text
identity
roles
scopes
delegations
approval requests
NIP-98
NIP-46 owner approval
audit model
```

Create (implemented as `imattau/nostrhost-policy`).

Initially preserve the current policy implementation. Do not introduce a new policy engine while restructuring the whole system.

## 2.3 From Nostr Catalog

Extract:

```text
catalogue event schema
relay discovery
publisher verification
attestation verification
trust filtering
repository resolution
```

Create (implemented as `imattau/nostrhost-catalog`).

The existing `_ynh` packages remain operational during this stage.

---

# 3. Control Plane: Internal Relay + Event Model — ✅

This is the architecture-defining phase, completed *before* significant fork
modifications began. It adds a fifth foundational component — `nostrhost-control`,
wrapping an existing relay implementation — and defines the NostrHost event
protocol. No fork behaviour changed in this phase; the four forks remained
pinned and source-identical.

The local Nostr relay is the control-plane bus: identity, policy, approvals,
execution, catalogue and audit state all flow as signed events. Projectors
materialise read models (LDAP compatibility, policy state, catalogue cache)
and a control executor is the single writer to the YunoHost engine. Interfaces
(Portal, Admin, MCP, CLI) are relay clients, not owners of bespoke
point-to-point APIs.

See `CONTROL-PLANE.md` for the full specification — architecture, event
protocol (primitive-first, kind ranges, validation), relay selection
criteria, retention/access/bridging policy, the redundancy analysis, and the
boundary of what stays local (HTTP sessions, CSRF, challenges, the `broker/`
privilege transport, LDAP writes, YunoHost machine state).

The design is **primitive-first**: standard Nostr primitives are used wherever
possible (NIP-86 relay management, NIP-42 relay auth, NIP-78 app data, NIP-51
lists, NIP-44 encrypted payloads, NIP-77 sync, NIP-98 HTTP auth, NIP-89/32267
software discovery), and custom kinds are reserved for genuine NostrHost
semantics. `NIP-MAPPING.md` is the component → NIP mapping that precedes any
custom-kind allocation.

Phase 3 deliverables:

```text
component → NIP mapping (NIP-MAPPING.md)
event-model specification
kind registry (validated against the live NIPs and the existing
  catalogue kinds 1100 / 30078-30080)
relay backend selection (khatru-based; goss / strfry candidates for later)
nostrhost-control component: local-only relay config, NIP-86/42 access,
  event validation, per-kind retention, NIP-77 sync, external bridging rules
```

This phase removed (or shrank to projectors/resolvers) the bespoke approval
service, catalogue database/API, audit database, MCP identity storage and
polling/notification infrastructure that the earlier architecture implied.
Implemented: relay runs on-loopback with allowlist + NIP-42 protected kinds
and `server_pubkey` enforcement; replay is stable-sorted at EOSE.

---

# 4. Make Nostr Identity Native (events + projection) — ✅

This is the first significant modification to the YunoHost fork.

The target identity model is:

```text
npub = canonical external identity
YunoHost username = local compatibility identity
LDAP = compatibility/storage backend
```

LDAP is not removed initially.

Introduce a core identity abstraction:

```text
Identity {
    id
    pubkey
    username
    display_name
    email
    identities[]
    groups[]
}
```

Provide native functions such as:

```text
resolve_pubkey(pubkey)
resolve_username(username)
link_identity(username, pubkey)
revoke_identity(pubkey)
```

Under the control-plane architecture (§3), identity is authored as signed
identity/delegation **events** on the local relay and *projected* into this
native API and, for compatibility, into LDAP. The native functions above are
the identity projector's surface rather than owning their own store: identity
is a projection, not a database.

Implemented and proven on the testbed: `link`/`revoke` author kind-31102
identity events, the projector materialises them into LDAP-compatible accounts,
and `resolve_pubkey`/`resolve_username` resolve across the mapping. Bootstrap
is hardened into five roles — `server_sk` (machine key, signs execution
results), `operator_sk` (primary admin, signs approvals/capabilities),
`notice_sk` (portal notice key), `publisher_sk` (catalogue publisher) and
`notifier_sk` (notification service) — plus an `admins` list — via root-only
`nostrhost-bootstrap` / `postinstall --new` (§19, `docs/POSTINSTALL-KEYS.md`).

---

# 5. Consolidate Authorisation: Capability / Delegation Events — ✅

Bring the MCP authorisation model into the common architecture.

Define one shared permission vocabulary:

```text
app.read
app.install
app.upgrade
app.remove

backup.read
backup.create
backup.restore
backup.delete

user.read
user.create
user.modify
user.delete

system.read
system.upgrade

catalog.read
catalog.publish

permission.read
permission.modify
```

The common model becomes:

```text
Identity
   ↓
Role
   ↓
Scopes
   ↓
Policy evaluation
```

Under the control-plane architecture, roles, scopes, delegations and policy
declarations are authored as signed **capability/delegation events** on the
local relay (§3). What remains is the policy **evaluator** — the computation
of "may npub X perform Y on Z" — which keeps its current logic (the extracted
`nostrhost-policy` engine, or Casbin later) but no longer maintains its own
identity/delegation database: that state is projected from relay events.

The same policy engine serves Admin UI, MCP, Portal, SSO and background jobs —
one authorisation system, not separate permission logic for each interface.

Implemented: kind-31100 capability grants (scopes such as `server.read`,
`apps.read`, `services.read`, `services.write`) are authored as signed events,
projected by the operations engine, and gate requester authorisation; relay
allowlisting is granted via NIP-86 `allowpubkey` (NIP-98-signed). Server-scoped,
expiring kind-27236 delegations are now first-class operation authorisation
events: a delegator can grant only scopes it currently holds, and the
delegator or an administrator can revoke via kind 27237. Delegations are
signature-verified, retained for replay, and dynamically clipped when the
delegator loses its own capability.

---

# 6. Approval + Execution: Structured Operations + State Machine — ✅

Before introducing declarative machine state, prove that signed Nostr intent
can safely drive YunoHost through a narrow execution boundary.

The preferred operation model is structured rather than generic shell execution:

```text
system.version
app.list
service.status
app.install
app.upgrade
backup.create
service.restart
```

A control operation follows an explicit state machine:

```text
REQUESTED
   |
   +--> REJECTED
   |
   +--> APPROVED
           |
           v
       EXECUTING
           |
      +----+----+
      |         |
 SUCCEEDED    FAILED
```

The executor must enforce semantic transitions, expiry, signer authority,
duplicate-execution protection and policy version/state. `signed != valid`: an
invalid transition is refused even when correctly signed.

Under the control-plane architecture, the operation chain is authored as
signed events (kind 2200 request → 2201 approval → 2203 executing → 2204
result), the executor is the single writer to the YunoHost engine, and the
server key signs the terminal states. The audit trail *is* the signed event
chain.

Implemented and proven on the testbed: `REQUESTED → APPROVED → EXECUTING →
SUCCEEDED` chains with a genuine write operation (`service.restart`, scoped
`services.write`, approval-gated, bounded to a single known service), signed
by the distinct server key; the first proofs used harmless tools
(`system.version`, `app.list`, `service.status`). NIP-42 is restored and
enforced on the protected control kinds.

---

# 7. Introduce `nostrhost-state` with ngit / NIP-34 — ◑ (Stage A + B complete; Stage C ◑, Stage D ✓ §16)

This is the correct point to introduce durable configuration-state management.
Identity, policy and execution semantics (§4–§6) now exist, so state history
can become authoritative enough to support rollback and reconciliation.

**Stage A (state history) is implemented and proven on the testbed**:
semantic export (domains/apps/services/identities/packages/capabilities),
the git-backed state repository (server-pubkey identity), automatic pre/post
snapshots linked to operation event ids, known-good markers, semantic diffs,
and the NIP-34 kind-30617 repository announcement discoverable as
`nostr://<server-npub>/nostrhost-state`. Restic client + assisted rollback
(Stage B) are complete (§9).

The state layer uses **ngit / NIP-34 as the Nostr-aligned repository model**,
with normal Git objects underneath. Plain Git remains the storage engine, but
repository identity, ownership, discovery and signed repository state align
with Nostr identities.

The full design lives in `docs/STATELAYER.md`; this section condenses it.

## 7.1 Why ngit rather than plain Git alone

Plain Git provides excellent history, diffs, branches, tags and object
storage, but NostrHost would otherwise need a separate layer to answer:

```text
Who owns this state repository?
Who may publish authoritative refs?
How is the repository discovered?
Who proposed a change?
How does repository authority map to npubs?
```

With ngit / NIP-34, those concepts remain in the same cryptographic identity
namespace as the rest of NostrHost.

```text
Server npub
    |
    v
NIP-34 repository announcement
    |
    v
nostrhost-state
    |
    +--> signed repository state
    +--> PRs / patches
    +--> CI results
    |
    v
Git objects
```

A server therefore has a naturally discoverable state repository such as
`nostr://<server-npub>/nostrhost-state`; the server identity and its durable
state history remain linked without inventing a second identity system.

## 7.2 State is semantic, not a copy of `/etc`

Do not indiscriminately version the filesystem. Store NostrHost's semantic
desired configuration:

```text
state/
├── manifest.toml
├── system/
├── apps/
├── domains/
├── services/
├── network/
├── dns/
├── certificates/
├── identities/
├── capabilities/
├── backups/
├── schedules/
└── package-versions/
```

The repository describes intent (`caddy should serve this domain`), not
runtime observation (`caddy is running`). Runtime truth belongs to Linux/systemd.
Secrets must not be stored in plaintext: reference secret identifiers backed
by systemd credentials, age/SOPS or another dedicated encrypted secret store.

## 7.3 Automatic pre/post state history

Every meaningful configuration change creates before and after snapshots:

```text
operation request
      |
      v
pre-change semantic snapshot
      |
      v
execute operation
      |
      v
post-change semantic snapshot
      |
      v
health validation
```

Each state change is linked to the Nostr operation event that caused it.

## 7.4 Link configuration state to Restic data snapshots

Git/ngit is configuration-state history, not a replacement for data backup.
Restic remains the data recovery system. For operations that can affect
application data: `pre-change commit S1 → Restic snapshot R1 → execute →
health check`. A machine-readable state manifest records the relationship:

```toml
[state]
schema = 1
known_good = true

[operation]
event = "<nostr-event-id>"

[backup]
restic_snapshot = "<snapshot-id>"
required = true

[health]
result = "passed"
```

## 7.5 Known-good state and assisted rollback

Maintain the concept of a validated known-good state:

```text
main       -> current desired state
known-good -> latest health-validated state
previous   -> previous accepted state
```

Rollback is orchestrated, not a blind `git revert` — different changes have
different reversibility (see `STATELAYER.md` §8.5 for the change-class table).
The first rollback UX is assisted: `select previous state → semantic diff →
generate rollback plan → policy / approval → execute → health check`.

## 7.6 Disaster recovery and machine reconstruction

A failed server should be recoverable from identity, state and data:
install NostrHost → restore/authorise server identity → discover the NIP-34
state repository → retrieve latest known-good state → retrieve the linked
Restic snapshot → install required apps/packages → restore data → reconcile
configuration → validate. The goal is to reconstruct what the machine was, not
merely restore files.

## 7.7 Human and agent changes through NIP-34

Agents propose state changes without receiving root access: `agent npub →
branch / patch → NIP-34 proposal / PR → CI validation → human review if
required → merge → NostrHost policy → reconciliation / execution`. CI can
validate schema, policy, DNS, dependencies, security constraints and simulated
reconciliation; signed CI results are published as Nostr events associated
with repository coordinates and commits.

## 7.8 Repository authority is not operational authority

A valid repository change must never bypass `nostrhost-policy`:

```text
NIP-34 change → verify repository authority → NostrHost policy
    → risk classification → approval if required → executor / reconciler
```

ngit establishes repository identity and state provenance; `nostrhost-policy`
decides whether that state may actually be applied to the machine.

## 7.9 Stage the implementation

Do not introduce full GitOps-style reconciliation immediately. Stages:

### Stage A: state history
Export semantic configuration; commit pre/post states through the ngit-backed
repository; link commits to Nostr operation IDs; mark known-good states; link
Restic snapshots where required; produce semantic diffs.

### Stage B: assisted rollback
Add rollback-plan generation, policy evaluation and controlled restoration.

### Stage C: ngit replication and recovery
Publish relevant NIP-34 repository events outbound through the private relay
to multiple external relays; Git object storage uses ordinary Git/GRASP-style
storage without making a central forge authoritative.

### Stage D: declarative reconciliation
Compare the committed semantic state with live YunoHost state, classify drift
by risk, and apply only bounded, policy-approved operations. Unsupported drift
remains manual; avoid Kubernetes-like complexity: a single-server NostrHost
installation has one straightforward reconciliation process.

---

# 8. Portal Nostr Authentication + Native Session — ✓ (all three signer flows browser-proven; /nostr-account landed 2026-09-11)

Retain the existing Nuxt/Vue/TypeScript portal stack.

Move the existing Nostr-authentication user experience into the portal fork:

```text
/nostr-login        ✓ (NIP-07 sign-in page, deployed at /yunohost/sso/)
/nostr-account      ✓ (saved signer management + self-service identity linking,
                       landed 2026-09-11 — link/revoke/rename/unlink)
NIP-07              ✓ (browser-proven)
NIP-46              ✓ (browser-proven against a local bunker)
passkey UI          ✓ (button + unlock path reachable; full WebAuthn
                       attestation needs a real browser with PRF support)
saved signer management   ✓ (reconnect/forget bunker + local key, passkey
                       recovery/restore/forget on /nostr-account)
identity linking    ✓ (portal self-link via a privilege-separated control
                       socket: the unprivileged portal-api verifies session +
                       kind-22242 challenge, root nostr-identityd operator-signs
                       the kind-31102 definition — link/add/replace, revoke,
                       rename, unlink-all; admins still use nostr-identity-admin)
identity revocation ✓ (self-service revoke on /nostr-account; admin
                       `nostr-identity-admin revoke` remains)
```

The server side is implemented and proven live on the testbed:
`GET /yunohost/portalapi/nostr/challenge` + `POST /yunohost/portalapi/nostr/login`
(mint a passwordless `yunohost.portal` cookie after a verified kind-22242
challenge signature), with the login notice (kind 2206) signed by a dedicated
low-privilege portal notice key rather than the root operator keys. The
redesigned client (NIP-07 `/nostr-login` page + Tailwind/shadcn-vue) is
built from the derivative pin and deployed on the testbed at `/yunohost/sso/`.

**All three signer flows are now proven in a real browser** (headless
chromium via Playwright on the testbed, `docs/VM-TESTBED.md` §8): NIP-07
(`window.nostr` shim with the dave key), NIP-46 (a local NIP-46 bunker on a
loopback test relay, `bunker://` URI pasted into the deployed page), and the
passkey path (button renders + unlock path reachable once a stored identity
exists; WebAuthn PRF attestation is the documented headless limitation).
Each end-to-end flow mints the passwordless `yunohost.portal` cookie as
`dave`, renders the post-login dashboard, and the SSO-protected test app
launches with that session. Browser-flow bugs found and fixed in the portal
fork: the auth guard treated `/nostr-login` as a non-login route, the Nuxt
`/yunohost/sso` baseURL double-prefixed the portalapi `$fetch`, the NIP-44
vendor IIFE clobbered its own global, and the passkey button raced the
deferred vendor script (fork `a18c53e`). NIP-46 also required the SSO CSP to
allow `connect-src ws: wss:` for the remote signer relay (fork `yunohost_sso.conf.inc`).

Remaining §8 client work: a real extension-capable browser session to
exercise passkey attestation and the redesigned app grid visually (headless
limit only). `/nostr-account` (saved signer management + self-service
identity linking) landed and is VM-proven (2026-09-11).

Recommended browser-side Nostr stack: `@nostr/tools`; NDK where relay
functionality is required.

## Target flow

```text
Portal
  ↓
challenge
  ↓
NIP-07 / NIP-46 / passkey
  ↓
signature verification
  ↓
identity resolver
  ↓
YunoHost session
```

## Replace the session-minting workaround

The standalone authentication service currently needs special session-minting
plumbing because standard YunoHost does not provide a clean passwordless
portal-session API. Once the fork controls the authentication flow, replace
this workaround with a native internal API with a clear privilege boundary:

```text
create_portal_session(identity)
```

Remove transitional components where possible (`mint_session_server.py`, the
Unix-socket privilege workaround, duplicated portal-cookie implementation).

Live browser sessions are deliberately **not** carried as Nostr events:
short-lived session tokens, CSRF and challenge state, and the `broker/`
Unix-socket privilege transport stay in the local HTTP subsystem (§3 /
`CONTROL-PLANE.md` §2.3). The relay records login/link/revoke *notices* only.

## Portal milestone

A clean installation must support:

```text
create YunoHost user
→ link npub
→ log out
→ Sign in with Nostr
→ open Portal
→ launch existing YunoHost application
```

After the identity link, a password should not be required for normal sign-in.

---

# 9. Restic Linkage + Known-Good + Assisted Rollback (Stage B) — ✅

Complete the 0.3 "State History and Recovery Foundation" milestone by moving
from history to restoration:

```text
✓ semantic diff across state history          (Stage A)
✓ known-good state markers (health-validated) (Stage A)
✓ Restic snapshot linkage in the state manifest (Stage A)
✓ Restic client (backup/snapshots/restore/check, env-only secrets)  (Stage B)
✓ assisted rollback plan generation (change-class aware)            (Stage B)
✓ policy / approval gate on restoration       (Stage B: `rollback.apply` runs as a
                                               first-class operation-chain tool — signed
                                               2200 request → 2201 admin approval → 2203 →
                                               2204 result, scoped `state.write`; the
                                               local `--approve` remains the operator CLI path)
✓ controlled execution + re-validation        (registry-bounded — service.control,
                                               app.remove, restic restore — validated on the
                                               testbed end-to-end; app reinstall/upgrade
                                               reverse steps stay manual pending install-arg
                                               provenance)
```

`src/nostr_restic.py` wraps the `restic` CLI (config `/etc/nostrhost/
restic.toml`; secrets via `RESTIC_PASSWORD`, never argv) and drives the
recorder's pre-op data snapshot; `src/nostr_rollback.py` classifies each
semantic change per the STATELAYER §8.5 table, emits a plan with reversibility
and Restic linkage, and executes only through the operation registry
(`service.control` was added as the bounded runtime-setting reverse-action).
Restoration itself is a first-class chain operation (`rollback.apply`, scope
`state.write`, admin-approval-gated) so a repository change can never apply
state outside the signed control plane. This stage remains short of fully
automatic reconciliation (Stage D, §17).

---

# 10. Fork and Extend the Admin Interface — ⏳

Retain the current Vue/Vite/TypeScript admin stack.

Add Nostr-native management sections:

```text
Identities
Signers
Agents
Delegations
Approvals
Catalogue
Publishers
Trust
Audit
```

## Example identity view

```text
Matt
├── username: matt
├── npub1...
├── NIP-07 device
├── NIP-46 signer
├── passkey
├── groups
├── roles
└── active delegations
```

## Example agent view

```text
Codex
├── npub1...
├── role: package-developer
├── delegated by: Matt
├── allowed scopes
└── expires: ...
```

Functionality currently handled through configuration files or MCP CLI
commands should progressively gain native UI.

## First-class views

As the backend capabilities grow (§11–§27), make these first-class Admin
views rather than CLI-only:

```text
Identities · Agents · Delegations · Pending approvals

Apps
├── native
├── legacy
└── migration status

Operation plans
├── resources affected
├── risk
├── rollback availability
└── approval state

Restore points

Security
├── CrowdSec alerts
├── current decisions
└── security events

State
├── current revision
├── known-good
└── drift

System health
```

---

# 11. Make Nostr Catalog Native — ✓

Introduce a catalogue-provider interface in the YunoHost fork:

```text
LegacyYunoHostCatalogue
NostrCatalogue
```

Initially support both; the trusted Nostr projection is now the default when
available, with legacy YunoHost catalogues retained as an explicit fallback.
The Nostr provider handles relay queries, package events, publisher
signatures, CI attestations, trust policy, architecture and YunoHost-version
compatibility, and repository resolution. Once a package source is resolved,
continue using the existing YunoHost application installer — do not rewrite
the installation engine.

Under the control-plane architecture, the local relay **is the local
catalogue cache**: a catalogue synchroniser bridges external relays into the
NostrHost relay, and replaceable package/release/attestation events are
subscribed to directly by Admin, the installer, and MCP. Only the catalogue's
logic remains (the extracted `nostrhost-catalog`): trust calculation,
compatibility checking, repository resolution and attestation verification.

```text
external relays
     ↓
catalogue synchroniser
     ↓
NostrHost relay          ← the local catalogue cache
     ↓
Admin / installer / MCP
```

## Integrate catalogue trust with policy

This is where identity, catalogue and authorisation reinforce one another —
Nostr becomes part of the software trust model, not merely an authentication
mechanism:

```text
Agent requests app.install → catalogue finds package → signature valid?
→ trusted publisher? → CI attestation valid? → policy evaluates operation
→ owner approval required? → NIP-46 signature → install
```

Policy input can include `actor`, `action`, `package`, `publisher_trusted`,
`ci_attested`, `source_signed` and `actor_type` (see `STATELAYER.md` and the
control-plane policy spec for the exact schema).

---

# 12. Web-Layer Authentication: Caddy forward_auth — ✓ (SSOwat retired)

The authentication enforcement point is now **Caddy `forward_auth` → the
Python auth daemon**, not nginx/SSOwat. This supersedes the earlier
"NGINX → auth_request → nostrhost-authd" plan and the "reduce SSOwat"
goal: SSOwat has been **retired** (deleted) — see
`docs/CADDY-MIGRATION.md` P3/P6 and §18.4.

```text
Caddy
  ↓
forward_auth
  ↓
nostrhost-authd (auth daemon)
  ↓
identity resolution
  ↓
policy
```

The authentication daemon returns compatibility headers such as
`X-Remote-User`, `X-Remote-Email`, `X-Nostr-Pubkey`, `X-Nostr-Npub` so existing
YunoHost applications continue receiving the headers they expect (the authd
always emits the full header set, empty when unknown, and overwrites
client-supplied copies).

SSOwat is not reduced — it is removed. The Python auth daemon performs the
URL→permission matching (ported from `access.lua`), reads a native permission
projection (`/etc/nostrhost/permissions.json` generated by
`nostrhost.permissions`), and Caddy owns session validation and compatibility
header injection. Remaining work is residual-reference cleanup only (see §20,
Caddy P7).

---

# 13. MCP Adapter — ✅

MCP becomes another interface to the same internal service layer, not an
owner of bespoke integration:

```text
                YunoHost service layer
                   ↑      ↑      ↑
                   │      │      │
                 Admin   MCP   CLI
```

Under the control-plane architecture, MCP is now an **adapter**: it keeps the
MCP protocol, tool definitions, package-development tools, diagnostics
presentation, and NIP-98 client authentication, while publishing signed
operation-request events to the local relay and subscribing to
approval/execution/result events (§3). Its identity, approval, delegation,
audit and queue state use the shared policy/control-plane model. Remaining
work is incremental removal of duplicated legacy YunoHost integration as
equivalent native APIs are introduced.

---

# MCP Transition Plan (nostrhost-mcp)

The goal is not "port the MCP server". It is:

> **Preserve the useful client integrations and tool surface, but move
> authority, policy, approvals, execution and state into NostrHost itself.**

The architectural rule kept throughout:

> **MCP is an interface, not an authority boundary.**

`nostrhost-mcp` is a thin protocol adapter over the installed fork's operation
model. The fork `ToolSpec` registry (`src/nostr_operations.py` +
`src/nostrhost/native_ops.py`, 43 ops) is the single source of truth;
`operation_catalog()` drives generated MCP tools, CLI, API and Admin forms.
The protocol-neutral `NostrMCPAdapter` submits signed kind-2200 requests and
correlates 2201/2203/2204/2205. The reference implementation
(`libs/yunohost-mcp`, frozen) holds the feature inventory; its duplicated
modules are retired as native equivalents land. Full detail:
`docs/MCP-TRANSITION.md`.

## Phase plan and status

| Phase | Scope | Status |
|---|---|---|
| **0** | Registry hardening + full native surface (scopes aligned to policy enum, Pydantic input/result models, risk/reversibility, `operation_catalog()`) | ✅ |
| **1** | `nostrhost-mcp` skeleton — tools generated from the catalog, reads stream to 2204, writes return `approval_required` + `operation_id`, `op_status` helper, NIP-98 HTTP on loopback, unprivileged deploy unit | ✅ (VM: 44 tools) |
| **2** | Native identity + capabilities — client npub rides as the operation `actor`; agents are native 31100/27236 capabilities; the daemon authorizes the actor, not the signing key | ✅ |
| **3** | Signed mutations + streaming — service/backup/dns/credential/domain/app/package/state/rollback mutations VM-proven; strict input models; redaction container fix | ✅ |
| **4** | Approval flow (out of MCP) — control-plane 2201/NIP-46; `op_status` surfaces `approval_required`/`REJECTED`/result; owner co-signature + rejection proven; operationsd keepalive (1011) debt resolved | ✅ (gate `PHASE4-PROOF-OK`) |
| **5** | Resource Engine integration — **complete**. `package.plan`/`package.reconcile` native and proven; native catalog surface (`catalog.list`/`catalog.get`/`catalog.publish`/`catalog.verify`); and the full Phase 5 backlog landed — `updates.check/refresh`, `system.migrations`/`system.migrate`, `service.history`, `logs.read`/`logs.web` (Caddy access log, /var/log/caddy — nginx is not part of the stack), `backup.delete`, `domain.cert.info`/`domain.cert.install`, `user.update`, `user.group.*`, `user.permission.*`, `audit.list`/`audit.get` (signed chain on the control relay). Registry is 69 ops. Legacy `package_*` test-tool mapping and the explicit legacy compat path were **dropped by direction** (no legacy deployment exists). | ✅ |
| **6** | Client integrations — port claude-code/codex/gemini/hermes/openclaw/opencode configs to `nostrhost-mcp`; rename the `yunohost-mcp-operations` skill; OpenCode Web → loopback streamable HTTP; package + publish (`python3-nostrhost-mcp` deb + PyPI) | ⏳ |
| **7** | Multi-host / fleet projection (per-node adapter; client → node relay mapping) | ⏳ deferred |
| **8** | Retire duplicated `yunohost-mcp` logic (kept: protocol, schema/tool exposure, client setup, redaction, result translation, transport) | ⏳ gated on 5–6 |

## Phase 5 backlog — the missing native operation surface

**Complete (fork `e85ca0b7`): the registry is 69 ops.** Read ops land
un-gated, write ops carry their policy gates; `audit.*` reads are owner
co-signed per call. Legacy `package_*` test-tool mapping + explicit legacy
compat path dropped by direction (no legacy deployment exists).

| Op group | Status |
|---|---|
| catalog | ✅ `catalog.list`/`catalog.get`/`catalog.publish` (publisher key signs kind-32267 declarations) + `catalog.verify` (Python id/sig/schema/trusted-publisher check; naddr rejected — no nip19 decoder) |
| audit | ✅ `audit.list`, `audit.get` — the signed operation chain on the control relay is the audit log (`query_chain_events`); owner co-signature per call |
| system | ✅ `updates.check`, `updates.refresh`, `system.migrations`, `system.migrate` |
| services | ✅ `service.history` |
| logs | ✅ `logs.read` (allowlisted journals incl. caddy + nostr daemons), `logs.web` (Caddy JSON access log, /var/log/caddy — nginx is not part of the stack) |
| backups | ✅ `backup.delete` |
| domains | ✅ `domain.cert.info`, `domain.cert.install` (staging rejected; ACME failure surfaced via `acme_error`) |
| users | ✅ `user.update`, `user.group.*` (`admins` escalates to `users.admin_access`), `user.permission.*` (`users.permissions` tier) |
| diagnosis | ◑ composite tools (`ssh_diagnose`, `http_probe`, `incident_snapshot`) still map to `diagnosis.run` composites — no separate ops |

Policy gates carried: confirmation for `app.change_url`/`app.config.set`/
`domain.cert.install`/`catalog.publish`; recent-backup + ≥2 GB free for
`app.upgrade`/`package.reconcile`; confirmation + different-admin co-signature
for `backup.restore`/`system.upgrade`/`system.migrate`/`firewall.*`/
`user.delete`/`user.group.delete`/`user.permission.add|remove`; owner
co-signature for `audit.read`.

## Verification

- **Local**: fork suite (539 passing) + `nostrhost-mcp` unit tests (22 passing,
  1 skip) + flake8 clean.
- **VM**: real MCP client → `nostrhost-mcp` (unprivileged) → submit → approve →
  execute → streamed result, with the MCP process holding no host write
  authority. Phase 4 gate: reads → app install → owner approval → health check
  → result returned.

---

# 14. OIDC Compatibility — ◑ (bridge VM-proven; client management + signing-key rotation remain)

Once Nostr identity is stable, add a conventional application-authentication
bridge:

```text
Nostr identity → YunoHost identity → OIDC provider → applications
```

Authlib is a suitable candidate for the OIDC/OAuth layer. This gives
applications a standards-based interface while Nostr remains the underlying
authentication and identity system, and may progressively reduce the number of
applications requiring YunoHost-specific SSO integration.

---

# 15. ngit Replication / Disaster Recovery (Stage C) — ◑ (announcement publication landed; repository/object replication remains)

Publish relevant NIP-34 repository events outbound through the private relay
to multiple external relays so the configuration-state history is recoverable
off-box. Combined with Restic data snapshots (§9), this completes the
disaster-recovery story from §7.6: identity, state and data are each
retrievable, and the machine can be reconstructed rather than merely
restored. Git object storage uses ordinary Git/GRASP-style storage; no central
forge becomes authoritative.

---

# 16. Declarative Reconciliation (Stage D) — ✓

The reconciler compares the clean committed semantic state with live YunoHost
state and emits low/medium/high-risk changes. Bounded service and application
changes can be submitted as `state.reconcile` operations and require the
existing scope plus administrator approval; unsupported changes remain
manual. A valid repository change never bypasses `nostrhost-policy` (§7.8).

---

# 17. Distribution and Release Tooling — ⏳

Once the architecture is stable, turn it into a real distribution. The
umbrella repository manages:

```text
Debian repository
installer image
upgrade repository
package signing
release manifest
integration-test image
```

CI should test at minimum:

```text
fresh install
upgrade from previous derivative release
user creation
Nostr identity linking
Nostr login
SSO-protected app
catalogue discovery
app install
agent authentication
delegated MCP operation
NIP-46 approval
backup/restore
legacy password login
```

Password login should remain available initially as a recovery path.

## 17.1 Native self-update

The platform itself should update through the same architecture it provides:
signed release → catalogue/release metadata → verify publisher + artifact →
state S1 + recovery snapshot → system upgrade plan → approval → apt/dpkg →
reboot if needed → health validation → state S2 known-good. This reuses the
native state, recovery and policy layers rather than a bespoke updater:

```text
signed NostrHost release
   ↓
Nostr catalogue / release metadata
   ↓
verify publisher + artifact
   ↓
state S1 + recovery snapshot
   ↓
system upgrade plan
   ↓
approval
   ↓
apt/dpkg
   ↓
reboot if needed
   ↓
health validation
   ↓
state S2 known-good
```

---

# 18. Platform Simplification: Native Messaging, Mail Retirement and Host Security — ⏳

Once the Nostr-native identity, Portal/Admin, control plane and state/recovery
layers are stable (§4–§10), simplify the inherited YunoHost platform services
that no longer fit the NostrHost architecture.

The objective is not to replace proven Linux infrastructure unnecessarily. It
is to remove services whose responsibilities are now provided more naturally
by the Nostr control plane, and to modernise security components where there
is a clear operational benefit.

## 18.1 Native Nostr messaging and notifications

See `docs/NOTIFICATION-SERVICE.md` for the working design of this service —
architecture, event classes, policy schema and delivery mechanics.

NostrHost should not depend on email as its native notification mechanism.
Platform notifications should originate as structured local events and, where
human delivery is required, be delivered through encrypted Nostr messaging.

```text
NostrHost subsystem
        |
        +-- backup result
        +-- health alert
        +-- approval required
        +-- operation result
        +-- security event
        +-- update available
        +-- recovery result
        |
        v
private NostrHost relay
        |
        v
notification service
        |
        v
encrypted Nostr message
        |
        +--> owner
        +--> administrator
        +--> delegated operator
        +--> authorised agent
```

Use existing Nostr primitives wherever possible, with NIP-17/NIP-59-style
private messaging as the preferred direction for human-readable private
notifications.

Machine control events must remain structured NostrHost events (kinds
2200-2204 etc. = structured machine operations). Do not turn the
administrative event protocol into a chat protocol; private Nostr messaging is
the human-facing notification layer *derived from* those events, not a
replacement for them.

Notification policy should determine: recipient npub, event classes, severity
threshold, immediate vs. summary delivery, local-only vs. external delivery.

The private NostrHost relay remains the local event source (§3). Notification
delivery uses outbound relay connections, preserving the design goal that
normal NostrHost operation does not require an Internet-accessible inbound
Nostr relay (§0 / architectural principle 17).

## 18.2 Remove the built-in mail stack from the default platform

See `docs/MAIL-RETIREMENT.md` for the working dependency inventory and phase
plan required by §18.7 before any removal work lands in `forks/yunohost`.

NostrHost should not operate a complete Internet mail server by default. The
inherited YunoHost mail stack can be progressively removed from the default
NostrHost installation, including components and configuration associated
with: Postfix, Dovecot, Rspamd/spam filtering, DKIM signing, SMTP submission,
IMAP, local mailboxes, MX configuration, SPF/DMARC platform assumptions, and
mail reputation management.

The target model is:

```text
Nostr  = native identity, native private messaging, native system notifications
Email  = optional external integration or separately installed application
```

This removes a substantial operational and security burden from the default
server while retaining the ability for users to run email where they
explicitly need it. Do not prevent NostrHost applications from sending or
receiving email — remove the assumption that every NostrHost server must
itself be a mail server. Applications requiring email should be able to use an
external SMTP provider, a self-hosted mail application, a local optional mail
package, or application-specific mail configuration. External email
notification bridges may also be provided for administrators who want
conventional email alerts.

## 18.3 Simplify the identity model around Nostr

Removing mandatory platform email also simplifies the user model (§4). The
long-term native identity should centre on npub, signer, Kind 0 profile,
capabilities, groups and delegations — rather than username, password,
mandatory email address and mailbox. A compatibility username may continue to
exist where required by Unix accounts or legacy applications. Email becomes
optional profile/contact metadata rather than an architectural identity
requirement. LDAP compatibility projections must therefore not require
creation of a functioning mailbox for every Nostr identity.

The final model:

```text
Nostr messaging = native platform communication
Email          = optional application/integration
```

The mail retirement is far along, but the identity/UI consequences remain:

```text
remove mandatory mailbox from user creation
remove email-reset / email-login assumptions
remove remaining mail Admin UI
ensure DNS no longer assumes MX / SPF / DMARC by default
represent optional mail integration in semantic state (§18.6)
```

## 18.4 Modernise host intrusion protection

Retain nftables as the underlying Linux firewall:

```text
NostrHost policy/control -> firewall management -> nftables
```

Do not replace a mature kernel firewall with a Nostr-specific implementation.
The inherited fail2ban layer was evaluated against CrowdSec and **retired in
favour of CrowdSec** (P4–P6 of `docs/CROWDSEC-MIGRATION.md`): behaviour-based
detection plus shared threat intelligence (CAPI) while still integrating with
the host firewall.

Adopted architecture:

```text
Current (retired):  logs -> fail2ban -> nftables
Adopted:            service logs / journald -> CrowdSec -> local decisions -> nftables (bouncer-nftables)
```

The decision followed the evaluation criteria in this section: memory/CPU
footprint, dependency footprint, offline behaviour, privacy, external
threat-intelligence dependency, nftables integration, false-positive
behaviour, IPv4/IPv6 handling, NostrHost event integration, and
upgrade/maintenance burden. CrowdSec materially improved the
security/operational model (structured events + Nostr-native integration over
fail2ban's ban-only model), so it replaced fail2ban rather than sitting
alongside it.

## 18.5 Integrate security events with the Nostr control plane

CrowdSec (the adopted intrusion-protection layer, fail2ban retired) should
feed the NostrHost control plane:

```text
CrowdSec -> nftables
             |
             v
      security projector
             |
             v
     local NostrHost relay
             |
       +-----+------+
       |            |
       v            v
    audit       notification
                    |
                    v
              admin npub
```

Examples: repeated authentication failures, blocked address, unusual service
activity, firewall policy change, new listening service, administrative
authentication failure, privileged operation rejection. These should become
structured security/audit events first (following the audit model of §5–§6);
human-facing encrypted Nostr notifications are then derived from them. This
preserves the architectural distinction: a structured event is system
truth/audit, while a private Nostr message is a notification to a person.

## 18.6 State and recovery integration

Changes to security, notification and optional-mail configuration must
participate in `nostrhost-state` (§7):

```text
state/
├── notifications/
│   ├── policy.toml
│   └── recipients.toml
├── network/
│   └── firewall.toml
├── security/
│   └── intrusion-protection.toml
└── integrations/
    └── email.toml
```

Do not place private keys, SMTP passwords or other credentials in the ngit
repository — reference secrets through the NostrHost secret-management
mechanism. Changes follow the normal lifecycle: signed request/approved
desired-state change -> pre-change state snapshot -> policy evaluation ->
executor -> health validation -> post-change state (§7.3, §7.8). Firewall and
remote-access changes should receive a higher risk classification because a
failed configuration may lock an administrator out of the machine.

## 18.7 Implementation sequence

Implement this work after the core Portal/Admin (§8, §10) and state/recovery
(§7, §9) paths are operational:

```text
Nostr identity
      |
control / policy / executor
      |
ngit state + Restic recovery
      |
Portal + Admin
      |
      v
Native notification service
      |
encrypted Nostr notifications
      |
remove internal dependencies on email notifications
      |
make email optional
      |
remove default mail-server stack
      |
security event integration
      |
✓ evaluate CrowdSec against fail2ban
      |
✓ adopt winner with nftables backend
      |
distribution hardening
```

Do not remove the mail stack until all NostrHost components that currently
depend on local mail have been identified and migrated. Before removal,
inventory: YunoHost core mail dependencies, diagnosis, certificate
notifications, backup notifications, Admin notifications, application
installation assumptions, user creation/deletion, domain configuration,
SSO/Portal assumptions, application packaging helpers, and system
cron/systemd mail output. Each dependency must be classified as: replace with
Nostr notification, remove entirely, make optional, or retain as
compatibility behaviour.

## 18.8 Milestone: Nostr-native platform services

```text
✓ system alerts can reach an administrator through encrypted Nostr messaging
✓ approval requests can generate private Nostr notifications
✓ operation/backup/recovery results can generate notifications
✓ notification recipients are npub-based
✓ notification policy is represented in semantic state
✓ core NostrHost functionality no longer depends on local email
✓ new users do not require a local mailbox
✓ mail-server installation is optional rather than default
✓ nftables remains the firewall backend
✓ fail2ban vs CrowdSec has been benchmarked/evaluated
✓ selected intrusion-protection system feeds structured security events
✓ important security events can generate encrypted Nostr notifications
✓ security configuration participates in ngit state history
✓ rollback/recovery procedures cover firewall/security configuration
```

The resulting platform boundary:

```text
NostrHost

                    Private Local Relay
                            |
       +--------------------+--------------------+
       |                    |                    |
    Identity              Policy             Operations
       |                    |                    |
       +--------------------+--------------------+
                            |
                      nostrhost-state
                            |
                       ngit / NIP-34
                            |
                +-----------+-----------+
                |                       |
             Executor                 Restic
                |
+--------+---------+----------------+
        |                  |                |
     systemd             CADDY          nftables
        |                  |                |
  optional apps       web / TLS      intrusion
                                     protection

                    Notification Service
                            |
                            v
                 encrypted Nostr messaging
                            |
                  owner/admin/user npubs
```

Default platform: Nostr identity + messaging + notifications. Optional:
external email provider / self-hosted mail application.

**Architectural principle:** NostrHost should provide Nostr-native identity,
control and communication by default. Traditional Internet email remains
available where users need it, but operating a public mail server should no
longer be a prerequisite for operating a NostrHost server.

This change reduces the default service footprint, removes one of the most
operationally difficult parts of self-hosting, and makes the base platform
more consistent with its Nostr-native identity and control architecture.

---

# 19. Native Bootstrap / Postinstall — ◑ (postinstall CLI + five-key bootstrap landed; acceptance loop + `--restore` DR path remain)

The biggest missing platform-level piece. A clean install must no longer
bootstrap through the old YunoHost admin/password assumptions. `postinstall
--new` provisions the five hardened roles root-only (§4, `docs/POSTINSTALL-KEYS.md`):
`server_sk` / `operator_sk` (default admin) / `notice_sk` / `publisher_sk`
(catalogue) / `notifier_sk` (notification service), renders `relay.toml`,
`policy.toml`, `notify.toml` and `catalogue.env`, records state S0, and
presents the keys for safe keeping once (`nsec1` recovery bundle + root-only
`/etc/nostrhost/keys.recovery`). `postinstall --restore` recovers identity +
state + Restic and requires every node key explicitly (flags or `--keys-file`);
the blank-VM acceptance loop and the legacy `tools_postinstall` bypass remain.

```text
Debian
   ↓
NostrHost packages
   ↓
nostrhost-bootstrap
   ↓
domain / network
   ↓
server identity
   ↓
owner npub proof
   ↓
initial capabilities
   ↓
private relay
   ↓
Caddy
   ↓
Portal/Admin
   ↓
state S0
   ↓
READY
```

Support two entry points:

```bash
nostrhost postinstall --new
nostrhost postinstall --restore
```

`--new` provisions a fresh node. `--restore` reconstructs the machine from
server/owner identity + NIP-34 state + Restic (§7.6, §15): install NostrHost →
restore/authorise server identity → discover the state repository → retrieve
known-good state + linked Restic snapshot → install apps → restore data →
reconcile → validate. Restore is the disaster-recovery path, made a
first-class install mode rather than a manual procedure.

---

# 20. Web Cutover Completion (Caddy P7) — ⏳

The Caddy migration is far along (P0–P6 passed on the VM: Caddy serves
80/443, SSOwat deleted, the Python auth daemon owns authorisation, Caddy owns
automatic TLS, nginx removed from core dependencies/templates). Finish the
P7 tail before declaring the web transition complete — see
`docs/CADDY-MIGRATION.md` §5 P7:

```text
Caddy storage in backup/restore   (include /var/lib/caddy alongside the
                                   exported /etc/yunohost/certs)
certificate state in semantic state (record certificates/, services/)
remove remaining nginx helpers     (helpers/*/nginx, ynh_add_nginx_config)
remove residual nginx migrations/references
update ROADMAP terminology        (this document, §12, §18.8, End State)
```

P6 also noted `scripts/verify-clean.sh` no longer pins ssowat and the
six nginx-referencing test files now assert the Caddy model; confirm those
are green at the P7 gate.

---

# 21. End-to-End Native App Lifecycle — ◑ (plan/reconcile proven on nostrhost-test; the real-app vertical loop remains)

The declarative resource engine is broad enough; stop adding resource types
temporarily and prove one substantial real application completely through the
vertical loop. The resource-engine machinery is in place (`package.toml`,
plan/reconcile model, native providers, native Caddy routes, databases,
runtimes, permissions, secrets/settings, backup declarations). What is missing
is proof of the whole, trusted, signed loop on a real app:

```text
Nostr Catalog
   ↓
trusted package.toml
   ↓
package.plan
   ↓
plan digest
   ↓
signed request
   ↓
policy
   ↓
approval
   ↓
Restic + pre-state
   ↓
reconcile
   ↓
health verification
   ↓
post-state
   ↓
Admin result
```

Once this works reliably, the architecture is proven as a whole — including
the native Caddy route path (P4) and the catalog→policy trust integration
(§11).

---

# 22. YNH Package Migration Analyser — ⏳

The current migration command (`nostrhost/package_engine.py`
`migrate_manifest_file`) handles declarative v2 resources but rejects
packages with imperative lifecycle scripts. The next version should analyse
them rather than refuse:

```text
YNH repository
   ↓
manifest parser + Bash AST analyser
   ↓
helper recogniser
   ↓
semantic resource graph
   ↓
deterministic migration
   ↓
unresolved behaviour
   ↓
optional AI
   ↓
native package.toml
   ↓
VM validation
```

Crucially: a known `ynh_*` helper maps deterministically; only unknown or
custom Bash is AI-assisted — AI must not rewrite the whole package blindly.
This is the path from the §24 "legacy packages 100% → 0%" metric.

---

# 23. Behavioural Equivalence Testing — ⏳

Automated migration is credible only with behavioural comparison between the
original and the migrated package:

```text
VM A  original YunoHost package
VM B  migrated NostrHost package
        ↓
   compare
 service status · HTTP behaviour · ports · database · permissions ·
 data directories · install · upgrade · backup · restore · remove
```

A migration should get an actual confidence score / attestation.

---

# 24. Native vs Compatibility Boundary — ⏳

Make the boundary explicit and measurable:

```text
NostrHost Native
├── package.toml
├── resource engine
├── Caddy
├── Nostr auth
├── CrowdSec
├── native state
└── signed lifecycle

YunoHost Compatibility
├── legacy manifest
├── Bash lifecycle
├── remaining LDAP projection
└── temporary helper compatibility
```

Then make compatibility shrink measurably:

```text
Legacy dependency count:  122 helpers → 87 → 41 → 0
Legacy packages:          100%       → 70% → 25% → 0%
```

---

# 25. LDAP Dependency Inventory / Reduction — ⏳

With SSOwat gone, LDAP's purpose is shrinking. Do not rip it out immediately;
first inventory what genuinely still needs it:

```text
Unix account projection?
legacy applications?
group compatibility?
slapd itself?
old admin APIs?
```

The eventual target:

```text
Nostr identity
   ↓
local account/group projection

LDAP = optional compatibility provider (not a default platform service)
```

---

# 26. Native DNS Management — ⏳

Caddy solves certificate issuance, but DNS still matters for domain
provisioning, NIP-05, application subdomains, IPv4/IPv6 changes and dynamic
DNS (DNS-01 later). A typed `DnsResource` with provider adapters fits the
resource-engine architecture:

```toml
[dns.records.app]
type = "A"
name = "photos"
target = "$server_ipv4"
```

Provider APIs replace Bash helpers. DNS participates in semantic state
(`state/network/`, `state/dns/` — §7.2 already reserves `dns/`).

---

# 27. Secrets / Key Lifecycle — ◑ (node-key inventory + safe keeping landed; rotation/backup/recovery architecture remains)

NostrHost holds increasingly valuable keys: server nsec, operator nsec,
notification key, catalogue publisher key, Restic credentials, database
secrets, external relay credentials, DNS provider credentials, Caddy-related
secrets, agent keys.
Formalise the lifecycle as first-class design:

```text
generation · storage · access · rotation · backup · recovery · revocation
```

The **node identity keys** are now a defined set with a safe-keeping story
(`docs/POSTINSTALL-KEYS.md`):

```text
operator_sk  — primary admin / owner (approvals, grants, identity defs)
server_sk    — server machine key (execution events 2203/2204)
notice_sk    — portal low-privilege notice key (portal.toml, ynh-portal)
publisher_sk — catalogue publisher (catalog.publish; writer-only on the relay)
notifier_sk  — notification service (reads notices, sends NIP-17 DMs only)
```

Storage: root-only `operator.toml` (0600) + `portal.toml` (0640 ynh-portal);
the relay allowlists all four control pubkeys (operator/server/notice/publisher
as writers, only the operator as admin). **Backup**: the installer is shown the
`nsec1` bundle once and a root-only `/etc/nostrhost/keys.recovery` is written —
the keys are never in ngit state. **Recovery**: `postinstall --restore` takes
every key explicitly (64-hex or `nsec1`, or `--keys-file`). Rotation and the
remaining secret classes (Restic/DB/external/DNS/Caddy/agent) still need the
explicit architecture below.

systemd credentials are a useful storage primitive, but the overall
key-management policy needs explicit architecture. Secrets are referenced by
identifier in ngit state, never stored in plaintext (§7.2).

---

# Recommended Implementation Order

The order matters. The internal relay + event model (§3) was the
architecture-defining phase and preceded any significant fork modification; it
was purely additive and left the forks pinned. The state layer (§7) is gated
on identity, policy and execution semantics, which now exist.

```text
0.  Source-identical fork baseline                          ✅
1.  Extract proven existing Nostr code                      ✅
2.  INTERNAL RELAY + EVENT MODEL        (nostrhost-control) ✅
3.  Identity events + projection                            ✅
4.  Capability / delegation events                          ✅
5.  Approval + execution events (structured ops + state machine) ✅
6.  nostrhost-state Stage A            (ngit / NIP-34)      ✅   (Stage A + B complete)
7.  Portal Nostr authentication (+ native session creation) ✓  (all three signer flows + /nostr-account self-service identity mgmt browser-proven; only real-browser passkey attestation pending — headless limit)
8.  Restic linkage + known-good + assisted rollback (Stage B) ✅  (registry-bounded execution, chain-gated, testbed-validated)
9.  Admin interface                                         ⏳
10. Native catalogue (sync + trust events)                  ✓ (trusted projection, relay sync, attestations, and YunoHost integration)
11. Web-layer auth: Caddy forward_auth, SSOwat retired      ✓ (P0–P6 of CADDY-MIGRATION on the VM; §12, §20 P7 residual cleanup remains)
12. MCP adapter                                             ✅ (MCP transition Phases 0–4 complete; 5–8 remain — see plan above)
13. OIDC                                                    ⏳
14. ngit replication / disaster recovery (Stage C)          ◑ (multi-relay NIP-34 announcement publication landed; repository/object replication remains)
15. Declarative reconciliation (Stage D)                    ✓ (risk-classified plans + approval-gated bounded apply)
16. Distribution release                                    ⏳
17. Platform simplification (native messaging, mail          ◑ (§18; mail identity/UI cleanup and security-state remain)
    retirement, host security)
18. Alpha plan W0–W3 (docs → runtime deb → bootstrap →     ◑ (W0/W1 landed, W2 in flight, W3 pending — see plan above)
    end-to-end native app lifecycle)
```

## Phase 2 — Platform consolidation and cutover

The core architecture is now largely complete. The next phase stops adding
subsystems and instead closes NostrHost's own platform loops so YunoHost
becomes purely a compatibility/migration source (§19–§27):

```text
18. Caddy P7 cleanup + residual nginx/SSO reference removal  ⏳ (§20)
19. Native postinstall/bootstrap (--new / --restore)         ⏳ (§19)
20. Mail identity/UI cleanup (user creation, DNS, Admin UI)  ⏳ (§18)
21. End-to-end real native app lifecycle                     ⏳ (§21)
22. YNH package migration analyser (+ AI repair loop)        ⏳ (§22)
23. Behavioural equivalence testing for migrated packages    ⏳ (§23)
24. Admin UI first-class views (identities, plans, security) ⏳ (§10)
25. Native vs compatibility boundary (measurable shrink)     ⏳ (§24)
26. LDAP dependency inventory / reduction                   ⏳ (§25)
27. Native DNS resource + provider adapters                  ⏳ (§26)
28. Secrets / key lifecycle architecture                    ⏳ (§27)
29. Native NostrHost release/update process                 ⏳ (§17)
30. Gradual YunoHost compatibility retirement               ⏳ (§24)
```

Do not begin by rewriting SSOwat (retired — §12) or rebuilding the admin
interface (still on the list). Stand up the control plane and get identity
events + projection working first — done — then prove execution (§5–§6, done),
then build the state-history layer (§7) before the portal. Portal
authentication follows on top of identity events and native session creation.

---

# Alpha Execution Plan — "make it a product"

Scope agreed (2026-09-12): **docs + python-deps distribution + native bootstrap
+ end-to-end native app lifecycle** as the near-term path to the 0.1 alpha.
§25 (LDAP demotion) and §26/§27 (native DNS + secrets) are the later phase.
Full detail: `docs/ALPHA-PLAN.md`.

The threshold this plan targets:

```text
Fresh Debian 12 VM
   ↓
install NostrHost APT repo → apt install nostrhost → postinstall --new | --restore
   ↓
Nostr owner login → Admin works → install native app → app works over HTTPS
   ↓
backup → upgrade → deliberately break it → restore/rollback
```

If that works repeatedly from a blank VM, NostrHost 0.1 alpha is real, even
with LDAP and some YunoHost compatibility code still underneath.

| Workstream | Scope | Status |
|---|---|---|
| **W0** Documentation truth — README/`BASELINE.md`/CI scripts describe what exists (no stale ssowat/moulinette/source-identical claims) | ✅ | README + baseline clean of ssowat references; verify `verify-clean.sh`/`pin-forks.sh` |
| **W1** `nostrhost-runtime` deb — private venv at `/opt/nostrhost/venv`, bundled wheels (nostr-sdk, bech32, coincurve, pydantic), daemons on venv python, `nostrhost-core(-system)` depends on it | ✅ | declared in `packaging/packages.yml`; acceptance = clean-VM install with no manual pip |
| **W2** Native bootstrap / postinstall (§19) — `nostrhost postinstall --new` (keys → operator.toml/policy.toml → relay/Caddy/daemons → state S0) and `--restore` (identity → state repo → known-good + Restic → reconcile); retire legacy `tools_postinstall` | ◑ | both `--new` and `--restore` are implemented in `cli.py`; blank-VM acceptance loop + legacy `tools_postinstall` bypass ⏳ |
| **W3** End-to-end native app lifecycle (§21) — `app install <coordinate>` CLI through the signed plan/approval/reconcile chain; native `app remove/upgrade/change_url`; backup/restore linkage; proof on nostrhost-test then one **real** app | ⏳ | |

Sequencing: W0 → W1 → W2 → W3; each ends green on CI. Final gate is the alpha
acceptance loop.

Later phase (not near-term): **§25 LDAP demotion** (native user/group store,
optional `LDAPInterface`, native authenticator, slapd/nslcd hooks optional) and
**§26/§27 native DNS + secrets** (`DnsResource` + provider adapters; SecretBroker
consolidation on systemd credentials).

---

# Agent Distribution Plan

Keep the agent runtime and model artifacts **independently installable**: APT
ships the Go daemon (`libs/nostrhost-agent`) + service integration; Hugging
Face Hub is the later home for validated model artifacts; the platform must run
without a Hugging Face account when the operator supplies a local
OpenAI-compatible endpoint. **The current LoRA adapter is rejected** (22
independent episodes; 3/17 on the frozen regression suite) — do not publish or
ship it. Full detail: `docs/AGENT-DISTRIBUTION-PLAN.md`.

| Phase | Scope | Status |
|---|---|---|
| 1 | Daemon packaging — systemd unit (unprivileged `nostrhost-agent`, hardening, SIGTERM-clean), first-run disabled until operator config, secret handoff with the strict config loader, private audit/state dir, build + VM checks | ⏳ |
| 2 | APT package — `golang` entry in `packaging/packages.yml`, staging rules, upgrade/remove/disabled-behaviour VM acceptance on a review branch (publishing `main` is a publication action) | ⏳ |
| 3 | Model artifacts on Hugging Face — only after a candidate passes the training-regime gates; hash-verified GGUF, no pickles, no embedded tokens | ⏳ blocked on a candidate |
| 4 | "NostrHost Agent Lab" HF Space — synthetic/public-safe evaluation UI only; never dispatches operations; reproducible pinned-input reports | ⏳ |

Gates: restore `nostrhost-clean6` access and verify core `12.1.41.28` before
package acceptance; continue independent episode collection; no model release
until corpus/holdout/regression/safety/license gates pass. The APT package and
Space are independent of model training.

---

# Resource Engine Cutover Plan

The resource engine describes and reconciles a native package but is not yet
the sole application-lifecycle authority. The cutover establishes one owner per
concern, connects the engine to the NostrHost planes, then retires
compatibility code only after the replacement is proven. Full detail:
`docs/RESOURCE-ENGINE-CUTOVER.md`.

Target authority is deliberately separated: catalogue decides trust; identity
decides actor + compatibility projection; policy decides whether a plan may
apply (resource ownership, risk, approval, restore); the control plane
transports the signed chain; the resource engine owns package desired state
and provider execution; Restic owns data recovery.

| Step | Scope | Status |
|---|---|---|
| 1 | Canonical native package-coordinate/plan envelope shared by catalog, policy, control, state (`package.plan` schema-versioned envelope with `plan_sha256`; `package.reconcile` verifies the digest) | ✅ |
| 2 | Policy-aware executor adapter in `nostr_operationsd`; remove direct `native_providers()` construction from request handlers | ✅ (policy/approval seam live; provider construction is inside the executor backend) |
| 3 | Pre/post state + Restic linkage around native reconciliation | ◑ | native reconciliation classified data-affecting + plan digest carried; **remaining: link the policy-selected Restic snapshot into the native plan result** |
| 4 | Wire Admin + catalogue install to native plans (legacy path retained for non-native packages) | ⏳ |
| 5 | Migrate representative packages; publish native/legacy inventory | ⏳ |
| 6 | Disable legacy lifecycle scripts for native packages; retire helpers + fallback catalog sources by domain | ⏳ |

Removal gates (all must hold): native plan/reconcile pass in a clean test root;
trusted architecture-specific catalogue declaration; policy evaluates the full
plan and records approval; control-plane executor applies and verifies;
pre/post state + required data snapshots linked; restore/rollback exercised;
Portal/Admin show identical package + operation state; no remaining supported
package imports the retired helper surface. Until then, the old path stays an
explicitly labelled compatibility adapter, never an implicit fallback.

---

# Release Milestones

## 0.1 - Native Nostr Identity

```text
✓ forked Portal
✓ control plane standing (local relay + event model)
✓ identity events + projection (npub ↔ YunoHost mapping via relay)
✓ native Nostr login           (passwordless; browser-proven on the testbed)
✓ NIP-07
✓ NIP-46                        (local bunker; SSO CSP allows ws relay)
✓ passkeys                      (UI + unlock path; WebAuthn attestation pending a real browser)
✓ native session creation       (passwordless yunohost.portal cookie)
✓ existing YunoHost apps work
✓ password recovery remains available
```

This is the first useful derivative release. The identity half of the
milestone is proven; the login/session half is the §8 portal work.

## 0.2 - Policy and Agents

```text
✓ capability / delegation events        (capability grants + formal delegations)
✓ agents
✓ relay-mediated approval + execution events
✓ NIP-46 privileged approvals
✓ MCP adapter integrated with the control plane
✓ audit = signed event chain (with derived index/read model)
```

Achieved in substance on the testbed (capabilities, agents, the full signed
operation chain, formal delegations, NIP-46 remote-signed approvals, and the
protocol-neutral MCP adapter that submits and correlates native operations.

## 0.3 - State History and Recovery Foundation

```text
✓ structured operation executor
✓ operation state machine
✓ semantic state exporter                     (Stage A)
✓ ngit / NIP-34-backed state repository       (Stage A)
✓ server-npub repository ownership/discovery  (Stage A: announce kind 30617)
✓ automatic pre/post state snapshots          (Stage A)
✓ Nostr operation provenance (commits linked to operation events)   (Stage A)
✓ known-good state markers                    (Stage A)
✓ Restic snapshot linkage                     (Stage A manifest + Stage B client/hook)
✓ semantic diff                               (Stage A)
✓ assisted rollback plan generation            (Stage B: change-class aware)
✓ controlled execution + re-validation        (Stage B: registry-bounded — service.control,
                                               app.remove, restic restore — validated on the
                                               testbed; the restoration gate flows through the
                                               full Nostr policy/approval chain as
                                               `rollback.apply`, milestone 0.3 complete)
```

The first release of this layer stops short of fully automatic reconciliation.

## 0.4 - Native Nostr Catalogue

```text
✓ catalogue sync + trust events            (relay is the local cache — §11)
✓ publisher trust                          (trusted projection default)
✓ CI attestations                          (§11)
✓ catalogue policy input                   (publisher_trusted / ci_attested in policy)
⏳ Admin catalogue UI                      (§10)
⏳ native catalog.list / catalog.publish / catalog.verify operations
                                            (MCP transition Phase 5 backlog)
⏳ application discovery over relays       (native catalog surface)
```

## 0.5 - Web Auth and Application Compatibility

```text
✓ Caddy forward_auth → authd enforcement (SSOwat and nginx retired; §12,
  CADDY-MIGRATION P0–P6 on the VM)
✓ compatibility headers (X-Remote-* and linked X-Nostr-* headers emitted by
  the authd for Caddy-protected routes)
◑ OIDC provider (discovery/JWKS/authorization-code bridge and userinfo are live and VM-proven; client-management and signing-key rotation deferred)
◑ residual nginx/SSO reference cleanup (Caddy P7 — §20)
```

## 1.0 - Native Distribution

```text
✓ identity native
✓ policy native
◑ catalogue native                        (trusted projection ✓; native catalog.* ops ⏳)
✓ MCP native (adapter)                    (adapter ✅; transition Phases 5–8 ⏳)
✓ Nostr approvals native
◑ state native                            (ngit / NIP-34 repo + assisted rollback ✓; Stage C DR ◑)
◑ OIDC compatibility                      (deferred after the VM-proven bridge)
⏳ `_ynh` bridge packages no longer required
⏳ tested derivative upgrade path
⏳ release repository and installer
⏳ native postinstall --new / --restore   (alpha W2 — §19)
⏳ end-to-end native app lifecycle         (alpha W3 — §21)
```

## 1.1 - Platform Simplification (Native Messaging, Mail Retirement, Host Security)

```text
✓ native notification service (encrypted Nostr messaging for alerts/approvals/results) — nostrhost-notify merged to nostrhost-control main, deployed, e2e verified (login-401 ban → critical 2213 → NIP-17/NIP-59 DM)
⏳ mail-server installation optional rather than default
⏳ new users do not require a local mailbox
✓ CrowdSec adopted (fail2ban retired); bouncer-nftables integrated — CROWDSEC-MIGRATION P4–P6
✓ security events feed the control plane and generate encrypted Nostr DMs (kind-2213 → nostrhost-notify → NIP-17/NIP-59, recurring-critical proven)
◑ security state participates in nostrhost-state (intrusion-protection.toml + security.json); notification policy/recipients state wiring landed (§18.6 follow-up ✅); digest-cadence default decision open
```

**Follow-ups** (2026-09-11 — all four landed, verified on the testbed):

- ✅ **State wiring (§18.6):** `state/notifications/{policy,recipients}.toml` now renders into `nostrhost-state` via `export_state` (`Backend.notifications()`, raw TOML preserved verbatim so go-toml keeps parsing the `[[recipient]]`/`[[rule]]` arrays) and is committed to the state repo (git history, backups, restore).
- ✅ **Mail phase 2 sources:** certificate (`certificate.py`) and diagnosis (`diagnosis.py`, the auto-diagnosis cron) already publish kind-2210 notices; backup/cron outcomes are covered through the operation chain (kind-2204, class `operation`) once the policy declares it. The notify policy now declares all classes.
- ✅ **Operation-chain notifications:** `approval` (kind-2200) and `operation` (kind-2204) classes added to the policy; verified live — a 2200 produced `[approval/warning] approval required: system.upgrade` and a failed 2204 produced `[operation/warning] operation failed`, both delivered as NIP-17 DMs.
- ✅ **Real outbound relays:** `outbound_relays` now includes `wss://nos.lol` (a NIP-17-friendly relay that indexes gift-wraps by `p` tag) alongside the testbed loopback relay; a live security DM was delivered to nos.lol and unwrapped with the operator key. Note: `relay.damus.io` accepts kind-1059 events but does not index/return them via `#p` — not NIP-17-usable for DM discovery.

See §18 for the full design.

---

# Proposed Shared Architecture

```text
                    External Nostr
                         │
        outbound publisher (catalogue / software / CI / ngit events;
        no inbound public relay port required for normal operation)
                         │
                         ▼
                  NostrHost Relay        ← LOCAL control plane, private by default
                         │                (event store + bus)
         ┌───────────────┼───────────────┐
      Identity        Policy         Operations
      projector      evaluator        engine
         │               │               │
         └───────┬───────┴────────┬──────┘
                 │                │
          nostrhost-state    Control executor   ← single writer to the engine
          (ngit / NIP-34)         │
                 │                ▼
            Git objects    YunoHost service layer
            desired state          │
                 │          ┌──────┼───────┐
                 ▼          Portal  Admin   MCP   CLI   ← relay clients
            reconciler
                 │
     executor │ Restic │ outbound publisher ──► external Nostr relays
```

Caddy is the web/TLS enforcement point (see `CADDY-MIGRATION.md`, and
`CONTROL-PLANE.md` §5): session + identity state is *projected from relay
events* before policy evaluation allows or denies the application request.

```text
request → Caddy → forward_auth → authd → policy engine → ALLOW / DENY
                                                                   ↓
                                                             application
```

---

# Key Architectural Principles

1. **Keep YunoHost's mature server-management functionality; YunoHost itself
   becomes a compatibility and migration source, not the platform goal.**
2. **Make the local Nostr relay the control-plane bus.** The event schema is
   the internal control-plane API: identity, delegation, approval, execution,
   catalogue and audit state flow as signed events; interfaces are relay
   clients, not owners of bespoke point-to-point APIs.
3. **Make Nostr the canonical external identity layer.**
4. **Keep LDAP initially as an internal compatibility mechanism, projected
   from identity events.**
5. **Use one policy engine across Admin, MCP, Portal and SSO** — computation
   stays in the evaluator; roles/scopes/delegation *storage* moves to relay
   events.
6. **Treat humans, agents and services as cryptographic identities.**
7. **Use NIP-46 approvals for privileged or high-risk actions**, mediated by
   the relay (request event → signed approval event → executor).
8. **Keep sessions, CSRF and challenge state in the local HTTP subsystem, not
   in the event stream.**
9. **Use standard Nostr primitives wherever possible; treat the relay as a
   commodity component.** NIP-42/44/51/65/66/77/78/86/89/98 before custom
   kinds; use an existing relay implementation; NostrHost owns the event
   model and the validation, retention, access and bridging policy.
10. **Make Nostr Catalog a native catalogue and trust provider, not a
    replacement app installer** — the relay is the local cache; catalogue
    logic remains.
11. **Keep existing `_ynh` implementations usable on stock YunoHost.**
12. **Replace integration workarounds only after equivalent native interfaces
    exist.**
13. **Maintain a bootable, usable derivative at every stage.**
14. **Use ngit / NIP-34 for durable semantic configuration state** so
    repository identity aligns with Nostr identities.
15. **Keep repository authority separate from operational authority:** all
    applied state still passes through NostrHost policy.
16. **Use Restic for data backup and link data snapshots to
    configuration-state restore points.**
17. **Keep the NostrHost relay private by default and publish public events
    outbound to multiple external relays.**
18. **Delay full declarative reconciliation until identity, policy, execution
    and state history have been proven.**
19. **Caddy is the web/TLS layer and the authentication enforcement point** —
    nginx and SSOwat are retired, not reduced (§12, §20).
20. **Bootstrap and restore are first-class install modes** — `--new` and
    `--restore` reconstruct the machine from identity + ngit state + Restic
    (§19).
21. **Make the native/compatibility boundary explicit and shrink it
    measurably**, with behavioural equivalence as the migration gate (§22–§24).
22. **DNS, secrets and the platform's own update are first-class native
    resources**, not Bash helpers (§17.1, §26, §27).

---

# End State

The target is not "YunoHost with Nostr added".

It is:

> A Nostr-native Debian-based self-hosting platform derived from YunoHost.
> Nostr provides its native identity, authority, control, software-trust and
> audit layers. Applications are managed through declarative resources and
> bounded execution, Caddy provides the web and TLS layer, CrowdSec provides
> intrusion detection, and ngit plus Restic provide state and data recovery.
> YunoHost compatibility is retained temporarily for existing applications
> and selected mature Linux-management functionality.

Nostr provides:

```text
identity
authentication
delegation
agent access
approvals
software discovery
publisher trust
attestations
remote administration
repository identity and state provenance through ngit / NIP-34
outbound publication to external relays
```

NostrHost natively provides:

```text
application lifecycle (declarative package.toml resources + bounded execution)
domains
web serving + automatic TLS (Caddy)
CrowdSec intrusion detection + security events
configuration state (ngit / NIP-34) + data recovery (Restic)
services
system administration
Debian integration
```

YunoHost compatibility is retained temporarily for:

```text
legacy manifests and Bash lifecycle scripts
remaining LDAP projection
selected mature Linux-management functionality
```

The existing `yunohost-nostr-auth`, Nostr Catalog and `yunohost-mcp` projects
form the working reference implementation and migration base for the
derivative. See `docs/STATELAYER.md` for the state-layer design source and
`docs/CONTROL-PLANE.md` for the control-plane specification.
