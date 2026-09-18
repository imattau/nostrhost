# Packaging and releases

NostrHost is distributed as a set of Debian packages built from pinned
components. `packaging/packages.yml` is the package bill of materials and
`packaging/compatibility.yml` records cross-component constraints.

## Package groups

- `nostrhost` installs the complete server.
- `nostrhost-core-system` installs a headless server.
- Component packages provide the core, relay, catalogue, notifications,
  Caddy, security configuration, Admin, Portal, libraries, and runtime.
- `nostrhost-agent` is optional and never enabled automatically.
- MCP client tooling is installed on the client machine, not pulled into the
  server by a meta-package.

## Local checks and builds

```bash
packaging/scripts/verify-dependencies
packaging/scripts/generate-meta-package -o packaging/build
packaging/scripts/build-package --name nostrhost-control -o packaging/build
packaging/scripts/publish-deb --repo packaging/repository packaging/build/*.deb
```

The dependency check must pass before release. Build affected components from
clean pinned sources and test the resulting packages on Debian 12 rather than
only running code from a checkout.

## Runtime dependencies

Python dependencies unavailable at suitable Debian versions are pinned and
bundled into `nostrhost-runtime`. The package creates the managed environment
under `/opt/nostrhost/venv`. Change a pin through the runtime requirements and
bump the package version; never repair a target with manual `pip` commands.

## Publish

The release workflow builds packages, verifies the dependency graph, creates a
signed APT repository, and publishes it under the project's Debian repository
path. Publication requires the configured signing key and fails closed without
it. Never publish an unsigned repository or tell users to add `[trusted=yes]`.

## Release checklist

1. All component commits are available and top-level pins are correct.
2. Unit, component, integration, and relevant VM tests pass.
3. Package dependency and compatibility checks pass.
4. Upgrade and fresh-install paths work from built packages.
5. Backup and restore work across the changed version.
6. Documentation matches the released CLI and behaviour.
7. Repository metadata and signatures verify from a clean client.
