# Authority register

**Status:** WP0–WP4 (complete) of
[`docs/RELAY-STATE-MIGRATION-PLAN.md`](../RELAY-STATE-MIGRATION-PLAN.md). The
projector framework is documented in
[projector-framework.md](projector-framework.md).

The register gives NostrHost **one explicit authority for every persistent
control-plane fact**. It exists so that no fact has two documented canonical
stores and so that deleting a projection and replaying its authority recreates
the same effective state.

- Machine-readable data: [`authority/registry.toml`](../../authority/registry.toml)
- Event authority matrix: [`authority/authority-matrix.toml`](../../authority/authority-matrix.toml)
- Event protocol (schemas + conformance corpus): [`authority/event-protocol/`](../../authority/event-protocol/README.md)
- Contract: [`schema/authority-registry.schema.json`](../../schema/authority-registry.schema.json)
- Guards: `tools/authority_registry.py` and `tools/event_protocol.py`
  (run by `.github/workflows/authority.yml`); the Go reference
  `libs/nostrhost-control/internal/eventprotocol` runs in `libraries.yml`.

## Class model

| Class | Meaning | Recovery rule |
|---|---|---|
| `event` | A signed relay event or deterministic fold is canonical | replay relay events |
| `repository` | An ngit commit is canonical | restore and reconcile repository |
| `secret` | Local encrypted/root-only material is canonical | restore credential backup |
| `bootstrap` | Minimal local config needed before relay reads are safe | restore bootstrap bundle |
| `projection` | Rebuildable local read or execution model | delete and rebuild |
| `transactional` | Short-lived, atomic, or process-local state | expire or restore local DB |
| `external` | State owned by Linux, YunoHost, Restic, or the agent | query or restore owning system |

A fact is one of: event, repository, secret, bootstrap, projection,
transactional, or external — never two. `secret` entries must not name an
`events:` authority; the CI guard rejects that.

## What is already event-authoritative

| Fact | Authority | Projection |
|---|---|---|
| pubkey ↔ account link | kind `31102` | `identity.db` (`nostr_identityd`) |
| capability scopes | kind `31100` | `/var/lib/nostrhost/capabilities.json` (WP3) |
| delegation / revocation | kinds `27236` / `27237` | same file (`revoked`/`delegations`) |
| app/domain permission sets | NIP-51 kind `30000` | `nip51_permissions.json` → `permissions.json` |
| trusted publishers / approved repositories | NIP-51 kind `30000` people sets | `lists.json` → `catalogue.env` |
| preferred / blocked relays, nsite blocklist | NIP-51/65 kinds `10002`/`10006`/`10000` | `lists.json` (+ mandatory merge) |
| portal settings / per-user preferences | NIP-78 kind `30078` | `lists.json` → `portal/<domain>.json` |
| operation request→result audit | kinds `2200-2205` | relay event store, live fold |
| notices | kinds `2206`, `2210-2213` | notification service / agent triggers |
| catalogue declarations/endorsements/attestations | kinds `32267` / `30079` / `30080` | `catalogue.json` |
| desired machine state | ngit repo | `state-repository`, kind-`2214` bundles |

## Direct-write inventory (no signed event first)

These are the writer call sites that mutate a store directly rather than
publishing a signed event. They are recorded under `direct_writes` in the
registry so a rename or removal is caught. Each maps to a later work package.

