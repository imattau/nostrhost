# Writing a native app package

A native app describes desired resources in a manifest. NostrHost validates
and plans those resources before any change reaches the host.

## Start a package

```bash
nostrhost-package init my-app
nostrhost-package validate my-app/package.json
nostrhost-package plan my-app/package.json --json
nostrhost-package explain my-app/package.json
```

Use `nostrhost-package --help` for the exact options installed on your system.
The canonical schema is `schema/package.schema.json`, and examples live under
`packages/`.

## Declare the whole lifecycle

A complete package should declare, as needed:

- package identity, version, source, and trust metadata;
- Unix users and groups;
- directories, ownership, and modes;
- runtime and database requirements;
- systemd services and health checks;
- Caddy routes and access policy;
- settings and secret references;
- backup and restore coverage; and
- removal behaviour.

Do not embed plaintext secrets or arbitrary install, upgrade, and removal shell
scripts. Add a typed resource and provider when the platform lacks a required
primitive.

## Distribute as an .npk artifact (npack)

A native package can be published as a signed, content-addressed `.npk`
artifact using the bundled `npack` binary (see the `forks/npack` submodule).
This replaces repository-manifest catalogue distribution and URL `[source]`
fetching with publisher-signed release events (kind 9900), NIP-94 artifact
metadata, and Blossom storage. The resource engine still plans and applies
resources; npack is the discovery, integrity, and transport layer.

Build a package root whose payload sits at host-relative paths, then pack it:

```bash
cargo build --release --manifest-path forks/npack/Cargo.toml

NPACK_BIN="$PWD/forks/npack/target/release/npack" \
nostrhost-package build-npk my-app/package.toml \
  --payload my-app/payload \
  --output my-app-0.1.0.npk \
  --publisher <npub-or-hex>
```

The command validates the manifest (the `[app] version` must be valid SemVer),
embeds the canonical native manifest at `.npack/nostrhost/manifest.json`,
runs `npack pack` (a deterministic tar.zst archive), and prints the artifact
SHA-256. Verify the artifact with `npack verify my-app-0.1.0.npk`.

## Install from a verified .npk artifact

Installation uses the hybrid staged store. The `npack` binary resolves the
publisher-signed release (kind-9900), verifies its signature, revocation state
and SHA-256, and stages the payload into an isolated `--store` prefix at
host-relative paths. The resource engine then plans the native resources from
the embedded manifest (binding the artifact SHA-256 into the approved plan
envelope) and applies them through the normal signed request -> policy ->
approval -> execute chain, copying the staged payload into place with
`payload.sync`.

CLI:

```bash
nostrhost app install-npk <publisher>/<name>[@<version>] \
  [--relay wss://relay.example] [--store /var/lib/nostrhost/npack-store]
```

MCP/HTTP: `package.install` stages the release and returns the plan envelope;
submit it to the approval-gated `package.reconcile` (or the
`/package/npk/install/plan` + `/package/npk/install/apply` HTTP endpoints).
`npack update --check` reports available upgrades; removal reverses the
recorded manifest (including the payload sync).

See `packages/nostrhost-npk-example/` for a complete buildable example.

### Pre-install setup values (not yet wired into nostrhost)

Upstream npack (`forks/npack`, pinned at `81d9de1` "Add extensible install
input metadata") added a publisher-signed `app.install_inputs[]` descriptor
array (id, namespaced `value_type`, `required`, `sensitive`, `description`,
`constraints`), discoverable through `resolve`/`GetPackage` and validated
against a new `install_values{}` map on the npackd daemon's `Install` RPC.
This is a *pre-install* setup contract — distinct from this repo's own
`[settings]` package.toml section, which is *post-install* config-panel state
(`app.config.read/set`, webadmin).

Nothing in nostrhost populates or consumes `install_inputs` yet:
`build_npk_artifact` (`forks/yunohost/src/nostrhost/package_authoring.py`)
calls `npack init`/`npack pack` without setting them, and `npk.py::stage()`
shells out to the `npack` CLI `install` subcommand, which upstream did not
extend to accept `install_values` (only the daemon RPC path was). Treat this
as a known gap, not a bug, until a package.toml section, build-pipeline
plumbing, and an install-time value-collection step are designed.

## Planning and application

Authoring-time planning validates the TOML manifest, resolves dependencies,
and returns ordered operations. It is read-only. Installation through Admin or
the catalogue creates a server-side plan envelope with a digest and provenance,
then submits that envelope through the normal policy and audit path. The
executor verifies it again before applying resources. Do not edit an approved
plan by hand or treat authoring output as an approval token.

## Package quality checklist

- Validation rejects missing and unexpected fields.
- Replanning produces the same result for the same inputs.
- A second reconciliation is safe and converges.
- Health checks detect a broken service or route.
- Backups include all durable data and restore successfully.
- Upgrade and URL changes preserve data and access.
- Removal deletes only declared package-owned resources.
- Logs contain no secrets.
- Permissions are least-privilege and public access is explicit.

Test install, upgrade, backup, restore, URL change, and removal on a clean VM.
