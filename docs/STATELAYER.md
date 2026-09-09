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


## Architectural Control and State Layers

NostrHost should separate control, configuration state, data recovery and runtime truth.

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

The NostrHost relay remains private/local by default. It acts as the local system event bus and publication staging point. Public catalogue, software, CI and ngit events are published outbound to multiple configured external relays. Private identity, policy and control events remain local-only.

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

# 1. Fork Baseline

Create an umbrella repository, for example:

```text
nostr-yunohost/
```

This repository owns:

- architecture
- integration tests
- dependency/version pins
- release tooling
- packaging metadata
- derivative documentation

Fork the main upstream components:

```text
YunoHost/yunohost
    -> imattau/yunohost-nostr

YunoHost/yunohost-portal
    -> imattau/yunohost-portal-nostr

YunoHost/yunohost-admin
    -> imattau/yunohost-admin-nostr

YunoHost/SSOwat
    -> imattau/ssowat-nostr
```

Do not change behaviour immediately.

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

Create a reusable authentication/identity library, conceptually:

```text
nostr-yunohost-auth/
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

Create:

```text
nostr-yunohost-policy/
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

Create:

```text
nostr-yunohost-catalog/
```

The existing `_ynh` packages remain operational during this stage.

---

# 3. Make Nostr Identity Native

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

---

# 4. Integrate Nostr Login into the Portal

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

# 5. Replace the Session-Minting Workaround

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

---

# 6. Consolidate Authorisation

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

---

