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

---

# 1. Fork Baseline

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

This creates a known-good baseline before any Nostr-native changes are introduced.

---

# 2. Extract the Existing Nostr Work

The existing projects should be treated as reference implementations and implementation bases, not discarded prototypes.

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

Create a reusable authentication/identity library (implemented as
`imattau/nostrhost-auth`):

```text
nostrhost-auth/
    python/
    web/
```

The existing standalone implementation should continue working during the migration.

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

Create (implemented as `imattau/nostrhost-policy`):

```text
nostrhost-policy/
```

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

Create (implemented as `imattau/nostrhost-catalog`):

```text
nostrhost-catalog/
```

The existing `_ynh` packages remain operational during this stage.

---

# 3. Control Plane: Internal Relay + Event Model

This is the architecture-defining phase, completed *before* significant fork
modifications begin. It adds a fifth foundational component — `nostrhost-control`,
wrapping an existing relay implementation — and defines the NostrHost event
protocol. No fork behaviour changes in this phase; the four forks remain
pinned and source-identical.

The local Nostr relay becomes the control-plane bus: identity, policy,
approvals, execution, catalogue and audit state all flow as signed events.
Projectors materialise read models (LDAP compatibility, policy state,
catalogue cache) and a control executor is the single writer to the YunoHost
engine. Interfaces (Portal, Admin, MCP, CLI) are relay clients, not owners of
bespoke point-to-point APIs.

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

Phase 2 deliverables:

```text
component → NIP mapping (NIP-MAPPING.md)      ← design gate, done first
event-model specification
kind registry (validated against the live NIPs and the existing
  catalogue kinds 1100 / 30078-30080)
relay backend selection (goss / strfry candidates)
nostrhost-control component: local-only relay config, NIP-86/42 access,
  event validation, per-kind retention, NIP-77 sync, external bridging rules
```

This phase removes (or shrinks to projectors/resolvers) the bespoke approval
service, catalogue database/API, audit database, MCP identity storage and
polling/notification infrastructure that the earlier architecture implied.

---

# 4. Make Nostr Identity Native

This is the first significant modification to the YunoHost fork.

The target identity model is:

```text
npub = canonical external identity
YunoHost username = local compatibility identity
LDAP = compatibility/storage backend
```

LDAP should not be removed initially.

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

Initially, these functions may wrap the mappings and database behaviour already implemented in `yunohost-nostr-auth`.

The important architectural change is that other components stop needing to know where identity originated.

Under the control-plane architecture (roadmap §3), identity is authored as
signed identity/delegation **events** on the local relay and *projected* into
this native API and, for compatibility, into LDAP. The native functions above
become the identity projector's surface rather than owning their own store:
identity is a projection, not a database.

---

# 5. Integrate Nostr Login into the Portal

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

Recommended browser-side Nostr stack:

```text
@nostr/tools
NDK where relay functionality is required
```

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

# 6. Replace the Session-Minting Workaround

The standalone authentication service currently needs special session-minting plumbing because standard YunoHost does not provide a clean passwordless portal-session API.

Once the fork controls the authentication flow, replace this workaround with a native internal API:

```text
create_portal_session(identity)
```

The API should have a clear privilege boundary.

Where possible, remove transitional components such as:

```text
mint_session_server.py
Unix-socket privilege workaround
duplicated portal-cookie implementation
```

This is one of the major benefits of controlling the fork.

Live browser sessions are deliberately **not** carried as Nostr events: short-
lived session tokens, CSRF and challenge state, and the `broker/` Unix-socket
privilege transport stay in the local HTTP subsystem (roadmap §3 /
`CONTROL-PLANE.md` §2.3). The relay records login/link/revoke *notices* only.

---

# 7. Consolidate Authorisation

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

At this point, consider migrating policy evaluation to Casbin.

The same policy engine should serve:

```text
Admin UI
MCP
Portal
SSO
background jobs
```

The goal is one authorisation system, not separate permission logic for each interface.

Under the control-plane architecture, roles, scopes, delegations and policy
declarations are authored as signed **capability/delegation events** on the
local relay (roadmap §3). What remains is the policy **evaluator** — the
computation of "may npub X perform Y on Z" — which keeps its current logic
(Casbin or the extracted `nostrhost-policy` engine) but no longer maintains
its own identity/delegation database: that state is projected from relay
events.

