# Architecture overview

This page orients a new contributor: what runs where, how the pieces talk to
each other, and which document to read next for depth. It summarises
[`../CONTROL-PLANE.md`](../CONTROL-PLANE.md), [`../NIP-MAPPING.md`](../NIP-MAPPING.md)
and [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md) — those are the
authoritative sources; this page will drift out of sync with the fine
detail before they do.

## The one-sentence version

YunoHost's server-management engine still does the machine-state work (apps,
domains, certificates, backups, services, firewall), but every interface
that used to talk to it directly now talks to a **local Nostr relay**
instead, and that relay — not a REST API or a database — *is* NostrHost's
internal control-plane protocol.

## Repository shape

This umbrella repository doesn't contain most of the code. It owns
architecture, integration tests, version pins, release tooling, packaging
metadata and documentation; the actual components are git submodules:

```text
nostrhost/
├── forks/            # forks of upstream YunoHost components
│   ├── yunohost/     #   core engine (derivative branch `nostrhost`,
│   │                 #   ships as the `nostrhost-core` package)
│   ├── portal/       #   end-user Portal (Nuxt/Vue/TS)
│   ├── admin/        #   Admin SPA (Vue/Vite/TS)
│   └── installer/    #   custom Debian ISO installer
├── libs/             # NostrHost-native libraries (not YunoHost forks)
│   ├── nostrhost-auth/     # identity: challenge/verify/npub/mappings/NIP-05
│   ├── nostrhost-policy/   # roles/scopes/NIP-98/delegation/approvals/audit
│   ├── nostrhost-catalog/  # catalogue schema/relay/attestation/trust
│   ├── nostrhost-control/  # the control-plane relay + event model
│   ├── nostrhost-agent/    # optional policy-bound local administrator agent
│   ├── nostrhost-mcp/      # MCP adapter for the native control plane
│   └── yunohost-mcp/       # MCP adapter for legacy YunoHost operations
├── packages/         # native package.toml example/test apps
├── packaging/        # APT release BOM, build/publish scripts, compat matrix
├── schema/           # package.schema.json — the app-manifest JSON Schema
├── baseline/         # pins.yml — authoritative fork → pinned-ref mapping
├── scripts/          # pin-forks.sh / verify-clean.sh
├── testbed/          # VM/e2e test infrastructure
└── docs/             # this documentation tree
```

Every fork is pinned to a specific upstream tag (see
[`../BASELINE.md`](../BASELINE.md) and `baseline/pins.yml`); `forks/yunohost`
and `forks/portal`/`forks/admin` are **derivative** — they deliberately
diverge from upstream on their own branch rather than staying
source-identical. `scripts/verify-clean.sh` checks this invariant.

## Runtime architecture: the control plane

The core idea, in full, from [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md):

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
        Apps      Domains  Backup   Caddy    System
```

Interfaces (Portal, Admin, MCP, CLI) sit above the relay as clients — they
publish signed events and subscribe to the kinds they care about, rather
than calling bespoke REST endpoints on each other:

```text
         Portal       Admin        MCP        CLI
            \           |           |          /
             \          |           |         /
              └──── NostrHost Relay ────────┘
