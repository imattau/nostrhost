# MCP diagnosis tools

MCP clients can gather health and incident evidence without receiving general
administrator authority. Availability depends on the adapter in use; clients
should discover the current tool catalogue at connection time.

## Core tools

| Tool | Purpose | Typical scope |
|---|---|---|
| `health_check` | Read the latest diagnosis report | `diagnosis.read` |
| `diagnosis_get` | Compatibility alias for the health report | `diagnosis.read` |
| `diagnosis_run` | Refresh selected diagnosis categories | `diagnosis.read` |
| `system_snapshot` | Uptime, load, memory, disk, processes, and OOM evidence | `server.read` |
| `ssh_diagnose` | SSH service, listener, firewall, and journal evidence | `diagnosis.read` |
| `incident_snapshot` | Time-bounded system, service, web, SSH, and network evidence | `diagnosis.read` |
| `diagnose_app` | App details, server diagnosis, and related operations | `apps.read` |
| `validate_server` | Pre-flight server, update, service, backup, and health summary | `server.read` |
| `safe_upgrade` | Backup, upgrade, and verify an app | `apps.upgrade` plus approval |

Responses identify fixture data when the adapter is running in fake/test mode.
Callers must not present fixture results as live server evidence.

## Behaviour

`diagnosis_run` can take time because some checks use the network. A timeout
does not prove failure; retain the operation ID and query again.

Snapshots read current operating-system state and can be more detailed than
the cached diagnosis report. They are evidence, not repair commands.
`incident_snapshot` is the preferred starting point when the failure time is
known. `diagnose_app` is useful when only one app appears affected.

`safe_upgrade` is a write workflow. It checks health and policy, creates a
backup, performs the upgrade, and runs follow-up checks. It still requires the
normal capability and any owner approval; the name does not guarantee success
or make an upgrade reversible without a valid backup.

## Ignore filters

Diagnosis ignore and unignore are not general read-only diagnosis tools. When
exposed by an adapter, they use the native audited write operations and require
`diagnosis.write` plus approval. An agent must not hide a finding merely to
make a health report pass.

## Handling output

Snapshots can contain hostnames, usernames, process arguments, paths, IP
addresses, and log messages. Redact secrets and personal data before sending
results to another service or including them in a support report.
