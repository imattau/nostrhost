# Nostr-Native YunoHost Derivative
## Fork-to-Implementation Roadmap

### Objective

Build a Nostr-native YunoHost derivative that keeps YunoHost's mature server-management engine, but replaces or reworks the identity, catalogue, authorisation, administration and remote-control layers around it.

The target is not a complete rewrite of YunoHost. The aim is to retain the proven machinery for:

- application installation, removal and upgrades
- domains
- Nginx configuration
- certificates
- backups
- services
- firewall
- diagnosis
- Debian packaging
- user/group compatibility

while making Nostr the primary control-plane technology for:

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
is hardened into three roles — `server_sk` (machine key, signs execution
results), `operator_sk` (primary admin, signs approvals/capabilities), and an
`admins` list — via root-only `nostrhost-bootstrap`.

---

# 5. Consolidate Authorisation: Capability / Delegation Events — ◑

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
allowlisting is granted via NIP-86 `allowpubkey` (NIP-98-signed). **Partial:**
formal delegation events (NIP-26-style or custom) are not yet a first-class
mechanism; evaluate Casbin migration when this phase completes.

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

# 7. Introduce `nostrhost-state` with ngit / NIP-34 — ⏳ NEXT

This is the correct point to introduce durable configuration-state management.
Identity, policy and execution semantics (§4–§6) now exist, so state history
can become authoritative enough to support rollback and reconciliation.

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

The repository describes intent (`nginx should be enabled`), not runtime
observation (`nginx is running`). Runtime truth belongs to Linux/systemd.
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
Only once the state schema and executor are proven should merged desired-state
changes be automatically reconciled. Avoid Kubernetes-like complexity: a
single-server NostrHost installation has one straightforward reconciliation
process.

---

# 8. Portal Nostr Authentication + Native Session — ⏳

Retain the existing Nuxt/Vue/TypeScript portal stack.

Move the existing Nostr-authentication user experience into the portal fork:

```text
/nostr-login
/nostr-account
NIP-07
NIP-46
passkey UI
saved signer management
identity linking
identity revocation
```

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

# 9. Restic Linkage + Known-Good + Assisted Rollback (Stage B) — ⏳

Complete the 0.3 "State History and Recovery Foundation" milestone by moving
from history to restoration:

```text
✓ semantic diff across state history
✓ known-good state markers (health-validated)
✓ Restic snapshot linkage in the state manifest
✓ assisted rollback plan generation (change-class aware)
✓ policy / approval gate on restoration
✓ controlled execution + re-validation
```

This stage remains short of fully automatic reconciliation (Stage D, §17).

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

---

# 11. Make Nostr Catalog Native — ⏳

Introduce a catalogue-provider interface in the YunoHost fork:

```text
LegacyYunoHostCatalogue
NostrCatalogue
```

Initially support both; later `NostrCatalogue = default`. The Nostr provider
handles relay queries, package events, publisher signatures, CI attestations,
trust policy, architecture and YunoHost-version compatibility, and repository
resolution. Once a package source is resolved, continue using the existing
YunoHost application installer — do not rewrite the installation engine.

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

# 12. SSO Simplification — ⏳

Do not attempt this early. Once identity and policy are stable, move
authentication enforcement towards:

```text
NGINX
  ↓
auth_request
  ↓
nostrhost-authd (auth daemon)
  ↓
identity resolution
  ↓
policy
```

The authentication daemon returns compatibility headers such as
`X-Remote-User`, `X-Remote-Email`, `X-Nostr-Pubkey`, `X-Nostr-Npub` so existing
YunoHost applications continue receiving the headers they expect.

Long-term goal: reduce `nostrhost-ssowat` to primarily NGINX configuration,
session validation, auth_request integration and compatibility headers rather
than maintaining a substantial Lua-based authentication implementation.

---

# 13. MCP Adapter — ⏳

MCP becomes another interface to the same internal service layer, not an
owner of bespoke integration:

```text
                YunoHost service layer
                   ↑      ↑      ↑
                   │      │      │
                 Admin   MCP   CLI
```

Under the control-plane architecture, MCP becomes an **adapter**: it keeps the
MCP protocol, tool definitions, package-development tools, diagnostics
presentation, and NIP-98 client authentication, but behind the tools it
publishes signed operation-request events to the local relay and subscribes to
approval/execution/result events (§3). Its bespoke identity database, approval
workflow, delegation state, audit history and command queue move out to the
relay event stream. Remove duplicated YunoHost integration code as equivalent
native APIs are introduced.

---

# 14. OIDC Compatibility — ⏳

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

# 15. ngit Replication / Disaster Recovery (Stage C) — ⏳

Publish relevant NIP-34 repository events outbound through the private relay
to multiple external relays so the configuration-state history is recoverable
off-box. Combined with Restic data snapshots (§9), this completes the
disaster-recovery story from §7.6: identity, state and data are each
retrievable, and the machine can be reconstructed rather than merely
restored. Git object storage uses ordinary Git/GRASP-style storage; no central
forge becomes authoritative.