| Store | Direct writers | Plan |
|---|---|---|
| `accounts.json`, `ssh-keys.json` | `forks/yunohost/src/nostrhost/accounts.py`, `forks/yunohost/src/user.py`, `forks/yunohost/src/nostrhost/portal_api.py:63` | WP3 keeps account provisioning an execution projection; link authority stays `31102` |
| `permissions.json`, `portal/<domain>.json` | `forks/yunohost/src/nostrhost/permissions.py:260,208`, `forks/yunohost/src/permission.py:630`, `forks/yunohost/src/user.py:95`, `forks/yunohost/src/domain.py:367,553` | WP4 — recompute from events + projection |
| `signer_sessions.db` | `forks/yunohost/src/nostr_account.py:343,397,415` | local runtime by design (transactional) |
| NIP-86 `policy.db` | `libs/nostrhost-control/internal/policy/store.go`, `.../internal/relay/server.go:369-404` | WP8 — audit event per mutation + signed snapshot |
| catalogue derived index (endorsements `30079`, announcements `1`, profile `0` read back from the control relay; no local files) | `forks/yunohost/src/nostrhost/native_ops.py:1216-1300` | WP5 — done (relay-derived; replaceable `d`-tag/`version`-tag idempotency) |
| notification `recipients.toml` / `policy.toml` | `forks/yunohost/src/nostrhost/cli.py:1416-1417` | WP6 — addressable notification document |
| rendered service config (`nsite.toml`, `catalogue.env`, `connectivity.json`) | `forks/yunohost/src/nostrhost/nsites/service.py`, `.../connectivity.py`, `.../cli.py` | WP7 — provenance-tracked projections |
| bootstrap config (`relay.toml`, `operator.toml`, `policy.toml`, `portal.toml`) | `forks/yunohost/src/nostr_identity.py:280-348`, `forks/yunohost/src/nostrhost/cli.py` | bootstrap/secret authority (intentional) |

## Known competing-authority findings (to resolve in later WPs)

These are the ambiguities the migration exists to remove. They are recorded
here so the register stays honest about current overlap:

1. **Two admin stores** — `operator.toml:admins`/`operator_pubkey` vs
   `policy.db:admins`. NIP-86 grants are intentionally reconciled away on
   restart (`store.go:96-134`, `server.go:74-80`). WP8 hardens this.
2. **Allowed kinds are additive-only** — `relay.toml:allowed_kinds` seeds
   `policy.db`, but NIP-86 `allowkind`/`disallowkind` mutate the same buckets
   with no reconcile, and `relay.toml:denied_kinds` is parsed but never applied
   (`config.go:41`; no use in `server.go`).
3. **Three policy concepts** — host `/etc/nostrhost/policy.toml` (operation
   safeguards), relay `policy.db` (relay access), and notification
   `state/notifications/policy.toml` (delivery) are independent. WP6/WP8
   assign each one authority.
4. **Unused trust primitive** — kind `31101` is defined, schema-validated and
   admin-gated in `nostrhost-control`, but has no producer or projector.
   WP1/WP6 make it real.
5. **Ledger duplication** — the two catalogue ledgers (attestations,
   announcements) and the profile cache duplicated the node's own
   already-relayed events. WP5 removed them: endorsements/announcements/profile
   are read back from the control relay (`query_chain_events(authors=…)`),
   attest idempotency is the replaceable `30079` `d`-tag, and announce
   idempotency a `version` tag.
6. **Two chain readers** — `/package/operations` paginates
   (`fetch_chain_events`), while `audit.list` used an unpaginated REQ
   (`query_chain_events`). WP5 unified both on `page_all` bounded `until`
   pagination; the audit view folds each operation through
   `_operation_entry` with signer-anomaly annotation (never dropping events).

## WP1 — frozen event protocol

[`authority/event-protocol/`](../../authority/event-protocol/README.md) freezes
the common envelope, the revision/conflict/revocation rules, the schema-version
compatibility policy, and a cross-language conformance corpus.

The corpus is the source of truth. Two references consume it and must agree:

| Reference | Command |
|---|---|
| Python | `python tools/event_protocol.py conformance` |
| Go | `go test ./internal/eventprotocol/...` (in `libs/nostrhost-control`) |

Writing the corpus exposed a real gap: the Python reference and the corpus were
stricter than the relay's `eventmodel`. The relay accepted several documents the
frozen contract rejects. WP1 therefore **tightened `eventmodel`** to enforce the
contract, so the relay and the corpus now agree by construction (the Go
`eventprotocol` package delegates to `eventmodel`). Changes:

