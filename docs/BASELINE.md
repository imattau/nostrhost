# Baseline

Stage 1 of the roadmap: **fork baseline**. The goal of this stage is a
known-good, source-identical baseline before any Nostr-native change is
introduced.

> The derivative installs, boots and behaves identically to standard YunoHost.

## What "identical" means here

In Stage 1 no derivative OS image is built yet (building an image only becomes
meaningful once the forks deviate). Baseline identity is established by:

1. **Source identity** — every fork under `forks/` is a git fork of an
   upstream YunoHost component, checked out at exactly the upstream release
   tag that the `stable` apt pipeline ships (and that the live reference
   servers run). `scripts/verify-clean.sh` asserts each fork HEAD equals its
   pinned commit AND equals the upstream tag's commit, and that the working
   tree is clean.
2. **Behaviour identity** — the pinned source is the source the live
   reference servers (`YunoHost 12.1.x stable`, Debian bookworm) were built
   from, so the derivative is defined to behave identically by construction.
   Once a build pipeline exists, upstream's own test suites run against the
   pins in CI (`baseline.yml`).

## Pins

The authoritative record is `baseline/pins.yml`. Each pin is an upstream
`debian/<version>` release tag.

| component | upstream repo | fork | pin | live server |
|---|---|---|---|---|
| yunohost (core) | `YunoHost/yunohost` | `imattau/nostrhost-yunohost` | `debian/12.1.41.2` | 12.1.41.2 |
| portal | `YunoHost/yunohost-portal` | `imattau/nostrhost-portal` | `debian/12.1.2` | 12.1.2 |
| admin | `YunoHost/yunohost-admin` | `imattau/nostrhost-admin` | `debian/12.1.15` | 12.1.15 |
| ssowat | `YunoHost/SSOwat` | `imattau/nostrhost-ssowat` | `debian/12.1.1` | 12.1.1 |
| moulinette (dep, not forked) | `YunoHost/moulinette` | — (upstream) | `debian/12.1.4` | 12.1.4 |

`moulinette` is a hard dependency of the yunohost core package. It is pinned
as an upstream dependency in Stage 1 and forked only when the derivative
needs to change it.

## Dev rules

- **Derivative forks:** when the derivative deliberately changes a fork's
  behaviour (roadmap Phase 3 onwards), that fork moves onto its own branch
  (e.g. `nostrhost`), is marked `derivative: true` in `baseline/pins.yml`,
  and `verify-clean.sh` then reports "expected divergence" for it instead of
  requiring source-identity. The other forks stay source-identical.
- Bump a pin deliberately: update `baseline/pins.yml`, re-pin the submodule
  with `scripts/pin-forks.sh`, and re-run `scripts/verify-clean.sh`.
- `verify-clean.sh --strict` also detects a source-identical fork whose tag
  has drifted stale relative to upstream (e.g. a republished tag).

Status: `yunohost` is now a **derivative fork** on its `nostrhost` branch
(identity layer, Phase 3); `portal`, `admin` and `ssowat` remain
source-identical.

## How the baseline becomes the derivative

Later stages introduce, in order: extraction of reusable libraries (identity/
policy/catalogue) from `yunohost-nostr-auth`, `yunohost-mcp` and
`nostr-yunohost`; the internal relay + event model (the control plane, roadmap
§3, `CONTROL-PLANE.md`); identity events + projection; portal Nostr login and
native session creation; capability/delegation events; approval + execution
events; admin integration; catalogue sync + trust events; SSO simplification;
MCP adapter; OIDC; and finally distribution/release tooling (Debian repo,
installer image, upgrade repo, signing, release manifest). See `ROADMAP.md`
for the full plan. The fork baseline here is the floor every stage builds on.