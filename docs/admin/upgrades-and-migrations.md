# Upgrades and migrations

NostrHost has already carried out several major internal migrations while
staying, at every stage, a bootable and usable derivative. This page
summarises what changed and what it means for you as an operator; each
linked design document has the full phased history.

## The core rename: `yunohost` → `nostrhost-core`

The core engine ships as the **`nostrhost-core`** Debian package. A
transitional, empty `yunohost` package `Depends` on it, and `nostrhost-core`
itself `Provides`/`Replaces`/`Conflicts` the old `yunohost` name — so
anything still referencing the old package name keeps resolving. See
[`../BASELINE.md`](../BASELINE.md).

## Completed migrations

| Migration | From → To | Status | Design doc |
|---|---|---|---|
| Web/TLS | nginx + SSOwat (Lua) → Caddy + `forward_auth` | P0–P6 complete; P7 (backup hooks/semantic state) remaining | [`../CADDY-MIGRATION.md`](../CADDY-MIGRATION.md) |
| Security | fail2ban → CrowdSec (nftables enforcement unchanged) | Complete (P0–P7 landed, all gates passed) | [`../CROWDSEC-MIGRATION.md`](../CROWDSEC-MIGRATION.md) |
| Admin framework | moulinette → native `python3-nostrhost` | Complete — moulinette is not a dependency at all any more | [`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md) "Correction" section |
| Mail | SMTP/IMAP-dependent notifications → structured events + encrypted Nostr DMs | Phase 1 (notification service) done; later phases in progress | [`../MAIL-RETIREMENT.md`](../MAIL-RETIREMENT.md), [notifications.md](notifications.md) |

## In progress

| Migration | What's changing | Where to read the current phase |
|---|---|---|
| LDAP retirement | LDAP is already fully out of the *authentication* path (native NIP-98/Nostr auth is live); remaining work replaces LDAP's role as the Unix account/group directory and app-permission-membership store with NIP-51 lists | [`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md) "Status" |
| Native DNS + secrets | `DnsResource` provider adapters (Cloudflare/deSEC/DuckDNS/manual); SecretBroker consolidation onto systemd credentials | [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) "Later phase" (§26/§27) |

## Upgrading a running server

> **Status note.** The full upgrade path (`apt upgrade` across one of these
> migrations, on a real server, with a proven rollback if it goes wrong) is
> exactly what [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md)'s acceptance loop is
> proving out — "install → app works → backup → upgrade → deliberately
> break it → restore/rollback." Until that loop is signed off, treat
> upgrades on anything but a disposable test VM with caution, and always
> take a fresh backup first (see [backup-and-recovery.md](backup-and-recovery.md)).

In general:

```bash
sudo apt update
sudo apt upgrade
```

pulls new versions of the componentised `.deb` packages from the configured
NostrHost APT repository (see [`../../packaging/README.md`](../../packaging/README.md)).
Because each component is its own package, an upgrade can move the core
engine, the control-plane relay, the Portal/Admin SPAs, and the security
stack independently — check
[`../../packaging/compatibility.yml`](../../packaging/compatibility.yml)
for the version constraints between them if you're pinning versions rather
than upgrading everything together.

Before any upgrade that touches configuration:

1. A pre-change semantic-state snapshot is taken automatically (see
   [backup-and-recovery.md](backup-and-recovery.md)).
2. If the upgrade fails validation or health checks, use the assisted
   rollback flow described there rather than trying to hand-revert package
   versions.

## Related reading

- [`security-model.md`](security-model.md) for what the Caddy/CrowdSec
  migrations actually changed about how the server is protected.
- [`deployment-topology.md`](deployment-topology.md) for the resulting
  architecture these migrations converged on.
- [`../ROADMAP.md`](../ROADMAP.md) for the complete provenance, including
  migrations not yet summarised on this page.
