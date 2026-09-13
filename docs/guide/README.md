# User guide

For people installing and running NostrHost as their own self-hosting
platform — the Portal/Admin end of things, not the codebase.

> **Status.** NostrHost is pre-alpha. The flow below (`apt install nostrhost`
> → `nostrhost postinstall` → Nostr login → install an app) is the target
> path the project is currently building and proving end-to-end; see
> [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) for exactly which steps are wired up
> today versus still in progress. Where a page describes something not yet
> available, it says so.

## Pages

| Page | Covers |
|---|---|
| [Getting started](getting-started.md) | What NostrHost is, requirements, installing the APT package, first-run (`postinstall`), logging in with a Nostr key |
| Installing apps *(TODO)* | Using the catalogue, installing/upgrading/removing a `package.toml` app from the Portal or CLI |
| Managing your identity *(TODO)* | Nostr keys, NIP-05, delegated/agent keys, linking additional devices |
| Backups and recovery *(TODO)* | Restic-backed backups, restoring a snapshot, disaster recovery via the ngit state repo |
| Notifications *(TODO)* | Configuring admin notifications (NIP-17/59 encrypted DMs) |
| Troubleshooting *(TODO)* | Common failures during install/first-run and how to diagnose them |

Pages marked *(TODO)* aren't written yet — see
[`dev/README.md`](../dev/README.md#contributing-to-the-docs) if you'd like to
contribute one.

## Related reading

- [`admin/`](../admin/README.md) if you're responsible for keeping the
  server running (upgrades, security, capacity) rather than just using it.
- [`../AI-PACKAGE-AUTHORING.md`](../AI-PACKAGE-AUTHORING.md) if you want to
  package your own app for the catalogue.
