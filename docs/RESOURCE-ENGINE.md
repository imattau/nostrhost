# NostrHost Resource Engine

Native packages declare desired resources in `package.toml`. The Python
package engine validates that document, builds a dependency graph, and emits a
deterministic dry-run plan of executor-neutral operations. Planning is
unprivileged; only a future executor/provider implementation may mutate the
host.

The first supported model includes app metadata, sources, apt packages,
users, directories, runtimes, databases, services, web routes, health,
backups, settings, secrets, and restricted Python hooks. Native packages use
the `source` table (`source.main`, `source.plugins`, etc.). There is no Bash or
legacy-script capability in this engine.

```sh
nostrhost-package plan packages/nostrhost-native-example/package.toml
nostrhost-package plan packages/nostrhost-native-example/package.toml --json
nostrhost-package schema --json
nostrhost-package migrate existing-app/manifest.toml --output package.toml
```

Migration is explicit and declarative-only. The migration command converts
supported YunoHost v2 resources including ports, Portal permissions, database
declarations, runtimes, config, settings, and backup inputs, but refuses packages containing imperative
install, upgrade, remove, backup, or restore scripts. Those packages must be
converted before they can enter the native engine.

Operation envelopes have stable names, resource identities, typed arguments,
dependencies, risk, reversibility, reverse operation, and a human-readable
summary. Native providers now apply directory, configuration, source, and service operations
without shell helper wrappers. Config resources support inline content or
strict Jinja2 templates, with atomic writes and Python-managed ownership and
mode. Source handling uses streaming HTTP, hash
verification, and Python archive libraries with traversal, link, and
special-file rejection. Sources also support explicit tar/zip/file formats,
safe renaming, bounded path-component stripping, and architecture variants
selected during planning. Services render hardened systemd units and perform
bounded daemon reloads on changes/removal. Directory and service reverse
operations are lifecycle-aware: directories are only removed when empty,
while service units are removed from the managed unit directory.
`NativeOperationExecutor` dispatches only registered providers, leaving
privileged policy and approval at the existing NostrHost executor boundary.
Restricted Python hooks are registered as semantic references only; they are
not executed by the native provider layer and must be dispatched later through
a bounded typed hook runtime.

Systemd resource reversals are explicit: timers are disabled before their
unit pair is removed, credentials are deleted from the managed credential
store, and sysusers declarations are withdrawn without implicitly deleting
the underlying operating-system account. System-user resources may also
declare managed groups, and service/timer/FPM executables and credential paths
are validated before rendering.

APT, PostgreSQL, MySQL, MongoDB, and Redis database resources, including SQL
user/grant declarations, Caddy, access, secrets, backup, user/sysusers, and
tmpfiles providers
use this same registry; timers, health checks, typed settings, and backup
declarations are also native providers. They are intentionally not silently
implemented through legacy helper commands. Runtime resources now verify the
selected native executable and version with bounded argv-based execution;
PHP is included as a runtime, and PHP-FPM resources render an owned pool
configuration and reload only the matching FPM service. Missing or mismatched
runtimes may be installed only through an explicitly injected host-policy
installer, then are re-verified by the provider; the engine never invents a
package-manager command.

Caddy route removal requires an explicit native configuration builder and is
submitted through the same validated `/load` endpoint as route creation.

Portal permissions are separate from filesystem access policies. Native
packages declare permission URLs, additional URLs, allowed users/groups, tile
visibility, protection, auth headers, and the staged `auth_request` flag;
the provider reconciles those values through the existing permission API and
regenerates the SSO policy projection.

Settings resources may declare typed fields (`string`, `integer`, `number`,
`boolean`, or `enum`) with defaults. Values are validated before planning and
persisted state is checksum-compared during reconciliation; secret settings
must use the dedicated secret resource.

Backup resources persist validated `nostrhost-backup-v1` manifests. The
provider registers filesystem/database inputs but deliberately leaves the
Restic repository and credential data plane to host policy. Database providers
also expose explicit bounded `database.dump` and `database.restore`
operations using backend-native argv; Redis rejects SQL-style dump/restore
because its databases are pre-created logical indexes.

Host policy resources can also render managed Fail2ban jail and Logrotate
definitions with the same atomic-write, drift-detection, and reverse-operation
semantics as application resources.
