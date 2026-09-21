# nostrhost-npk-example

A native NostrHost package that demonstrates the npack-based distribution
flow (hybrid staged store). The payload under `payload/` is packed together
with the canonical native manifest into a deterministic `.npk` artifact.

## Build the .npk

```bash
# build npack once (the pinned fork):
cargo build --release --manifest-path forks/npack/Cargo.toml

NPACK_BIN="$PWD/forks/npack/target/release/npack" \
nostrhost-package build-npk packages/nostrhost-npk-example/package.toml \
  --payload packages/nostrhost-npk-example/payload \
  --output /tmp/nostrhost-npk-example-0.1.0.npk \
  --publisher <npub-or-hex>
```

The command validates the manifest, embeds the canonical native manifest at
`.npack/nostrhost/manifest.json`, runs `npack pack` (deterministic tar.zst)
and prints the artifact SHA-256. `[app] version` must be valid SemVer.

## What the archive contains

```text
.npack/manifest.json                     npack metadata (skipped on install)
.npack/nostrhost/manifest.json           canonical native package.toml
var/www/nostrhost-npk-example/from-payload.html   payload at host-relative path
```

`npack verify <artifact>` proves the archive hash. Installing uses the hybrid
staged store: `npack` resolves the publisher-signed release and stages the
payload into an isolated `--store` prefix, then the resource engine plans the
native resources from the embedded manifest (binding the artifact SHA-256 into
the approved plan) and applies them through the signed chain, copying the
staged payload into place with `payload.sync`.

```bash
nostrhost app install-npk <publisher>/nostrhost-npk-example \
  [--relay wss://relay.example] [--store /var/lib/nostrhost/npack-store]
```

The `package.install` MCP tool (and `/package/npk/install/plan` +
`/package/npk/install/apply` HTTP endpoints) expose the same staging + plan
flow, with apply going through the approval-gated `package.reconcile` path.