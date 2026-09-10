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
supported YunoHost v2 resources, but refuses packages containing imperative
install, upgrade, remove, backup, or restore scripts. Those packages must be
converted before they can enter the native engine.

Operation envelopes have stable names, resource identities, typed arguments,
dependencies, risk, reversibility, reverse operation, and a human-readable
summary. Native providers now apply directory, configuration, source, and service operations
without shell helper wrappers. Config resources support inline content or
strict Jinja2 templates, with atomic writes and Python-managed ownership and
mode. Source handling uses streaming HTTP, hash
verification, and Python archive libraries with traversal, link, and
special-file rejection; services render hardened systemd units and perform
bounded daemon reloads on changes/removal. Directory and service reverse
operations are lifecycle-aware: directories are only removed when empty,
while service units are removed from the managed unit directory.
`NativeOperationExecutor` dispatches only registered providers, leaving
privileged policy and approval at the existing NostrHost executor boundary.

Systemd resource reversals are explicit: timers are disabled before their
unit pair is removed, credentials are deleted from the managed credential
store, and sysusers declarations are withdrawn without implicitly deleting
the underlying operating-system account.

APT, PostgreSQL and MySQL database, Caddy, access, secrets, backup, user/sysusers, and tmpfiles providers
use this same registry; timers, health checks, typed settings, and backup
declarations are also native providers. They are intentionally not silently
implemented through legacy helper commands. Runtime resources now verify the
selected native executable and version with bounded argv-based execution;
installation remains host-policy-owned because each runtime needs a
package-manager-specific strategy.

Caddy route removal requires an explicit native configuration builder and is
submitted through the same validated `/load` endpoint as route creation.

Backup resources persist validated `nostrhost-backup-v1` manifests. The
provider registers filesystem/database inputs but deliberately leaves the
Restic repository and credential data plane to host policy.
