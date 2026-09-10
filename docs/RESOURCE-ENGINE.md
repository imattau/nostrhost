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
summary. This leaves the planner independent of the current Nostr operation
tool names while allowing a later adapter to submit approved operations to the
existing NostrHost executor.
