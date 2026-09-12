# Native Admin and Package Authoring Plan

**Status:** active
**Scope:** NostrHost admin SPA, its native API integration, Debian package, and the package-authoring workflow exposed through admin and CLI tools.  
**Target:** Debian 12 (Bookworm), with a native NostrHost admin and package toolchain. This is a clean cutover; YunoHost admin API, installer, package-name, and URL compatibility are out of scope.

## Objective

Build an admin interface for NostrHost's native identity, policy, operation, and package planes. Make package development predictable for both people and AI agents: packages should be described declaratively, schemas and examples should be machine-readable, validation should return actionable errors, and plans should be explainable before any privileged operation runs.

The YunoHost admin source is a useful starting point for selected UI patterns and components. Its existing YunoHost screens and API semantics are not the product specification. Reuse only what maps cleanly to NostrHost concepts.

## Current state and required changes

1. **The native asset route is implemented.** Vite and the release manifest use `/yunohost/admin/`; Caddy serves the SPA from `/usr/share/nostrhost/admin` at that path.
2. **The umbrella BOM now owns the admin package.** The admin component's stale YunoHost Debian packaging has been removed; its core recommendation now names `nostrhost-admin` and `nostrhost-portal` at their NostrHost versions.
3. **The former YunoHost UI could not use the native API as-is.** Its old routes and unused UI dependencies have been removed from the shipped admin build. The NIP-07 package screen now sends JSON to `POST /package/plan`; Caddy proxies that route to the native API on loopback port 8190. Package writes continue through the separate policy and approval path.
4. **The SPA builder now owns build and package assembly.** Toolchain, install/build commands, and output directories are declared in the BOM. CI calls the builder after setting up Node 22; there is no separate SPA shell build step.
5. **Native package lifecycle is declarative.** `package.toml` and the resource engine describe files, permissions, routes, health, and backups without per-app Bash. The mixed legacy/native test app should become a clean native package fixture; old installer support is not a target requirement.
6. **The AI authoring surface uses the existing Typer CLI.** `nostrhost package schema` publishes the checked-in JSON Schema and `nostrhost package plan` validates a JSON manifest and returns a plan. This replaces the redundant argparse package wrapper; package lifecycle tests remain.

## Implementation progress on Debian 12

- Complete: native `/yunohost/admin/` SPA route, sole NostrHost admin package definition, core recommendations, SPA build/package command, Typer package schema/plan commands, checked-in JSON Schema, and AI authoring guide.
- Complete: NIP-98-signed `POST /package/plan`, matching Caddy proxy to the native API, and NIP-07 package planning UI using the shared JSON package contract.
- Complete: dormant legacy YunoHost admin modules and unused frontend dependencies were removed from the SPA build graph; the package API is separate from YunoHost's legacy API route.
- Complete: current screen inventory and first-release decisions in [ADMIN-FEATURE-MATRIX.md](ADMIN-FEATURE-MATRIX.md).
- Remaining: generated client contract, system-health and catalogue UI, richer identity management, typed operation submission/status/history, clean native test package lifecycle, and disposable package test runner.

## Target architecture

- **Admin frontend:** static SPA distributed as `nostrhost-admin`. The release BOM supplies `/admin/` to the Vite build; a packaging contract test keeps that value aligned with Caddy. No install-time script is needed for the static asset package.
- **Native API:** versioned endpoints with typed JSON inputs/outputs, structured errors, operation IDs, and idempotency for writes. Model APIs after package, identity, policy, and operation concepts rather than translating legacy YunoHost endpoints.
- **Authentication and authorization:** supported Nostr signer integration creates short-lived, request-bound NIP-98 events. The browser never receives the server operator secret or persists raw private keys in app storage. Every mutating endpoint enters policy/approval/execution; no endpoint accepts arbitrary shell commands.
- **Package lifecycle:** `package.toml` expresses desired resources. The resource engine validates, plans, applies, verifies, upgrades, removes, and registers backup inputs. Per-package imperative install/upgrade/remove scripts are not the normal extension mechanism.
- **Package tooling:** a Python library owns build, validation, schema, and plan behavior. A Typer CLI provides a usable human/agent entry point. One release BOM remains authoritative for APT package metadata.
- **AI authoring loop:** inspect schema/examples → scaffold package → edit declaration → validate → inspect JSON plan → run isolated tests → build artifact → request policy-authorized install. AI tooling may create and check declarations, but privileged execution remains behind the existing approval boundary.

## Implementation phases

### Phase 0 — Define native product scope and contracts

**Work**

- Inventory the admin UI by screen and user goal. For each feature, decide: implement natively, defer, or drop. Do not port a screen solely because it exists upstream.
- Inventory current native API/CLI/provider capabilities. Map every selected admin action to an existing or planned typed operation, noting read/write status, authority requirement, request/response types, and health/backup implications.
- Select the first useful release slice: signer connection and identity status; system/daemon health; trusted native package catalogue; package validation/plan review; approval/execution status; operation history/results.
- Specify route, API versioning, signer UX, error envelope, progress model, and the boundary between catalogue trust and user-provided package declarations.

