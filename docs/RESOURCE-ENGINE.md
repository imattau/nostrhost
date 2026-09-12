# NostrHost Resource Engine

The cutover and integration map for legacy removal and NostrHost plane
integration is documented in [RESOURCE-ENGINE-CUTOVER.md](RESOURCE-ENGINE-CUTOVER.md).

Native packages declare desired resources in a JSON `package.json` document.
The Python package engine validates that document, builds a dependency graph,
and emits a deterministic plan of executor-neutral operations. Planning is
read-only; applying a plan is a separate authorized operation.

The first supported model includes app metadata, sources, apt packages,
users, directories, runtimes, databases, services, web routes, health,
backups, settings, secrets, and restricted Python hooks. Native packages use
the `source` table (`source.main`, `source.plugins`, etc.). There is no Bash or
legacy-script capability in this engine.

`plan_package_removal()` produces a reverse-order lifecycle plan from the
same manifest. It reverses only explicitly owned resources; shared APT
dependencies and runtimes are retained, and database removal remains a
high-risk operation subject to backup policy.

```sh
nostrhost package schema --output schema/package.schema.json
nostrhost package plan packages/my-app/package.json --output-as json
```

The Typer `nostrhost package` commands are designed for people and automated
package authors. The checked-in JSON Schema at `schema/package.schema.json`
describes the manifest vocabulary, and `plan` validates a manifest before
returning its deterministic operations. These commands are read-only except
for writing a requested schema file. Applying a package remains a separate
policy-gated operation.
See [AI-assisted package authoring](AI-PACKAGE-AUTHORING.md) for the complete
agent workflow and package safety rules.

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
Node, Python, Go, Ruby, Composer, and PHP are supported, including explicit
isolated prefixes. PHP-FPM resources render an owned pool
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

Host policy resources can also render managed Logrotate and CrowdSec
definitions (CrowdSec replaces the retired fail2ban jails — see
[CROWDSEC-MIGRATION.md](CROWDSEC-MIGRATION.md)) with the same atomic-write,
drift-detection, and reverse-operation semantics as application resources.
