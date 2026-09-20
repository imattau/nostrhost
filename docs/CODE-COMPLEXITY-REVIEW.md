# NostrHost Whole-of-Code Complexity Review

**Date:** 2026-09-20
**Scope:** the parent repository plus all 12 submodules declared in
`.gitmodules` at their current checkouts. The 12 submodules measure ~198k
lines and the parent repo's own committed source ~2.4k lines (python, Go,
TypeScript, Vue). This review changes no public API, schema, or stored data;
it delivers an evidence-backed inventory and a ranked refactoring backlog.
Application code is not modified by this review.

**Method:** static inventory of every component's dependencies, largest modules
and functions, branching, duplication, protocol handling, validation,
persistence, retries, caching, CLI/UI utilities, and observability code;
independent verification of each backlog candidate against the source.
Line counts below are from the working tree at the pinned submodule commits
(`baseline/pins.yml`), excluding `.git`, `node_modules`, virtualenvs,
`__pycache__`, `dist`, `.nuxt`, `.output`, and the gitignored VM testbed
`testbed/vm`.

---

## 1. Component inventory

### 1.1 Parent repository (exclusive of submodules)

Small by comparison with the forks: ~2.4k committed Python lines across
`tools/`, `packaging/scripts/`, and `schema/`, plus the `scripts/` fork-pin
tooling.

| Surface | Lines | Role |
|---|---|---|
| `tools/authority_registry.py` | 338 | validate `authority/registry.toml` (largest func `validate_registry` 32 l) |
| `tools/event_protocol.py` | 424 | NIP-34 state-event validation + folding |
| `tools/legacy_inventory.py` | 114 | report-only legacy resource-engine inventory |
| `packaging/scripts/build-package` | 586 | largest packaging script; builds each `.deb` kind |
| `packaging/scripts/publish-deb` | 222 | APT index regeneration |
| `packaging/scripts/verify-dependencies` | 174 | manifest dependency-graph check |
| `schema/*.json` | — | `package.schema.json`, `authority-registry.schema.json` |

Branching: `tools/`+`packaging/scripts/` show ~111 `if`, 15 `elif`, 46 `for`,
8 `try`. No third-party CLI/UI library is used (`argparse` throughout).
Generated/report-only tooling; no refactoring candidates beyond keeping the
two `schema/*.json` files in sync with the native package manifest (covered in
§3, adopt-typed-contracts).

### 1.2 `forks/admin` — Vue 3 + Vite admin SPA (22,230 lines)

Dependencies (`app/package.json`): `vue ^3.5`, `vue-router ^4.5`,
`nostr-tools`, `@lucide/vue`, `class-variance-authority`, `clsx`,
`tailwind-merge`. **No** Pinia, no axios, no TanStack Vue Query, no generated
client, no Orval/OpenAPI tooling.

- **API layer:** single fetch wrapper `app/src/api/client.ts` (30 s
  `AbortController` timeout, session-cookie + CSRF header, NIP-07/NIP-98
  fallback, `Idempotency-Key` on every POST, two error classes `ApiError` /
  `OperationError`). 22 hand-written typed modules in `app/src/api/`
  (`nativeSystem.ts`, `nativeOperations.ts`, `nativeUsers.ts`, …). Types are
  hand-written TS, **not generated** from OpenAPI.
- **Server state:** per-view-local data refs; no shared query cache. Session
  probe cached with a 30 s TTL (`useSigner.ts:33`). `useAsyncResource` (13
  views) is the screen-load loading/error pattern; `useActionRunner` (27 views)
  the mutation busy/error pattern. `useBusyAction`, `usePermissionAction`, and
  `useOperation` (an SSE composable) are **defined and tested but not imported
  by any view** — dead code today.
- **Polling:** `OperationsView.vue` only — `setInterval(pollPairing, 3000)`
  (`:77`), `setInterval(refreshQuietly, 15000)` + `visibilitychange` (`:179`,
  `:183–202`). Everywhere else reload is manual.
- **Retries:** none for mutations; poll loops swallow transient errors to the
  next tick. No query invalidation.
- Largest handlers (measured): `AppManagementView.vue applyPlan` 44 l,
  `nsites/CollectionsSection.vue doReview` 41 l,
  `PublishWizardSection.vue doUpload` 40 l, `useSigner._refreshSession` 33 l.
- 66 `.vue` files; 15 use `onMounted` directly, 13 via `useAsyncResource`.

### 1.3 `forks/portal` — Nuxt 3 user portal (4,565 lines)

Dependencies: `nuxt ^3.13`, `vee-validate`/`@vee-validate/yup`, `nostr-tools`,
`nostr-passkey`, `dompurify`. **No** Pinia, no TanStack Vue Query.

- `composables/api.ts` `useApi()` = fetch-once `$fetch` returning
  `{data, error}` refs; **no refetch/invalidate/reuse**; non-400/404 errors
  escalate to a fatal Nuxt error screen (`:17–68`).