**Deliverables**

- Native admin feature matrix with prioritized decisions and operation owners (`docs/ADMIN-FEATURE-MATRIX.md`).
- API/auth contract for the first slice.
- NostrHost route and asset-path configuration source.

**Exit checks**

- Every selected UI action maps to a typed native operation.
- Out-of-scope legacy screens are excluded from navigation and build scope.
- Mutations have a defined policy, approval, execution, and result path.

### Phase 1 — Consolidate package metadata and SPA build

**Work**

- Keep `packaging/packages.yml` (or a deliberate replacement) as the sole APT release BOM. Remove the unused YunoHost Debian package metadata from the admin component; update core recommendations and package graph to NostrHost names.
- Declare SPA build inputs in metadata: source directory, pinned Node/package-manager versions, frozen install command, build command, output directory, install directory, and route/base path.
- Move SPA build execution into the Python package builder so local and CI builds follow one path. Fail on missing, empty, or unexpected build output; never package a stale `dist/` silently.
- Add maintainer/agent commands such as `nostrhost package build admin`, `nostrhost package verify`, and `nostrhost package publish`. Use Typer for the command surface, while keeping core functions independently testable.
- Remove YunoHost-owned names and paths from the admin package metadata, core dependency declarations, Caddy route, and production SPA build config. No transitional package, alias route, or old-package upgrade bridge is required.

**Deliverables**

- One command builds `nostrhost-admin` from a clean checkout.
- CI invokes the same command with a pinned toolchain.
- BOM, generated package control fields, core dependencies, Caddy, and SPA base path agree.

**Exit checks**

- Clean checkout build is deterministic with lockfile enforcement.
- Built `.deb` has the expected files at the declared path and no custom `postinst` behavior.
- Dependency graph and generated `.deb` metadata validate.

### Phase 2 — Make package authoring AI-friendly

**Work**

- Publish a versioned JSON Schema for `package.toml`, generated from or checked against the Pydantic model. Include descriptions, examples, enums, defaults, resource ownership rules, risk semantics, and cross-field constraints.
- Add `nostrhost package init <id>` to scaffold a minimal valid package and selectable patterns (static site, systemd service, database-backed service, timer/worker). Scaffold comments should explain decisions and point to canonical docs; do not bake unnecessary values into generated packages.
- Add `nostrhost package validate <path>` with stable machine-readable output (`--json`): code, JSON/TOML path, message, severity, and remediation hint. Keep human output concise and deterministic.
- Expand `nostrhost package plan <path> --json` into a stable, versioned plan format that includes resource IDs, dependencies, risk, reversibility, ownership, required backup/approval, and verification steps. Add `package explain` or equivalent to turn each operation into a plain-language explanation without changing the plan.
- Provide canonical minimal and complete examples, a resource reference, package lifecycle guide, security model, and a troubleshooting index. Keep these machine-indexable and avoid duplicating schema facts in prose.
- Add an optional package-authoring MCP/tool surface over the same library: schema lookup, scaffold, validate, plan, and test dispatch. Tool results must be structured and bounded. The tool must not bypass policy or execute privileged package changes.
- Add a disposable test harness: validate declaration, resolve pinned sources, build package, apply to a disposable VM/container with the same providers, assert health and declared state, then test upgrade/remove/backup behavior as applicable.
- Keep package-specific behavior declarative. Extend the engine with typed resources or narrowly scoped typed hooks when needed; reject arbitrary shell scripts as an undocumented escape hatch.

**Deliverables**

- Generated schema, scaffolds/examples, JSON diagnostics, stable plan output, and package authoring documentation.
- CLI and optional MCP commands for the same package library.
- A machine-runnable package conformance test format and isolated runner.

**Exit checks**

- An AI agent with only schema/docs/tool outputs can create a valid example package without reverse-engineering implementation code.
- Invalid declarations return precise field-level errors and actionable fixes.
- A plan can be reviewed and explained without host mutation.
- Package tests execute only in an isolated target and report deterministic structured results.
- Privileged apply still requires policy and approval, regardless of whether a person or AI authored the manifest.

### Phase 3 — Implement the native Admin API and auth

**Work**

- Add typed endpoints for identity/session, system health, trusted packages, package validate/plan, operation submit/status/history, and approval state for the initial slice.
- Use NIP-98 request signing with correct HTTP method, URL, payload hash, timestamp/freshness handling, and bounded replay protection. Agree on signer interface (NIP-07, NIP-46, or both) before frontend integration.
- Keep reads and writes explicit. Plan is read-only. Apply requires a plan digest, actor, policy decision, and any required approval; results link to operation and resource IDs.
- Return stable structured errors and progress/events. Use SSE or event-backed polling with reconnect and refresh recovery.
- Enforce same-origin routing and a deliberate CORS/cookie policy. Browser cookies are not an authorization mechanism for this API.
- Add authorization and request validation tests: missing/invalid/expired signature, unknown identity, insufficient capability, replay, malformed body, duplicate submission, denied approval, and authorized success.

