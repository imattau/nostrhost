# Relay backend selection

Decision for the NostrHost internal relay (roadmap §3 / `CONTROL-PLANE.md`),
recorded after the Phase-2 evaluation.

## Decision: **khatru** (embedded in `nostrhost-control`)

`nostrhost-control` builds the control-plane relay on
[khatru](https://github.com/fiatjaf/khatru) (MIT), the standard Nostr relay
framework. The framework provides the WebSocket protocol (NIP-01), NIP-42
AUTH, NIP-77 negentropy and the NIP-86 management dispatch; NostrHost adds
the event-model validation, the durable access/kind/admin policy, and
per-kind retention. We do **not** write a relay protocol from scratch — we
use an existing relay framework and own the policy around it.

## Why not the other candidates

| candidate | strengths | gaps → why not primary |
|---|---|---|
| **khatru** (chosen) | native NIP-86 (full `RelayManagementAPI` incl. kind allow/deny + NIP-98 auth), NIP-77, NIP-42; Go; MIT; proven base (nostr.wine, relay-86, …) | framework (we wire it) — exactly the intended split |
| **relay-86** (khatru-based) | ready-made NIP-86 + 98 + negentropy + allowlist, Go | **no LICENSE file** (not reusable); depends on a private Forgejo fork of khatru; no NIP-42/retention; niche |
| **strfry** | battle-tested; native NIP-42/70/77; packaged for YunoHost | **no native NIP-86** (wrapper + write-policy plugin needed); no per-kind retention; not Go |
| **goss** | per-kind retention; NIP-42; Go | NIP-86/77 support uncertain; not packaged for YunoHost |
| **nostr-rs-relay** | mature | NIP-77 support still incomplete (issue #234) |

## NIP-86 is the deciding factor

The control plane needs a standard management surface (allow/ban pubkeys and
kinds, IP blocks, admins). khatru implements NIP-86 natively with NIP-98
authentication built into the dispatch — the exact "NIP-86 administers the
relay, Nostr events administer NostrHost" split from `CONTROL-PLANE.md`.
strfry would require us to build NIP-86 on top of its plugin system anyway.

## Fallback for stock-YunoHost packaging

When the derivative's stock-YunoHost deployment model needs a packaged,
self-contained relay (roadmap §14), **strfry** is the fallback: it is already
packaged for YunoHost and covers NIP-42/70/77 natively; `nostrhost-control`
would supervise it and add NIP-86 + retention via its write-policy plugin.
Revisited at the distribution phase.