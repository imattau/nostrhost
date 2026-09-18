# Administrator guide

This guide is for the people responsible for keeping a NostrHost server
available, secure, current, and recoverable.

## Operator responsibilities

- Keep Debian and NostrHost packages current.
- Monitor service health, capacity, certificates, security events, and backup
  results.
- Maintain least-privilege roles, capabilities, groups, and app permissions.
- Keep the public network surface limited to the required web and SSH ports.
- Store recovery keys and backup credentials away from the host.
- Test upgrades and disaster recovery before depending on them.
- Preserve operation IDs and audit records during incident response.

## Guides

1. [Deployment and network layout](deployment-topology.md)
2. [Security model](security-model.md)
3. [Backup and disaster recovery](backup-and-recovery.md)
4. [Updates and routine maintenance](upgrades-and-migrations.md)
5. [Notifications](notifications.md)
6. [Optional resident agent](resident-agent.md)

Use the [reference section](../reference/README.md) for event, operation,
diagnosis, and MCP details.

## Daily and periodic checks

Daily checks should cover failed services, security decisions, recent failed
operations, free disk space, and backup completion. Periodic checks should
cover package updates, certificate renewal, inactive identities, recovery
material, restore tests, and capacity trends.

Prefer Admin for routine work. Use `nostrhost --help` for recovery, automation,
or detailed JSON output. Both interfaces use the same policy and operation
registry.
