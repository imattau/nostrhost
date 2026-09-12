# Native Admin API

**Status:** read-only API and package-authoring UI slice implemented
**Platform baseline:** Debian 12 (Python 3.11)
**Canonical prefix:** `/api/v1`

The API exposes native NostrHost concepts. The admin client must not translate
requests into YunoHost API calls. The initial endpoints support package
authoring and a minimal system identity check; they do not install, reconcile,
or otherwise apply a package plan.

## Authentication

Every endpoint except the loopback health probe requires an
`Authorization: Nostr <base64-event>` header containing a signed NIP-98 event.
The verifier checks kind 27235, signature and event ID, a 60-second clock
window, the exact browser-visible request URL and method, and the SHA-256 body
tag for non-empty request bodies. Valid events can be used once; a process-local
replay cache rejects reuse. After signature verification, the pubkey must map
to a linked identity and be configured as an admin or operator.
The current Bottle service runs as one process; if its deployment is ever
changed to multiple workers, the replay cache must move to shared storage.

The API listens on loopback behind Caddy. Caddy preserves the `/api/v1/...`
path, forwards the original `Host`, and supplies the external scheme in
`X-Forwarded-Proto`. NIP-98 URL verification uses those values, the raw path,
and the raw query string. Do not strip or rewrite the versioned prefix in the
proxy route.

The first native package-authoring view uses a NIP-07 browser signer. It asks
the extension to sign each request and stores only the public key and
authorized identity in component memory; it does not persist or request a
private key. NIP-46,
signer recovery UX, and generated TypeScript client types remain follow-up
work. No endpoint accepts browser cookies as API authority.

## Implemented endpoints

| Method and path | Request | Result |
| --- | --- | --- |
| `GET /healthz` | none; loopback probe | `{ "ok": true, "version": 1 }`; public and intended for local service checks |
| `GET /api/v1/system/version` | none | Native system version information |
| `GET /api/v1/system/status` | none | Read-only host snapshot from the native system tool |
| `GET /api/v1/identity/me` | none | Authenticated linked identity and admin authority |
| `GET /api/v1/catalog` | none | Trusted native catalogue projection |
| `GET /api/v1/packages/schema` | none | The same JSON Schema document emitted by `nostrhost-package schema` |
| `POST /api/v1/packages/validate` | `{ "manifest": "<TOML text>" }` | `{ "schema": 1, "valid": boolean, "package": ..., "diagnostics": [...] }` |
| `POST /api/v1/packages/plan` | `{ "manifest": "<TOML text>" }` | Deterministic resource operations from the same package engine used by the CLI |

Package endpoints accept a JSON object containing only the string `manifest`
field. The text limit is 1 MiB. Invalid TOML or declarations return a normal
validation result with stable diagnostic `code`, `path`, `message`, and
optional `hint` fields; malformed HTTP request bodies use the API error
envelope `{ "error": string, "code": string }`.

Planning validates the manifest and serializes the package engine's
read-only desired-state operations. It may select architecture-specific
source metadata using the host architecture, but it does not inspect or
mutate installed host resources. Plan output is a review artifact, not an
authorization token and not an apply request. A future apply endpoint must
require an explicit plan digest and enter the existing policy, approval,
operation, and verification path.

## Source of truth

The schema, field guidance, validation diagnostics, and plan serialization
come from `nostrhost.package_authoring` and `nostrhost.package_engine`. CLI and
HTTP tests compare the API schema and exercise the same validation and plan
functions. The API does not accept paths, URLs to fetch, shell commands, or
arbitrary operation objects in package-authoring requests.

The unversioned HTTP routes and the YunoHost admin route table have been
removed from the shipped admin surface. New browser endpoints belong under
`/api/v1`; no password, cookie, form-data, or YunoHost endpoint adapter is
part of this cutover.

## Next contract work

1. Test NIP-07 exact URL/body signing through Caddy on Debian 12, including
   signer account changes and denied admin identities.
2. Add API OpenAPI/schema publication and generated TypeScript types from the
   endpoint request/response models.
3. Add durable local draft handling and stronger plan refresh/reconnect states
   to the package-authoring view.
4. Add operation submit/status/history endpoints only after request
   idempotency and the policy/approval boundary are represented in typed
   contracts.
