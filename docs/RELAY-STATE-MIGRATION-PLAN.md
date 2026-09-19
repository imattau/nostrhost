# Relay-backed control state implementation plan

**Status:** in progress. WP0 (authority register), WP1 (frozen event
protocol, schemas, conformance corpus), WP2 (shared projector framework,
rebuild/verify/shadow, projection health), WP3 (durable capability
projection, identity rebuild, operationsd on the shared runtime, authorization
freshness), WP4 (NIP-51/NIP-78 list and preference projection, self-service
preferences), WP5 (catalogue + audit read models: NIP-77 negentropy
rebuild/verify for the catalogue, relay-derived endorsement/announcement/
profile reads with no local ledgers, signer-anomaly-annotated audit folding
with bounded `until` pagination), WP6 (kind-31101 policy declarations:
notification-rules / restic-policy / host-policy folded by nostr-policyd,
Restic desired state separated from its secrets, DDNS/security tokens already
in the credential broker) and WP7 (generated service configuration as a
provenance-tracked projection: nsite.toml / notify.toml / oidc.toml /
security.toml / ddns.toml with native validation, reload + post-reload
health-check rollback, and drift/reconcile tooling) are implemented — see
`authority/`, `docs/dev/authority-register.md` and
`docs/dev/projector-framework.md`. WP8 onward remain proposed.  
**Scope:** migrate NostrHost control-plane authority from overlapping TOML,
JSON and database stores to signed relay events or the ngit state repository,
while retaining local projections, secrets and bootstrap state where required.

## 1. Outcome

NostrHost has one explicit authority for every control-plane fact:

- signed relay events for identities, capabilities, permissions, trust lists,
  preferences, operation history and small independently replaceable settings;
- the ngit-backed semantic-state repository for atomic, multi-file desired
  machine configuration and its history;
- a local credential store for private keys, passwords and provider tokens;
- small root-owned bootstrap configuration for starting and securing the relay;
- local databases and generated files only where they are execution stores,
  transactional session state, caches or rebuildable projections.

The migration is complete when deleting any projection such as `identity.db`,
`catalogue.json` or generated service TOML and replaying its authoritative
source recreates the same effective state, without widening access or losing
an accepted operation.

This is not a goal to eliminate TOML, JSON or databases. It is a goal to
eliminate ambiguous and competing sources of truth.

## 2. Non-goals

- Do not put private keys, passwords, recovery bundles, DNS credentials,
  Restic credentials or OIDC signing keys in relay events.
- Do not turn application databases, website content, logs, blobs, backups or
  draft working directories into Nostr events.
- Do not replace Git/ngit semantic state with hundreds of fine-grained events.
- Do not make the relay depend on reading its own event stream before it can
  establish its root administrator, bind address or storage backend.
- Do not make remote/public relays authoritative for local machine control.
- Do not remove local projections when they provide atomic queries, bounded
  latency or compatibility with an existing service.

## 3. Authority classification

Every existing state item must be assigned exactly one of these classes before
it is migrated.

| Class | Meaning | Examples | Recovery rule |
|---|---|---|---|
| Event authority | A signed event or deterministic fold is canonical | identities, grants, lists, preferences, audit chain | replay relay events |
| Repository authority | An ngit commit is canonical | desired machine configuration, package/state manifests | restore and reconcile repository |
| Secret authority | Local encrypted/root-only material is canonical | operator keys, Restic password, DNS token | restore credential backup |
| Bootstrap authority | Minimal local configuration needed before relay reads are safe | operator trust anchor, bind address, DB paths | restore bootstrap bundle |
| Projection/cache | Rebuildable local read or execution model | `identity.db`, `catalogue.json`, rendered TOML/JSON | delete and rebuild |
| Transactional runtime | Short-lived, atomic or process-local state | challenges, sessions, OIDC codes, cursors | expire or restore local DB as appropriate |
| External/runtime truth | State owned by Linux or another engine | systemd state, CrowdSec DB, app DB, Restic repository | query/restore owning system |

No migration may proceed while two stores are documented as canonical for the
same fact.

## 4. Target allocation

### 4.1 Move to relay-event authority

