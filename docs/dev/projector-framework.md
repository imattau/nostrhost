# Projector framework

**Status:** WP2 of [`docs/RELAY-STATE-MIGRATION-PLAN.md`](../RELAY-STATE-MIGRATION-PLAN.md).

Projectors materialise durable read models from signed relay events. Before
WP2, `nostr-identityd`, `nostr-permissiond` and `nostr-operationsd` each
re-implemented the same WebSocket replay/AUTH/backoff loop and had no durable
checkpoint, no rebuild/verify mode and no health surface.

The shared framework is `forks/yunohost/src/nostr_projector.py`. Consumers
subclass `Projector` and run it through `ProjectionRuntime`.

## Lifecycle contract (§7)

| Method | Responsibility |
|---|---|
| `validate(event)` | accept a normalised fact, or reject (quarantine) |
| `fold(current, fact)` | next deterministic state |
| `render(state)` | projection candidate (text), or `None` for no-op |
| `commit(candidate)` | atomic install (temp file + rename / transaction) |
| `_advance(event)` | persist the checkpoint — **only after commit succeeds** |
| `health()` | source revision, applied revision, freshness, quarantine |
| `apply(event)` | validate → fold → render → commit → checkpoint |

`ProjectionRuntime` owns the relay subscription: NIP-01 `REQ`, NIP-42 `AUTH`,
replay buffering, deterministic ordering (`sort_events`, with a per-kind
priority like operationsd's replay priority), reconnect backoff, future-skew
rejection and per-event quarantine.

## Operational modes

`bin/nostr-projector` (packaged in `nostrhost-core`):

```sh
nostr-projector status [--json]           # all projection cursors
nostr-projector rebuild <name> [--json]   # refold the full event set
nostr-projector verify <name> [--json]    # shadow-compare, report drift
nostr-projector shadow <name> --to <path> # render without touching live
```

Programmatic equivalents: `rebuild()`, `verify()`, `shadow()`.

## Guarantees

- **Atomic writes** — projections and cursors go through a temp file in the
  same directory, `fsync`, then `os.replace`.
- **Checkpoint after commit** — a failed commit never advances the cursor, so
  a restart replays from the last good event.
- **Idempotent duplicates** — re-applying an event is safe (replaceable folds
  and `_advance` are stable).
- **Out-of-order tolerance** — replay is sorted before folding.
- **Quarantine, not fatal** — an invalid event is recorded with a bounded
  reason and the projector continues; the cursor does not silently skip it.
- **Cursors outside the config tree** — `/var/lib/nostrhost/projections/`, so
  losing them only costs a replay (`authority/registry.toml`
  `projection-cursors`).

## Observability

- `/package/projections` API route → `projection.status` tool (read-only,
  `server.read`) reads the cursor files cross-process.
- `diagnosers/65-projections.py` reports fresh/stale/missing-revision per
  projection (translation keys `diagnosis_projection_*`).
- `ProjectionRegistry` (in-process) exposes live `Health()` for daemons that
  want to publish richer status.

## Migrated so far

| Projection | Status |
|---|---|
| `permissions` (NIP-51 kind 30000) | runs on `ProjectionRuntime`; `rebuild`/`verify`/`shadow` wired into `nostr-projector` |
| `identity` (kind 31102) | runs on `ProjectionRuntime`; `nostr-projector rebuild identity` replays the mapping |
| `operations` (chain 2200-2205 + capabilities 31100/27236/27237) | migrated onto `ProjectionRuntime` (WP3) via the `apply` override + `prepare_replay`; capability grants fold into the persisted projection below |

## Runtime extension points (added in WP3)

`ProjectionRuntime` grew three knobs so a daemon that is more than a pure
projection can reuse the loop:

- **`apply`** — overrides per-event application. `nostr-operationsd` passes
  `engine.handle_event`, so execution and projection share one subscription.
- **`prepare_replay`** — called with the raw replay buffer *before* it is
  sorted and applied. operationsd uses it to mark already-executed request ids
  from terminal results, so a restart never re-runs an approved write.
- **`apply_in_thread`** — runs each application in a worker thread, because
  operationsd's handler does blocking relay round-trips and state snapshots
  while the websocket must keep draining during a replay burst.

## Capability/authorization projection (WP3)

`forks/yunohost/src/nostr_capability_projection.py` makes the authorization
read model durable:

- `CapabilityProjection` — a JSON fold of `31100` grants and
  `27236`/`27237` delegations with the exact decision semantics the executor
  applies (admin bypass, direct scope, delegated scope clipped by expiry and
  the delegator's own live authority). Newest replaceable grant wins (stamped
  by `(created_at, event_id)`), so an older replay cannot clobber a revoke.
- `CapabilityProjector` — the WP2 `Projector` that validates (admin author,
  signature, server key, scope set, expiry/lifetime, delegator authority),
  quarantines rejects and atomically writes
  `/var/lib/nostrhost/capabilities.json`.
- `load_capabilities` / `capabilities_are_fresh` — the cross-process read and
  freshness guard the HTTP authorizer uses.

`nostr-operationsd` loads the file at start (falling back to a relay refresh
when missing/stale), folds new grants through it, and mirrors its state into
the legacy in-memory fields the state recorder reads. `bin/nostr-projector
rebuild capabilities` refolds from the relay with per-kind queries (the
badger NIP-33 truncation rationale).

## List / preference projection (WP4)

`forks/yunohost/src/nostrhost/list_projection.py` projects the host's NIP-51/
NIP-65/NIP-78 families (kind `10000` mute list, `10002` preferred relays,
`10006` blocked relays, `30000` people sets, `30078` application data) through
one `ListProjector` into `/etc/nostrhost/lists.json`. The family coordinates,
ownership and merge rules are declared in
`forks/yunohost/src/nostrhost/list_specs.py`:

- **subject** — `coordinate` (the `d` value), `author` (per-author replaceable
  slots like relays/mute lists) or `operator` (one host-wide slot);
- **merge** — `additive` (server ∪ user), `operator-wins`, `user-wins` or
  `mandatory-wins` (a server restriction no preference may override);
- **self-service** — only the per-user preference coordinate
  (`nostrhost:user-preferences:<pubkey>`) is self-servable, and only by its
  own pubkey; every host list is operator-only, so a user can never grant
  themselves a host capability.

`bin/nostr-listd` runs the projector on `ProjectionRuntime`; `bin/nostr-projector
rebuild|verify|shadow lists` are wired. Compatibility files are rendered by
`forks/yunohost/src/nostrhost/list_render.py` (trusted publishers →
`catalogue.env`, portal settings → the per-domain portal files, preserving the
permission-owned `apps` key).

## Verify semantics

`verify(projector, expected)` refolds the event set on a **fresh clone** of
the projector and compares rendered output to the live projection, catching a
missing or stale row anywhere in a multi-row projection. Projectors opt in by
implementing `clone()`; the framework falls back to the render-latest contract
otherwise.

## Not yet done (per §7)

- NIP-77 Negentropy reconciliation for missed events (replay-only today).
- `--shadow` comparison against a live legacy store during soak.
- Per-projection metrics export (the health dict is the current surface).
