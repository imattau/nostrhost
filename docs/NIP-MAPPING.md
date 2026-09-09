# NostrHost component → NIP mapping

> Status: **draft.** This is the Phase-2 design step that must precede any
> custom-kind allocation. It maps each YunoHost / NostrHost control-plane
> component onto existing Nostr primitives and records only the remainder as
> genuine NostrHost functionality. Some rows are marked **to verify** — they
> are proposals, not decisions.

Guiding philosophy (roadmap §3 / `CONTROL-PLANE.md` §2.0):

> NostrHost uses standard Nostr primitives wherever possible and introduces
> custom event kinds only where YunoHost-specific semantics genuinely
> require them.

## 1. Primitive reference

| primitive | what it gives NostrHost |
|---|---|
| **kind 0** (NIP-01) | public user profile |
| **NIP-26** | delegated event signing (agent keys) |
| **NIP-42** (kind 22242) | relay client authentication ("who are you") |
| **NIP-44** | versioned encrypted payloads inside signed events (no forward secrecy) |
| **NIP-51** | lists & sets — public entries in tags, private entries NIP-44-encrypted in content |
| **NIP-65** (kind 10002) | relay list metadata |
| **NIP-66** (kinds 30166/10166) | relay discovery + liveness monitoring |
| **NIP-70** | protected events |
| **NIP-77** | Negentropy sync (client-relay and relay-relay) |
| **NIP-78** (kind 30078 / 78) | application-specific data (relay as "bring your own database"), NIP-42-gated to owner |
| **NIP-86** | relay management API (JSON-RPC over the relay HTTP endpoint, NIP-98 auth) |
| **NIP-89** (31989/31990) + kind 32267 | app-handler discovery + software-application events |
| **NIP-98** (kind 27235) | HTTP request authentication |
| NIP-17 / NIP-59 | encrypted direct messages / gift wrap (admin notifications) |

## 2. Component mapping

| NostrHost / YunoHost surface | existing standard | custom NostrHost | notes |
|---|---|---|---|
| Public user identity & profile | kind 0 | — | portal/account display |
| Account ↔ pubkey mapping (canonical identity) | kind 0 + NIP-65 relay hints | **server-authoritative identity/role events** (addressable) | the server's own admin/agent registry; the mapping LDAP materialises |
| Relay-level access (who may read/write) | NIP-42 + NIP-86 (`allowpubkey`, `allowkind`, `listallowedkinds`, `banpubkey`, `blockip`) | — | loopback plane; no bespoke API-key mechanism |
| Relay administration (name, roles, moderation) | NIP-86 (`changerelayname`, `createrole`, `assignrole`, …) | — | *to verify:* whether NostrHost admin roles reuse NIP-86 roles or need their own |
| Role / capability grants | NIP-86 roles (relay-scoped) | **NostrHost capability events** (addressable, server-authoritative) | policy evaluator reads projected grants |
| Delegation / agent keys | NIP-26 (delegated signing) | **NostrHost delegation events** (if scoping beyond signing is needed) | *to verify:* NIP-26 covers signing delegation; scope grants may need a custom event |
| Trusted publishers / approved repositories / preferred relays | NIP-51 lists (30000 people sets, 30002 relay sets, 10006 blocked relays; private entries NIP-44) | — | security-critical server policy gets strict NostrHost semantics on top, not raw list-as-authority |
| User/portal preferences & non-sensitive config | NIP-78 (`d = "nostrhost:portal-settings"`, …), NIP-42-gated | — | replaces bespoke settings DB |
| Private control data (approval detail, admin messages) | NIP-44-encrypted content; NIP-17/59 for notification | — | not for private keys/passwords/recovery material (no forward secrecy) |
| Operation request / approval / rejection / execution | — | **YunoHost operation chain** (regular kinds; the audit trail) | genuinely NostrHost semantics |
| Audit log | — | operation chain + derived index/read model | authority = signed events; no bespoke audit DB |
| Catalogue: software discovery | NIP-89 (31989/31990) + kind 32267 software-application; kind 30267 app-curation sets | — | *to verify:* how the existing nostr-yunohost schema (`1100`, `30078–30080`) relates to 32267/30063/30267; possible migration |
| Catalogue: releases / artifacts | kind 30063 release-artifact sets (references kind 1063 file metadata) | — | *to verify* |
| Catalogue: build / CI attestations | — | package attestation events (if 32267/30063/CI standards don't fit) | *to verify* |
| Catalogue: local cache | the local relay + NIP-77 sync | — | bespoke catalogue DB/API redundant |
| Relay discovery for catalogue | NIP-65/66 | — | |
| HTTP authentication of operations (MCP/adapter) | NIP-98 | — | |
| Browser sessions / CSRF / challenges | — | stays in local HTTP subsystem | explicitly NOT relay events |
| SSO enforcement (NGINX `auth_request`) | — | stays (projected identity/policy) | |
| Policy evaluation ("may X do Y on Z") | — | evaluator (extracted `nostrhost-policy`) | computation stays; storage moves to events |
| LDAP | — | stays initially as compatibility projection | |
| YunoHost machine-state (apps, domains, backups, services, firewall, nginx, system) | — | stays as executor | intent via events only |

## 3. Custom kind surface (current best estimate)

After the mapping, NostrHost-only kinds are small:

- server-authoritative identity/role/capability definitions (addressable)
- NostrHost delegation events (only if NIP-26 + capability events are insufficient)
- YunoHost operation request / approval / rejection / execution-result (regular; the audit chain)
- package attestation (only if 32267/30063/CI standards don't fit)
- system / service / backup / security events (regular)

## 4. Open questions to resolve at Phase 2

1. **NIP-86 roles vs NostrHost roles.** Does `assignrole`/`createrole`
   (relay-scoped) carry NostrHost admin roles, or do we need capability
   events on top?
2. **NIP-26 vs delegation events.** Does NIP-26 delegated-signing suffice for
   agents, or do scope-bearing delegation events remain necessary?
3. **Catalogue schema.** Relationship between the existing `nostr-yunohost`
   schema (`1100`, `30078–30080`) and NIP-89/32267/30063/30267; whether to
   migrate or bridge.
4. **Settings placement.** Confirm NIP-78 (`30078`/`78`) on the internal relay
   is acceptable for user settings (single-tenant loopback; NIP-42 owner
   gate).
5. **Audit read model.** Projector/index derived from the operation chain for
   admin reporting (kind/schema not yet chosen).
6. **Custom-kind numbers.** Final allocation only after the above; validated
   against the live NIPs registry and existing catalogue kinds.