| Current state | Target representation | Local result |
|---|---|---|
| `identity.db` mappings | kind `31102` addressable identity definitions | SQLite read projection |
| roles and scoped capabilities | kind `31100` addressable grants and existing delegation/revocation events | authorization projection |
| trusted publishers and approved repositories | NIP-51 people/repository sets where suitable; `31101` only for semantics a list cannot express | resolver cache |
| preferred and blocked relays | NIP-65/NIP-51 relay lists | relay-selection cache |
| app/domain access membership | NIP-51 lists with server-defined ownership and merge rules | `permissions.json` and portal projections |
| user and portal preferences | NIP-78 addressable application data | per-user settings cache |
| operation requests and lifecycle | existing `2200`-`2205` immutable chain | query index only |
| login/system/service/backup/security notices | existing `2206`, `2210`-`2213` events | notification cursor/index |
| catalogue declarations, releases and attestations | existing standard catalogue kinds plus the approved attestation kind | `catalogue.json` cache |
| small non-secret policy objects | schema-versioned `31101` addressable declarations | validated policy projection |
| notification recipients | private NIP-51 list or encrypted server-authoritative addressable document | rendered recipients configuration |
| notification rules | server-authoritative addressable policy document | rendered policy configuration |

### 4.2 Keep in the ngit semantic-state repository

Use repository state when a change benefits from an atomic diff, review,
known-good marking, rollback planning or coordination across several files:

- installed package and version intent;
- domain, DNS, certificate and network intent;
- nsite gateway and hosted-site desired state;
- security configuration;
- backup paths, retention and schedule, excluding credentials;
- service enablement and bounded service configuration;
- notification configuration if it must change atomically with other machine
  state;
- package manifests used to reconcile installed resources.

Relay events should announce the repository, request and approve changes,
reference the applied commit, record the result and replicate approved state
bundles. The repository remains the authority for the complete desired-state
document.

### 4.3 Keep local

| State | Reason |
|---|---|
| `events.db` | physical relay event store; moving it “into events” is circular |
| `policy.db` | immediate NIP-86 enforcement and relay bootstrap; mutations are auditable but the enforcement view remains local |
| minimal `relay.toml` | relay must know how and where to start before it can read events |
| `operator.toml`, `portal.toml`, recovery key bundle | contains signing keys and the root trust anchor |
| credential store and credential-bearing parts of `restic.toml` | secrets must not enter Git or the relay |
| login/link challenge DB | atomic single-use consumption is a local transaction |
| HTTP sessions, cookies, CSRF state and OIDC authorization codes | short-lived request-path security state |
| signer-session bookkeeping | user-local runtime metadata, not authority over identity |
| OIDC private signing key | private cryptographic material |
| application/CrowdSec/system databases | owned runtime state, not control-plane declarations |

## 5. Root of trust and bootstrap contract

Reduce the root-owned bootstrap file to the minimum needed to start safely:

```text
relay listen host and port
event-store and policy-store paths
primary operator public key
server/public service identities needed for initial writer policy
allowlist mode and hard safety limits
secret-key references or local secret paths
```

The primary operator public key remains a local recovery anchor. Additional
administrators, agents, capabilities and normal mutable policy are projected
from signed events after startup. A relay must never grant authority merely
because an event claims it; the event author must already be authorized by the
bootstrap root or by a valid capability chain rooted there.

At startup:

1. Load and validate bootstrap configuration.
2. Open the local policy and event stores.
3. Seed/reconcile the root operator and required service writers.
4. Start the authenticated loopback relay.
5. Replay authoritative definitions into projectors.
6. Enable mutating consumers only after their required projections report a
   valid revision.

If replay fails, keep the last-known-good projections for read/runtime
continuity, but fail closed for new privileged mutations.

## 6. Event protocol requirements

### 6.1 Common envelope

Every NostrHost-controlled addressable document must define:

- `schema`: positive integer schema version;
- `server`: stable server public key or server identifier;
- `subject`: stable resource identifier, mirrored in the `d` tag;
- `enabled`: explicit active/disabled state where revocation is meaningful;
- `revision`: monotonic logical revision scoped to the address;
- `updated_by`: omitted when identical to the signer, otherwise the initiating
  event ID, never an unsigned identity claim;
- `reason`: optional bounded, non-secret operator explanation;
- content fields defined by a checked-in JSON Schema.