- the shared envelope (`schema >= 1`, `revision >= 0`, `subject` mirrors `d`);
- `31100`: `d` hex-64, non-empty `type`, `scopes` must be an array of strings;
- `31101`: envelope `schema` is required;
- `31102`: `enabled`/`admin` must be booleans when present, `signer_type` enum;
- `27236`: `expiry` must be a positive integer.

The Go module is standalone, so it bundles a byte-identical fixture mirror under
`libs/nostrhost-control/internal/eventprotocol/testdata/`; a test fails on
drift. Regenerate it with `python tools/event_protocol.py sync-mirror`.

## WP3 — identity and capability reference cutover

**Exit gate:** deleting the identity and grant projections and replaying the
relay reproduces login, admin and operation-authorization decisions exactly.

What the cutover changed:

1. **Capabilities are durable.** `31100` grants and `27236`/`27237`
   delegations are no longer in-memory-only: `nostr-operationsd` folds them
   through `CapabilityProjector` into
   `/var/lib/nostrhost/capabilities.json`, loads that file before subscribing,
   and keeps the in-memory fields as a mirror for the state recorder.
   `nostr-projector rebuild capabilities` refolds from the relay.
2. **Identity is rebuild-only-event.** The only `identity.db` writer is
   `handle_identity_event`, driven by the `31102` projector;
   `nostr-projector rebuild identity` replays the mapping. `MappingStore.link`
   /`unlink` are test-only library helpers, not production call sites.
3. **Accounts are execution, not authority.** A `31102` materialisation may
   create a YunoHost account (`ensure_user`) as a side effect, but rebuilds
   pass `accounts=None` — account provisioning never runs during a state
   rebuild and never defines the pubkey↔account link.
4. **Revocation is immediate.** Admin-authored empty scopes, `enabled:false`,
   and `27237` revocations fold straight into the projection; the HTTP
   authorizer reads the projection, and delegation authority is clipped by the
   delegator's *live* direct authority, so revoking a delegator instantly
   removes every derived scope.
5. **Freshness/version invalidation.** `default_authorizer` gates non-admin
   callers by reading the persisted projection and only falls back to a single
   relay read when it is missing or older than
   `FRESHNESS_WINDOW_SECONDS` (300 s), failing closed on error — replacing the
   previous per-request relay query.

## WP4 — NIP-51 lists and NIP-78 preferences

**Exit gate:** app visibility/access and trust resolution remain identical
through rebuild, revocation and account-deletion tests.

What the cutover established:

1. **One coordinate registry.** `nostrhost/list_specs.py` declares every
   family's kind, `d` coordinate (or per-author/operator subject), who may
   author it, whether it is self-service, and its merge rule. The projector
   and the self-service publisher both read it, so ownership cannot drift.
2. **Deterministic merge.** Membership lists merge additively where declared;
   a `mandatory` server restriction always wins; NIP-78 settings merge
   field-by-field with the server's `mandatory_restrictions` re-applied last.
   The reads (`trusted_publishers`, `approved_repositories`, `blocked_relays`,
   `portal_settings`, `user_preferences`) return the effective view.
3. **Importers preserve access.** `import_trusted_publishers` /
   `import_approved_repositories` publish the current effective set as a
   signed event, so publishing the initial event does not change who is
   trusted.
4. **Self-service is coordinate-bounded.** Only
   `nostrhost:user-preferences:<pubkey>` is self-servable, only by that
   pubkey; the portal route resolves the session → linked pubkey and the
   projector re-checks ownership. No host list is self-service, so a user can
   never grant themselves a capability.
5. **Permission membership** (kind 30000) stays operator-authored and is
   merged additively with LDAP membership; the projector now has direct tests.

## Adding an entry

See [`authority/README.md`](../../authority/README.md). In short: add a
`[[state]]` block, choose one `class` and `sensitivity`, name the
`target_authority`, give a concrete `retention` and `recovery`, list any
`direct_writes`, then run:

```sh
python tools/authority_registry.py check
```

The CI job fails on an unregistered persistent path, a `secret` entry pointing
at event authority, an invalid enum, a missing required field, or a
reader/writer/direct-write file that no longer exists.
