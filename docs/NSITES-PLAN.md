# Nsites: implementation plan

Status: **proposed; discovery and packaging spike not started**. Nsites are a
post-alpha platform workstream. They do not change the current 0.1 alpha gate
(native bootstrap and an end-to-end conventional native app lifecycle).

This plan treats NIP-5A as an evolving interoperability target, not as a
protocol implementation frozen into NostrHost. The specification is currently
draft/optional, so event validation and hostname handling must be tested against
the version pinned for each release.

Protocol and implementation references: [NIP-5A](https://github.com/nostr-protocol/nips/blob/master/5A.md)
and the candidate [nsite-gateway](https://github.com/hzrd149/nsite-gateway).
Pin exact revisions during Phase 0; upstream behavior and the draft may change.

## Objective

Make NostrHost able to serve public NIP-5A sites and let an administrator
publish sites with their own Nostr identity. Keep the public site-serving path
separate from NostrHost's private local control plane. Use NostrHost's existing
typed plans, policy, approval, operation tracking, Caddy and domain services
for host mutations.

The target flow is:

```text
Admin browser + owner's signer
        │
        ├── upload immutable blobs ─────► selected Blossom server(s)
        ├── sign site manifest ─────────► owner's signer (NIP-07 / later NIP-46)
        └── publish manifest ───────────► selected public relay(s)

Visitor ──HTTPS──► Caddy ──► Nsite Gateway
                                ├── resolve manifest from public relays
                                ├── resolve blobs from Blossom servers
                                └── verify content hashes + cache responses

NostrHost control plane remains private and handles authorized management
operations; it is not an anonymous public relay or blob-serving endpoint.
```

## Fit with the current codebase

| Existing capability | Reuse | Gap |
|---|---|---|
| Native package/resource engine | Package the gateway service and manage its config, service, health and reverse route through typed resources. | No nsite resolver, Blossom uploader, manifest resource, or site lifecycle operations exist. |
| Caddy | Terminate HTTPS and route a dedicated site-hosting hostname or verified custom domains to the gateway. | Existing `WebResource` handles a fixed domain/path and local file root or upstream. Wildcard DNS-01 certificate support is explicitly deferred in the Caddy plan. |
| Identity and signer UI | Reuse Admin's NIP-07 signer connection and NIP-98 request pattern. | Current browser API supports NIP-07 for API requests; it does not provide a general event-publishing UX or NIP-46 publishing flow. |
| Operations, policy and approval | Make uploads/publishing and domain changes explicit operations with plans, actor identity, approval where required, progress and results. | There are no site-specific operations, permissions or operation schemas. |
| Domain and DNS services | Reuse native domain ownership, DNS planning and Caddy integration for conventional domains. | Site-to-domain claims and CNAME ownership checks need a defined lifecycle and conflict handling. |
| Native catalogue | Link a catalogue app descriptor to an nsite using NIP-5A's optional `app` reference. | Catalogue UI and nsite-aware discovery are not implemented. |
| Packaging | Ship the gateway as an independently versioned, optional component. | No gateway package is present in `packaging/packages.yml`; Deno is not among the current declared native runtime types. |

Relevant implementation seams are `forks/yunohost/src/nostrhost/package_engine.py`
(`WebResource` and lifecycle planning), `forks/yunohost/src/nostrhost/caddy_admin.py`
(`build_web_route`), `forks/yunohost/src/nostrhost/api.py` (NIP-98 API),
`forks/admin/app/src/api/nativePackages.ts` (NIP-07 requests), and
`forks/yunohost/src/nostrhost/domains/service.py` (domain/DNS/Caddy orchestration).

## Protocol and product boundaries

1. **NIP-5A events are authored by the site owner.** Root manifests use kind
   `15128`, named manifests use `35128` with a `d` identifier, and snapshots
   use kind `5128`. Validate required path tags, hashes, identifier constraints,
   snapshot references and aggregate hashes against the NIP version adopted by
   the release. Do not sign user manifests with `operator_sk`, `server_sk`, or
   the catalogue `publisher_sk`.
2. **Blobs are content-addressed; manifests are mutable identity statements.**
   Upload and verify every file before asking the signer to publish the
   manifest. A failed or partial upload must not produce a published manifest.
   Store snapshots as separate immutable manifest events when requested.
3. **The public gateway and control plane have different trust boundaries.**
   The gateway may read public Nostr events and public Blossom content; it must
   not expose the loopback control relay, operation events, credentials, or
   administrative HTTP APIs. Do not use public nsite hostnames as an Admin or
   Portal origin, and do not set management cookies for the parent domain.
4. **An nsite is static content, not a native backend package.** “Create my
   copy” can publish a new owner-signed manifest referencing existing blobs.
   It does not install a system service or establish that the site is trusted,
   safe, or sandboxed. Native server applications remain under the resource
   engine and catalogue trust policy.
5. **Custom domains are an optional layer.** A custom domain maps to a site
   only after an ownership challenge, conflict check, DNS/CNAME verification,
   and successful Caddy/TLS configuration. Removal must detach the mapping
   without deleting the user's DNS records unless they are explicitly
   NostrHost-managed.

## Work plan

### Phase 0 — Protocol and component spike

- Pin the exact NIP-5A text and build a small conformance corpus for root,
  named, snapshot, malformed and copied-site manifests.
- Evaluate the upstream `nsite-gateway` as a separately supervised service:
  supported NIP revision, relay selection, Blossom discovery, hash checking,
  path normalization, redirect behavior, response-size/time limits, cache
  policy, custom-domain behavior, license, release cadence and operational
  configuration.
- Run it on a disposable Debian 12 VM behind the existing Caddy setup. Verify
  the local control relay remains private and is not required for public
  resolution.
- Decide whether to package the upstream gateway, maintain a pinned fork, or
  implement a gateway in a supported NostrHost language. Record the decision,
  hostname format, public-gateway default, and DNS/TLS approach before adding
  package/API surfaces.

**Exit:** a reproducible VM proof serves a known test nsite over HTTPS, checks
the expected content hash, rejects an invalid manifest/blob, and survives a
gateway restart with its configured cache. A short decision record documents
trade-offs and remaining upstream risks.

### Phase 1 — Optional gateway package and public serving

- Add an independently versioned `nostrhost-nsite-gateway` package and systemd
  unit with an unprivileged service account, restricted filesystem access,
  bounded memory/file descriptors, explicit environment/config, and health
  endpoint. Do not add it to the default `nostrhost` meta-package until the
  public-serving resource and abuse profile are accepted.
- Declare package/service/config/health resources using existing package
  engine providers where they fit. Add a narrow typed provider only where
  generic `WebResource` cannot represent a gateway-specific route or setting;
  do not pass arbitrary Caddy JSON through a browser-supplied plan.
- Route one dedicated gateway origin through Caddy. Keep the Admin/Portal
  origin separate. Prove the selected host format and certificate path,
  including the deferred wildcard DNS-01 question if subdomains are used.
- Configure public event lookup through external relays and manifest relay
  hints. Keep the local control relay private. Treat an event cache as a
  disposable/read-only gateway cache, not authoritative NostrHost state.
- Make public serving opt-in per host. Define conservative defaults for
  maximum file size, cache storage, request rate, fetch concurrency, response
  timeout and relay/blob upstream count.

**Exit:** a clean VM can install, configure, start, health-check, upgrade and
remove the optional gateway through a reviewed NostrHost plan. Public reads
cannot reach Admin, Portal or control-plane endpoints.

### Phase 2 — Safe manifest and blob resolution

- Test hostname-to-site resolution for root, named and snapshot forms; use
  canonical formats supported by the selected NIP-5A revision. Return bounded,
  non-leaky not-found responses for invalid/missing events and paths.
- Normalize request paths before manifest lookup. Reject traversal, encoded
  separators, ambiguous duplicate path tags, invalid hashes and unsupported
  manifest structures. Apply the NIP's index-page and not-found rules.
- Resolve blob servers from manifest hints and the author's server list where
  supported. Fetch only allowed public HTTP(S) destinations. Defend against
  loopback/private/link-local addresses, DNS rebinding, redirect-to-private,
  oversized responses and slow streams; verify the final bytes against the
  manifest hash before serving or caching.
- Use content hashes as cache keys, bounded disk quotas, conditional HTTP
  caching, and cache invalidation appropriate to mutable manifests versus
  immutable blobs/snapshots. Never trust upstream Content-Type without safe
  handling; preserve correct static content types and security headers.
- Add metrics and structured logs that omit secrets and avoid unbounded event,
  URL, and header contents.

**Exit:** automated tests cover malformed manifests, hostile paths, hash
mismatch, malicious server hints/redirects, private-network fetch attempts,
size/time limits, cache eviction and valid fallbacks across multiple Blossom
servers. A VM test confirms restart and disk-quota behavior.

### Phase 3 — Owner-controlled publishing (Admin, MCP and agents)

- Add an Admin Nsites view for site identity, root/named type, source
  directory/archive, selected Blossom server(s), relay set, title/description,
  and optional snapshot/source metadata. Start with a local directory upload;
  defer Git automation and templates until the basic flow is proven.
- Validate and inventory files before upload: reject symlinks, path traversal,
  device/special files, excessive file count/size and unsafe paths. Show the
  exact file list, destination hashes, target identity, event kind/tags,
  servers and relays before signature approval.
- Upload blobs using supported Blossom endpoints and verify returned hashes.
  Support retry/idempotency by hash. Mirror only to explicitly selected
  servers; report partial mirror failures without claiming redundancy.
- Build the NIP-5A event client-side or in a service that returns an unsigned
  event. Request the owner's signature via NIP-07; validate returned pubkey,
  kind, tags, id and signature server-side before publication. Add NIP-46 only
  through the established signer abstraction, not by storing an `nsec` on the
  NostrHost machine.
- Publish to user-selected/public relays. Do not use the catalogue publisher
  identity as a fallback signer. Return relay acceptance results and the
  resulting site URL; allow retry where some relays fail.
- Represent publish/update as a typed, idempotent operation with a plan,
  progress events and result. Keep destructive blob deletion out of the first
  release; content-addressed assets may be referenced by multiple manifests.

#### AI surfaces: MCP and the Admin agent

- Define nsite inputs, result models, risk, reversibility and scopes once in
  the native operation registry (`ToolSpec` / operation catalogue). Generate
  MCP tool schemas and Admin agent actions/forms from that contract; do not
  build an independent MCP nsite API or let an LLM construct executable Caddy
  JSON or provider operations.
- Add read tools first: list/inspect a site's signed metadata, resolve a
  manifest, validate a candidate manifest, show relay/blob reachability, and
  explain a typed publish plan. Return bounded structured results with event
  IDs, hashes and provenance; redact credentials and untrusted HTML.
- Add write proposals for publish, snapshot, mirror, and domain attach/detach
  only after their typed operations and policy rules exist. An MCP client or
  Admin agent may prepare the proposal and follow its operation ID, but the
  authoritative operation daemon revalidates actor, capabilities, source
  inventory, policy and approval before any mutation.
- The Admin agent can guide site setup, generate/edit static files in an
  explicit user-selected draft area, identify missing metadata, summarize
  validation failures, and present a reviewable diff/plan. It must not read
  arbitrary host paths, run generated scripts, upload files without a visible
  user-selected inventory, choose unapproved relay/Blossom destinations, or
  publish without owner authorization.
- For publish, the review screen must bind approval to the exact file hashes,
  site kind/identifier, event tags, destination relays and Blossom servers.
  Changes after review invalidate the approval. The site owner's signer signs
  the NIP-5A event; the NostrHost agent identity and catalogue publisher key
  cannot substitute for that signature.
- Keep AI assistance optional and model-independent. The MCP tool contract and
  human Admin flow must remain usable with no local AI model, and no nsite
  prompt, source files, or generated HTML are sent to a remote model unless the
  operator explicitly configures that model endpoint and the user chooses to
  provide those contents.
- Reuse the resident `nostrhost-agent` typed planner/executor interfaces where
  it is appropriate for operator-directed maintenance and verification. Keep
  new nsite operations denied by default in autonomous mode until each action
  has explicit capabilities, fresh-read verification rules, and evaluation
  evidence. Publishing and domain ownership changes begin as approval-required
  operations, not autonomous actions.

**AI acceptance:** the same schema drives MCP and Admin agent planning; a
read-only prompt cannot cause a write; a forged or stale proposal is rejected;
the operation daemon enforces authorization after the model proposes an
action; a required approval is visible and correlated through `op_status`;
and the signer is asked to sign only the reviewed manifest after upload
verification. Human-only operation remains fully supported.

**Exit:** from Admin on a clean VM, an owner can publish a small site using
NIP-07, receive a valid publicly retrievable manifest, and load each path from
the gateway. Tests prove that no manifest is published after failed upload or
signature validation and that the server never receives or stores the user's
private key. The same publish plan can be inspected through MCP, then
submitted only through its typed, policy-gated operation; Admin and MCP return
the same operation result.

### Phase 4 — Site lifecycle and custom domains

- Add list/inspect/update/snapshot/republish operations with provenance,
  current manifest, aggregate hash, blob locations, relay publication status,
  gateway health and cache status.
- Preserve prior manifests as snapshots when requested. Do not describe a
  mutable root event as an immutable version; make restore/re-publish semantics
  explicit.
- Add custom-domain claim and detach operations only after DNS ownership
  proof, uniqueness enforcement, CNAME/ALIAS handling and a Caddy certificate
  strategy are demonstrated. Keep per-site mappings in managed local state and
  make them reconstructable; do not invent a NostrHost custom event if ordinary
  domain state plus signed NIP-5A events is sufficient.
- Add administrator-configurable gateway exposure, disk quota, cache policy,
  allowed upstream schemes and rate limits. Keep public-read configuration
  separate from management authentication and site publishing permissions.

**Exit:** ownership conflicts and invalid DNS/TLS states fail without leaving
orphaned routes; detach/remove is reversible until the DNS owner removes their
own records; a domain cannot resolve to a site under the wrong actor.

### Phase 5 — Catalogue and broader ecosystem integration

- Permit a NostrHost catalogue descriptor to reference an nsite using the
  standard NIP-5A `app` tag where applicable. The descriptor remains the source
  for title, publisher trust, release/runtime compatibility and catalogue
  policy; the nsite manifest remains a file map.
- Add “open nsite” and “create my copy” only for explicitly compatible
  static/client-side apps. Show publisher/source provenance and requested
  external origins. Copying content does not confer trust or sandboxing.
- Add deployment from a pinned NIP-34 source/release only after source
  verification, build reproducibility, file inventory and signing UX are
  specified. Treat build automation as a later extension to the user-selected
  local-upload flow.
- Consider Blossom storage as an independent optional service with its own
  quotas, abuse controls, privacy policy and data-retention contract. Hosting
  a public gateway must not silently make the server a public upload service.

**Exit:** catalogue discovery distinguishes native host packages from static
nsites and does not route an nsite through the native package installer.

## Security and operational gates

- **Origin isolation:** gateway hostname is not an Admin/Portal origin; no
  parent-domain auth cookies; no admin HTML/API assets served through the
  gateway. Verify browser origin isolation with a malicious test nsite.
- **Untrusted HTML/JS:** nsite responses are arbitrary internet content. Use
  appropriate CSP/content headers where compatible, never inject gateway
  dashboard state into site responses, and keep status/management surfaces on
  a separate origin/path with explicit access controls.
- **Fetch boundary:** Blossom URLs and relay URLs are untrusted network input.
  Restrict schemes, resolve and re-check IPs, block private/link-local ranges,
  bound redirects/concurrency/bytes/time, and validate response hashes.
- **Resource abuse:** set limits on concurrent requests, fetch size, event
  lookups, cache disk, file count, upload size, mirror fan-out and per-actor
  publishing. Use backpressure and clear operator alerts.
- **Key boundary:** browser/remote signer owns user-event signing; server keys
  retain only their documented machine/control/catalogue roles. No browser
  `nsec` export or server-side user-key persistence.
- **Domain integrity:** require explicit ownership verification, prevent
  duplicate mappings, and test Caddy host matching and cert renewal. Never
  allow an nsite route to shadow an Admin or Portal route.
- **Recovery:** record gateway package/config/domain mappings in native state;
  cache contents are reconstructable and disposable. Do not place private
  signer material, relay auth secrets or Blossom credentials in ngit state.

## Cross-cutting verification

- Unit tests: NIP-5A parsing and validation, hashes/aggregate hash, hostname
  decoding, path normalization, typed plan validation, operation authorization
  and Caddy matchers.
- Integration tests: fake relays/Blossom servers, signed events from a test
  identity, event lookup, upload/retry, mirror failure, safe cache behavior,
  malformed inputs and network-boundary rejection.
- Agent/MCP tests: strict schemas, bounded observations, untrusted manifest
  text treated as data, no shell/direct-provider path, authorization and
  approval rechecks after proposal, stale-plan rejection, and parity between
  MCP and Admin operation results. Evaluate read-only, assist and approval-
  required cases before enabling any autonomous maintenance action.
- VM acceptance: clean Debian 12 install, optional gateway lifecycle through
  package plan/reconcile, HTTPS on the isolated origin, publish with a browser
  signer, anonymous retrieval from a second client, restart/recovery, upgrade,
  domain attach/detach and control-plane isolation.
- Regression: existing alpha W0–W3 checks, Caddy tests, package-engine tests,
  Admin build and accessibility review stay green. Nsites do not weaken
  NostrHost's normal private-relay, authentication or operation-approval
  defaults.

## Decisions required before implementation

1. Upstream `nsite-gateway` package, maintained fork, or native implementation.
2. Canonical gateway domain/hostname format and whether wildcard DNS-01 is an
   explicit prerequisite or out of scope for the first deployment.
3. Whether a public gateway is opt-in per node and what default cache/abuse
   limits apply.
4. Which Blossom server(s) to test against and whether NostrHost will merely
   publish to external servers or later offer an optional upload service.
5. Which public relays are user-selectable defaults and how relay acceptance
   failures are represented in operation results.
6. Whether source/Git deployment is postponed until the local upload + signer
   workflow has passed VM acceptance.

## Initial milestone

The first milestone is **Phase 0 only**: a short protocol/component decision
record and VM proof using an existing gateway. It must establish separation
from the local control relay, path/hash correctness, origin isolation, and a
credible hostname/TLS plan before NostrHost adds a gateway package or Admin
publishing surface.
