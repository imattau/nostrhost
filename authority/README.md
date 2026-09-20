# Authority register

This directory is the checked-in, machine-readable answer to **"what is the
authority for this fact?"** for every persistent control-plane datum in
NostrHost. It implements WP0 of
[`docs/RELAY-STATE-MIGRATION-PLAN.md`](../docs/RELAY-STATE-MIGRATION-PLAN.md).

- `registry.toml` — one `[[state]]` entry per persistent fact.
- `authority-matrix.toml` — one `[[kind]]` row per event kind/address family.
- `event-protocol/` — compatibility marker; the envelope, per-kind schemas, and
  the cross-language conformance corpus now live in the reusable
  `libs/nostrhost-protocol` library (`spec/`, `python/`, `go/`), consumed by
  `tools/event_protocol.py` and the Go binding (WP1).

The human guide, including the direct-write inventory, is
[`docs/dev/authority-register.md`](../docs/dev/authority-register.md).

## Classes

| Class | Meaning | Recovery rule |
|---|---|---|
| `event` | A signed relay event or deterministic fold is canonical | replay relay events |
| `repository` | An ngit commit is canonical | restore and reconcile repository |
| `secret` | Local encrypted/root-only material is canonical | restore credential backup |
| `bootstrap` | Minimal local config needed before relay reads are safe | restore bootstrap bundle |
| `projection` | Rebuildable local read or execution model | delete and rebuild |
| `transactional` | Short-lived, atomic, or process-local state | expire or restore local DB |
| `external` | State owned by Linux / YunoHost / Restic / the agent | query or restore owning system |

## Invariants enforced by CI

`tools/authority_registry.py check` (run by `.github/workflows/authority.yml`)
fails when:

1. a persistent path discovered in the source tree is not covered by a
   registry entry;
2. a `secret` entry names an `events:` authority (secrets never go on the
   relay);
3. a required field is missing or an enum is invalid (validated against
   `schema/authority-registry.schema.json`);
4. a referenced reader/writer/direct-write source file does not exist.

## Adding an entry

1. Add `[[state]]` to `registry.toml`. `path` is an absolute host path, an
   absolute glob (`/var/lib/nostrhost/state/**`), a repo-relative path, or a
   logical coordinate (`in-memory:Name`, `relay:kind`).
2. Pick exactly one `class` and one `sensitivity`.
3. Name the `target_authority` (see the header comment) and give a concrete
   `retention` and `recovery` rule.
4. If the store is mutated without first publishing a signed event and it
   holds event/repository authority, list those call sites under
   `direct_writes`.
5. Run:

   ```sh
   python tools/authority_registry.py check
   ```

## Inspecting

```sh
python tools/authority_registry.py scan       # paths discovered in source
python tools/authority_registry.py validate   # registry vs its schema
python tools/authority_registry.py check      # full guard
```