Use standard Nostr tags for address, references and participants. Content must
be canonical JSON where hashes or fixture comparison depend on serialization.

### 6.2 Deterministic replacement and conflicts

- Accept events only from an author authorized for that event address.
- Select the greatest valid logical revision.
- Reject a revision that does not advance the current revision.
- When importing historical data with equal revisions, choose deterministically
  by `(created_at, event_id)` and emit a conflict notice.
- Enforce timestamp skew limits at relay ingress, but never use arrival order
  as authority.
- Use `enabled: false` for semantic revocation. NIP-09 deletion requests alone
  are insufficient for authorization revocation because replicas may retain
  the original event.
- Replaceable lists are revoked by a newer valid empty/changed list, not by
  physical database deletion.

### 6.3 Atomicity

Use one addressable document when all fields must change atomically, for
example a notification rule set. For a multi-resource change, place the atomic
configuration in ngit and publish one operation referencing its commit.

Do not invent cross-event transactions. A projector may support a bundle ID
for staging, but it must not expose a partial bundle as effective state.

### 6.4 Authorization rules

Maintain a checked-in matrix containing, for every kind/address family:

- permitted authors;
- required capability and resource scope;
- whether self-service publication is allowed;
- validation schema;
- encryption/privacy requirement;
- retention class;
- projection owner;
- external replication policy.

Relay writer permission is not equivalent to permission to change the host.
NIP-42 authenticates the connection, NIP-86 administers the relay, and the
NostrHost policy evaluator authorizes the semantic action.

### 6.5 Privacy

- Keep all control kinds protected by NIP-42 reads and writes.
- Encrypt private list entries/content where a standard permits it.
- Treat NIP-44 as confidentiality for event content, not as a secret-key
  vault; event metadata and long-term ciphertext still exist.
- Reject known secret field names and credential-shaped values in state-event
  validators where practical.
- Define external bridging per kind; default to no bridge for identities,
  permissions, administrative policy and operational detail.

## 7. Projector framework

Build a common projector contract before migrating more stores. Go and Python
implementations may differ, but must consume the same schemas and conformance
fixtures.

Required interface:

```text
Validate(event) -> accepted normalized fact or rejection
Fold(previous, fact) -> next deterministic state
Render(state, staging_path) -> projection candidate
Verify(candidate) -> validation result
Commit(candidate) -> atomic local replacement
Checkpoint(revision/event IDs) -> durable cursor
Rebuild(all relevant events) -> complete projection
Health() -> source revision, applied revision, freshness, last error
```

Implementation requirements:

- write projections through a temporary file/database followed by atomic
  rename or transaction;
- never checkpoint an event before its projection commits;
- make duplicate event delivery idempotent;
- tolerate out-of-order delivery by refolding affected addresses;
- quarantine invalid events with a bounded reason and publish a security or
  service notice without including secrets;
- support `--rebuild`, `--verify` and `--shadow` modes;
- expose source event IDs and schema versions in projection metadata;
- preserve the last-known-good projection if rendering or validation fails;
- place service cursors outside the authoritative configuration tree;
- include metrics for relay connectivity, lag, rejected events, rebuild time
  and applied revision.

For addressable state, rebuild by querying the complete valid address set. For
immutable chains, maintain a cursor ordered by `(created_at, event_id)` and
periodically reconcile using NIP-77 rather than assuming a WebSocket
subscription delivered every event.

## 8. Migration workflow for each store

Every migrated store follows the same gates.

### Gate A — inventory and schema

1. List every reader and writer.
2. Record current ownership/mode, secret fields and atomicity requirements.
3. Decide event versus ngit authority.
4. Check in the schema, author matrix, fixtures and migration mapping.
5. Define disable/revocation and downgrade behavior.

### Gate B — projector first

1. Implement the projector while the existing store remains authoritative.
2. Backfill signed events from existing data using an explicit migration
   signer and migration identifier.
3. Run the projector in shadow mode to a separate path.
4. Compare semantic state, ignoring representation-only differences.
5. Exercise duplicate, reordered, conflicting, invalid and revoked events.

### Gate C — event-first writes

