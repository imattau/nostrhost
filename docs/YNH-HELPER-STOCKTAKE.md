# YunoHost helper and scripting stocktake

The fork's `helpers/helpers.v2.1.d/` exports 122 `ynh_*` functions across 26
helper files/domains. This is valuable operational knowledge, but it should be mined for
contracts and invariants rather than translated one function at a time. The
Resource Engine should expose declarative resources and bounded Python
providers; helper names are an input catalogue, not the target API.

## Inventory

| Domain | Helpers | Native Resource Engine destination |
|---|---:|---|
| Common utilities | 21 | validation, safe paths, process/user inspection, temp workspaces |
| MongoDB | 11 | `DatabaseProvider` + dump/restore operations |
| Config panels | 8 | typed settings schema, diff, validation, file bindings |
| MySQL | 8 | driver-backed database provider + backup operations |
| PostgreSQL | 8 | `psycopg` database provider + backup operations |
| Logging | 7 | structured operation logs and failure results |
| Backup | 6 | Restic/state resource declarations and restore plans |
| Permissions | 6 | access/policy resource and portal projection |
| Settings | 5 | typed app state, not an untyped key/value bag |
| String/templating | 8 | typed serialization, safe config renderers, no shell substitution |
| System users | 4 | `systemd-sysusers` definitions |
| APT | 3 | `python-apt` package provider and repository policy |
| Nginx | 3 | Caddy JSON route provider, with compatibility analysis for edge cases |
| Systemd | 3 | unit/timer/credential providers and bounded D-Bus/systemctl actions |
| Sources | 1 | streaming download, hash, archive, cache and provenance provider |
| Node/Go/Ruby/Composer | 8 | runtime providers with pinned versions and isolated prefixes |
| PHP/FPM | 2 | runtime/pool resource, likely systemd/socket integration |
| Logrotate/CrowdSec | 4 | host policy resources or system-level platform providers (fail2ban helpers retired in CROWDSEC-MIGRATION P6) |
| Multimedia/Redis/Getopts | 6 | specialised capability providers or platform services |

The counts are exported function counts, not complexity counts. Several
functions call private helpers and have substantial behavior behind one public
name.

## What the helpers teach us

### Desired state and reconciliation

- `ynh_apt_install_dependencies` treats dependencies as an app-owned set and
  has replacement/additive behavior across calls.
- system users, install/data directories, sources, databases, runtime
  versions, services, permissions, and configuration are all repeatedly
  inspected and updated across install, upgrade, restore, and config changes.
- the correct native abstraction is therefore `inspect → diff → plan → apply
  → verify`, with explicit ownership and removal semantics.

### Ordering and dependency edges

The existing v2 resource manager encodes priorities: sources, users, install
directories, data directories, APT, ports, permissions, databases, and
runtimes are not independent. Script examples add further edges:

```text
packages → user → directories → source → runtime/database
→ rendered config → service unit → web route → enable/start → health
```

The planner must preserve these edges while allowing unrelated resources to
run independently. Upgrade and removal need reverse edges.

### Safety contracts worth preserving

- absolute-path and traversal checks before file removal or extraction;
- package-name, database-name, username, service-name, domain, and port
  validation;
- source SHA-256 verification before extraction or installation;
- archive extraction that rejects path traversal;
- explicit ownership of generated files and backup checksums;
- non-interactive APT operation with retries and conflict reporting;
- systemd action validation, daemon reload, enable/disable behavior, and
  optional readiness/log matching;
- secret redaction from logs and no plaintext secrets in generic settings;
- refusal to overwrite manually modified managed configuration without a
  backup/checksum decision;
- clear failure propagation and rollback/restore boundaries.

### Hidden side effects

The most important migration risk is that helpers do more than their names
imply. Examples include:

- APT dependency installation creates an app-specific virtual/equivs package,
  handles version relationships, adjusts PHP defaults, and may affect the
  PostgreSQL package state.
- source setup supports architecture-specific assets, prefetch caches,
  extraction formats, renaming, retained files, and cleanup of old content.
- systemd configuration performs installation, daemon reload, enable/disable,
  stop/start/restart, optional wait-until-log behavior, and failure logging.
- config panels combine typed questions with settings, files, multiline text,
  custom getters/setters, change detection, hashes, and backup-on-change.
- backup helpers register file paths and checksums; they do not themselves
  constitute the complete backup data plane.
- Nginx helpers render templates, alter root/subpath behavior, remove special
  directives, preserve checksums, and reload the proxy.
- database helpers create users, grant access, terminate connections before
  drops, and produce dump/restore streams with database-specific options.
- runtime helpers manage isolated toolchain prefixes and environment changes,
  not merely a package name.

These behaviors belong in provider tests and operation schemas, not in hidden
global Python side effects.

## Script and hook surface

Package lifecycle conventions include `install`, `upgrade`, `remove`,
`restore`, `backup`, and often `change_url`/`config` scripts. The fork also
ships global backup, restore, configuration-regeneration, and user lifecycle
hooks. Package examples commonly sequence:

```text
validate parameters
→ prepare source
→ install/build runtime
→ render config
→ render systemd unit
→ render web config
→ configure permissions
→ enable/start service
```

The native package format should model those outcomes directly. A package
with imperative Bash scripts is not a native package; migration should either
convert the behavior into resources/providers or reject the package pending
conversion. Restricted Python hooks should receive typed resource clients,
not `os.system` or unrestricted subprocess access.

## Provider migration map

| Existing knowledge | Native provider/operation |
|---|---|
| apt dependencies and repositories | `package.apt.ensure`, repository policy |
| system users/groups | `system_user.ensure` via sysusers |
| install/data dirs and permissions | `directory.ensure` via tmpfiles + access policy |
| source prefetch/setup | `source.fetch` / `source.verify` |
| systemd templates/actions | `service.ensure`, `service.enable`, `service.start`, timers |
| Nginx templates and reload | `web.route.ensure` via Caddy JSON API |
| SQL/Mongo/Redis setup | database-specific driver providers |
| app settings/config panels | typed desired/generated/secret state |
| file checksum/backup helpers | backup registration + semantic state/Restic linkage |
| Node/Go/Ruby/Composer/PHP | runtime providers with isolated prefixes |
| permissions and SSO paths | access resource and policy projection |
| logrotate / crowdsec policy | system policy providers (fail2ban retired — CROWDSEC-MIGRATION P6) |
| error/progress/rollback behavior | structured operation results and state snapshots |

Port helpers are a special case: they should not reserve ports through a
global text database. The native provider validates the requested bind at plan
application time, while the service declaration remains the source of truth.

## Recommended extraction order

1. **Contract tests:** capture helper behavior for paths, ownership, retries,
   hashes, idempotency, failure, and removal before replacing implementations.
2. **Pure providers:** sources, directories, service-unit rendering,
   settings, secrets, and operation planning.
3. **Native system adapters:** sysusers, tmpfiles, systemd actions, APT,
   database drivers, and Caddy API.
4. **Stateful providers:** backups, restores, runtime installation, database
   migrations, permissions, and generated configuration.
5. **Package conversion:** convert representative packages and reject native
   packages that still require unbounded imperative behavior.

The existing helper tree should remain available as a reference corpus during
this work, but it should not be called by native providers.