---

# 8. Fork and Extend the Admin Interface

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

Functionality currently handled through configuration files or MCP CLI commands should progressively gain native UI.

---

# 9. Replace or Reduce SSOwat Authentication Logic

Do not attempt this early.

Once identity and policy are stable, move authentication enforcement towards:

```text
NGINX
  ↓
auth_request
  ↓
nostr-yunohost-authd
  ↓
identity resolution
  ↓
policy
```

The authentication daemon should return compatibility headers such as:

```text
X-Remote-User
X-Remote-Email
X-Nostr-Pubkey
X-Nostr-Npub
```

Existing YunoHost applications should continue receiving the headers they expect.

## Long-term goal

Reduce `nostrhost-ssowat` to primarily:

```text
NGINX configuration
session validation
auth_request integration
compatibility headers
```

rather than maintaining a substantial Lua-based authentication implementation.

---

# 10. Make Nostr Catalog Native

Introduce a catalogue-provider interface in the YunoHost fork.

Example providers:

```text
LegacyYunoHostCatalogue
NostrCatalogue
```

Initially support both.

Later:

```text
NostrCatalogue = default
```

The Nostr provider should handle:

```text
relay queries
package events
publisher signatures
CI attestations
trust policy
architecture compatibility
YunoHost version compatibility
repository resolution
```

Once a package source has been resolved, continue using the existing YunoHost application installer.

```text
Nostr Catalogue
      ↓
repository / package source
      ↓
existing YunoHost app installer
```

Do not rewrite the application installation engine.

Under the control-plane architecture, the local relay **is the local
catalogue cache**: a catalogue synchroniser bridges external relays into the
NostrHost relay, and replaceable package/release/attestation events are
subscribed to directly by Admin, the installer, and MCP. The catalogue's
bespoke local database/API server is not needed — only its logic remains:
trust calculation, compatibility checking, repository resolution and
attestation verification (the extracted `nostrhost-catalog` packages).

```text
external relays
     ↓
catalogue synchroniser
     ↓
NostrHost relay          ← the local catalogue cache
     ↓
Admin / installer / MCP
```

---

# 11. Integrate Catalogue Trust with Policy

This is where identity, catalogue and authorisation begin to reinforce one another.

Example flow:

```text
Agent requests app.install
        ↓
catalogue finds package
        ↓
signature valid?
        ↓
trusted publisher?
        ↓
CI attestation valid?
        ↓
policy evaluates operation
        ↓
owner approval required?
        ↓
NIP-46 signature
        ↓
install
```

Policy input could include:

```json
{
  "actor": "npub1...",
  "action": "app.install",
  "package": "ditto",
  "publisher_trusted": true,
  "ci_attested": true,
  "source_signed": true,
  "actor_type": "agent"
}
```

This turns Nostr into part of the software trust and authorisation model rather than merely an authentication mechanism.

---

# 12. Make MCP a Native Interface

The current model:

```text
MCP
 ↓
integration layer
 ↓
YunoHost
```

should gradually become:

```text
                YunoHost service layer
                   ↑      ↑      ↑
                   │      │      │
                 Admin   MCP   CLI
```

MCP becomes another interface to the same internal service layer.

Retain the valuable existing MCP functionality:

```text
NIP-98 authentication
agent keys
delegation
owner co-signatures
audit
MCP protocol
package-development tools
diagnostics
```

Remove duplicated YunoHost integration code as equivalent native APIs are introduced.

Under the control-plane architecture, MCP becomes an **adapter**: it keeps
the MCP protocol, tool definitions, package-development tools, diagnostics
presentation, and NIP-98 client authentication, but behind the tools it
publishes signed operation-request events to the local relay and subscribes
to approval/execution/result events (roadmap §3). Its bespoke identity
database, approval workflow, delegation state, audit history and command
queue move out to the relay event stream.

---

# 13. Add OIDC Compatibility

Once Nostr identity is stable, add a conventional application-authentication bridge.

Recommended approach:

```text
Nostr identity
     ↓
YunoHost identity
     ↓
OIDC provider
     ↓
applications
```

Authlib is a suitable candidate for the OIDC/OAuth layer.

This gives applications a standards-based interface while Nostr remains the underlying authentication and identity system.

Example:

```text
Sign in with Nostr
        ↓
YunoHost
        ↓
OIDC
        ↓
third-party application
```