1. Change all mutation paths to publish a signed request/event first.
2. Wait for relay acknowledgement and projector application.
3. Stop direct writes to the old authoritative store.
4. Retain an emergency feature flag that restores the old read path without
   producing divergent dual writes.

### Gate D — read cutover

1. Switch one consumer at a time to the projection.
2. Run audit comparisons during a defined soak period.
3. Make staleness visible and fail closed for privileged changes.
4. Back up the old store, mark it read-only and remove it from normal startup.

### Gate E — rebuild and recovery

1. Delete only the projection in a test environment.
2. Rebuild it from authoritative sources.
3. Verify byte-independent semantic equivalence and authorization behavior.
4. Restore onto a blank machine from bootstrap, secret backup, event replica,
   ngit state and Restic data.
5. Remove legacy authority code only after both tests pass.

## 9. Work packages

### WP0 — Complete the state inventory and authority register

**Deliverables**

- A machine-readable registry of state objects with class, owner, readers,
  writers, sensitivity, target authority, retention and recovery method.
- An architecture decision recording the hybrid event/ngit/local model.
- A CI check that every new persistent NostrHost path is added to the registry.
- A list of current direct-write call sites for each migration candidate.

**Initial inventory targets**

- `/etc/nostrhost/*.toml`, `.json`, `.env` and credential references;
- `/var/lib/nostrhost/*.db`, `.json`, cursor files and state directories;
- generated portal, Caddy, permission and service projections;
- catalogue and notification state;
- every SQLite/Bolt/Badger store in `nostrhost-auth` and
  `nostrhost-control`.

**Exit gate:** architecture review confirms one intended authority per fact
and no secret-bearing store is scheduled for event publication.

### WP1 — Freeze protocol schemas and authority rules

**Deliverables**

- JSON Schemas and positive/negative fixtures for kinds `31100`, `31101`,
  `31102`, delegation/revocation and the selected NIP-51/NIP-78 documents.
- A kind/address authorization and replication matrix.
- Deterministic revision, conflict and revocation rules.
- Schema-version compatibility policy: readers support current and previous
  versions; migrations publish a new revision rather than rewriting events.
- Cross-language conformance tests used by Go and Python consumers.

**Exit gate:** the same fixture corpus produces identical accepted/rejected
and folded outcomes in every implementation.

### WP2 — Implement projector infrastructure and observability

**Deliverables**

- Shared projector lifecycle and durable checkpoint format.
- Atomic file renderer and transactional SQLite projection helpers.
- `rebuild`, `verify`, `shadow` and health/status commands.
- NIP-77 reconciliation for missed events.
- Metrics and structured notices for lag, invalid events and failed renders.
- A projection-status API used by diagnosis and the Admin UI.

**Exit gate:** a synthetic projector survives process termination between
render and checkpoint, duplicate delivery, reverse delivery order and relay
unavailability without publishing partial state.

### WP3 — Finish identity and capability event authority  ✅ complete

Identity already treats kind `31102` as authoritative; this package completed
the cutover and established the reference implementation.

Delivered: `CapabilityProjection`/`CapabilityProjector` persisting `31100`
grants + `27236`/`27237` delegations to `/var/lib/nostrhost/capabilities.json`
(newest-replaceable stamping, atomic write, quarantine); `nostr-operationsd`
loads the projection before subscribing and runs on the shared
`ProjectionRuntime` (`apply` override + `prepare_replay` + `apply_in_thread`);
`nostr-projector rebuild|verify|shadow identity|capabilities`; identity rebuild
is data-only (no account provisioning) and the only `identity.db` writer is the
`31102` projector; API authorization reads the projection with a 300 s
freshness fallback to a single relay read; `verify` refolds on a fresh clone to
catch multi-row drift.

**Deliverables**

- Rebuild `identity.db` solely from valid `31102` events.
- Project `31100` capabilities/delegations into the authorization read model.
- Remove remaining direct identity/capability DB mutation paths.
- Enforce disabled definitions and delegation revocation immediately.
- Add freshness/version invalidation to API authorization caches.
- Preserve Unix account provisioning as an execution projection, not as the
  authority for the pubkey/account link.

**Exit gate:** deleting both identity/grant projections and replaying the
relay reproduces login, admin and operation-authorization decisions exactly.

