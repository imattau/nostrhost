# Control-plane event reference

The concrete event kinds NostrHost's control plane uses today, plus the
standard NIPs it relies on instead of inventing new ones. This is a
lookup-table companion to [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md) (the
narrative design) and [`../NIP-MAPPING.md`](../NIP-MAPPING.md) (the
requirement → NIP mapping); those remain authoritative, and the final
registry is a `nostrhost-control` `EVENT-PROTOCOL.md` deliverable, not this
repo. Treat the kind numbers below as **current, not frozen** — Phase 2 of
the roadmap validates the final registry against the live NIPs.

## Kind-range discipline (NIP-16 / NIP-33)

| Range | Semantics | Used for |
|---|---|---|
| `1000–9999` | Regular (stored, immutable, one per event) | The operation request → approval → rejection → execution chain; system/service/security notices |
| `10000–19999` | Replaceable | Reserved (current-state snapshots, if ever needed) |
| `20000–29999` | Ephemeral (not stored) | Transient coordination messages, if needed |
| `30000–39999` | Addressable (`d`-tag keyed, replaceable per subject) | Server-authoritative identity/role/capability definitions; trust/policy declarations not expressible as a NIP-51 list |

## The operation chain (kinds 2200–2205)

The audit-trail chain every administrative action flows through:

| Kind | Meaning |
|---|---|
| `2200` | Operation **request** |
| `2201` | **Approval** |
| `2202` | **Rejection** |
| `2203` | **Executing** (started) |
| `2204` | **Result** (terminal: success/failure) |
| `2205` | **Progress** (intermediate updates for long-running operations) |

Correlation across the chain is an `["e", request-id]` tag pointing back to
the originating `2200` request. The executor daemon subscribes to this
range plus `31100`/`27236`/`27237` (delegation/capability-adjacent kinds),
validates signer authority and policy, executes, and signs terminal states
with the server's own key. Clients (CLI `op follow/status`, the API's SSE
endpoint, the MCP adapter) stream progress by `REQ`-subscribing to
`2203`/`2204`/`2205` filtered by `#e`.

## System / service / security notices (2210–2213)

| Kind | Meaning |
|---|---|
| `2210` | System notice |
| `2211` | Service notice |
| `2212` | Backup notice *(inferred from the 2210–2213 range; confirm against the live `EVENT-PROTOCOL.md` before depending on it)* |
| `2213` | Security notice |

These are distinguished from each other by a `class` field/tag in content
rather than by separate kinds per notification type — e.g. "update
available", "recovery result" and "certificate event" all ride on `2210`
(system) or `2211` (service) with a differing `class`, and a CrowdSec ban
rides on `2213` with `class = "security"`. This is the source the
notification service ([`../admin/notifications.md`](../admin/notifications.md))
subscribes to. See [`../NOTIFICATION-SERVICE.md`](../NOTIFICATION-SERVICE.md)
§3 for the full class table.

## State-bundle replication (kind 2214)

Stage-C ngit disaster-recovery chunks: a gzip git bundle of the
configuration-state repository, split into signed chunks and published
outbound to external relays so the repository can be reconstructed from
relays + server identity alone. See
[`../admin/backup-and-recovery.md`](../admin/backup-and-recovery.md).

## Standard Nostr primitives NostrHost relies on

Rather than custom kinds for everything, most control-plane requirements
map onto existing NIPs:

| Requirement | NIP / kind |
|---|---|
| Public user profile | kind `0` (NIP-01) |
| Delegated event signing (agent keys) | NIP-26 |
| Relay client authentication | NIP-42 (kind `22242`) |
| Encrypted payloads inside signed events | NIP-44 |
| Lists / sets (trusted publishers, approved repos, preferred relays, groups) | NIP-51 (kinds `10000`/`10002`/`30000`/`30002`/`10006`) |
| Relay list metadata | NIP-65 (kind `10002`) |
| Relay discovery / liveness | NIP-66 (kinds `30166`/`10166`) |
| Protected events | NIP-70 |
| State/event sync (catalogue, control events) | NIP-77 Negentropy |
| App/user settings | NIP-78 (kind `30078` addressable, or kind `78`) |
| Relay administration (allow/ban pubkeys & kinds, roles) | NIP-86 |
| HTTP request authentication | NIP-98 (kind `27235`) |
| Software application discovery | NIP-89 handlers + kind `32267` (software-application), `30063` (release-artifact sets), `30267` (app-curation sets) |
| Administrative notifications | NIP-17 (private DM) + NIP-59 (gift wrap) |
| State-repository discovery | NIP-34 (kind `30617`, repository announcement) |

See [`../NIP-MAPPING.md`](../NIP-MAPPING.md) for the complete
component-by-component mapping, including what each primitive replaces from
YunoHost's original control plane, and which decisions are still marked "to
verify" versus locked.

## What is deliberately *not* a relay event

| Stays local (HTTP/auth subsystem) |
|---|
| Live browser sessions, cookies |
| CSRF state |
| Login/link challenge state |
| The `broker/` Unix-socket privilege boundary |
| LDAP writes (being retired regardless — see [`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md)) |

The relay records `LOGIN_SUCCEEDED`/`LOGIN_REVOKED`/`IDENTITY_LINKED`
*notices*, but is never the live session store itself.

## Related reading

- [`../dev/architecture-overview.md`](../dev/architecture-overview.md) — the
  narrative version of how these events flow through the system.
- [`mcp-integration.md`](mcp-integration.md) — how an MCP client submits and
  observes these events without needing root authority itself.
