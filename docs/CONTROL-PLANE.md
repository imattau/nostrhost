# Control Plane: the internal Nostr relay

The local Nostr relay is a first-class architectural component of NostrHost.
It is the **control-plane bus** — the medium through which identity, policy,
approvals, execution, catalogue and audit state flow — so Nostr is not merely
the login method or catalogue transport but the *primary control-plane
technology* of the platform.

This document supersedes the older "Proposed Shared Architecture" sketch in
`ROADMAP.md`.

## 1. Architecture

Interfaces (Portal, Admin, MCP, CLI) and system processes become **clients of
the local relay**: they publish signed events and subscribe to the kinds that
concern them. Projectors materialise durable read models from the event
stream. The control executor is the single writer to YunoHost machine state.

```text
                    External Nostr
                         │
                selective sync / bridge
                         │
                         ▼
                  ┌──────────────────────┐
                  │   NostrHost Relay    │   ← LOCAL control plane
                  │   (event store + bus)│
                  └──────────┬───────────┘
                             │
          ┌──────────────────┼─────────────────┐
          │                  │                 │
      Identity            Policy           Catalogue
      projector          evaluator         resolver
          │                  │                 │
          └──────────────────┼─────────────────┘
                             │
                       Control executor
                             │
                             ▼
                    YunoHost service layer
                             │
         ┌──────────┬────────┼────────┬─────────┐
         │          │        │        │         │
        Apps      Domains  Backup   NGINX    System
```

Interfaces sit above the relay:

```text
         Portal       Admin        MCP        CLI
            \           |           |          /
             \          |           |         /
              └──── NostrHost Relay ────────┘
```

The relay communicates **intent and events**. YunoHost remains the
machine-state executor (apps, domains, certificates, backups, services,
firewall, diagnosis, Debian integration, user/group compatibility).

## 2. The event protocol is the internal control-plane API

Instead of designing dozens of bespoke HTTP endpoints between components,
NostrHost defines an event protocol. Components write signed events and
subscribe (`REQ`) to the kinds they need; projectors/executors react. The
event schema *is* NostrHost's internal API.

### 2.0 Primitive-first: use existing Nostr standards wherever possible

Before inventing NostrHost-specific kinds, map each requirement onto existing
Nostr primitives. Only genuinely YunoHost-specific semantics get custom kinds.
This removes not only YunoHost bespoke infrastructure but much of the *new*
infrastructure the earlier design would have written.

| NostrHost requirement | existing Nostr primitive |
|---|---|
| Public user profile | **kind 0** (NIP-01) |
| Delegated signing | **NIP-26** |
| Relay authentication (who are you) | **NIP-42** (kind 22242) |
| Private/encrypted payloads | **NIP-44** (no forward secrecy — not for key material) |
| Lists / collections (trusted publishers, approved repos, preferred relays) | **NIP-51** (kinds 10000/10002/30000/30002/10006, private entries NIP-44-encrypted) |
| Relay list metadata | **NIP-65** (kind 10002) |
| Relay discovery / liveness | **NIP-66** (kinds 30166/10166) |
| State / event sync (catalogue, control events) | **NIP-77 Negentropy** (`NEG-OPEN`/`NEG-MSG`) |
| App/user settings & per-user preferences | **NIP-78** (kind 30078 addressable; kind 78 multi-record), NIP-42-gated to the owner |
| Relay administration (allow/ban pubkeys & kinds, roles) | **NIP-86** (JSON-RPC over the relay HTTP endpoint, NIP-98-authenticated) |
| HTTP authentication for operations | **NIP-98** (kind 27235) |
| Software application discovery | **NIP-89** handlers + kind **32267** software-application; kind **30063** release-artifact sets; kind **30267** app-curation sets |
| Administrative notifications | NIP-17 / NIP-59 (encrypted DMs / gift wrap) |

Three implications for the design:

- **NIP-86 administers the relay; Nostr events administer NostrHost.**
  Relay-level access (who may write/read, which kinds are allowed) is NIP-86
  (`allowpubkey`, `allowkind`, `listallowedkinds`, `banpubkey`, `blockip`) and
  NIP-42 for client auth — no proprietary relay-management API.