- `composables/states.ts` `useSettings()`/`useUser()` fetch once and cache
  forever in `useState` with no TTL/invalidation (`:108–167`); after mutations
  these are never refreshed.
- `composables/asyncAction.ts` `useAsyncAction()` — shared busy/status banner
  boilerplate.
- **No server polling anywhere**; no mutation retries; no idempotency headers.
- `my-site.vue publish()` 67 l and `nostr-account.vue linkWithQr()` 41 l are
  the largest page handlers; they talk to the native `/package` API and the
  portal API with raw `$fetch` and inline interfaces.

### 1.4 `forks/installer` — custom Debian ISO builder (1,891 lines)

- **Console/UI is entirely custom:** `cli/clibella.py` (380 l) wraps
  `print()`/`input()` with centered colored `[PREFIX]` labels on `colorama`;
  `prompt_yes_or_no` uses regex loops (`clibella.py:341–380`). Progress via
  `tqdm` only for downloads (`net/download.py:64–77`). No Rich, Click,
  questionary, prompt_toolkit. No `isatty` detection; stdlib `input()` raises
  `EOFError` on closed stdin. Exit codes are plain `exit(0)`/`exit(1)`
  (`udib.py`).
- Largest funcs: `iso/injection.py inject_files_into_iso` 141 l, `udib.main`
  128 l, `gpg/verify.assert_detached_signature_is_valid` 119 l,
  `repack_iso` 107 l.
- Dependencies (`requirements.txt`): beautifulsoup4, colorama, requests, tqdm —
  no UI library.
- DNS/network module (`net/`) does **not** manage DNS records at all; it only
  downloads/scrapes ISO URLs.

### 1.5 `forks/yunohost` — core server-management engine fork (105,319 lines)

The largest component by far; the fork consumes the `nostrhost-*` libraries
rather than vendoring them, but retains a large custom API/CLI layer.

**Biggest modules (measured):**

| File | Lines | Note |
|---|---|---|
| `src/nostrhost/cli.py` | 4,103 | Typer app; `build_app` 1,904 l |
| `src/nostrhost/native_ops.py` | 3,110 | native op wrappers over the registry |
| `src/nostrhost/nsites/service.py` | 2,671 | **raw NIP-01 WebSocket** query loop + HTTP probes |
| `src/app.py` | 2,653 | legacy app lifecycle (`app_upgrade` 570 l, `app_install` 368 l) |
| `src/backup.py` | 2,589 | backup/restore |
| `src/nostr_operations.py` | 2,572 | operation registry; Pydantic `_Strict` input/result models |
| `src/nostrhost/api.py` | 2,533 | FastAPI admin API; `build_app` 1,796 l |
| `src/nostrhost/native_providers.py` | 2,120 | native provider adapters |
| `src/nostr_state.py` | 1,403 | ngit state repository |
| `src/nostr_operationsd.py` | 900 | executor daemon (replay idempotency) |
| `src/dns.py` | 1,050 | legacy lexicon-based DNS |
| `src/dyndns.py` | 530 | legacy Dynette/TSIG |
| `src/nostrhost/ui.py` | 261 | stdlib-only interactive CLI (`_require_tty` at `:70`) |

**API layer (`api.py`):**
- `build_app` is a single 1,796-line function registering **156 route
  decorators** plus 27 declarative GET forwards (`_SIMPLE_GET_FORWARDS`,
  `:154–196`); `portal_api.py:262–286` registers 25 routes programmatically.
  No `APIRouter`s.
- **Manual body parsing, no Pydantic:** `_json_body()` at `api.py:2426–2434`;
  ~326 `body.get(...)` sites and 11 `set(body) != {...}` key-set validations
  across handlers.
- **OpenAPI disabled:** `FastAPI(..., openapi_url=None)` at `api.py:593` and
  `portal_api.py:259`. There is no schema for client generation.
- **Auth:** NIP-98 verification in `nostrhost-policy/auth/nip98.py:49–113`
  (kind 27235, 60 s skew, `u`/`method`/`sha256(payload)` binding, replay last);
  portal-session cookie + HMAC CSRF (`api.py:256–278`); `_NIP98_REPLAY_CACHE`
  (`api.py:92`).
- **Error semantics:** `ApiError(status, code, message)` → envelope
  `{"error", "code"}`; unhandled exceptions → `500 internal_error` with no
  detail echoed (`api.py:517–561`); structured problem log in
  `nostrhost/problems.py`.
- **Idempotency:** plan/apply `plan_sha256` re-check (409 `plan_changed`);
  executor-level replay idempotency (`nostr_operationsd.py:204–214`,
  `:714–743`).

**DNS providers (`src/nostrhost/dns/providers/`):** custom minimal HTTP
clients — `cloudflare.py` (273 l, REST, per_page=100, `_MAX_PAGES=50`, TTL 300),
`desec.py` (260 l, cursor pages of 500, `_MAX_PAGES=10`), `duckdns.py` (127 l),
`dynu.py` (128 l), `dynette.py` (228 l, dnspython TSIG), `manual.py` (74 l).
All credentials via `secret:dns/<provider>/<name>` broker refs.