```

**Projectors** turn the event stream into durable read models (e.g. "who is
the current owner", "what capabilities does this pubkey hold"). The
**control executor** is the single writer to YunoHost's machine state — it's
the only component that actually calls into the YunoHost service layer, and
it only acts on validated, policy-approved operation events. This is why
every administrative action ends up as an auditable, cryptographically
signed chain:

```text
REQUEST    npub-agent   app.upgrade   ditto
APPROVAL   npub-admin   request-id
EXECUTION  npub-server  request-id   started
RESULT     npub-server  request-id   success
```

`nostrhost-control` (in `libs/`) is the component that owns this: it wraps
the **khatru** relay framework (chosen over strfry — see
[`../RELAY-SELECTION.md`](../RELAY-SELECTION.md)) configured for
localhost-only operation, relay administration via NIP-86, client auth via
NIP-42, per-kind retention policy, and selective external sync via NIP-77
Negentropy.

### Primitive-first: standard Nostr NIPs, not bespoke APIs

The design rule (see [`../NIP-MAPPING.md`](../NIP-MAPPING.md) for the full
table) is: **map every requirement onto an existing Nostr NIP before
inventing a custom event kind.** In practice this means, for example, user
profiles are plain kind-0 events, relay access is NIP-42 + NIP-86, app
discovery uses NIP-89 handlers and kind 32267, and settings storage is
NIP-78 — not bespoke NostrHost databases and endpoints for each of those
concerns. What's left over and genuinely NostrHost-specific is small:
server-authoritative identity/role/capability definitions, the
operation-request/approval/execution audit chain, package/CI attestation,
and system/service/security notices. Custom kinds live in the
`1000–9999` (regular/audit-chain), and `30000–39999` (addressable/
server-authoritative) NIP-33 ranges — see `CONTROL-PLANE.md` §2.1 for the
full range discipline.

### What lives in the relay vs. what stays local

| in the relay (as signed events) | stays in the local HTTP/auth subsystem |
|---|---|
| identity/role/capability definitions | live browser sessions, cookies |
| capability/trust declarations, NIP-51 lists | CSRF state |
| approval + execution events (the audit chain) | login/link challenge state |
| package metadata, releases, attestations | the `broker/` Unix-socket privilege boundary |
| NIP-78 user/portal settings | LDAP writes |

Browser sessions are deliberately **not** relay events — they're short-lived
tokens outside the event stream; the relay only records
`LOGIN_SUCCEEDED`/`LOGIN_REVOKED`/`IDENTITY_LINKED` notices.

## The native app lifecycle (`package.toml` / resource engine)

Apps are not installed via Bash install scripts (YunoHost's traditional
model). Instead a native package declares its **desired resources** — users,
directories, runtimes, databases, services, web routes, health checks,
backups, settings, secrets — in a manifest validated against
[`../../schema/package.schema.json`](../../schema/package.schema.json). The
Python resource engine (`nostrhost package plan`) turns that manifest into a
deterministic, dependency-ordered plan of typed operations. Planning is
read-only; applying a plan is a separate, policy-gated operation that flows
through the same request → approval → execution chain as everything else.
See [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md) for the full resource
model and provider list, and
[`../../packages/`](../../packages) for example manifests.

## State and backup

Configuration state (not application data) is tracked as an **ngit/NIP-34**
git-like repository — server configuration changes are commits, and the
repository is announced via a NIP-34 `kind 30617` event so it can be
discovered and, for disaster recovery, reconstructed from Nostr relays plus
the server's identity alone (no dependency on a central git forge). This is
linked to **Restic** for actual data backup/restore, so a
`postinstall --restore` can bring a server back to a known-good
configuration and data state after total loss. See
[`../STATELAYER.md`](../STATELAYER.md) for the complete design.

## Packaging and distribution

NostrHost ships as a **componentised Debian/APT distribution** — many small
`.deb` packages built from the pinned submodules, not one giant binary. The
umbrella repo owns the release bill-of-materials
(`packaging/packages.yml`), the compatibility matrix
(`packaging/compatibility.yml`), and the build/publish scripts that produce
a GitHub Pages-hosted APT repository. See
[`../../packaging/README.md`](../../packaging/README.md) for the full
package graph, and [`../BASELINE.md`](../BASELINE.md) for how forks are
pinned and re-pinned.

## Where to go next

- Read [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md) in full before touching
  anything event-related — it's the architectural core.
- Read [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) to see what's currently being
  built and in what order (docs → runtime packaging → native bootstrap →
  end-to-end app lifecycle).
- Read [`../ROADMAP.md`](../ROADMAP.md) for the complete history of how the
  platform got from a source-identical YunoHost fork to today's derivative.
- See [`dev/README.md`](README.md) for the topic-indexed list of every other
  design document.