This may progressively reduce the number of applications requiring YunoHost-specific SSO integration.

---

# 14. Retire Transitional `_ynh` Packages

Only retire packages once their functionality exists natively.

Potentially transitional packages:

```text
nostr_auth_ynh
nostr_catalog_ynh
yunohost-mcp_ynh
```

Keep the repositories available for stock YunoHost.

This provides two supported deployment models.

## Stock YunoHost

```text
nostr_auth_ynh
nostr_catalog_ynh
yunohost-mcp_ynh
```

## Nostr-native derivative

```text
identity built in
catalogue built in
MCP built in
policy built in
```

The current work therefore remains useful even after the derivative exists.

---

# 15. Distribution and Release Tooling

Once the architecture is stable, turn it into a real distribution.

The umbrella repository should manage:

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

The order matters. The internal relay + event model (phase 2) is the
architecture-defining phase and must precede any significant fork
modification; it is purely additive and leaves the forks pinned.

```text
0. Source-identical fork baseline
        ↓
1. Extract proven existing Nostr code
        ↓
2. INTERNAL RELAY + EVENT MODEL          ← control plane (nostrhost-control)
        ↓
3. Identity events + projection
        ↓
4. Portal Nostr authentication (+ native session creation)
        ↓
5. Capability / delegation events
        ↓
6. Approval + execution events
        ↓
7. Admin interface
        ↓
8. MCP adapter
        ↓
9. Catalogue sync + trust events
        ↓
10. SSO simplification
        ↓
11. OIDC
        ↓
12. Distribution release
```

Do not begin by rewriting SSOwat or rebuilding the admin interface.

Stand up the control plane and get identity events + projection working
first; portal authentication follows on top of it.

---

# Release Milestones

## 0.1 - Native Nostr Identity

```text
✓ forked Portal
✓ control plane standing (local relay + event model)
✓ identity events + projection (npub ↔ YunoHost mapping via relay)
✓ native Nostr login
✓ NIP-07
✓ NIP-46
✓ passkeys
✓ native session creation
✓ existing YunoHost apps work
✓ password recovery remains available
```

This is the first useful derivative release.

## 0.2 - Policy and Agents

```text
✓ capability / delegation events
✓ agents
✓ relay-mediated approval + execution events
✓ NIP-46 privileged approvals
✓ MCP adapter integrated with the control plane
✓ audit = signed event chain (with derived index/read model)
```

## 0.3 - Native Nostr Catalogue

```text
✓ catalogue sync + trust events (relay is the local cache)
✓ publisher trust
✓ CI attestations
✓ catalogue policy
✓ Admin catalogue UI
✓ application discovery over relays
```

## 0.4 - SSO and Application Compatibility

```text
✓ NGINX auth_request
✓ reduced/simplified SSOwat
✓ compatibility headers
✓ OIDC provider
```

## 1.0 - Native Distribution

```text
✓ identity native
✓ policy native
✓ catalogue native
✓ MCP native (adapter)
✓ Nostr approvals native
✓ OIDC compatibility
✓ `_ynh` bridge packages no longer required
✓ tested derivative upgrade path
✓ release repository and installer
```

---

# Proposed Shared Architecture

The current shared architecture is the **relay-centric control plane**
(roadmap §3). The full specification — architecture diagrams, event protocol
with kind ranges, relay selection, retention/access/bridging policy, and the
redundancy analysis — lives in `CONTROL-PLANE.md`.

Summary:

```text
                    External Nostr
                         │
                selective sync / bridge
                         │
                         ▼
                  NostrHost Relay        ← LOCAL control plane
                         │                (event store + bus)
         ┌───────────────┼───────────────┐
      Identity        Policy          Catalogue
      projector      evaluator        resolver
         └───────────────┼───────────────┘
                         │
                   Control executor
                         │
                         ▼
                YunoHost service layer
                 ↑       ↑       ↑
                 │       │       │
              Portal   Admin    MCP   CLI    ← relay clients
```

NGINX becomes primarily an enforcement point (see `CONTROL-PLANE.md` §5):
session + identity state is *projected from relay events* before policy
evaluation allows or denies the application request.

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

The existing `yunohost-nostr-auth`, Nostr Catalog and `yunohost-mcp` projects form the working reference implementation and migration base for the derivative.