**Deliverables**

- API schema and backend implementation.
- Shared backend/frontend contract tests and generated TypeScript client types.
- Security review of signer custody, replay behavior, and admin/delegation policy.

**Exit checks**

- Rejected requests cause no provider mutation.
- Every completed write links signed request → plan digest → policy/approval → execution → verification result.
- Operations remain recoverable after page reload or network interruption without accidental resubmission.

### Phase 4 — Build the first native admin vertical slice

**Work**

- Replace the legacy API client with a typed native client; remove old routes, form-encoded payload behavior, cookie assumptions, and YunoHost error adapters.
- Build signer connection/identity display, system health, native package catalogue, package detail/provenance, validation feedback, plan review, approval state, execution progress, and operation history.
- Show affected resources, risk/reversibility, backup requirements, and verification expectations before a write.
- Add UI states for signer unavailable, unauthorized, pending approval, denied, failed, partially completed, reconnecting, and completed-but-unverified.
- Apply current NostrHost branding and accessible interaction patterns; run focused keyboard, screen-reader, contrast, and responsive checks on shipped screens.

**Deliverables**

- Useful browser-based native admin for the first release slice.
- Feature/component tests for auth, plan review, operations, errors, refresh, and reconnect.

**Exit checks**

- No shipped screen calls the legacy YunoHost API.
- UI reports success only after executor result and verification pass.
- User can understand why a package plan is safe or requires approval before applying it.

### Phase 5 — Prove package lifecycle through the admin

**Work**

- Replace the mixed YunoHost/native `nostrhost-test` fixture with a minimal native package used to exercise the whole developer and operator workflow.
- From the admin, inspect a trusted declaration, validate it, review its plan, approve, apply, verify health, and inspect the linked operation/state/backup record.
- Exercise a package authored through the AI-friendly scaffold/tool loop, then upgrade and remove it according to resource ownership and backup rules.
- Expand admin features only as corresponding native APIs/providers are implemented and covered by the feature matrix.
- Remove leftover YunoHost installer scripts, API routes, package names, and comments from the NostrHost target once no native build or test depends on them.

**Deliverables**

- End-to-end VM proof for native install, upgrade, remove, backup linkage, denial, and recovery.
- Documented first-party workflow for human and AI package authors.
- Updated package/core manifests with only NostrHost names and dependencies.

**Exit checks**

- A clean supported VM completes the end-to-end path using only native declarations, API, policy, and providers.
- Upgrade/remove preserve or delete data exactly as declared and authorized.
- AI-authored package passes the same validation, review, and isolated tests as a human-authored package.
- No legacy installer or API adapter is required by the native product.

## Cross-cutting verification

- **Package model:** schema/Pydantic parity, field diagnostics, migration-free native examples, dependency graph, deterministic JSON plans, operation ownership and reversibility.
- **Build:** clean reproducible SPA build, package file/control inspection, pinned toolchain, no pre-generated assets required.
- **API/security:** NIP-98 validation and replay controls, identity/capability enforcement, denial-before-mutation, idempotency, redacted errors, policy/approval traceability.
- **Frontend:** lint/type-check, contract/client tests, plan and operation states, accessibility review.
- **End-to-end:** signer → validate → plan → approval → provider execution → health → backup/state linkage; include denial and interrupted/retry cases.
- **Platform:** test on each Debian release NostrHost explicitly supports; the static nature of the SPA does not establish platform support by itself.
- **AI workflow:** schema discovery, scaffold, validation errors, plan explanation, isolated tests, artifact build, and policy-gated apply are exercised as one documented loop.

## Decisions before implementation

1. **Resolved for the first package-authoring screen:** NIP-07; NIP-46 and signer recovery UX are follow-up work.
2. Which admin capabilities are required in the first native release, and which upstream screens are dropped?
3. **Resolved:** the admin is served at `/admin/`; the versioned native API prefix is `/api/v1`.
4. Should the optional package-authoring MCP tools be delivered with the first package tooling release or after the CLI/schema contract stabilizes?
5. Which Debian releases are first-class targets for the native admin and package test runner?

## Recommended order

Complete the feature/API matrix first. In parallel, consolidate BOM ownership and make SPA build/package reproducible. The schema/scaffold/JSON-plan authoring loop, initial read-only `/api/v1` package contract, and first NIP-07 package-authoring screen are implemented. Next deliver health/catalogue and operation views against typed contracts, then prove the lifecycle with the disposable package test harness and VM before expanding screens.