**Observability:** ~960 log/print call sites across `src/`; bounded JSONL
problem log; no Prometheus endpoints in the fork.

### 1.6 `libs/nostrhost-agent` — Go resident administrator (10,617 lines; ~7.3k prod)

- `agent/cycle.go` `CycleRunner.Run` 222 l (Observe→Retrieve→Plan→Evaluate→
  Approve→Execute→Verify state machine). `agent/registry.go` (303 l) contains
  the **hand-rolled partial reflective JSON Schema interpreter** —
  `validateGeneratedArguments` (`:85–109`), `validateGeneratedValue`
  (`:111–145`), `validateArgument` (`:239–262`), plus `isInteger`/`isNumber`
  coercion (`:271–295`). Supported subset: `type`, `enum`, `anyOf`,
  `properties`, `required`, `additionalProperties`; **not** interpreted:
  `$ref`, `oneOf`, `allOf`, `items`/nested subschemas, `minLength`/`maxLength`,
  `format`, numeric bounds. A second partial parse (`schemaProperties`) lives in
  `nostr_verifier.go:118–127`. Schema source is generated/embedded in
  `agent/catalog_generated.go` (178 KB, generated by
  `scripts/generate_operation_registry.py`).
- `agent/relay_transport.go` uses `nostr.NewSimplePool` with NIP-42 client auth
  (`WithAuthHandler`, `:57–59`); publish/subscribe via go-nostr; strict
  loopback/SSRF URL validation (`:219–235`).
- `agent/model_catalog.go` 433 l (GGUF model + llama.cpp runtime download).
- Branching: 1,243 `if`, 155 `for`, 12 `switch` across the module.
- **No third-party JSON-Schema library** in `go.mod` (only `nbd-wtf/go-nostr`).

### 1.7 `libs/nostrhost-auth` — Python identity library (1,966 lines; 1,211 prod)

13 modules. `auth/challenge.py` (153 l, sqlite single-use challenge store),
`auth/nostr_verify.py` (113 l, NIP-01 + BIP-340 via **Python `nostr-sdk`**),
`identity/mappings.py` (349 l), `identity/signer_sessions.py` (168 l),
`identity/relays.py` (146 l, NIP-65 over `nostr-sdk.Client`),
`identity/relay_cache.py` (79 l, sqlite TTL cache), `_sqlite.py` (94 l),
`nip05.py` (36 l). Small, focused; the dependency on the Python `nostr-sdk`
binding is the only non-stdlib platform dependency. No retry/backoff code.

### 1.8 `libs/nostrhost-policy` — Python policy library (5,275 lines; 3,113 prod)

`auth/` (nip98 65 l, replay 38 l, signing, delegation, owner, groups, npub,
revocation, key_resolve, identity) + `policy/` (roles, scopes, enforcement,
confirmation, package_sessions, locks 40 l) + `audit/` (log, decorator).
Pydantic-based. **This library is the canonical copy; the frozen
`yunohost-mcp` carries a verbatim mirror** — see §2 duplication. Largest funcs:
`enforcement.require_confirmation` 95 l, `decorator` 80 l. Retries exist only
in confirmation replay logic (no network retries).

### 1.9 `libs/nostrhost-catalog` — Go catalogue pipeline (4,649 lines; ~3k prod)

`internal/relay` `Client` (`client.go` 252 l) uses go-nostr `SimplePool` +
direct `RelayConnect`/`QuerySync` for historical reads; **NIP-77 negentropy
DOWN** sync replaces unbounded REQ to survive relay page truncation
(`negentropy.go:20–118`). `internal/publisher` builds kind 32267 declarations.
`internal/repository` verifies declarations by cloning at the exact commit and
re-hashing (`metadata.go:138–241`, `verifyCheckedOutDirectory` 51 l).
`internal/trust` = explicit-publisher allow-list + attestation policy.
Validation is regex/struct-based (`protocol/types.go:56–66`), **not** JSON
Schema. Branching: 563 `if`, 70 `for`, 2 `switch`.

### 1.10 `libs/nostrhost-control` — Go control plane (4,082 lines; ~2.5k prod)

`internal/relay/server.go` (474 l) = **khatru**-based local relay with NIP-42
read/write gates (`requireAuthPolicy` `:275–283`, `requireAuthForRead`
`:330–340`), protected kinds, badger store capped `MaxLimit: 20000` (`:120`).
the `nostrhost-protocol` Go binding (`go/validate.go`) + `internal/policy/store.go` 391 l
(bbolt-backed). `internal/notify` NIP-17/NIP-59 DM sender via `nip17` with
persisted `Since` cursor (`cmd/nostrhost-notify/main.go:89–111`).
`eventprotocol.go` `codeFor` 62 l. Branching: 391 `if`, 45 `for`, 17 `switch`.