### WP4 — Migrate NIP-51 lists and NIP-78 preferences  ✅ complete

Delivered: `nostrhost/list_specs.py` (family registry: kind, coordinate,
ownership subject, merge rule, self-service flag) and
`nostrhost/list_projection.py` (one `ListProjector` → `/etc/nostrhost/lists.json`
for kinds `10000`/`10002`/`10006`/`30000`/`30078`), run by `bin/nostr-listd`
on the `ProjectionRuntime`; family readers merge operator policy, mandatory
server restrictions and user preferences deterministically; importers publish
signed initial events preserving effective access; `list_render.py` keeps the
`catalogue.env` and per-domain portal compatibility files; the permission
projector (`nostr-permissiond`, kind 30000) is covered by tests; a portal
self-service `GET/PUT /preferences` publishes a user-owned NIP-78 document via
the server-attested identityd control path, never a host capability; the relay
allowlist (`CONTROL_KINDS`) now admits the WP4 kinds.

**Order**

1. preferred/blocked relays and nsite discovery lists;
2. trusted publishers and approved repositories;
3. app/domain permission membership;
4. portal and per-user preferences.

**Deliverables**

- Server-defined `d` coordinates and ownership rules for each list/settings
  family.
- Importers that publish signed initial events without changing effective
  access.
- Deterministic merge rules between operator policy, user preference and
  mandatory server restrictions.
- Permission and portal projectors producing current compatibility files.
- Self-service publication limited to preference/list addresses owned by the
  authenticated user; it must never imply a host capability.

**Exit gate:** app visibility/access and trust resolution remain identical
through rebuild, revocation and account deletion tests.

### WP5 — Migrate catalogue and audit read models ✅

**Deliverables**

- Treat catalogue declarations/releases/attestations in the relay as
  authoritative; make `catalogue.json` explicitly disposable.
- Replace any announcement/attestation ledgers that duplicate accepted events
  with derived indexes or idempotency checks against the relay.
- Build operation/audit queries from the `2200`-`2205` chain, including
  validation of signer, link and terminal-state precedence.
- Test histories larger than the relay query default; use bounded pagination
  or NIP-77 so older terminal events cannot be silently omitted.

Package TOML remains part of the signed/hashed artifact. Catalogue events
carry its digest, release coordinates and normalized discoverable metadata,
not an independently editable second manifest.

**Exit gate:** removal and rebuild of catalogue/audit indexes preserve the
same trusted catalogue and operation terminal states.

### WP6 — Migrate notification and small policy documents ✅

**Deliverables**

- Final decision: recipients/rules are an **addressable, schema-versioned
  kind-31101 document** (public, NIP-42-gated on the control relay), not a
  private NIP-51 or encrypted NIP-59 wrapper — the npubs and delivery rules are
  non-secret, and the frozen event protocol already standardises 31101.
- Addressable `notification-rules` document with the WP1 envelope
  (`schema`/`revision`/`value`).
- `nostr-policyd` projector renders the current notification TOML inputs
  (`recipients.toml`/`policy.toml`) for the Go daemon, so delivery is unchanged.
- `31101` policy declarations for small independent non-secret rules: the host
  operation safeguards (`host-policy`) are a 31101 document rendered back to
  `/etc/nostrhost/policy.toml`.
- Restic desired schedule/retention/paths are separated into the `restic-policy`
  31101 document; repo URL + password stay in the root-only `restic.toml`.
- DDNS/security desired config remains bootstrap; provider tokens already live
  in the credential broker (`secret:dns/<provider>/<name>`), never in the
  desired config.

Policy documents that must change atomically with machine state remain in the
ngit repository and are referenced by an applied-commit event instead.

**Exit gate:** notification delivery and policy evaluation continue after
deleting and rebuilding their projections; no secret appears in event
fixtures, relay queries or state commits.

### WP7 — Make generated service configuration a projection  ✅ complete

Delivered: a declarative `ServiceSpec` registry (`nostrhost/service_specs.py`)
plus a shared `render_managed`/`check_drift`/`reconcile` framework
(`nostrhost/service_projection.py`) that treats every generated service config
as a provenance-tracked projection — see `docs/dev/authority-register.md`.

