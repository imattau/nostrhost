# Administrator guide

For people responsible for keeping a NostrHost server running: deployment,
upgrades, security posture, backup/recovery policy. If you just want to use
an already-running server, see the [user guide](../guide/README.md) instead.

## Pages

| Page | Covers |
|---|---|
| [Deployment topology](deployment-topology.md) | Single-server layout, request path through Caddy, what runs where, domains/DNS, network exposure |
| [Security model](security-model.md) | CrowdSec + nftables, request-time `forward_auth`, Nostr identity, capability/role authorization, the audit chain |
| [Backup and disaster recovery](backup-and-recovery.md) | The four-layer state model (Nostr/ngit/Restic/Linux), known-good state and rollback, full server restore |
| [Upgrades and migrations](upgrades-and-migrations.md) | The core rename, completed Caddy/CrowdSec/moulinette migrations, in-progress LDAP retirement, upgrading a running server |
| [Notifications](notifications.md) | Configuring `nostrhost-notify` — recipients, event classes, severity, digest vs. immediate delivery |

## Planned pages

| Page | Will cover | Written from |
|---|---|---|
| Running the optional agent *(TODO)* | Enabling `nostrhost-agent`, scoping its capabilities, Observe mode | [`../../packaging/README.md`](../../packaging/README.md), [`../AGENT-DISTRIBUTION-PLAN.md`](../AGENT-DISTRIBUTION-PLAN.md) |
| Testing changes on a VM *(TODO)* | Using the VM testbed before rolling changes to a real server | [`../VM-TESTBED.md`](../VM-TESTBED.md) |

## Related reading

- [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) for what in the operational surface
  above is proven end-to-end today versus still in progress.
- [`dev/`](../dev/README.md) if you need to understand *why* something is
  built the way it is, not just how to operate it.
