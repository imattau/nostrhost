# NostrHost Resource Engine

Native packages declare desired resources in `package.toml`. The Python
package engine validates that document, builds a dependency graph, and emits a
deterministic dry-run plan of executor-neutral operations. Planning is
unprivileged; only a future executor/provider implementation may mutate the
host.

The first supported model includes app metadata, sources, apt packages,
users, directories, runtimes, databases, services, web routes, health,
backups, settings, secrets, and hooks. Native packages use the `source` table
(`source.main`, `source.plugins`, etc.).

```sh
nostrhost-package plan packages/nostrhost-native-example/package.toml
nostrhost-package plan packages/nostrhost-native-example/package.toml --json
nostrhost-package schema --json
nostrhost-package migrate existing-app/manifest.toml --output package.toml
```

Migration is explicit. Existing YunoHost `manifest.toml` packages continue to
use their current lifecycle until a later integration stage routes migrated
packages through the resource executor. Unsupported imperative behavior is
represented as an explicit legacy hook rather than silently discarded.

Operation envelopes have stable names, resource identities, typed arguments,
dependencies, risk, reversibility, reverse operation, and a human-readable
summary. This leaves the planner independent of the current Nostr operation
tool names while allowing a later adapter to submit approved operations to the
existing NostrHost executor.