### 1.11 `libs/nostrhost-mcp` — thin MCP protocol adapter (2,643 lines; 982 prod)

9 modules. `server.py` (332 l) generates tools from the fork's operation
catalog, streams the 2201→2205 chain (`_typed_events` 61 l), fails closed on
server-signature-verified results, nsite redaction. `http.py` (95 l)
`Nip98AuthMiddleware` (1 MiB body cap, actor contextvar). `auth.py` (54 l)
wraps `nostrhost-policy` NIP-98 + `ReplayCache`. `client.py` (107 l)
`OperationClient` verifies kind-2204 digest + server pubkey. **No JSON Schema
interpreter here** — schemas pass through from the fork catalog
(`registry.py` `tool_meta`). No raw WebSocket loops (mcp SDK transport).

### 1.12 `libs/nostrhost-nsite` — Go nsite gateway (4,026 lines; ~2.1k prod)

- **Metrics are hand-rolled:** `internal/metrics/metrics.go` (216 l) is a
  dependency-free counters/histograms registry with **manual Prometheus text
  exposition** (`Registry.Render` `:133–179` + label-suffix helpers to `:215`;
  `+Inf` derived from total count `:87–88,173`). Served on loopback
  `/internal/metrics` with `text/plain; version=0.0.4`
  (`internal/server/server.go:275–277`). No `client_golang`/`promhttp`
  anywhere (zero matches across all Go modules). Metric families/increments:
  `server.go:48–70`, `:228`, `:246`, `:253`, `:371`, `:382`, `:404`.
- **Cache is custom + content-addressed:** `internal/cache/cache.go` (215 l) —
  blob store keyed by sha256 with hash-verified atomic writes
  (`cache.go:90–125`, "a poisoned fetch never lands in the cache") + LRU quota
  eviction (`:128–149`); separate in-memory manifest TTL cache (`:159–215`).
- **SSRF controls:** `_NoRedirectHandler` / `_PinnedHTTPConnection` in the
  fork's `nsites/service.py:259–…`, and blossom checks in Go
  (`blossom/ssrf_test.go`). Retain custom.
- `internal/nip5a/manifest.go` `Validate` 169 l. Manifest resolution uses
  go-nostr `SimplePool` (`internal/resolve/resolve.go:89–98`). Branching:
  408 `if`, 77 `for`, 12 `switch`.

### 1.13 `libs/yunohost-mcp` — **frozen** reference MCP implementation (31,011 lines; ~18.7k prod)

