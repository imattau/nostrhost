# Core Internal-Library Extraction

## Summary

Implement the three high-confidence extractions in dependency order:

1. Create a cross-language `nostrhost-protocol` library.
2. Consolidate shared authentication primitives into `nostrhost-auth`.
3. Extract the existing projector framework into `nostrhost-projection`.

Use copy-then-rewire migrations, preserve all wire formats and persisted state, and keep compatibility imports for one release. Operation-client, browser-auth, and testkit packages remain follow-up candidates.

## Implementation Changes

### 1. `nostrhost-protocol`

- Create `imattau/nostrhost-protocol` as a new submodule under `libs/`, following the existing library ownership and pinning model.
- Structure it as a language-neutral specification plus standalone Python and Go bindings:
  - `spec/`: event manifest, JSON Schemas, envelope rules, verdict fixtures, and fold fixtures.
  - `python/`: installable `nostrhost-protocol` package.
  - `go/`: module `github.com/imattau/nostrhost-protocol/go`.
- Move the authoritative material from `authority/event-protocol` into `spec/`; leave a compatibility README at the old path and update the authority registry and documentation.
- Define a machine-readable manifest containing event names, numeric kinds, category, schema version, schema reference, and stable rejection codes.
- Expose equivalent Python and Go APIs:
  - Kind constants.
  - `Verdict` and `FoldResult` types.
  - `validate_event`, `fold_events`, and schema-loading functions.
  - Go equivalents accepting `go-nostr` events.
- Rewire the control relay, YunoHost operation/projection code, policy delegation checks, root conformance tooling, and agent event handling to use the library.
- Keep existing application-level constants as deprecated aliases for one release. Remove private Go `internal/eventmodel` and mirrored fixtures after every consumer passes against the library.
- Add the submodule to `.gitmodules`, `baseline/pins.yml`, library CI, architecture documentation, and authority checks.

### 2. Authentication consolidation

- Make `nostrhost-auth` the sole owner of generic authentication and cryptographic identity primitives:
  - `nostrhost_auth.keys`: NIP-19 public/private key conversion and canonical parsing.
  - `nostrhost_auth.events`: signed/unsigned event models, signing, ID computation, and verification.
  - `nostrhost_auth.nip98`: NIP-98 verification.
  - `nostrhost_auth.replay`: replay protection.
  - `nostrhost_auth.signing`: client request signing.
  - `nostrhost_auth.server_identity`: server signing identity.
- Add Pydantic to `nostrhost-auth` because the canonical event models are typed there.
- Change `nostrhost-policy` to depend on `nostrhost-auth` and `nostrhost-protocol`. Keep authorization-specific identity resolution, roles, scopes, groups, delegations, revocations, confirmations, audit, locks, and redaction in policy.
- Replace the old `nostrhost_policy.auth` primitive modules with compatibility re-exports preserving exception identity and call signatures.
- Rewire YunoHost and active MCP consumers to import the canonical auth APIs directly. Do not modify the frozen `libs/yunohost-mcp` reference implementation.
- Delete duplicate implementations from policy only after all workspace imports have migrated; retain the re-export modules for one release and document their removal target.

### 3. `nostrhost-projection`

- Create `imattau/nostrhost-projection` as a Python library submodule under `libs/`.
- Extract the existing projector lifecycle without changing behavior:
  - `Projector`, `ProjectionRuntime`, and `ProjectionRegistry`.
  - `Checkpoint`, `ProjectionHealth`, and `ProjectionResult`.
  - Atomic commits, quarantine, rebuild, verify, shadow, and status reading.
- Add explicit `RelayTransport` and `AuthProvider` protocols so the package no longer imports private YunoHost identity functions. Supply a default adapter using `nostrhost-auth`.
- Preserve the current WebSocket transport during extraction; migrating it to `nostr-sdk` is a separate parity-tested change.
- Keep cursor paths, checkpoint JSON, quarantine behavior, ordering, and health output compatible.
- Rewire identity, permission, policy, list, capability, service, and operation projectors to import the package. Keep only YunoHost-specific rendering, paths, service control, and domain logic in the fork.
- Remove `yunohost.nostr_projector` after a one-release compatibility module that re-exports the new package.

### 4. Release sequence

- Land and release protocol first, then auth/policy, then projection.
- For each library: copy code and tests, prove standalone packaging, release/pin the library, rewire consumers, and only then remove the old implementation.
- Update superproject submodule pins only after the corresponding library and consumer commits are available.
- Rollback consists of reverting consumer imports and the submodule pointer; no data migration or persisted-state rollback is required.

## Public Interfaces and Compatibility

- Event numbers, JSON envelopes, validation order, stable rejection codes, folds, operation-chain behavior, HTTP APIs, and stored events remain unchanged.
- Existing auth and projector import paths remain compatibility aliases for one release and emit deprecation warnings without changing exception behavior.
- Projection checkpoint files under `/var/lib/nostrhost/projections` remain readable without conversion.
- Libraries must install and test independently without umbrella-relative paths.
- Dependency direction becomes acyclic: protocol and auth are foundational; policy depends on both; projection depends on protocol and auth; applications depend on the libraries.

## Test Plan

- Run the verdict and fold corpus through both protocol bindings and require identical results, including malformed content, tag validation, conflicts, revisions, and revocations.
- Add manifest/schema consistency tests, duplicate-kind detection, stable-code snapshots, standalone Python wheel installation, and standalone Go module tests.
- Run the complete auth and policy suites against canonical and compatibility imports. Cover malformed keys, wrong key types, signature failures, timestamp bounds, NIP-98 body hashes, replay, and concurrent replay attempts.
- Run projector unit and fault-injection tests for initial replay, NIP-42 authentication, reconnects, duplicate and out-of-order events, invalid-event quarantine, atomic-write failure, checkpoint ordering, rebuild, verify, shadow, and last-known-good preservation.
- Run all YunoHost Nostr tests, control and agent Go tests, MCP tests, authority checks, packaging builds, and dependency-cycle checks.
- Add drift guards rejecting newly introduced local event-kind definitions or copied protocol fixtures outside compatibility modules.

## Assumptions

- New reusable libraries follow the existing separate-repository/submodule model and use AGPL-3.0-or-later.
- Python remains at 3.11+, and Go bindings follow the minimum Go version of current consumers.
- This phase introduces no TypeScript protocol binding; the language-neutral specification will support one when frontend consumption is required.
- No changes are made to the frozen `libs/yunohost-mcp` implementation.
- Operation-client, browser-auth, and shared-testkit extraction will be reconsidered after these foundations have at least two active consumers and stable APIs.