\n# 7. Add Structured Operations and the Operation State Machine\n\nBefore introducing declarative machine state, prove that signed Nostr intent can safely drive YunoHost through a narrow execution boundary.\n\nThe preferred operation model is structured rather than generic shell execution:\n\n```text\nsystem.version\napp.list\nservice.status\napp.install\napp.upgrade\nbackup.create\nservice.restart\n```\n\nA control operation should follow an explicit state machine:\n\n```text\nREQUESTED\n   |\n   +--> REJECTED\n   |\n   +--> APPROVED\n           |\n           v\n       EXECUTING\n           |\n      +----+----+\n      |         |\n SUCCEEDED    FAILED\n```\n\nThe executor must enforce semantic transitions, expiry, signer authority, duplicate-execution protection and policy version/state.\n\nThe first end-to-end proof should use a harmless operation such as `system.version`, `app.list` or `service.status`.\n\n---\n\n# 8. Introduce `nostrhost-state` with ngit / NIP-34\n\nThis is the correct point to introduce durable configuration-state management. Identity, policy and execution semantics should already exist before state history becomes authoritative enough to support rollback or reconciliation.\n\nThe state layer should use **ngit / NIP-34 as the Nostr-aligned repository model**, with normal Git objects underneath. Plain Git remains the storage engine, but repository identity, ownership, discovery and signed repository state align with Nostr identities.\n\n## 8.1 Why ngit rather than plain Git alone\n\nPlain Git provides excellent history, diffs, branches, tags and object storage, but NostrHost would otherwise need a separate layer to answer:\n\n```text\nWho owns this state repository?\nWho may publish authoritative refs?\nHow is the repository discovered?\nWho proposed a change?\nHow does repository authority map to npubs?\n```\n\nWith ngit / NIP-34, those concepts remain in the same cryptographic identity namespace as the rest of NostrHost.\n\n```text\nServer npub\n    |\n    v\nNIP-34 repository announcement\n    |\n    v\nnostrhost-state\n    |\n    +--> signed repository state\n    +--> PRs / patches\n    +--> CI results\n    |\n    v\nGit objects\n```\n\nA server can therefore have a naturally discoverable state repository such as:\n\n```text\nnostr://<server-npub>/nostrhost-state\n```\n\nThe server identity and its durable state history remain linked without inventing a second identity system.\n\n## 8.2 State is semantic, not a copy of `/etc`\n\nDo not indiscriminately version the filesystem. Store NostrHost's semantic desired configuration.\n\nRecommended structure:\n\n```text\nstate/\n├── manifest.toml\n├── system/\n├── apps/\n├── domains/\n├── services/\n├── network/\n├── dns/\n├── certificates/\n├── identities/\n├── capabilities/\n├── backups/\n├── schedules/\n└── package-versions/\n```\n\nThe repository should describe intent:\n\n```text\nnginx should be enabled\n```\n\nnot runtime observation:\n\n```text\nnginx is running\n```\n\nRuntime truth belongs to Linux/systemd.\n\nSecrets must not be stored in plaintext. State should reference secret identifiers backed by systemd credentials, age/SOPS or another dedicated encrypted secret store.\n\n## 8.3 Automatic pre/post state history\n\nThe first implementation should be deliberately simple. Every meaningful configuration change creates before and after snapshots.\n\n```text\noperation request\n      |\n      v\npre-change semantic snapshot\n      |\n      v\nexecute operation\n      |\n      v\npost-change semantic snapshot\n      |\n      v\nhealth validation\n```\n\nExample history:\n\n```text\nA  known-good state\nB  install Alby Hub\nC  reverse-proxy change\nD  permission update\n```\n\nEach state change should be linked to the Nostr operation event that caused it.\n\n## 8.4 Link configuration state to Restic data snapshots\n\nGit/ngit is configuration-state history, not a replacement for data backup. Restic should remain the data recovery system.\n\nFor operations that can affect application data:\n\n```text\npre-change state commit S1\n        |\n        +--> Restic snapshot R1\n        |\n        v\nexecute\n        |\n        v\nhealth check\n```\n\nA machine-readable state manifest can record the relationship:\n\n```toml\n[state]\nschema = 1\nknown_good = true\n\n[operation]\nevent = "<nostr-event-id>"\n\n[backup]\nrestic_snapshot = "<snapshot-id>"\nrequired = true\n\n[health]\nresult = "passed"\n```\n\nThis creates a restore point that describes both configuration and associated data.\n\n## 8.5 Known-good state and assisted rollback\n\nNostrHost should maintain the concept of a validated known-good state.\n\n```text\nmain       -> current desired state\nknown-good -> latest health-validated state\nprevious   -> previous accepted state\n```\n\nRollback should be orchestrated, not treated as a blind `git revert`. Different changes have different reversibility.\n\n| Change class | Example | Automatic rollback |\n|---|---|---:|\n| Declarative config | firewall rule, service enabled | Usually |\n| Runtime setting | systemd unit state | Usually |\n| Package install | new app | Often |\n| Package upgrade | 1.4 to 1.5 | Conditional |\n| Database migration | schema change | Only with known procedure/backup |\n| Data deletion | app removal | Restore required |\n| External side effect | DNS API, payment, external message | Often impossible |\n| Credential rotation | replace key | Special handling |\n\nThe first rollback UX should be assisted:\n\n```text\nselect previous state\n      |\n      v\nshow semantic diff\n      |\n      v\ngenerate rollback plan\n      |\n      v\npolicy / approval\n      |\n      v\nexecute\n      |\n      v\nhealth check\n```\n\n## 8.6 Disaster recovery and machine reconstruction\n\nA failed server should be recoverable from identity, state and data.\n\n```text\nnew machine\n    |\ninstall NostrHost\n    |\nrestore / authorise server identity\n    |\ndiscover NIP-34 state repository\n    |\nretrieve latest known-good state\n    |\nretrieve linked Restic snapshot\n    |\ninstall required apps/packages\n    |\nrestore application data\n    |\nreconcile configuration\n    |\nvalidate\n```\n\nThe goal is not merely to restore files. It is to reconstruct what the machine was.\n\n## 8.7 Human and agent changes through NIP-34\n\nAgents should be able to propose state changes without receiving root access.\n\n```text\nAgent npub\n   |\nbranch / patch\n   |\nNIP-34 proposal / PR\n   |\nCI validation\n   |\nhuman review if required\n   |\nmerge\n   |\nNostrHost policy\n   |\nreconciliation / execution\n```\n\nCI can validate:\n\n```text\nschema\npolicy\nDNS\ndependencies\nsecurity constraints\nsimulated reconciliation\n```\n\nSigned CI results can be published as Nostr events associated with repository coordinates and commits.\n\n## 8.8 Repository authority is not operational authority\n\nA valid repository change must never bypass `nostrhost-policy`.\n\n```text\nNIP-34 change\n     |\nverify repository authority\n     |\nNostrHost policy\n     |\nrisk classification\n     |\napproval if required\n     |\nexecutor / reconciler\n```\n\nngit establishes repository identity and state provenance. `nostrhost-policy` decides whether that state may actually be applied to the machine.\n\n## 8.9 Stage the implementation\n\nDo not introduce full GitOps-style reconciliation immediately.\n\n### Stage A: state history\n\n```text\noperation\n  |\nsnapshot\n  |\nexecute\n  |\nsnapshot\n  |\nhealth result\n```\n\nImplement first:\n\n1. Export semantic configuration.\n2. Commit pre/post states through the ngit-backed repository.\n3. Link commits to Nostr operation IDs.\n4. Mark known-good states.\n5. Link Restic snapshots where required.\n6. Produce semantic diffs.\n\n### Stage B: assisted rollback\n\nAdd rollback-plan generation, policy evaluation and controlled restoration.\n\n### Stage C: ngit replication and recovery\n\nPublish relevant NIP-34 repository events outbound through the private NostrHost relay to multiple external relays. Git object storage can use ordinary Git/GRASP-style storage without making a central forge authoritative.\n\n### Stage D: declarative reconciliation\n\nOnly once the state schema and executor are proven should merged desired-state changes be automatically reconciled.\n\nAvoid Kubernetes-like complexity. A single-server NostrHost installation should have one straightforward reconciliation process.\n\n---\n
# 9. Fork and Extend the Admin Interface

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

# 10. Replace or Reduce SSOwat Authentication Logic

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

Reduce `ssowat-nostr` to primarily:

```text
NGINX configuration
session validation
auth_request integration
compatibility headers
```