- `nsite.toml` is rendered from the ngit desired-state revision, validated
  with the gateway's own Go checker (`nostrhost-nsite -check-config`), written
  atomically and SIGHUP-reloaded.
- `notify.toml` renders the non-secret fields provenance-tracked; the notifier
  private key is resolved from the local secret store at render time.
- Non-secret OIDC client registrations are a kind-31101 `oidc-clients`
  document folded into `oidc.toml`; each `client_secret` is resolved from the
  root-only credential store (`secret:oidc/<id>`) and never appears in the
  document.
- `security.toml` and `ddns.toml` (operator-derived schedules, no secrets) are
  rendered provenance-tracked through the same framework.
- Every render records a `<target>.source.json` sidecar (source revision +
  rendered sha256 + reload outcome); a post-reload health check rolls the file
  back when the consumer fails to come up healthy.
- Drift and reconcile are surfaced by `nostr-projector verify/reconcile
  service`, the `service.config.status` / `service.config.reconcile`
  operations (the latter records the reconcile in the operation chain), and
  the `/package/service/configs` API endpoint.

**Targets**

- `nsite.toml`;
- non-secret OIDC client registrations;
- notification service configuration;
- security/DDNS scheduling configuration;
- Caddy/permission/portal compatibility files;
- other bounded service files identified by WP0.

**Deliverables**

- Render each service configuration from one validated event document or one
  known-good ngit revision.
- Validate with the service's native config checker before atomic replacement.
- Reload rather than restart where supported; roll back the rendered file when
  health validation fails.
- Record source revision, rendered digest and service reload result in the
  operation chain.
- Store secret references in desired state and resolve them locally only at
  execution time.

**Exit gate:** every generated configuration identifies its source revision,
manual edits are detected as drift, and reconcile safely restores the desired
version.

### WP8 — Harden NIP-86 policy persistence without circular authority

`policy.db` remains the immediate relay-enforcement store.

**Deliverables**

- Emit a protected audit event for every successful NIP-86 mutation, including
  actor, method, target and non-secret reason.
- Reconcile root admins and mandatory service writers from bootstrap on every
  start.
- Export/import a signed policy snapshot for disaster recovery, but require
  the bootstrap root to authorize its restoration.
- Define precedence: immutable safety defaults and bootstrap root, then valid
  NIP-86 state; NostrHost capability events cannot grant NIP-86 authority.
- Test loss/corruption of `policy.db` without allowing an untrusted event to
  become relay administrator.

**Exit gate:** a blank policy store can be safely reconstructed from bootstrap
plus an authorized policy snapshot/audit history, and compromised semantic
events cannot alter relay-level authority.

### WP9 — Replication, backup and blank-machine recovery

**Deliverables**

- Per-kind replication policy: local-only, encrypted backup, selective bridge
  or public catalogue data.
- NIP-77 reconciliation between approved replicas where appropriate.
- Restic backup of local relay storage, bootstrap and encrypted credentials,
  with application-consistent snapshot procedure.
- ngit repository discovery plus state-bundle replication and verification.
- Documented key-loss, relay-loss, projection-loss and full-machine recovery
  runbooks.
- Automated blank-VM recovery acceptance test.

Do not assume an event is durable merely because it is signed. At least one
tested independent copy must exist for every authoritative control event.

**Exit gate:** a blank VM restores the same identities, capabilities, desired
state and known-good projections, then passes health validation without using
the old machine's projection files.

### WP10 — Cutover, compatibility removal and documentation

**Deliverables**

- Feature flags removed after the soak period.
- Legacy direct writers rejected with actionable errors.
- Obsolete authority/import code removed while projection compatibility files
  remain where consumers still need them.
- Admin UI shows source revision, projection health, drift and rebuild action.
- Operator documentation explains which files may be edited, which are
  generated, and how to recover.
- Upgrade and downgrade behavior documented for each schema version.

**Exit gate:** CI fails on an unregistered persistent store, a direct write to
an event-authoritative projection, or a generated file without provenance.

## 10. Rollout and rollback controls

Use four explicit modes per migrated subsystem:

| Mode | Writes | Reads | Purpose |
|---|---|---|---|
| legacy | old store | old store | pre-migration |
| shadow | old store plus signed backfill/event publication | old store; compare projection | validate semantics |
| event-first | event only | old store until projection catches up | validate write pipeline |
| event-authoritative | event only | projection | final state |

