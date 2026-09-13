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
| State-repository discovery | NIP-34 (kind 30617 repository announcement, addressable) | — | server-signed; `nostr://<server-npub>/nostrhost-state` |
| State-repository replication / DR | — | **state-bundle chunks** (kind 2214, regular) | Stage C: gzip git bundle split into signed chunks published outbound; reconstructs repo from relays + identity, no central forge |

## 3. Custom kind surface (current best estimate)

After the mapping, NostrHost-only kinds are small:

- server-authoritative identity/role/capability definitions (addressable)
- YunoHost operation request / approval / rejection / execution-result (regular; the audit chain)
- package/CI attestation (no standard fits; supersedes the bespoke `30080`)
- system / service / backup / security events (regular)
- state-bundle replication chunks (kind 2214, regular) — Stage C ngit DR

NostrHost delegation is **NIP-26** (agent signing) + a small capability event
for scope grants; no separate bespoke delegation kind is planned unless that
combination proves insufficient.

## 4. Open questions — resolved at Phase 2

> Status: **resolved.** These decisions are locked into the control-plane
> design and the event protocol (`CONTROL-PLANE.md`, `RELAY-SELECTION.md`,
> `nostrhost-control/EVENT-PROTOCOL.md`).

1. **NIP-86 roles vs NostrHost roles → split.** NIP-86 (`assignrole`/
   `createrole`) carries **relay-level** access roles only. NostrHost
   authorisation (admin/agent/approval authority) is **server-authoritative
   capability events** on top, evaluated by the policy engine.
2. **NIP-26 vs delegation events → NIP-26 + capability events.** NIP-26
   covers agent *signing* delegation; a small NostrHost capability event
   carries scope grants. No bespoke delegation event kind.
3. **Catalogue schema → migrate to standard kinds.** Software discovery uses
   **32267** software-application, **30063** release-artifact sets, **30267**
   app-curation sets (replaces the bespoke `30078` declaration / `30079`
   endorsement). **CI attestation stays custom** (replaces `30080`). This
   resolves the `30078`/NIP-78 collision.
4. **Settings placement → NIP-78 on the internal relay** (kinds `30078`/`78`),
   NIP-42-gated to the owner. Confirmed for single-tenant loopback.
5. **Audit read model → derived index.** The signed operation chain is
   authoritative; a projector builds an index for admin reporting. Schema is
   defined in the event protocol (Phase 2) and implemented as a projector
   (Phase 6).
6. **Custom-kind numbers → allocated in the event protocol** (`EVENT-PROTOCOL.md`),
   validated against the live NIPs registry and the retained catalogue kinds
   (`30063`, `30267`, `32267`, custom CI attestation).