rather than maintaining a substantial Lua-based authentication implementation.

---

# 11. Make Nostr Catalog Native

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

---

# 12. Integrate Catalogue Trust with Policy

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

# 13. Make MCP a Native Interface

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

---

# 14. Add OIDC Compatibility

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

# 15. Retire Transitional `_ynh` Packages

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

# 16. Distribution and Release Tooling

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

The order matters.

```text
Fork baseline
   ↓
Extract existing libraries
   ↓
Native identity API
   ↓
Portal Nostr login
   ↓
Native session creation
   ↓
Unified policy engine
   ↓
Structured executor + operation state machine
   ↓
nostrhost-state Stage A
semantic pre/post snapshots via ngit / NIP-34
   ↓
Restic snapshot linkage + known-good state  (Stage B: client + hook done)
   ↓
Assisted rollback                            (Stage B: plan + gate done)
   ↓
Admin integration
   ↓
Native catalogue
   ↓
SSO replacement
   ↓
Native MCP
   ↓
OIDC
   ↓
ngit replication / disaster recovery
   ↓
Declarative reconciliation
   ↓
Distribution release
```

Do not begin by rewriting SSOwat or rebuilding the admin interface.

Get native identity and login working first.

---

# Release Milestones

## 0.1 - Native Nostr Identity

```text
✓ forked Portal
✓ native Nostr login
✓ NIP-07
✓ NIP-46
✓ passkeys
✓ npub ↔ YunoHost user mapping
✓ native session creation
✓ existing YunoHost apps work
✓ password recovery remains available
```

This is the first useful derivative release.

## 0.2 - Policy and Agents

```text
✓ unified roles/scopes
✓ agents
✓ delegations
✓ NIP-46 privileged approvals
✓ MCP integrated with common policy
✓ unified audit model
```


## 0.3 - State History and Recovery Foundation

```text
✓ structured operation executor
✓ operation state machine
✓ semantic state exporter
✓ ngit / NIP-34-backed state repository
✓ server-npub repository ownership/discovery
✓ automatic pre/post state snapshots
✓ Nostr operation provenance
✓ known-good state markers
✓ Restic snapshot linkage
✓ semantic diff
✓ assisted rollback plan generation
```

The first release of this layer should stop short of fully automatic reconciliation.

## 0.4 - Native Nostr Catalogue

```text
✓ Nostr Catalog built in
✓ publisher trust
✓ CI attestations
✓ catalogue policy
✓ Admin catalogue UI
✓ application discovery over relays
```

## 0.5 - SSO and Application Compatibility

```text
✓ NGINX auth_request
✓ reduced/replaced SSOwat
✓ compatibility headers
✓ OIDC provider
```

## 1.0 - Native Distribution

```text
✓ identity native
✓ policy native
✓ catalogue native
✓ MCP native
✓ Nostr approvals native
✓ OIDC compatibility
✓ `_ynh` bridge packages no longer required
✓ tested derivative upgrade path
✓ release repository and installer
```

---

# Proposed Shared Architecture

```text
                     Nostr identities
                            │
                    private local relay
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
       identity           policy          operations
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
                      nostrhost-state
                            │
                       ngit / NIP-34
                            │
                       Git objects
                            │
                     desired state
                            │
                            ▼
                       reconciler
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
       executor           Restic          publisher
          │                 │                 │
          ▼                 ▼                 └──> external Nostr relays
    YunoHost / Linux       data
          ↑
    ┌─────┼─────┐
    │     │     │
 Portal  Admin  MCP
```

NGINX becomes primarily an enforcement point:

```text
request
   ↓
NGINX
   ↓ auth_request
identityd
   ↓
policy engine
   ↓
ALLOW / DENY
   ↓
application
```

---

# Key Architectural Principles

1. **Keep YunoHost's proven server-management engine.**
2. **Make Nostr the canonical external identity layer.**
3. **Keep LDAP initially as an internal compatibility mechanism.**
4. **Use one policy engine across Admin, MCP, Portal and SSO.**
5. **Treat humans, agents and services as cryptographic identities.**
6. **Use NIP-46 approvals for privileged or high-risk actions.**
7. **Make Nostr Catalog a native catalogue and trust provider, not a replacement app installer.**
8. **Keep existing `_ynh` implementations usable on stock YunoHost.**
9. **Replace integration workarounds only after equivalent native interfaces exist.**
10. **Maintain a bootable, usable derivative at every stage.**
11. **Use ngit / NIP-34 for durable semantic configuration state so repository identity aligns with Nostr identities.**
12. **Keep repository authority separate from operational authority: all applied state still passes through NostrHost policy.**
13. **Use Restic for data backup and link data snapshots to configuration-state restore points.**
14. **Keep the NostrHost relay private by default and publish public events outbound to multiple external relays.**
15. **Delay full declarative reconciliation until identity, policy, execution and state history have been proven.**

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

The existing `yunohost-nostr-auth`, Nostr Catalog and `yunohost-mcp` projects form the working reference implementation and migration base for the derivative.
