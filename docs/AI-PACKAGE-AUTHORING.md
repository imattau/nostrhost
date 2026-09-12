# AI-Assisted Native Package Authoring

NostrHost packages are JSON desired-state declarations. Authors and AI agents
describe the resources an app needs; the package engine validates the
declaration and returns a deterministic plan. A manifest is data, not an
instruction to run shell commands.

## Authoring loop

1. Identify the app's source, runtime, system dependencies, service account,
   data paths, ports, web routes, configuration, secrets, health checks, and
   backup requirements. Ask for missing facts that change behavior or
   security. Never invent upstream hashes, secrets, domains, or service
   commands.
2. Read the checked-in [package schema](../schema/package.schema.json) and the
   closest example under `packages/`. Create a JSON manifest such as
   `packages/my-app/package.json`; keep it as the single source of truth.
3. Ask the Typer CLI to validate the manifest and produce a machine-readable
   plan:

   ```sh
   nostrhost package schema --output schema/package.schema.json
   nostrhost package plan packages/my-app/package.json --output-as json
   ```

   Planning validates the model and returns an error if any declaration is
   invalid. Treat high-risk, non-reversible, or unowned-resource operations as
   design review items. Plan output is descriptive; it is not authorization to
   apply changes.
4. Build and exercise the package only in a disposable Debian 12 test target
   using the same providers as production. Verify install, health, upgrade,
   backup inputs, restore behavior where applicable, and removal. Check that
   shared APT/runtime resources are retained and package-owned data follows its
   explicit policy.
5. Have a person review the manifest and plan. Applying a package is a
   separate privileged operation and must pass the configured policy and
   approval path.

## Authoring rules

- Keep `app.id` stable and versions explicit. Make package-owned paths absolute
  and specific to the app.
- Pin downloaded sources with SHA-256. Use architecture variants when release
  artifacts differ; do not use a mutable URL without a digest.
- Prefer the typed resources for APT packages, users, directories, services,
  web routes, permissions, configuration, databases, timers, settings,
  secrets, policies, health, and backups.
- Store generated credentials using secret resources. Never place secrets in
  manifests, examples, plans, or test output.
- State ownership and reversibility explicitly. Avoid broad filesystem paths
  and global configuration changes.
- If a capability cannot be expressed, propose a typed resource/provider or a
  narrowly scoped Python hook with a declared contract. Do not add an
  unreviewed shell-script escape hatch.
- Keep package metadata in JSON and avoid duplicating resource declarations in
  a second installer manifest.

## Tool contract for agents

The Typer `nostrhost package` group is the package authoring interface:

```sh
nostrhost package schema
nostrhost package plan packages/my-app/package.json --output-as json
```

Schema and plan results are JSON. Agents should use the schema to form a
manifest and parse structured plan fields rather than matching prose. Planning
does not inspect or mutate installed host resources. Package reconciliation is
a separate write operation and must only run through the authorized control
path.

From a source checkout, prefix the command with the repository's
`PYTHONPATH=forks/yunohost/src` and run `forks/yunohost/bin/nostrhost`.
