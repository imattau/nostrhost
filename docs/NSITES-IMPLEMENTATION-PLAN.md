# Nsites: implementation plan (code-level)

Status: **proposed, 2026-09-14 — awaiting decisions D1–D7 below before
Phase 0 starts.** This document turns the workstream plan in
[`NSITES-PLAN.md`](NSITES-PLAN.md) (roadmap §28) into a concrete design
against the codebase as it stands today. It does not replace that plan: the
product boundaries, security gates and phase exits there still apply. This
document records what changed since that plan was written, verifies the
integration seams it names, proposes the decisions it left open, and breaks
each phase into files, tests and exit checks.

The 0.1 alpha gate that §28 waited on is met (roadmap: W2 native bootstrap
and W3 native app lifecycle are both green on the clean7 VM), so §28 may
start once the decisions below are confirmed.

## 1. Review findings

### 1.1 What changed upstream since `NSITES-PLAN.md`

| Topic | State when the plan was written | State now (2026-09-14) | Effect on the plan |
|---|---|---|---|
| NIP-5A status | "draft/optional" | Merged into `nostr-protocol/nips` on 2026-03-25 (PR #1538). Kinds `15128` root, `35128` named, `5128` snapshot. | Pin the merged text; the "evolving target" caution stays but the corpus can be built now. |
| Canonical hostnames | unspecified | `<npub>.<gateway>` (root), `<pubkeyB36><d>.<gateway>` (named; base36 pubkey is exactly 50 chars, `d` matches `^[a-z0-9-]{1,13}$`), `v<eventIdB36>.<gateway>` (snapshot). Base36 was chosen specifically so wildcard certificates work. | Root labels are 63 chars (`npub1` + 58), which is the DNS label maximum. Named labels are at most 63. Both fit, with no headroom. |
| Aggregate hash | unspecified | `x` tag: SHA-256 over sorted lines `<sha256> <path>\n`. | Deterministic; implement once in Go and Python and cross-check in tests. |
| Copied sites | unspecified | `a` (parent) and `A` (origin) tags. | "Create my copy" (Phase 5) has a defined shape. |
| `app` tag | mentioned | `["app", "kind:pubkey:d", "relay"]`. | Direct link to the catalogue's kind `32267` descriptor. |
| Blossom discovery | unspecified | `server` tags first, then the author's kind `10063` (BUD-03) list, else 404. | The gateway needs a BUD-03 lookup; publishing should offer to update the user's `10063`. |
| `hzrd149/nsite-gateway` | candidate | Deno + Hono, MIT, ~158 commits, **no tagged releases**, supports `15128`/`35128`/`5128`, npub/base36/snapshot labels and CNAME custom domains, Deno KV cache, `MAX_FILE_SIZE` 128 MB, ETags. Docker-first; the reference compose stack fronts it with Caddy. | A commit pin is the only pin available. It is the behavioural oracle for Phase 0, whichever gateway ships. |
| Go alternatives | none listed | `mattn/nostr-nsite-server` (Go, MIT, 9 commits, kind `15128` only, gateway by npub subdomain, no named/snapshot, limits undocumented). `lez/nsite` (Python, AGPL, legacy kind `34128`). | Neither is shippable as-is; the Go one is useful only as a reading reference. |
| Publishing CLI | none listed | `sandwichfarm/nsyte` (Deno) publishes `15128`/`35128`, optionally `10063`, `10002`, NIP-89 handlers; NIP-46 bunker signing; one BUD-02 auth event per upload batch. | Reference for the publish UX and the Blossom auth pattern; not a dependency. |

### 1.2 Integration seams verified in the codebase

Every seam the workstream plan names exists and does what it says. The
lines below are the exact attachment points.

| Capability | Where | Notes for nsites |
|---|---|---|
| Typed operation registry | `forks/yunohost/src/nostr_operations.py:164` (`ToolSpec`: scope, `require_approval`, `input_model`, `risk`, `reversibility`), `operation_catalog()` at `:842`; tool table `NATIVE_TOOLS` in `forks/yunohost/src/nostrhost/native_ops.py:1651`; scopes at `nostr_operations.py:75-114` and mirrored in `libs/nostrhost-policy/src/nostrhost_policy/policy/{scopes,rules}.py`. | New `nsites.*` scopes and tools plug in here and are then generated for MCP, Admin and CLI automatically. 69 operations exist today. |
| Native HTTP API | `forks/yunohost/src/nostrhost/api.py` (Bottle, loopback `127.0.0.1:8190`, `/package/*`, NIP-98 or portal session cookie), dispatch via `_run_tool` at `:109`. | Add `/package/nsite/*` routes that call the same safe wrappers. |
| Caddy route builder | `forks/yunohost/src/nostrhost/caddy_admin.py:258` (`build_web_route`), `@id`-tagged idempotent `ensure_route`/`delete_route`, reserved prefixes `/nostrhost`, `/package`, `/.well-known/nostr.json` at `:37-38`. `CaddyProvider` in `native_providers.py:1694`. | Add `build_nsite_routes(domain, upstream)` with a wildcard host matcher. The reserved-path exclusion does not apply on the gateway origin, which must serve nothing of NostrHost's own. |
| Caddy global/base config | `forks/yunohost/conf/caddy/Caddyfile.template` (regenconf) and per-domain `caddy_domain.conf` (`tls internal`, portal/admin/API handlers on every domain). | The gateway domain must **not** get the standard per-domain snippet, or it would serve Admin/Portal on the public site origin. A distinct `caddy_nsite.conf` snippet is needed. |
| Domains and DNS | `forks/yunohost/src/nostrhost/domains/service.py:113` (`DomainService.add/remove/dns_*`), `domains/models.py` (`DomainExposure.wildcard` defaults to **true**, so `*.<domain>` A/AAAA records are already planned in `domains/planner.py:41`), `_dependents()` at `service.py:491`, DNS ownership markers in `dns/ownership.py`. | Wildcard **DNS** is solved. Wildcard **TLS** is not: `DomainTls.mode` is `automatic` (HTTP-01) and `CADDY-MIGRATION.md` §8 lists DNS-01 wildcard as a non-goal. See D2. |
| Admin console | `forks/admin/app/src/api/client.ts` (portal session cookie first, NIP-07 NIP-98 fallback), `composables/useSigner.ts`, `nostr-tools ^2.25.2` already a dependency, routes in `src/router/routes.ts`. | The browser already has a Schnorr-capable library and a signer abstraction. A publish wizard can hash, upload and sign entirely client-side. |
| Portal | `forks/portal/pages/login.vue:98` (NIP-46 `bunker://` sign-in via `NostrConnectUI`). | The only NIP-46 UI in the tree. Reuse for nsite signing later; not in the first publish flow. |
| MCP adapter | `libs/nostrhost-mcp` generates tools from `operation_catalog()`; reads run immediately, writes return `approval_required` + `operation_id`. | Nsite tools need no MCP-side code beyond redaction rules. |
| Resident agent | `libs/nostrhost-agent/agent/{llm_planner,nostr_executor,nostr_observer}.go` — typed proposals, executor re-checks authorisation. | Nsite operations start denied in autonomous mode (plan §Phase 3). No agent code change is needed for Phase 3; only capability grants. |
| Packaging | `packaging/packages.yml` kinds: `meta`, `debian-source`, `runtime`, `golang`, `python`, `python-cli`, `python-adapter`, `spa`, `caddy`, `config`. `build-package` builds Go with `CGO_ENABLED=0`, stages `deploy/*.service` and maintainer scripts. | A Go gateway is a first-class package kind today. A Deno gateway would need a new kind and a vendored Deno toolchain. |
| Go ecosystem in tree | `libs/nostrhost-control` and `libs/nostrhost-catalog` both on `github.com/nbd-wtf/go-nostr v0.52.3`. | A native gateway shares the Nostr library, CI job shape and hardening pattern of the existing daemons. |
| Control relay | `nostrhost-control`, loopback `ws://127.0.0.1:4848`, NIP-42 gated control kinds. | Must stay out of the public resolution path. The gateway gets no relay credentials. |
| Catalogue | `libs/nostrhost-catalog/internal/protocol/types.go:17` (`AppDeclarationKind = 32267`). | The NIP-5A `app` tag can reference `32267:<publisher>:<app_id>` directly. |
| VM testbed and e2e | `docs/VM-TESTBED.md`, `testbed/e2e/` (Playwright harness with a NIP-07 shim and a NIP-46 bunker), `docs/CADDY-P*-SPIKE.md` (decision-record format). | Phase 0 and Phase 3 acceptance reuse these; the spike report follows the Caddy spike format. |

### 1.3 Corrections and additions to `NSITES-PLAN.md`

1. **The alpha gate is met.** The plan's "not before the 0.1 alpha gate"
   condition no longer blocks Phase 0.
2. **Wildcard DNS already exists; wildcard TLS is the real gap.** The plan
   raises "the deferred wildcard DNS-01 question". The DNS half is done. The
   certificate half has a cheaper answer than DNS-01 for the first release
   (D2).
3. **Let's Encrypt rate limits are a design input, not a footnote.** Per-name
   HTTP-01 issuance on a public gateway is capped at 50 certificates per
   registered domain per week and 5 duplicate certificates per week. That
   caps an "open" gateway at a handful of new sites per day and makes an
   allowlisted "hosted" mode the safe default (D3).
4. **Hostname labels sit at the 63-character limit.** Any host-format
   variation (a prefix, a suffix) breaks root sites. Validation must reject
   labels over 63 characters before decoding.
5. **Blossom uploads can bypass the server entirely.** BUD-01 requires
   `Access-Control-Allow-Origin: *`, so the Admin browser can `PUT /upload`
   straight to the user's Blossom servers with a NIP-07-signed kind `24242`
   authorisation. The NostrHost server then never receives the files, which
   removes a whole class of upload-quota and temp-storage problems. One
   `24242` event may cover several blobs (multiple `x` tags), so a batch
   needs one signer prompt, not one per file.
6. **The MCP publishing path cannot use the owner's NIP-07 signer.** An MCP
   client authenticates with its own NIP-98 key. The operation therefore
   accepts a *pre-signed* manifest and verifies it; who signed it is the site
   identity. In hosted mode the manifest pubkey must be a registered site on
   this host (D3), which is what stops an MCP client from publishing sites
   for arbitrary keys.
7. **No Deno runtime.** Confirmed: `RuntimeResource.type` is limited to
   `node|python|go|ruby|composer|php` and there is no Deno package kind.
   Shipping the upstream gateway means adding both.

## 2. Decisions proposed (confirm before Phase 0)

Each decision below states a recommendation and the alternatives that were
considered. Phase 0 is scoped so that D1 can still be reversed cheaply after
the spike.

### D1. Gateway implementation: **native Go component `nostrhost-nsite`**, with `hzrd149/nsite-gateway` as the Phase 0 oracle

Recommended: write the gateway in Go under `libs/nostrhost-nsite` (new
submodule, same layout as `nostrhost-catalog`), packaged as `kind: golang`.

- Fits every existing mechanism: `packages.yml`, `build-package`,
  `CGO_ENABLED=0` static binary, `deploy/*.service` hardening, Go CI job,
  `go-nostr v0.52.3` already vetted.
- The security gates in the plan (SSRF defence, bounded fetch, streaming
  hash verification, disk quota, origin isolation, loopback-only management
  endpoints) are cheaper to build than to retrofit and audit in a Deno app
  that was designed as an open public gateway.
- The `ask` endpoint for on-demand TLS (D2) and the "hosted mode" allowlist
  (D3) are NostrHost-specific and would be forks either way.
- Size: about 2.5–3.5k lines of Go plus tests. Comparable to the catalogue
  service.

Alternatives:

- *Package the upstream Deno gateway.* Needs a `deno` package kind, a vendored
  Deno toolchain (or `deno compile` at build time producing a ~100 MB
  binary), a commit pin with no release cadence, and a fork for the `ask`
  endpoint and allowlist. Cheapest to reach a first demo; most expensive to
  own.
- *Fork `mattn/nostr-nsite-server`.* Go, but covers root sites only and
  documents no limits. Reading reference at best.

Phase 0 runs the upstream Deno gateway on the VM regardless, to build the
conformance corpus and record its behaviour on hostile inputs. If the spike
shows the upstream gateway is already safe enough behind Caddy, D1 can flip
to "package upstream" with the corpus as regression protection.

### D2. Hostname and TLS: **dedicated gateway domain + Caddy On-Demand TLS with an `ask` endpoint**; wildcard DNS-01 deferred

- The operator registers a dedicated native domain for sites (for example
  `sites.example.org`) through the normal `domain add`, which already plans
  `*.sites.example.org` A/AAAA records (`DomainExposure.wildcard`).
- Caddy issues per-label certificates lazily via On-Demand TLS. Caddy calls
  the gateway's loopback `GET /internal/tls-ask?domain=<host>` before each
  issuance; the gateway answers 200 only when the label decodes to a valid
  NIP-5A form **and** the site is allowed on this host (D3). This blocks
  certificate-issuance abuse and keeps issuance under the Let's Encrypt
  limits for hosted mode.
- Canonical subdomain forms only in the first release; custom domains come
  in Phase 4 via CNAME to the gateway domain, using the same on-demand path
  with an ownership check.
- Wildcard DNS-01 (one certificate for `*.sites.example.org`) becomes the
  prerequisite for "open" mode only. It needs a Caddy DNS module per
  provider and provider credentials inside Caddy, which conflicts with the
  current credential model (`credentials.py`, systemd credentials). Deferred,
  as `CADDY-MIGRATION.md` already states.

Alternative considered: put sites under the primary domain
(`<npub>.example.org`). Rejected: it would share a registrable domain with
the Admin/Portal origin, and a stray `Domain=` cookie or a future subdomain
app would collide with site labels. The gateway domain must be one that no
native app's `web.domain` and no other registered domain sits under; the
existing `_dependents()` check enforces this at enable time.

### D3. Exposure: **gateway disabled by default; when enabled, `hosted` mode**; `open` mode is a later, separately gated feature

- `hosted`: the gateway serves only sites registered on this host (the
  owner's identities plus explicitly added pubkeys, root or named), and
  snapshots referenced by those sites. Unknown labels get a bounded 404 and
  no certificate.
- `open`: any valid label. Requires the wildcard certificate (D2), the abuse
  limits in §4.4 and a mute-list curation option. Not in Phases 0–4.

Default limits for hosted mode are in §4.4.

### D4. Blossom: **publish to external servers only**; no local Blossom service in the first release

- Server selection in the publish wizard: the user's kind `10063` list
  (BUD-03) when present, else a host-configured default list, always
  editable. The wizard offers to publish an updated `10063` if the user
  picks servers not in their list.
- Phase 0 tests against two public servers plus a local fake; the specific
  public servers are an operator choice, not a code constant.
- A NostrHost-hosted Blossom server is a separate optional component with
  its own quota, abuse and retention contract (plan Phase 5). It would also
  make the fetch-boundary rules apply to a loopback destination, which the
  gateway's SSRF policy must then allow explicitly.

### D5. Relays: **user's NIP-65 write relays + host defaults for publishing; lookup relays + hints for resolution**

- Publish targets default to the owner's kind `10002` write relays, unioned
  with a host default list (operator-editable, initially the two lookup
  relays plus `nos.lol` / `relay.damus.io`). Per-relay OK/failed results are
  part of the operation result; a publish that reaches at least one relay
  succeeds with a warning list, one that reaches none fails.
- Gateway resolution: configured lookup relays (defaults `purplepag.es`,
  `user.kindpag.es` for `10002`/`10063`), the author's own `10002` read
  relays, then manifest `r`/relay hints when present. The local control relay
  is never in any list and the config validator rejects loopback relay URLs.

### D6. Source deployment: **browser directory upload first; server-side draft area second; Git/NIP-34 later**

- Phase 3a: Admin `<input webkitdirectory>` upload with client-side hashing.
- Phase 3b: a per-site draft directory under `/var/lib/nostrhost/nsites/drafts/<site>/`
  that the Admin agent may write to and the publish operation may read from
  (inventory shown to the user before signing). This is the only server-side
  file path involved and it is fixed, not user-supplied.
- NIP-34 pinned-source builds stay in Phase 5 as the plan says.

### D7. Signing: **NIP-07 in the Admin; NIP-46 through the portal's existing connector later; MCP submits a pre-signed manifest**

- The server never holds or receives a user private key. No `nsec` input
  field anywhere in Admin; the CLI publish command accepts only a signed
  event file or a `bunker://` URI handled by the existing NIP-46 client
  path, never a raw key.
- Server-side validation of every submitted manifest: kind, `pubkey`,
  `id` recomputation, Schnorr signature, tag rules, aggregate hash
  recomputation, and (hosted mode) pubkey registration.

## 3. Architecture

```text
                       public internet
                              │
   https://<label>.sites.example.org      https://example.org/nostrhost/admin
                              │                               │
                          ┌───▼───────────────────────────────▼───┐
                          │  Caddy (nostrhost-caddy)               │
                          │  on-demand TLS  ──ask──►  gateway      │
                          └───┬───────────────────────────────┬───┘
            route @id nostrhost-nsite:<gw-domain>       per-domain snippets
                              │                               │
                ┌─────────────▼─────────────┐        ┌────────▼─────────┐
                │ nostrhost-nsite (Go)      │        │ nostr-api :8190  │
                │ 127.0.0.1:8195            │        │ nostrhost.nsites │
                │ ├ resolve manifests       │◄──────┤ (typed ops)      │
                │ ├ fetch + verify blobs    │ config │ state/nsites/*   │
                │ ├ cache (disk quota)      │ reload └────────┬─────────┘
                │ └ /internal/{healthz,     │                 │ kind 2200 chain
                │     tls-ask,status,sites} │        ┌────────▼─────────┐
                └───┬───────────────┬───────┘        │ nostrhost-control│
                    │               │                │ (loopback relay) │
              public relays   Blossom servers        └──────────────────┘
              (lookup + hints) (hints, 10063)         never reached by the gateway
```

### 3.1 Trust boundaries

| Boundary | Rule | Enforcement |
|---|---|---|
| Gateway origin vs Admin/Portal origin | Different registrable domains. Gateway responses carry no NostrHost HTML, cookies or identity headers. | `caddy_nsite.conf` has no `/nostrhost/*` or `/package/*` handlers; a Caddy test asserts the gateway host never matches those routes; the Playwright test loads a malicious test nsite and checks it cannot read the portal cookie or reach `/package/session`. |
| Gateway vs control plane | The gateway has no relay credentials, no `operator.toml` access, no state-repo access. | systemd `ProtectSystem=strict`, `ReadWritePaths=/var/cache/nostrhost-nsite`, `IPAddressDeny=127.0.0.0/8 ::1` with `IPAddressAllow` only for its own bind and Caddy's admin **not** included; config file `0640 root:nostrhost-nsite`. |
| Gateway vs upstream network | Fetch only `https://` (and `http://` if the operator enables it) to public unicast addresses. | Resolver hook that rejects loopback, link-local, RFC 1918, ULA, multicast and the metadata range at connect time (not just at URL parse time), re-checked on every redirect; at most 3 redirects; per-fetch byte and time caps; hash verified before any byte is written to cache or served. |
| Management vs public | `/internal/*` is served only on the loopback listener and never through Caddy. | Separate `net.Listener`; the public handler returns 404 for any `/internal` path; the Caddy route only proxies the public listener port. |
| Publish operation vs signer | The server validates but never signs user manifests; `operator_sk`, `server_sk` and the catalogue publisher key are never accepted as a manifest signer. | Publish operation rejects manifests whose `pubkey` equals any host key; unit test covers all three. |

### 3.2 File and state layout

| Path | Owner | Purpose |
|---|---|---|
| `/usr/bin/nostrhost-nsite` | package | Gateway binary |
| `/lib/systemd/system/nostrhost-nsite.service` | package | Hardened unit, `nostrhost-nsite` system user, disabled by default |
| `/etc/nostrhost/nsite.toml` | fork (`ConfigFileResource`-style writer) | Gateway config: domain, mode, relays, servers, limits, allowed sites (rendered from state; the gateway also re-reads it on `SIGHUP`) |
| `/var/cache/nostrhost-nsite/` | gateway | Content-addressed blob cache and manifest cache; disposable; excluded from backups |
| `/var/lib/nostrhost/nsites/drafts/<site>/` | fork | Phase 3b draft area |
| `state/nsites/gateway.json` | ngit state | Enabled, domain, mode, limits, relay/server defaults |
| `state/nsites/sites/<pubkey>[.<d>].json` | ngit state | Registered site: identity, kind, `d`, title, last published event id, aggregate hash, relays, servers, custom domains, provenance (actor, operation id, timestamp) |
| `state/nsites/domains/<fqdn>.json` | ngit state | Custom-domain mapping (Phase 4): target site, verification record, Caddy route id |

No secret lives in any of these. Reconstruction from state (roadmap §7.6):
re-render `nsite.toml`, re-ensure Caddy routes, start the service; the
cache refills.

### 3.3 Caddy wiring

- Base template gains, inside the global block, an On-Demand TLS
  permission endpoint. Caddy 2.9 (pinned in `packages.yml`) supports the
  `on_demand_tls { ask ... }` global option; the `permission http` form is
  the same mechanism in newer releases. The endpoint is the gateway's
  loopback `http://127.0.0.1:8195/internal/tls-ask`. With the gateway
  stopped the endpoint is unreachable, Caddy refuses issuance, and no
  certificate is minted for anything, which is the safe failure.
- New regenconf snippet `forks/yunohost/conf/caddy/caddy_nsite.conf`:

  ```caddyfile
  *.{{ domain }}, {{ domain }} {
      log
      tls {
          on_demand
      }
      header {
          -Server
          X-Content-Type-Options nosniff
          Referrer-Policy strict-origin-when-cross-origin
          Cross-Origin-Opener-Policy same-origin
      }
      reverse_proxy 127.0.0.1:8195 {
          header_up X-Forwarded-Host {host}
      }
  }
  ```

  For `.test` and other non-public domains the writer substitutes
  `tls internal`, mirroring `caddy_domain.conf`.
- `caddy_admin.py` gains `build_nsite_routes(domain, upstream)` and
  `ensure_nsite_routes` / `remove_nsite_routes` (`@id nostrhost-nsite:<domain>`),
  so enable/disable is an idempotent admin-API mutation like every other
  route, and the snippet exists only so regenconf detects manual edits.
- `DomainService.remove()` treats an enabled gateway domain as a dependent
  and refuses without `force`; `_dependents()` grows a second source
  (`state/nsites/gateway.json`).
- The apex of the gateway domain serves a static host index (title, how to
  reach a site) from the gateway, not the portal.

### 3.4 Ports and identities

| Component | Bind | User |
|---|---|---|
| `nostrhost-nsite` public listener | `127.0.0.1:8195` | `nostrhost-nsite` |
| `nostrhost-nsite` internal listener | `127.0.0.1:8196` | `nostrhost-nsite` |
| `nostr-api` | `127.0.0.1:8190` (existing) | root daemon as today |

Two listeners keep `/internal/*` unreachable through the Caddy route even
if the route matcher is ever loosened.

## 4. Gateway design (`libs/nostrhost-nsite`)

```text
cmd/nostrhost-nsite/        main: flags, config load, two listeners, SIGHUP reload
internal/config/            TOML schema + validation (rejects loopback relays, bad domains)
internal/nip5a/             label codec (npub, base36 pubkey+d, v+base36 id),
                            manifest parse/validate, aggregate hash, path rules
internal/resolve/           relay client (go-nostr), 10002/10063 lookup,
                            manifest fetch with per-site cache + TTL, hosted allowlist
internal/blossom/           safe fetcher: scheme allowlist, resolved-IP policy,
                            redirect policy, byte/time caps, streaming sha256 verify
internal/cache/             content-addressed blob store on disk, LRU with quota,
                            manifest cache, negative cache
internal/server/            public handler (host parse → site → path → blob),
                            content-type by extension, headers, ETag/304,
                            bounded 404s; internal handler (healthz, tls-ask,
                            status, sites reload)
internal/metrics/           counters/histograms (requests, cache hits, fetch
                            failures by class, bytes served) exposed on internal
deploy/nostrhost-nsite.service, deploy/postinst|prerm|postrm, nsite.example.toml
```

### 4.1 Request path

1. Parse `Host` (or `X-Forwarded-Host`): strip the configured gateway
   domain; reject labels longer than 63 characters or containing anything
   outside `[a-z0-9-]`; decode in the NIP-5A order: `npub1…` → root;
   `v` + 50 base36 chars → snapshot; 50 base36 chars + `d` → named. Apex
   serves the host index. Anything else: 404, no upstream fetch.
2. Hosted mode: the decoded site must be in the allowlist (root/named) or
   be a snapshot whose author is allowlisted. Otherwise 404 without a
   relay query.
3. Normalise the path: percent-decode once, reject a second level of
   encoding, reject `..`, `\`, NUL and control characters, collapse `//`,
   ensure a leading `/`. A path ending in `/` or with no extension in its
   last segment gets `/index.html` appended, per the NIP's rule.
4. Resolve the manifest (cache → relays). Choose the `path` tag exactly;
   with an ambiguous duplicate path, reject the manifest as malformed. On a
   miss use `/404.html` with status 404 if present, else a plain 404.
5. Resolve the blob: cache by sha256 → `server` tags in manifest order →
   author's `10063` in order → configured fallbacks. Each fetch is bounded
   and verified; the first verified copy is cached and served.
6. Respond with content type from the path extension (never the upstream
   header), `ETag: "<sha256>"`, `Cache-Control: public, max-age=3600` for
   blobs, `no-store` for 404s and the host index, and the security headers
   in §3.3. No `Set-Cookie`, ever.

### 4.2 `/internal/tls-ask`

`GET /internal/tls-ask?domain=<host>` returns 200 when step 1 succeeds and
step 2 allows the site; otherwise 403. It performs no relay or Blossom
network calls, so it stays fast and cannot be used to amplify traffic.

### 4.3 Configuration (`/etc/nostrhost/nsite.toml`)

```toml
domain = "sites.example.org"
mode = "hosted"                       # hosted | open (open rejected until Phase 5)
public_listen = "127.0.0.1:8195"
internal_listen = "127.0.0.1:8196"

[relays]
lookup = ["wss://purplepag.es", "wss://user.kindpag.es"]
extra = []
manifest_ttl_seconds = 300
negative_ttl_seconds = 60

[blossom]
fallback_servers = []
allow_http = false

[limits]
max_blob_bytes = 33554432             # 32 MiB
fetch_timeout_seconds = 20
fetch_concurrency = 8
max_redirects = 3
cache_quota_bytes = 2147483648        # 2 GiB
max_paths_per_manifest = 5000
requests_per_second = 50
requests_burst = 200

[[sites]]                             # rendered from state/nsites/sites/*.json
pubkey = "…hex…"
kind = 15128
d = ""
```

### 4.4 Default limits

Values above are the hosted-mode defaults. They are all
administrator-editable through the typed `nsite.gateway.configure`
operation, with the validator rejecting `max_blob_bytes` above 128 MiB and
`cache_quota_bytes` above 50% of the filesystem's free space at configure
time.

## 5. Fork design (`forks/yunohost/src/nostrhost/nsites/`)

| File | Contents |
|---|---|
| `models.py` | `GatewayConfig`, `SiteRecord`, `CustomDomainRecord`, `PublishRequest` (Pydantic v1 style like `domains/models.py`) |
| `manifest.py` | Pure functions: parse/validate a NIP-5A event (kind, `d` rule, `path` tag shape, duplicate paths, hash hex, aggregate hash recomputation, `a`/`A` shape), label encode/decode, canonical site URL. Shared corpus with the Go implementation. |
| `service.py` | `NsiteService`: `gateway_status/enable/disable/configure`, `site_register/unregister/list/inspect`, `render_config` → `nsite.toml` + `SIGHUP`, `publish_plan` (builds the unsigned event and the plan digest), `publish` (verify signed event, broadcast, record), `snapshot`, `domain_attach/detach` (Phase 4). Caddy via `CaddyAdminClient`, relays via the fork's existing outbound publish helper. |
| `operations.py` | `_safe_*` wrappers, one per ToolSpec, strict `_Strict` input models. |
| `signer_guard.py` | Rejects manifests signed by `operator_sk`, `server_sk` or the catalogue publisher key. |

Registry additions (`nostr_operations.py`, `native_ops.py`, policy
`scopes.py`/`rules.py`):

| Tool | Scope | Approval | Risk | Reversible | Notes |
|---|---|---|---|---|---|
| `nsite.gateway.status` | `nsites.read` | no | low | — | enabled, mode, domain, health, cache usage, TLS state |
| `nsite.list` / `nsite.inspect` | `nsites.read` | no | low | — | registered sites, current manifest, aggregate hash, relay/blob status |
| `nsite.resolve` | `nsites.read` | no | low | — | fetch a manifest for any pubkey/label from public relays (read only; bounded) |
| `nsite.validate_manifest` | `nsites.read` | no | low | — | validate a candidate (signed or unsigned) event; no network |
| `nsite.reachability` | `nsites.read` | no | low | — | relay/server reachability for a site; bounded |
| `nsite.publish.plan` | `nsites.read` | no | low | — | file inventory → unsigned event + `plan_sha256` binding hashes, kind, `d`, servers, relays |
| `nsite.gateway.enable` / `disable` / `configure` | `nsites.admin` | yes | medium | yes | Caddy route + config + unit; `disable` keeps state, removes route |
| `nsite.register` / `unregister` | `nsites.admin` | yes | low | yes | hosted-mode allowlist |
| `nsite.publish` | `nsites.publish` | yes | medium | partial (previous manifest kept as snapshot when requested) | signed event + `plan_sha256`; verifies, broadcasts, records |
| `nsite.snapshot` | `nsites.publish` | yes | low | — | kind `5128` from the current manifest, signed client-side the same way |
| `nsite.mirror` | `nsites.publish` | yes | low | yes | re-upload missing blobs to selected servers from the draft area (Phase 3b) |
| `nsite.domain.attach` / `detach` | `nsites.admin` + `domains.write` | yes | medium | yes | Phase 4 |

`nsites.publish` is confirmation-gated in `rules.py` like `domains.write`.
Autonomous-mode capability for every `nsite.*` write stays absent until
the evaluation evidence the plan requires exists.

API routes (`api.py`): `GET/POST /package/nsite/...` one per tool, same
`_run_tool` dispatch and error envelope. CLI (`cli.py`): `nostrhost nsite
gateway {status,enable,disable,configure}`, `nostrhost nsite {list,inspect,
register,unregister,resolve,validate}`, `nostrhost nsite publish --signed
<event.json> --plan <sha256>`.

## 6. Admin design (`forks/admin`)

- `src/api/nativeNsites.ts`: typed client for the routes above.
- `src/views/native/NsitesView.vue` + route `native-nsites` (`/sites`, nav
  label "Sites", icon `Globe2`): gateway card (status, enable/disable,
  configure form generated from the operation schema), sites table, publish
  wizard.
- `src/lib/nsite/`: `inventory.ts` (walk a `webkitdirectory` selection,
  reject symlink-like and oversize entries, hash with Web Crypto, sort),
  `manifest.ts` (build the unsigned `15128`/`35128` event, aggregate hash),
  `blossom.ts` (`HEAD /<sha256>` skip, `PUT /upload` with one kind `24242`
  auth event per batch of up to 20 blobs, retry by hash, per-server result),
  `publish.ts` (plan → sign → submit → poll `op_status`).
- Wizard steps: 1 site identity (session pubkey or a registered site) and
  type/`d`; 2 choose directory, show inventory with sizes and hashes; 3
  servers and relays (prefilled from `10063`/`10002`); 4 upload with
  per-file progress and per-server outcome; 5 review: exact tags, plan
  digest, destinations; 6 sign with NIP-07 (`window.nostr.signEvent`) and
  submit; 7 result: event id, relay acceptance, site URL, "open site".
  Editing anything after step 5 discards the plan digest.
- Signer availability: the console signs in through the portal session, so
  `window.nostr` may be absent. The wizard checks for it up front and
  explains that publishing needs a NIP-07 extension until NIP-46 lands.
- Accessibility and i18n follow `UI-REVIEW-AND-RECTIFICATION-PLAN.md`; every
  string in `src/i18n`.

## 7. Phased work breakdown

Sizes: S ≤ 1 day, M ≤ 1 week, L > 1 week for one contributor. Each phase
ends with its exit check green in CI and on the VM.

### Phase 0 — Protocol and component spike (M)

| # | Task | Files | Exit evidence |
|---|---|---|---|
| 0.1 | Pin NIP-5A text (commit hash), BUD-01/02/03 revisions, `nsite-gateway` commit, `nsyte` version. | `docs/NSITES-DECISION-RECORD.md` (new, Caddy-spike format) | Pins table |
| 0.2 | Conformance corpus: valid root/named/snapshot/copied manifests signed by a test key; malformed cases (bad `d`, duplicate path, non-hex hash, relative path, oversize path count, `..`, wrong aggregate hash, wrong kind/`d` pairing, signer = host key). | `tools/tests/nsites/corpus/*.json`, generator script | Corpus checked in with expected verdicts |
| 0.3 | Python `manifest.py` + tests over the corpus (this lands early because Phases 3+ need it regardless of D1). | `forks/yunohost/src/nostrhost/nsites/manifest.py`, tests | pytest green |
| 0.4 | VM: run upstream gateway (`deno compile` or Docker) behind Caddy with `tls internal` on `sites.nostrhost.test`; local fake relay and fake Blossom (`testbed/nsites/`); publish the corpus site with `nsyte`; verify hash checking, path rules, hostile inputs, private-IP hints, restart behaviour, control-relay isolation. | `testbed/nsites/{docker-compose.yml,Caddyfile,fake-blossom.py,README.md}` | Spike report table |
| 0.5 | Decision record: confirm or flip D1–D3 with evidence. | `docs/NSITES-DECISION-RECORD.md` | Signed off |

### Phase 1 — Gateway package and public serving (L)

| # | Task | Files |
|---|---|---|
| 1.1 | Create `libs/nostrhost-nsite` (submodule), skeleton, config, two listeners, healthz, systemd unit + maintainer scripts modelled on `nostrhost-agent`. | new repo, `.gitmodules`, `packaging/packages.yml` (`kind: golang`, not in either meta-package), `.github/workflows/libraries.yml` |
| 1.2 | `internal/nip5a`: label codec and manifest validation against the corpus. | Go tests share `tools/tests/nsites/corpus` |
| 1.3 | `internal/resolve`, `internal/blossom`, `internal/cache`, `internal/server` per §4. | Go unit tests with `httptest` fake Blossom and an in-process khatru test relay |
| 1.4 | Fork: `nsites/models.py`, `service.py` gateway enable/disable/configure, `caddy_admin.build_nsite_routes`, `caddy_nsite.conf` snippet + base-template `on_demand_tls`, `_dependents` extension, ToolSpecs/scopes/rules, API routes, CLI. | listed in §5 |
| 1.5 | Admin: gateway card only (status, enable, disable, configure). | `nativeNsites.ts`, `NsitesView.vue` |
| 1.6 | VM acceptance: clean install of the optional package, enable through a reviewed plan, HTTPS on the isolated origin, upgrade, disable, remove; public reads cannot reach `/nostrhost/*`, `/package/*`, `:8190`, `:4848`, `:8196`. | `docs/NSITES-DECISION-RECORD.md` appendix |

### Phase 2 — Safe resolution hardening (M)

Fuzz and property tests for the label codec and path normaliser; SSRF
table tests (loopback, RFC 1918, ULA, link-local, metadata, DNS rebinding
via a resolver stub, redirect-to-private); slow-loris and oversize
upstreams; cache eviction under quota; multi-server fallback ordering;
restart with a warm cache on the VM. Metrics and structured logs with
bounded fields. Exit: the plan's Phase 2 list, each as a named test.

### Phase 3a — Owner-controlled publishing, Admin + NIP-07 (L)

Registry: `nsite.register/unregister`, `nsite.publish.plan`,
`nsite.publish`, `nsite.snapshot`, `nsite.validate_manifest`,
`nsite.resolve`, `nsite.reachability`, `nsite.list/inspect`. Fork:
`service.publish_plan/publish`, `signer_guard.py`, state records, relay
broadcast with per-relay results. Admin: wizard per §6. Tests: no manifest
recorded or broadcast after a failed upload, digest mismatch, bad
signature, host-key signer, unregistered pubkey in hosted mode; Playwright
run through the wizard with the NIP-07 shim from `testbed/e2e`, then
anonymous retrieval from a second client.

### Phase 3b — MCP and agent surfaces (M)

Nothing new in `libs/nostrhost-mcp` beyond redaction of manifest `content`
and untrusted titles; verify generated schemas. Draft area and
`nsite.mirror`. Agent: capability rules keep `nsite.*` writes denied in
autonomous mode; add the read tools to the Observe config allowlist only.
Parity test: the same `nsite.publish` plan submitted via MCP and via Admin
yields identical operation results; a read-only MCP session cannot cause a
write; a stale plan digest is rejected.

### Phase 4 — Lifecycle and custom domains (L)

`nsite.domain.attach/detach`: ownership proof (a TXT challenge under
`_nostrhost-site.<fqdn>` or a CNAME to the gateway domain, checked with
the existing DNS verification helpers), uniqueness across
`state/nsites/domains`, Caddy on-demand `ask` extended to attached FQDNs,
detach removes the route and marker only. Snapshot/restore semantics in the
Admin (a root manifest is mutable; a snapshot is immutable). Operator
configuration of limits and exposure.

### Phase 5 — Catalogue and ecosystem (M, later)

`app` tag linkage to kind `32267`, "open nsite" from the catalogue view,
"create my copy" with `a`/`A` tags, optional local Blossom component, open
gateway mode with wildcard DNS-01.

## 8. Test matrix

| Layer | Where | Runs |
|---|---|---|
| Corpus (shared) | `tools/tests/nsites/corpus` | consumed by Go and Python unit tests |
| Go unit/integration | `libs/nostrhost-nsite` | `libraries.yml` |
| Fork unit | `forks/yunohost` tests: manifest, service, Caddy builders, registry schema snapshot, API routes | `fork-*` jobs |
| Policy | `libs/nostrhost-policy` scope/rule tests for `nsites.*` | existing |
| MCP | `libs/nostrhost-mcp` generated-tool snapshot + parity | existing |
| Admin | lint, type-check, build; Playwright wizard on the VM | existing + `testbed/e2e` |
| VM acceptance | `docs/VM-TESTBED.md` addendum "Phase 28" | manual, recorded in the decision record |
| Regression | alpha W0–W3 loop, Caddy tests, package-engine tests | unchanged |

## 9. Risks and how the plan bounds them

- **Certificate issuance abuse or rate-limit exhaustion.** Bounded by the
  `ask` endpoint (only allowlisted labels), hosted mode by default, and
  monitoring of Caddy's issuance log in `nsite.gateway.status`.
- **Serving hostile content on a NostrHost-operated origin.** Bounded by
  origin separation, security headers, no cookies, hosted-mode allowlist,
  and the operator's ability to unregister a site (which removes it from
  `ask` and from serving within one config reload).
- **Upstream dependency drift.** The corpus and the Phase 0 report make the
  upstream gateway a test oracle rather than a runtime dependency.
- **Signer UX friction.** Batching Blossom auth events keeps NIP-07 prompts
  to a few per publish; NIP-46 reuse is the follow-up if that is still too
  many.
- **Scope creep into a public hosting service.** Open mode, a local Blossom
  server and Git deployment are all explicitly later phases with their own
  gates.

## 10. Decisions required from the maintainer

1. **D1** Native Go gateway (`nostrhost-nsite`) with the upstream Deno
   gateway as the Phase 0 oracle — or package upstream?
2. **D2** Dedicated gateway domain plus Caddy On-Demand TLS with an `ask`
   endpoint, wildcard DNS-01 deferred — agreed?
3. **D3** Disabled by default; `hosted` (allowlisted) mode when enabled;
   `open` mode deferred to Phase 5 — agreed? Are the §4.4 default limits
   acceptable?
4. **D4** External Blossom servers only in the first release; which two
   public servers should the spike test against?
5. **D5** Relay defaults as listed; any operator-specific relays to include?
6. **D6** Browser directory upload first, agent draft area second, Git
   later — agreed?
7. **D7** NIP-07 first, NIP-46 via the portal's connector later, MCP submits
   a pre-signed manifest — agreed?
8. Should portal users (non-admins) be able to publish their own sites in a
   later phase, or is nsite publishing admin-only for the foreseeable
   future? This affects whether `nsites.publish` is modelled as an admin
   scope or a per-user capability from the start.
9. Package naming: `nostrhost-nsite` (component) versus the plan's
   `nostrhost-nsite-gateway`. The shorter name is proposed because the
   component will also carry the `tls-ask` and status roles.