- **NIP-42 + NIP-98 cover access and HTTP-auth.** No bespoke API-key
  mechanism for relay access; NIP-86 itself authenticates with NIP-98.
- **NIP-78 and NIP-51 replace bespoke settings and list storage.** User/portal
  preferences (`d = "nostrhost:portal-settings"`), trusted-publisher lists,
  approved repositories and preferred relays live as standard events.

The full component-by-component mapping (including the parts of YunoHost's
control plane each primitive replaces) is tracked in `NIP-MAPPING.md` and is
the Phase-2 design step performed before any custom kinds are allocated.

### 2.1 Kind discipline

Custom kinds are allocated only for genuine NostrHost semantics, and must
respect the NIP-16 / NIP-33 treatment ranges:

| range | semantics | used for |
|---|---|---|
| `1000–9999` | **regular** (stored, immutable, one per event) | operation request → approval → rejection → execution events; system/service/security notices |
| `10000–19999` | **replaceable** | (reserved; current-state snapshots if ever needed) |
| `20000–29999` | **ephemeral** (not stored) | transient coordination messages, if needed |
| `30000–39999` | **addressable** (`d`-tag keyed, replaceable per subject) | server-authoritative identity/role/capability definitions; trust/policy declarations that aren't expressible as NIP-51 lists |

The operation/approval/execution chain is **regular** so every step is a
unique, immutable, stored event forming the audit trail with cryptographic
provenance:

```text
REQUEST    npub-agent   app.upgrade   ditto
APPROVAL   npub-admin   request-id
EXECUTION  npub-server  request-id   started
RESULT     npub-server  request-id   success
```

### 2.2 Custom kinds (minimal; registry is a Phase-2 deliverable)

Most of the earlier illustrative kind block is replaced by standard
primitives (2.0). What remains — NostrHost-only semantics:

```text
NostrHost identity/role/capability definitions   (addressable; server-authoritative)
NostrHost trust/policy declarations              (only if not expressible as NIP-51)
YunoHost operation request / approval / result   (regular; the audit chain)
package attestation                              (only if 32267/30063/CI standards don't fit)
system / service / backup / security events      (regular)
```

Constraints before allocation:

- Avoid collision with existing Nostr catalogue kinds (`1100`, `30078`,
  `30079`, `30080`) and with reserved/common NIP kinds.
- The `NIP-MAPPING.md` exercise runs first; a custom kind is only added when
  no standard primitive fits.
- Validate the final registry against the live NIPs at Phase 2 execution.

### 2.3 What the relay stores vs what stays local

| in the relay | stays in the local HTTP/auth subsystem |
|---|---|
| server-authoritative identity/role/capability definitions | live browser sessions, cookies |
| capability/trust declarations; NIP-51 lists (trusted publishers, relays) | CSRF state |
| approval + execution events (audit chain) | challenge state (login/link challenges) |
| package metadata, releases, attestations | the `broker/` Unix-socket privilege boundary |
| NIP-78 user/portal settings & preferences | LDAP writes |
| login/revoke/link event notices | — |

Sessions are short-lived tokens **outside** the public-style event stream;
the relay records `LOGIN_SUCCEEDED` / `LOGIN_REVOKED` / `IDENTITY_LINKED`
notices but is not the live HTTP session store.

## 3. The `nostrhost-control` component

The fifth foundational component. We **use an existing relay implementation**
rather than writing one; NostrHost owns the policy around it.

Scope of `nostrhost-control`:

- wraps/configures the chosen relay binary for localhost-only operation
- relay administration via **NIP-86** (allow/ban pubkeys & kinds, roles) and
  client access via **NIP-42** — no proprietary relay-management API
- event-model validation (allowed kinds, schema, signatures)
- local access policy (who may write/read which kinds on the loopback plane)
- per-kind retention policy (audit chain immutable; definitions replaceable;
  ephemeral dropped)
- external bridging rules (selective sync of catalogue/trust events out, and
  in, to external relays)
- NIP-77 Negentropy sync endpoints for state reconciliation (catalogue,
  control events)

Selection criteria for the relay backend (Phase-2 sub-task):

