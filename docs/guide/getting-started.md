# Getting started

## What NostrHost is

NostrHost is a **Nostr-native self-hosting platform**: install it on a
server (a VPS, a home box, a spare machine) and it gives you a personal
platform for running web apps, with Nostr — the decentralised social/identity
protocol — as the control plane instead of a traditional username/password
admin panel.

Concretely:

- **You log in with a Nostr key** (an `npub`/`nsec` keypair), not a username
  and password. The same key that's your Nostr identity elsewhere is your
  server login.
- **Every administrative action is a signed Nostr event** — installing an
  app, approving an operation, granting a role — flowing through a local
  Nostr relay that runs on the server itself. This is what
  [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md) calls the control-plane bus.
  You don't need to understand this to use NostrHost, but it's why actions
  are auditable and why identity/authority work the way they do.
- **Under the hood**, NostrHost builds on YunoHost's mature server-management
  engine (app lifecycle, domains, backups, diagnosis) — inherited maturity,
  not a rewrite from scratch — but replaces its authentication (SSOwat →
  Caddy), security (fail2ban → CrowdSec) and app-packaging model with
  Nostr-native equivalents. See the top-level [`README.md`](../../README.md)
  for the full component list.
- **Apps** are installed from a catalogue using a declarative `package.toml`
  manifest (see [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md)) rather than
  install scripts.

If you've used YunoHost before, the concepts (apps, domains, backups,
permissions) will feel familiar; the login/identity/audit layer is what's
different.

## Is NostrHost ready for you?

**Not yet for production use.** NostrHost is at the "make it a product"
stage — see [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) and the "Platform state"
table in the top-level [`README.md`](../../README.md). The architecture and
major components exist; the current work is proving the full
install → upgrade → break → restore loop end-to-end on a blank VM. This
guide describes that target path and will be updated as each step lands.

It's a good fit right now if you want to:

- try it on a disposable VM and give feedback,
- develop or package an app against the native `package.toml` engine, or
- contribute to closing out the alpha plan.

## Requirements

- A dedicated machine or VM running **Debian 12 ("bookworm")**, amd64. Other
  distributions and architectures aren't supported — NostrHost ships as a
  componentised APT distribution (see
  [`../../packaging/README.md`](../../packaging/README.md)).
- A domain name you control (for TLS and Nostr identity linkage), or a
  DuckDNS-style dynamic domain during evaluation.
- A Nostr key. If you don't have one, any standard Nostr client or a NIP-07
  browser extension can generate one — keep the private key (`nsec`) safe,
  it's your server login.

## Installing

Add the NostrHost APT repository and its signing key:

```bash
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://imattau.github.io/nostrhost/debian/nostrhost.asc \
  | sudo tee /etc/apt/keyrings/nostrhost.asc >/dev/null

echo "deb [signed-by=/etc/apt/keyrings/nostrhost.asc] https://imattau.github.io/nostrhost/debian/ bookworm main" \
  | sudo tee /etc/apt/sources.list.d/nostrhost.list

sudo apt update
```

Install the full server meta-package:

```bash
sudo apt install nostrhost
```

This pulls in the core engine, the local control-plane relay, the
catalogue, Caddy (web/TLS), CrowdSec (security), the Portal and Admin web
apps, and the Python runtime — see
[`../../packaging/README.md`](../../packaging/README.md) for the complete
dependency graph if you want to install a smaller footprint
(`nostrhost-core-system` is the headless-only meta-package).

## First run

```bash
sudo nostrhost postinstall --new
```

This is a fresh install. `postinstall` will:

- generate the server's own Nostr identity,
- start the local control-plane relay,
- configure Caddy with a base TLS configuration for your domain,
- record you as the owner (see below), and
- initialise the ngit/NIP-34 configuration-state repository
  ([`../STATELAYER.md`](../STATELAYER.md)).

If you're restoring a server rather than starting fresh (recovering from a
disk failure, moving to new hardware), use `--restore` instead: it
authorises your existing server identity, discovers and clones the
configuration-state repository from wherever it was published, restores the
linked Restic backup snapshot, and reconciles the machine back to that
known-good state. See [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) (Workstream 2)
for the current state of this flow.

## Logging in as the owner

Open the Portal (or Admin) in a browser at your server's domain. Instead of
a username/password form, you'll be asked to sign a login challenge with
your Nostr key — either via a NIP-07 browser extension, a NIP-46 remote
signer ("bunker"), or a passkey, depending on what's wired up at the time
you're reading this (see the "Nostr identity / auth" row of the platform
state table). The key you sign in with the first time, during
`postinstall --new`, becomes the server owner.

Once logged in, the Admin app lets you manage apps, domains, backups, users
and roles — the same shape of interface as YunoHost's admin panel, backed
by NostrHost's policy and control-plane layers underneath.

## Installing your first app

From the Admin app's catalogue, or from the CLI:

```bash
nostrhost package plan packages/<app>/package.json --output-as json
```

`plan` is read-only and shows you exactly what installing the app will do
(users, directories, services, database, web route, backup registration)
before anything is applied — see
[`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md) for the full manifest model.
Applying the plan is a separate, policy-gated operation that flows through
the same request → approval → execution event chain as every other
administrative action.

## Next steps

- [Managing your identity](README.md) *(TODO)* — additional devices,
  delegated/agent keys, NIP-05.
- [Backups and recovery](README.md) *(TODO)* — Restic snapshots and the
  `postinstall --restore` disaster-recovery path in full.
- If something doesn't work, check [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md)
  first — the exact install/upgrade/restore loop this guide describes is
  the plan's current acceptance target, so a rough edge you hit may already
  be a tracked, known gap rather than something wrong on your end.
