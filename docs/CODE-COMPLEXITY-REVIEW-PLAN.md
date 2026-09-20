# Whole-of-Code Complexity Review

## Summary

Review the parent repository and all 12 submodules at their current checkout, covering roughly 199k lines of source. Deliver an evidence-backed report with a ranked refactoring backlog; do not modify application code as part of the review.

Treat generated assets, vendored code, tests, upstream forks, and the frozen `libs/yunohost-mcp` reference separately so they do not distort maintainability findings. Distinguish committed code from current uncommitted changes.

## Review Method

- Inventory each component's dependencies, largest modules and functions, branching, duplication, protocol handling, validation, persistence, retries, caching, CLI/UI utilities, and observability code.
- For every candidate, record affected components, replacement library, estimated code reduction, migration risk, maintenance and security benefit, compatibility constraints, and confidence.
- Recommend a dependency only when it materially reduces custom behavior or risk under the selected balanced dependency policy.
- Rank findings as adopt, spike first, conditional/defer, or retain custom.

## Expected Refactoring Backlog

- **Adopt: typed API contracts.** Replace manual FastAPI body parsing with Pydantic request/response models and domain `APIRouter`s. Export OpenAPI during builds and use [Orval](https://orval.dev/docs/) with a custom authenticated request mutator to generate the admin TypeScript client and Vue Query hooks. Keep existing HTTP wire shapes, CSRF/NIP-98 handling, idempotency, and error semantics.
- **Adopt: frontend server-state management.** Use TanStack Vue Query for reads, mutations, polling, invalidation, and loading/error state. Disable automatic mutation retries and retain explicit operation confirmation behavior.
- **Retire rather than modernize:** migrate remaining consumers away from frozen `libs/yunohost-mcp` onto `nostrhost-mcp`, `nostrhost-policy`, `nostrhost-auth`, and the native operation registry. Report duplicated policy, authentication, replay, locking, and session code, but propose no new logic inside the frozen component.
- **Adopt: standards-based validation.** Replace the agent's partial reflective JSON Schema interpreter with [`santhosh-tekuri/jsonschema/v6`](https://pkg.go.dev/github.com/santhosh-tekuri/jsonschema/v6@v6.0.3), compiling schemas once per registry. Preserve project-specific Nostr tag, risk, and semantic validation outside JSON Schema.
- **Adopt: Prometheus instrumentation.** Replace nsite's custom exposition, counters, and histograms with the official [`client_golang`](https://prometheus.io/docs/guides/go-application/) collectors and a private registry served through `promhttp.HandlerFor`. Preserve metric names, labels, buckets, and endpoint behavior.
- **Spike first: Nostr relay clients.** Test the existing `nostr-sdk` against NIP-42 authentication, pagination beyond 5,000 events, replay order, cancellation, reconnection, and local-relay behavior before replacing raw WebSocket protocol loops. Retain projection/fold/checkpoint domain logic.
- **Spike first: DNS providers.** Exercise DNS-Lexicon adapters for Cloudflare, deSEC, Dynu, and DuckDNS; current Lexicon supports these providers through a standardized interface ([provider reference](https://dns-lexicon.github.io/dns-lexicon/configuration_reference.html)). Adopt per provider only where record identifiers, pagination, TTL, credentials, and supported record types match the native provider contract.
- **Adopt at lower priority:** replace the installer's custom console, prompt, and progress utilities with Rich while preserving plain/non-TTY output and exit behavior.
- **Conditional/defer:** use VueUse only if several lifecycle utilities can be removed together; defer Bleve for the bounded in-memory search corpus and `sse-starlette` for the small SSE formatter unless benchmarks or soak tests demonstrate a need.
- **Retain custom:** security-sensitive HTTP/SSRF controls, content-addressed nsite cache, thin go-nostr/khatru adapters, small SQLite and bbolt stores, atomic-write/locking helpers, and domain-specific event folding.

## Interfaces and Verification

The review itself changes no public API, schema, or stored data. Recommended implementations must retain externally observable compatibility except where a separately approved migration explicitly changes it.

Verification requirements for the backlog:

- OpenAPI snapshot, generated-client drift check, TypeScript build, API contract tests, and authentication/idempotency regression tests.
- Vue tests for polling, invalidation, cancellation, error mapping, and no mutation retries.
- Nostr replay corpus covering authentication, disconnects, duplicate events, pagination, and ordering.
- JSON Schema conformance and stable project-level validation codes.
- Golden Prometheus output plus collector consistency/race tests.
- Recorded DNS-provider contract tests for list/create/update/delete and propagation behavior.
- Installer snapshots for TTY, non-TTY, declined confirmation, interruption, and failure exits.

## Assumptions

- "All submodules" includes every entry in `.gitmodules`, including the frozen compatibility repository.
- Current uncommitted work is inspected but never altered or attributed as newly introduced technical debt without supporting history.
- Generated and upstream-derived code receives an ownership/disposition note rather than line-by-line refactoring recommendations.
- Recommendations must be compatible with project packaging, offline installation, licensing, supported Python/Go/Node versions, and YunoHost deployment constraints.