- per-kind retention control
- localhost-only binding + write/read auth (NIP-42 or loopback trust)
- NIP-70 protected events where needed
- durable storage for the audit chain
- headless, file-based configuration
- packagable for YunoHost (a `_ynh` package for stock, built-in for the
  derivative)

Candidates to evaluate: **goss** (per-kind retention, NIP-42 auth, Go — fits
the Go catalogue stack) and **strfry** (battle-tested, plugin write-policy,
already packaged for YunoHost). Evaluation result is recorded in this file
when decided.

**Decision (Phase 2):** build the relay on **khatru** (the standard relay
framework, MIT), embedded in `nostrhost-control` — native NIP-86/42/77, Go,
fits the stack. strfry remains the fallback for stock-YunoHost packaging.
See `RELAY-SELECTION.md` for the full comparison.

## 4. Redundancy

Adopting the relay removes enough bespoke infrastructure that it changes the
roadmap *before* development diverges from the baseline.

| original component | with internal relay |
|---|---|
| `identityd` (service + DB + API) | **Greatly reduced** to a projector/resolver |
| Identity DB (bespoke) | **Redundant** — identity definitions are relay events |
| MCP `identity.toml` / MCP-specific identity storage | **Redundant** — signed identity/capability events |
| Approval API/service + DB | **Redundant** — the relay is the request/response medium |
| Catalogue local DB + API | **Mostly redundant** — the relay is the local catalogue cache |
| Audit DB (as authority) | **Mostly redundant** — the signed event chain is authoritative; an index/read model is derived |
| Point-to-point internal REST glue | **Greatly reduced** — components subscribe to kinds |
| Polling / notification infrastructure | **Redundant** — live `REQ` subscriptions |
| Internal command queue | **Redundant** — operation-request events |
| MCP server | **Remains, becomes an adapter** (protocol, tools, package-dev, diagnostics) |
| Policy evaluator | **Remains** — computation, not storage |
| Identity resolver | **Remains, much smaller** |
| Catalogue resolver / trust logic | **Remains** |
| HTTP session subsystem | **Remains** (out of the relay) |
| SSO enforcement | **Remains, eventually smaller** (NGINX `auth_request`) |
| LDAP | **Remains initially** as a compatibility projection |
| YunoHost core | **Remains** |
| Portal / Admin forks | **Remain** |

## 5. SSO enforcement

The relay does not remove the request-path enforcement point:

```text
request
   ↓
NGINX
   ↓ auth_request
session + identity state (projected from relay events)
   ↓
policy evaluation
   ↓
ALLOW / DENY
   ↓
application
```

`auth_request` still makes sense; only the source of identity/policy state
changes — it is projected from Nostr events instead of a bespoke store.

## 6. Precedent

`yunohost-mcp`'s Armada/concord layer is already "deterministic,
authority-neutral folding of state over Nostr events", and its `broker/`
protocol is a local, auditable privilege-boundary transport. The event model
and the session boundary here build directly on that experience; the
extracted libraries (`nostrhost-auth`, `nostrhost-policy`,
`nostrhost-catalog`) provide the projector/evaluator/resolver logic the new
architecture consumes.

## 7. The component → NIP mapping

Before any custom kind is allocated, each YunoHost control-plane component is
mapped onto existing Nostr primitives (2.0). The running table — and the
review of which pieces of YunoHost's control plane each standard replaces —
lives in `NIP-MAPPING.md`. This is the Phase-2 design step that must precede
custom-kind allocation.

Resolved decisions (locked at Phase 2; see `NIP-MAPPING.md` §4):

- **Relay access/admin = NIP-42 + NIP-86** (relay-scoped roles only);
  NostrHost authorisation = server-authoritative capability events.
- **Agent delegation = NIP-26** for signing + a small NostrHost capability
  event for scope grants.
- **Catalogue = standard kinds** (32267 software-application, 30063
  release-artifact sets, 30267 app-curation sets) with **CI attestation
  custom** (replaces the bespoke 30078/30079/30080; resolves the
  30078/NIP-78 collision).
- **Settings = NIP-78** on the internal relay; **audit = derived read model**
  over the signed operation chain.