Avoid indefinite dual-write. It creates two authorities and ambiguous partial
failure. During event-first mode, a successful mutation means relay acceptance
and successful projection, not merely local file modification.

Rollback from event-authoritative mode changes readers back to the preserved
last-known-good legacy snapshot or projection. It does not resume unsynchronized
dual writes. Any accepted events remain authoritative and must be replayed
before attempting cutover again.

## 11. Testing strategy

### Unit and conformance

- schema acceptance and rejection fixtures;
- signature, author, scope and server-ID validation;
- revision, tie-break, revocation and list replacement;
- canonical rendering and secret-field rejection;
- idempotent fold under duplicate and permuted delivery.

### Integration

- publish → relay acknowledgement → projector → consumer read;
- NIP-42 protected read/write enforcement;
- capability revocation while a service is running;
- projector crash before and after atomic commit;
- relay restart, database lock and temporary unavailability;
- invalid future schema while the last-known-good projection remains active;
- ngit commit apply, health failure and assisted rollback.

### Security

- unauthorized writer with local loopback access;
- valid signer attempting an address outside its scope;
- replay of an older grant or enabled identity;
- NIP-09 deletion attempting to resurrect/erase authorization history;
- malicious encrypted/list content;
- event containing credential-like material;
- compromised agent attempting to grant itself capabilities;
- loss of `policy.db` and malicious attempt to become NIP-86 admin.

### Recovery

- projection-only loss;
- event-store loss with replica/backup recovery;
- ngit repository loss with bundle recovery;
- secret-store loss with recovery bundle;
- complete blank-machine reconstruction;
- operator-key rotation before and after replicated events.

## 12. Operational service levels

Define and monitor these before final cutover:

- maximum projector lag for authorization state: target seconds, not minutes;
- maximum tolerated projection age before privileged writes fail closed;
- event-store backup recovery point and recovery time objectives;
- required retention for immutable audit chains;
- rebuild duration at expected event volume;
- maximum event/query sizes and pagination behavior;
- notification when a projector is stale, quarantining events or repeatedly
  failing to render.

Reads that are not security-sensitive may continue from a marked stale
last-known-good projection. New grants, privileged operations and policy
changes must fail closed when their authority projection is unavailable or
beyond its allowed staleness window.

## 13. Dependency order and sizing

The strict dependency chain is:

```text
WP0 inventory
  -> WP1 schemas/authority
  -> WP2 projector framework
  -> WP3 identity reference cutover
  -> WP4-WP8 domain migrations
  -> WP9 recovery proof
  -> WP10 cleanup
```

After WP3 proves the pattern, WP4 catalogue/list work, WP6 notification/policy
work and WP7 service rendering can proceed independently, but none should
remove legacy authority before WP9 recovery primitives are available.

Indicative effort for one engineer familiar with the codebase is 12-18 weeks:

- 2-3 weeks for inventory, schemas and projector foundations;
- 2-3 weeks to complete identity/capability authority and conformance;
- 4-7 weeks for lists, catalogue, notification, policy and service projections;
- 2-3 weeks for replication, recovery drills and security testing;
- 1-2 weeks for soak, cleanup and operator documentation.

This is a sequencing estimate, not a release commitment. Each work package is
gated by demonstrated rebuild and authorization equivalence rather than elapsed
time.

## 14. Definition of done

The overall migration is done when:

1. Every persistent control-plane datum appears in the authority registry.
2. Every fact has one documented canonical authority.
3. All event schemas, author rules, revocation semantics and replication rules
   are checked in and tested.
4. Identity, grants, permissions, trust, preferences, catalogue and operation
   history rebuild from events.
5. Rich desired machine state rebuilds from ngit and reconciles through the
   policy/executor boundary.
6. Secrets never appear in relay events, Git state, notices or diagnostic
   output.
7. The relay starts securely from minimal local bootstrap state without
   trusting its own unvalidated event history.
8. Projections are atomic, observable, drift-detecting and disposable.
9. A complete blank-machine recovery has passed automatically and manually.
10. Legacy direct writers and undocumented authority stores are removed.

