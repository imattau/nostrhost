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

# 7. Fork and Extend the Admin Interface

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

# 8. Replace or Reduce SSOwat Authentication Logic

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

# 9. Make Nostr Catalog Native

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

# 10. Integrate Catalogue Trust with Policy

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

# 11. Make MCP a Native Interface

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

# 12. Add OIDC Compatibility

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

# 13. Retire Transitional `_ynh` Packages

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

# 14. Distribution and Release Tooling

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

## 0.3 - Native Nostr Catalogue

```text
✓ Nostr Catalog built in
✓ publisher trust
✓ CI attestations
✓ catalogue policy
✓ Admin catalogue UI
✓ application discovery over relays
```

## 0.4 - SSO and Application Compatibility

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
                     Nostr
                       │
          ┌────────────┴────────────┐
          │                         │
    @nostr/tools / NDK         nostr-sdk
       browser                  backend
          │                         │
          └────────────┬────────────┘
                       ▼
                  identityd
                       │
           ┌───────────┼────────────┐
           │           │            │
        sessions     policy        OIDC
           │           │            │
           └───────────┼────────────┘
                       ▼
                YunoHost service layer
                 ↑       ↑       ↑
                 │       │       │
              Portal   Admin    MCP
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