Frozen per `baseline/pins.yml:111–116` and `docs/MCP-TRANSITION.md:73–94` ("no
new platform logic"). `yunohost/adapter.py` 4,092 l, `server.py` 3,553 l,
`broker/operations.py` 1,096 l, `onboarding.py` 775 l, `approve.py` 769 l,
`bridge.py` 761 l, `concord_*` ~15 modules. **No current Python/Go code imports
`yunohost_mcp`**; it remains referenced only by `packaging/packages.yml:261–270`
(the `yunohost-mcp-connect` client package build), the runtime requirements
file, and docs. Disposition: treat as vendored/upstream-derived; report
duplication, propose **no new logic** inside it.

---

## 2. Cross-cutting duplication and hot spots

| # | Duplication | Evidence | Proposed home |
|---|---|---|---|
| D1 | `nostrhost-policy` mirrored verbatim inside frozen `yunohost-mcp` | 25 policy files mirrored under `yunohost_mcp/`; **14 byte-identical** modulo import prefix (`auth/replay.py`, `auth/nostr.py`, `auth/nip98.py`, `auth/signing.py`, `auth/npub.py`, `auth/server_identity.py`, `auth/delegation.py`, `policy/roles.py`, `policy/package_sessions.py`, …); ~2,860 mirrored policy lines. Diff vs prefix-normalized copy = 0 lines on replay/nostr/nip98/signing/npub/server_identity/delegation. | migrate consumers off `yunohost-mcp` onto `nostrhost-policy`; freeze then retire |
| D2 | Locking: three implementations | `forks/yunohost/src/nostrhost/locking.py` (141 l, `flock`), `nostrhost-policy/policy/locks.py` (40 l, `threading.Lock`), `yunohost-mcp/policy/locks.py` (40 l, duplicate). | single `nostrhost-policy` lock + fork adapter |
| D3 | Replay cache: two implementations | `nostrhost-policy/auth/replay.py:19–38` and identical `yunohost-mcp/auth/replay.py`. | `nostrhost-policy` only |
| D4 | Hand-rolled JSON Schema interpretation | `agent/registry.go:85–295` (~170 l) + second partial parse `nostr_verifier.go:118–127`. Partial subset; no `$ref`/`oneOf`/`items`/bounds. | `santhosh-tekuri/jsonschema/v6` (adopt) |
| D5 | Raw NIP-01 WebSocket query loop | `forks/yunohost/src/nostrhost/nsites/service.py:223–256` (`_query_relay_events`) — "Raw NIP-01 WebSocket, mirroring `events.query_chain_events`". | nostr-sdk / go-nostr (spike first) |
| D6 | Custom Prometheus exposition | `nsite/internal/metrics/metrics.go:133–215`; no `client_golang`. | `client_golang` + `promhttp` (adopt) |
| D7 | Manual FastAPI body parsing | `api.py:2426–2434` `_json_body`; ~326 `body.get` + 11 `set(body)` sites; no Pydantic request models; OpenAPI disabled (`api.py:593`). | Pydantic models + `APIRouter`s + OpenAPI export + Orval (adopt) |
| D8 | Two frontends hand-roll server-state | Admin `useAsyncResource`/`useActionRunner` + per-view refs, no cache/invalidation; portal `useApi` fetch-once, `useState` cached forever. | TanStack Vue Query (adopt) |
| D9 | Custom installer console | `installer/cli/clibella.py` (380 l) + `tqdm`; no TTY detection. | Rich (adopt, lower priority) |
| D10 | Custom DNS provider clients | `dns/providers/{cloudflare,desec,duckdns,dynu}.py` custom `httpx2` REST/push clients + legacy `dns.py` lexicon. | DNS-Lexicon adapters (spike first) |

---

## 3. Ranked refactoring backlog

Ranking follows the plan: **adopt** · **spike first** · **conditional/defer** ·
**retain custom**. Every candidate records affected components, replacement
library, estimated code reduction, migration risk, maintenance/security
benefit, compatibility constraints, and confidence.

### ADOPT

#### A1 — Typed API contracts: Pydantic request/response models + domain `APIRouter`s + OpenAPI export + Orval

- **Affected:** `forks/yunohost` (`api.py`, `portal_api.py`), `forks/admin`
  (22 hand-written `native*.ts` modules), `forks/portal`.
- **Replacement:** Pydantic v2 models and `APIRouter`s (already a dependency
  via `nostr_operations.py` `_Strict`); export OpenAPI during builds; Orval
  with a custom authenticated request mutator to generate the TS client + Vue
  Query hooks.
- **Estimated code reduction:** ~326 `body.get` sites + 11 key-set validations
  → typed models; `api.py` `build_app` 1,796 l → router-per-domain; admin
  hand-written types replaced by generated client (22 modules).
- **Migration risk:** **medium-high** — `build_app` is one 1,796-l function;
  must preserve CSRF/NIP-98 handling, idempotency, and exact error envelopes.
  OpenAPI is currently disabled (`api.py:593`), so enabling it first needs a
  wire-shape regression suite.
- **Maintenance/security benefit:** elimination of manual parsing/validation
  bugs; typed client catches API drift at build time; single source of truth
  for request/response shapes.
- **Compatibility:** keep wire shapes identical; `openapi_url` can be enabled
  without exposing docs publicly (gate behind loopback or auth).
- **Confidence:** high that this is the right direction; medium on exact
  sequencing given the single-function router.

#### A2 — TanStack Vue Query for frontend server-state

- **Affected:** `forks/admin` (66 views), `forks/portal` (22 views).
- **Replacement:** `@tanstack/vue-query`.
- **Estimated code reduction:** removes `useAsyncResource` (13 views),
  `useActionRunner` (27 views), `useBusyAction`/`usePermissionAction`,
  portal `useApi`/`useAsyncAction`, and the bespoke `OperationsView` polling;
  replaces dead code (`useOperation`, `useBusyAction`) with a live layer.
- **Migration risk:** low-medium. Two separate submodule repos (no shared
  package) — adopt per-repo or extract a shared package. Must **disable
  automatic mutation retries** and retain explicit operation-confirmation
  behavior and the `Idempotency-Key` semantics.
- **Benefit:** correct loading/error/invalidation, cancellation, polling, and
  retry policy in one maintained library instead of hand-rolled per-view refs.
- **Compatibility:** no network-shape change; session/Cookie/NIP-98 handling
  stays in `client.ts`.
- **Confidence:** high.

#### A3 — Standards-based JSON Schema validation in the agent

- **Affected:** `libs/nostrhost-agent` (`agent/registry.go:85–295`,
  `nostr_verifier.go:118–127`).
- **Replacement:** [`santhosh-tekuri/jsonschema/v6`](https://pkg.go.dev/github.com/santhosh-tekuri/jsonschema/v6@v6.0.3), compiled once per registry.
- **Estimated code reduction:** ~170 l of hand-rolled interpreter + the
  second partial parse; replaces a partial subset with full spec conformance
  (`$ref`, `oneOf`, `allOf`, `items`, bounds, `format`).
- **Migration risk:** low-medium. The generated catalogue
  (`catalog_generated.go`, 178 KB) must remain the single schema source;
  preserve project-specific Nostr-tag, risk, and semantic validation **outside**
  JSON Schema. Requires `go mod` bump and offline wheel/source packaging.
- **Benefit:** eliminates silent under-validation (e.g. `additionalProperties`
  is parsed at `registry.go:89` but ignored — unknown args are rejected by
  property absence at `:99–103`, so an explicitly `true` `additionalProperties`
  schema is still not honored);
  spec-complete behavior with far less code.
- **Compatibility:** same accepted/rejected surface expected; conformance tests
  + stable project-level validation codes required.
- **Confidence:** high.

#### A4 — Prometheus instrumentation for nsite

- **Affected:** `libs/nostrhost-nsite` (`internal/metrics/metrics.go`,
  `internal/server/server.go:275–277`).
- **Replacement:** `client_golang` collectors + a private registry served via
  `promhttp.HandlerFor`.
- **Estimated code reduction:** `metrics.go` 216 l of hand-rolled registry +
  manual text renderer → ~40 l of collector registration.
- **Migration risk:** low. Metric names, labels, buckets, and the loopback
  `/internal/metrics` endpoint must be preserved (golden-output tests).
- **Benefit:** race-free collectors, correct `+Inf` handling, `Content-Type`
  negotiation, ecosystem tooling compatibility.
- **Compatibility:** same names/labels/buckets; endpoint text format is
  standard Prometheus exposition.
- **Confidence:** high.

### SPIKE FIRST

#### S1 — Nostr relay clients (nostr-sdk vs raw WebSocket + go-nostr)

- **Affected:** `forks/yunohost` (`nsites/service.py:223–256` raw NIP-01 loop),
  `libs/nostrhost-auth`, `libs/nostrhost-policy` (Python `nostr-sdk`), and the
  go-nostr clients in `agent`, `catalog`, `control`, `nsite`.
- **Spike scope:** verify the existing Python `nostr-sdk` and go-nostr against
  **NIP-42 authentication, pagination beyond 5,000 events, replay order,
  cancellation, reconnection, and local-relay (khatru) behavior** before
  replacing the raw `_query_relay_events` loop or consolidating clients.
- **Estimated code reduction:** replace ~34 lines of raw WS loop per call site
  with a maintained client; but the main value is correctness/robustness, not
  LOC.
- **Migration risk:** medium — relay behavior differs per implementation;
  retain projection/fold/checkpoint domain logic regardless of transport.
- **Benefit:** NIP-42 auth, backpressure, reconnect, and cancellation handled
  by a maintained library instead of bespoke loops.
- **Compatibility:** wire protocol unchanged (NIP-01); local relay must keep
  passing the replay corpus.
- **Confidence:** medium pending spike results.

#### S2 — DNS providers via DNS-Lexicon

- **Affected:** `forks/yunohost` (`src/nostrhost/dns/providers/*.py`,
  `src/dns.py`, `src/dyndns.py`).
- **Spike scope:** exercise DNS-Lexicon adapters for **Cloudflare, deSEC,
  Dynu, DuckDNS** against the native provider contract; adopt **per provider**
  only where record identifiers, pagination, TTL, credentials, and supported
  record types match (Cloudflare/deSEC have custom REST clients today;
  DuckDNS/Dynu are push-only).
- **Estimated code reduction:** up to ~540 custom client lines (cloudflare
  273 + desec 260 + duckdns 127 + dynu 128) plus legacy `dns.py`/`dyndns.py`.
- **Migration risk:** medium — provider-specific pagination (cloudflare
  `_MAX_PAGES=50`, deSEC `_MAX_PAGES=10`), TTL defaults (300/3600/60), and
  credential broker (`secret:` refs) must be preserved; Dynette stays custom
  (dnspython TSIG, not Lexicon-supported).
- **Benefit:** one maintained provider interface instead of per-provider HTTP
  clients.
- **Compatibility:** record plans and applied records must remain byte-identical
  (recorded contract tests).
- **Confidence:** medium pending spike.

### ADOPT AT LOWER PRIORITY

#### L1 — Rich for the installer console

- **Affected:** `forks/installer` (`cli/clibella.py` 380 l, `net/download.py`).
- **Replacement:** Rich.
- **Estimated code reduction:** ~380 l → ~120 l.
- **Migration risk:** low-medium — must preserve plain/non-TTY output (Rich in
  `Console(no_color=...)`) and the exact `exit(0)`/`exit(1)` behavior; TTY
  detection should be added (today prompts rely on stdlib `input()` with no
  `isatty` guard).
- **Benefit:** progress/spinner/table/confirm primitives maintained upstream;
  Rich already ships in the runtime wheel closure
  (`packaging/runtime/requirements.txt:71`).
- **Compatibility:** installer snapshots for TTY, non-TTY, declined
  confirmation, interruption, and failure exits.
- **Confidence:** medium.

### CONDITIONAL / DEFER

- **VueUse** — adopt only if several lifecycle utilities can be removed
  together across admin/portal; otherwise low value. (defer)
- **Bleve** — defer: the search corpus is bounded in-memory
  (`agent/history_retrieval.go` RAG + static corpus); no benchmark shows a
  need. (defer)
- **`sse-starlette`** — defer: the SSE formatter surface is small
  (`useOperation` is currently dead code; portal polls instead). Adopt only
  when `useOperation`/SSE endpoints are activated and benchmarks/soak tests
  justify it. (defer)

### RETAIN CUSTOM

- **Security-sensitive HTTP/SSRF controls** — `_NoRedirectHandler`/
  `_PinnedHTTPConnection` (fork `nsites/service.py`), nsite blossom checks,
  agent `validateLocalEndpoint` (`relay_transport.go:219–235`).
- **Content-addressed nsite cache** — hash-verified atomic writes + LRU quota
  (`cache.go:90–149`); correctness-critical.
- **Thin go-nostr/khatru adapters** — `agent/relay_transport.go`,
  `catalog/relay/client.go`, `control/relay/server.go`; protocol-specific.
- **Small SQLite and bbolt stores** — auth `_sqlite.py`, control
  `policy/store.go`; simple and dependency-free.
- **Atomic-write/locking helpers** — fork `locking.py` (flock), state-file
  atomic rename patterns; replace only the *duplicated* policy lock (D2).
- **Domain-specific event folding** — `tools/event_protocol.py` `fold`,
  `nostr_operationsd` result folding, the `nostrhost-protocol` binding.

### RETIRE (no new logic inside frozen component)

- **Migrate remaining consumers off frozen `libs/yunohost-mcp`** onto
  `nostrhost-mcp`, `nostrhost-policy`, `nostrhost-auth`, and the native
  operation registry. Report the duplicated policy/auth/replay/locking/session
  code (§2 D1–D3). Packaging references (`packaging/packages.yml:261–270`,
  `runtime/yunohost-mcp-connect-requirements.txt`) move to the native client;
  the frozen submodule is then unpinned/removed in a separately approved
  migration.

---

## 4. Interfaces and verification requirements

The review itself changes no public API, schema, or stored data. The following
verification requirements apply to the backlog implementations and must retain
externally observable compatibility except where a separately approved
migration explicitly changes it:

- **A1 (typed API contracts):** OpenAPI snapshot in CI; generated-client drift
  check (`orval` output vs committed client); TypeScript build; API contract
  tests; authentication (NIP-98 + CSRF) and idempotency regression tests.
- **A2 (Vue Query):** Vue tests for polling, invalidation, cancellation, error
  mapping, and **no mutation retries**; confirmation-flow regression tests.
- **A3 (JSON Schema):** Nostr replay corpus covering authentication,
  disconnects, duplicate events, pagination, and ordering; JSON Schema
  conformance suite and stable project-level validation codes.
- **A4 (Prometheus):** golden Prometheus output plus collector
  consistency/race tests (loopback endpoint only).
- **S2 (DNS):** recorded DNS-provider contract tests for list/create/update/
  delete and propagation behavior per provider.
- **L1 (Rich):** installer snapshots for TTY, non-TTY, declined confirmation,
  interruption, and failure exits.
- **S1 (relay clients):** local-relay soak with NIP-42 auth, >5,000-event
  pagination, replay-order, cancellation, and reconnection assertions.

---

## 5. Assumptions and dispositions

- "All submodules" includes every entry in `.gitmodules` (12 total), including
  the frozen `libs/yunohost-mcp` compatibility repository.
- **Current uncommitted work is inspected but not counted as newly introduced
  debt:** `forks/yunohost` (nsites collections: +799/−27), `forks/admin`
  (nsite collection client +246/−2), `libs/nostrhost-mcp` (server +41/−2), and
  the untracked `tools/tests/nsites/collection-corpus/`. Line counts in §1 are
  committed-tree values unless noted.
- **Generated/upstream-derived code receives an ownership/disposition note**
  rather than refactoring recommendations: `agent/catalog_generated.go`
  (generated, 178 KB), `forks/admin/app/dist` and `forks/portal/.nuxt/.output`
  (build artifacts, untracked), `forks/portal`/`forks/admin`/`forks/installer`
  (upstream forks, `derivative: true` in `baseline/pins.yml`), and the frozen
  `libs/yunohost-mcp`.
- Recommendations are compatible with project packaging, offline installation,
  licensing, supported Python/Go/Node versions, and YunoHost deployment
  constraints (dependency bumps must land in `packaging/runtime/requirements.txt`
  wheel pins and the Go `go.mod`/vendor closure).
- The balanced dependency policy applies: a dependency is recommended only when
  it materially reduces custom behavior or risk.

---

## 6. Implementation status (2026-09-20)

Backlog items implemented in this pass; each preserves externally observable
compatibility except where noted.

| Item | Status | What changed | Verification |
|---|---|---|---|
| A4 nsite Prometheus | **Done** | `internal/metrics/metrics.go` rewritten as a thin `client_golang` wrapper (same public API); `/internal/metrics` served via `promhttp.HandlerFor`. Metric names/labels/buckets unchanged. Added `client_golang v1.21.1` (Go 1.24-compatible, no toolchain bump). | `go test ./...`, `go vet`, `-race` all green; new golden + concurrency tests; server tests updated for standard empty-family behaviour. |
| A3 agent JSON Schema | **Done** | `agent/registry.go` hand-rolled interpreter replaced by `santhosh-tekuri/jsonschema/v6` compiled once per operation (`compileArgumentValidator`); project-specific non-empty-string rule preserved outside JSON Schema. Removed dead code (`definedOperation`, `sortStrings`, scalar helpers). | `go test ./...` green; fixed pre-existing stale test/corpus data (backup.restore/create schemas regenerated in the pinned submodule). |
| A1 typed API contracts | **Done** | New `nostrhost/api_models.py` (typed request models); `api._body(model)` validates the cached `body_bytes` (NIP-98 binding unchanged) and returns the original dict → 92 write routes wire-identical. OpenAPI export enabled (`openapi_url` + `build_app_with_openapi` + `scripts/export-openapi.py`) with request bodies + path parameters injected. Admin SPA: Orval-generated `src/api/generated` (client + Vue Query hooks) via `orval.config.ts`, custom `orvalRequest` mutator through the authenticated `request()`, `api:generate/api:export/api:drift` npm scripts, `@tanstack/vue-query` installed. | 168 backend tests + 4 new contract tests; admin 115 vitest tests + type-check; drift script. Note: full `build_app` → domain-`APIRouter` split not performed (1,796-line single function left intact to avoid 209-test regression risk); the typed layer + OpenAPI + generated client are the delivered surface. |
| A2 Vue Query | **Done** | `@tanstack/vue-query` plugin installed in admin (`main.ts`) and portal (`plugins/vue-query.ts`), `mutations.retry: 0` globally. New `useQueryResource`, `useOperationsList`, portal `useApiQuery`; `useActionRunner` gained optional query invalidation; `useAsyncResource` exposes the query client. OperationsView's hand-rolled `setInterval`+`visibilitychange` polling replaced with a Vue Query `refetchInterval` query. | 115 admin tests + 3 new polling/invalidation/error tests; portal `nuxt build` succeeds; type-check clean. |
| L1 installer Rich | **Done** | `cli/clibella.py` rewritten on Rich with TTY detection (no ANSI on non-TTY, exact centered-prefix format preserved); `net/download.py` uses Rich `Progress` instead of tqdm; `rich==15.0.0` added to installer requirements. | 6 new installer unittest snapshots (plain/TTY output, prompts, download). |
| S1 nostr-sdk spike | **Done** (VM) | Spike script run on the clean7 VM against the live `nostrhost-control` relay. | **NIP-42 auth OK; single-REQ pagination truncates at ~535** on the deployed relay 0.1.7 even at limit 5000/20000 (packaged badger page cap) — an explicit `until`-cursor loop recovers the full set; replay returns no duplicate ids; short-timeout cancellation returns fast; disconnect/reconnect works. Conclusion: replacing the raw `nsites/service.py` WS loop with nostr-sdk requires an explicit cursor loop for large reads, and NIP-42 + cancellation are sound. |
| S2 DNS-Lexicon spike | **Done** | Spike exercises Lexicon 3.25 providers (Cloudflare/deSEC/Dynu/DuckDNS) against the native provider contract. | All four expose `list/create/update/delete`; record identity (name,type,ttl,data) matches the native `(zone,name,type)` key; `auth_*` credentials map onto broker secret refs. Per-provider adoption is viable for Cloudflare/deSEC (zone-enumerating); DuckDNS/Dynu stay push-only. |
| Retire yunohost-mcp packaging | **Done** | `packaging/packages.yml` `yunohost-mcp-connect` → `nostrhost-mcp-connect` built from `libs/nostrhost-mcp` (`app_wheel: nostrhost-mcp`, command `nostrhost-mcp serve --stdio`); new `packaging/runtime/nostrhost-mcp-connect-requirements.txt` (from nostrhost-mcp `uv.lock`); `build-package` python-cli derives the wheel glob from `app_wheel`; `compatibility.yml` break entry; `packaging/README.md` updated. The frozen `libs/yunohost-mcp` is no longer a build dependency. | `packaging/scripts/verify-dependencies` PASS. |

**Not performed in this pass** (deferred, wire-preserving):
- Splitting the 1,796-line `build_app` into domain `APIRouter`s (documented in A1) — high-risk refactor with no behaviour change; the typed-body layer + OpenAPI already deliver the contract.
- VueUse / Bleve / `sse-starlette` (explicitly deferred by the plan).
- Live DNS-provider create/update/delete contract tests (require real credentials; the spike validated the adapter surface).

**Pre-existing blocker, not attributed to this pass:** the admin `vite build`
fails on the untracked nsites-collections WIP file
`forks/admin/app/src/views/native/nsites/CollectionsSection.vue:683` (a Vue
template misparse in that WIP, present before and after this pass's changes).
`vue-tsc` type-check and the full vitest suite (115 tests) pass with this
pass's changes in place.