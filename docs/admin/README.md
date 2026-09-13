# Administrator guide

For people responsible for keeping a NostrHost server running: deployment,
upgrades, security posture, backup/recovery policy. If you just want to use
an already-running server, see the [user guide](../guide/README.md) instead.

> **Status.** These pages are scaffolded but not yet written in full. Each
> row below links to the design document the eventual page will be written
> from — read that in the meantime.

## Planned pages

| Page | Will cover | Written from |
|---|---|---|
| Deployment topology *(TODO)* | Single-server layout, domains/DNS, TLS via Caddy, network exposure | [`../CADDY-MIGRATION.md`](../CADDY-MIGRATION.md) |
| Upgrades and migrations *(TODO)* | Upgrading NostrHost, the completed Caddy/CrowdSec/core-rename migrations, what to expect from the pending LDAP demotion | [`../CROWDSEC-MIGRATION.md`](../CROWDSEC-MIGRATION.md), [`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md), [`../BASELINE.md`](../BASELINE.md) |
| Security model *(TODO)* | CrowdSec + nftables, relay access control (NIP-42/NIP-86), capability/role grants, what replaced fail2ban/SSOwat | [`../CROWDSEC-MIGRATION.md`](../CROWDSEC-MIGRATION.md), [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md), [`../ROLE-AND-APP-ACCESS-DESIGN.md`](../ROLE-AND-APP-ACCESS-DESIGN.md) |
| Backup and disaster recovery *(TODO)* | Restic backup policy, the ngit/NIP-34 state repository, full server restore | [`../STATELAYER.md`](../STATELAYER.md) |
| Notifications *(TODO)* | Configuring the NIP-17/59 notification daemon for admin alerts | [`../NOTIFICATION-SERVICE.md`](../NOTIFICATION-SERVICE.md) |
| Running the optional agent *(TODO)* | Enabling `nostrhost-agent`, scoping its capabilities, Observe mode | [`../../packaging/README.md`](../../packaging/README.md), [`../AGENT-DISTRIBUTION-PLAN.md`](../AGENT-DISTRIBUTION-PLAN.md) |
| Testing changes on a VM *(TODO)* | Using the VM testbed before rolling changes to a real server | [`../VM-TESTBED.md`](../VM-TESTBED.md) |

## Related reading

- [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) for what in the operational surface
  above is proven end-to-end today versus still in progress.
- [`dev/`](../dev/README.md) if you need to understand *why* something is
  built the way it is, not just how to operate it.