---

# 16. Declarative Reconciliation (Stage D) — ⏳

Only once the state schema and executor are proven (§6–§7) should merged
desired-state changes be automatically reconciled. Avoid Kubernetes-like
complexity: a single-server NostrHost installation has one straightforward
reconciliation process, still routed through `nostrhost-policy` (§7.8) — a
valid repository change never bypasses policy.

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
4.  Capability / delegation events                          ◑
5.  Approval + execution events (structured ops + state machine) ✅
6.  nostrhost-state Stage A            (ngit / NIP-34)      ⏳  ← NEXT
7.  Portal Nostr authentication (+ native session creation) ⏳
8.  Restic linkage + known-good + assisted rollback (Stage B) ⏳
9.  Admin interface                                         ⏳
10. Native catalogue (sync + trust events)                  ⏳
11. SSO simplification                                      ⏳
12. MCP adapter                                             ⏳
13. OIDC                                                    ⏳
14. ngit replication / disaster recovery (Stage C)          ⏳
15. Declarative reconciliation (Stage D)                    ⏳
16. Distribution release                                    ⏳
```

Do not begin by rewriting SSOwat or rebuilding the admin interface. Stand up
the control plane and get identity events + projection working first — done —
then prove execution (§5–§6, done), then build the state-history layer (§7)
before the portal. Portal authentication follows on top of identity events
and native session creation.

---

# Release Milestones

## 0.1 - Native Nostr Identity

```text
✓ forked Portal
✓ control plane standing (local relay + event model)
✓ identity events + projection (npub ↔ YunoHost mapping via relay)
⏳ native Nostr login
⏳ NIP-07
⏳ NIP-46
⏳ passkeys
⏳ native session creation
✓ existing YunoHost apps work
✓ password recovery remains available
```

This is the first useful derivative release. The identity half of the
milestone is proven; the login/session half is the §8 portal work.

## 0.2 - Policy and Agents

```text
✓ capability / delegation events        (capability grants; delegations ◑)
✓ agents
✓ relay-mediated approval + execution events
⏳ NIP-46 privileged approvals
⏳ MCP adapter integrated with the control plane
✓ audit = signed event chain (with derived index/read model)
```

Achieved in substance on the testbed (capabilities, agents, the full signed
operation chain, audit as event chain); remaining: formal delegation events
and NIP-46 privileged approvals.

## 0.3 - State History and Recovery Foundation

```text
✓ structured operation executor
✓ operation state machine
⏳ semantic state exporter
⏳ ngit / NIP-34-backed state repository
⏳ server-npub repository ownership/discovery
⏳ automatic pre/post state snapshots
⏳ Nostr operation provenance (commits linked to operation events)
⏳ known-good state markers
⏳ Restic snapshot linkage
⏳ semantic diff
⏳ assisted rollback plan generation
```

The first release of this layer stops short of fully automatic reconciliation.

## 0.4 - Native Nostr Catalogue

```text
⏳ catalogue sync + trust events (relay is the local cache)
⏳ publisher trust
⏳ CI attestations
⏳ catalogue policy
⏳ Admin catalogue UI
⏳ application discovery over relays
```

## 0.5 - SSO and Application Compatibility

```text
⏳ NGINX auth_request
⏳ reduced/simplified SSOwat
⏳ compatibility headers
⏳ OIDC provider
```

## 1.0 - Native Distribution

```text
✓ identity native
✓ policy native
⏳ catalogue native
✓ MCP native (adapter)                    (adapter ◑)
✓ Nostr approvals native
⏳ state native (ngit / NIP-34 repo + assisted rollback + DR)
⏳ OIDC compatibility
⏳ `_ynh` bridge packages no longer required
⏳ tested derivative upgrade path
⏳ release repository and installer
```

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

NGINX becomes primarily an enforcement point (see `CONTROL-PLANE.md` §5):
session + identity state is *projected from relay events* before policy
evaluation allows or denies the application request.

```text
request → NGINX → auth_request → identityd → policy engine → ALLOW / DENY
                                                                   ↓
                                                             application
```

---

# Key Architectural Principles

1. **Keep YunoHost's proven server-management engine.**
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

---

# End State

The target is not "YunoHost with Nostr added".

It is:

> A Nostr-native self-hosting platform built on YunoHost's mature server-management engine.

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

YunoHost continues to provide:

```text
application lifecycle
domains
certificates
backups
services
Nginx
system administration
Debian integration
```

The existing `yunohost-nostr-auth`, Nostr Catalog and `yunohost-mcp` projects
form the working reference implementation and migration base for the
derivative. See `docs/STATELAYER.md` for the state-layer design source and
`docs/CONTROL-PLANE.md` for the control-plane specification.