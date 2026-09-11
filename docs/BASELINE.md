# Baseline

The current derivative baseline. The original Stage-1 goal was a known-good,
source-identical fork baseline before any Nostr-native change; that stage is
long complete and the core fork is now a derivative on its own branch. This
file records where the platform pins sit today and the rules for changing them.

## Pins

The authoritative record is `baseline/pins.yml`. Each fork is a git fork of an
upstream YunoHost component, pinned to a `debian/<version>` release tag and
(depending on the fork) either source-identical at that pin or a derivative on
its own branch.

| component | upstream repo | fork | pin | branch | derivative |
|---|---|---|---|---|---|
| yunohost (core) | `YunoHost/yunohost` | `imattau/nostrhost-yunohost` | `debian/12.1.41.2` | `nostrhost` | yes (identity layer, packaging, native core) |
| portal | `YunoHost/yunohost-portal` | `imattau/nostrhost-portal` | `debian/12.1.2` | `dev` | yes (Nostr login + redesign) |
| admin | `YunoHost/yunohost-admin` | `imattau/nostrhost-admin` | `debian/12.1.15` | `dev` | yes (app-shell redesign) |

The core fork ships as the **`nostrhost-core`** Debian package (renamed from
`yunohost`; a transitional empty `yunohost` package Depends on it and the core
`Provides/Replaces/Conflicts` the old name). Moulinette is removed: the native
`python3-nostrhost` framework replaces it and is no longer a dependency.
SSOwat is retired (Caddy `forward_auth` replaced it).

## Dev rules

- **Derivative forks:** a fork that deliberately diverges from upstream moves
  onto its own branch (e.g. `nostrhost`), is marked `derivative: true` in
  `baseline/pins.yml`, and `scripts/verify-clean.sh` reports "expected
  divergence" for it instead of requiring source-identity.
- Bump a pin deliberately: update `baseline/pins.yml`, re-pin the submodule
  with `scripts/pin-forks.sh`, and re-run `scripts/verify-clean.sh`.
- `verify-clean.sh --strict` also detects a source-identical fork whose tag has
  drifted stale relative to upstream.
- Every core-fork commit lands on `nostrhost` (and is mirrored to
  `moulinette-removal` where applicable); the umbrella records the fork head in
  `baseline/pins.yml` (`pin_commit`) and as the `forks/yunohost` submodule
  pointer. The apt pipeline (`apt.yml`) builds from that pinned head and
  publishes the repo to GitHub Pages.

## Status

The core fork is a **derivative** on its `nostrhost` branch. The architectural
half of the roadmap is largely realised (control plane, identity/policy,
catalogue, notifications, state layer, Caddy/CrowdSec cutover, native
packaging). The platform has moved to closing its own loops: native bootstrap,
DNS, secrets, release/update, and proving the full install/upgrade/recovery
path — see `docs/ALPHA-PLAN.md` and the Phase-2 section of `docs/ROADMAP.md`.

## How the derivative was built

The stages that moved the baseline from source-identical to derivative are
recorded in `docs/ROADMAP.md`: extraction of the identity/policy/catalogue
libraries; the internal relay + event model (control plane); identity events +
projection; capability/delegation events; approval + execution events; the
ngit/NIP-34 state layer; portal Nostr login; Restic linkage + assisted
rollback; the native catalogue; Caddy `forward_auth` (SSOwat retired);
declarative reconciliation; and the componentised Debian distribution.