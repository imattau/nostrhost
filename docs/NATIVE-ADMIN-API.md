# Native Admin API

**Platform baseline:** Debian 12 (Bookworm)
**Native API:** `127.0.0.1:8190`
**Admin SPA:** `/admin/`

The admin SPA uses native NostrHost endpoints and does not call the YunoHost
admin API. The package screen sends a JSON package object to the native package
planner. Planning validates declarations and returns a deterministic,
read-only operation plan; it does not apply changes.

## Authentication

API routes require an `Authorization: Nostr <base64-event>` header containing
a signed NIP-98 event. The server verifies the event, resolves its public key
to a linked identity, and requires admin authority. Browser requests are
signed by a NIP-07 extension. The app keeps only the public key in component
memory and never receives or stores the private key.

Caddy serves the SPA from `/usr/share/nostrhost/admin` at `/admin/`. It proxies
`/package/*` on the same host to the loopback
native API at port 8190, preserving the request URL and method used by NIP-98.
The Vite production base path, release manifest, and Caddy route are checked
together by the admin packaging tests.

## Current endpoints

| Method and path | Request | Result |
| --- | --- | --- |
| `GET /healthz` | none; loopback probe | Service health and API version |
| `GET /app/management` | none | Trusted catalogue joined with installed inventory; unlisted installations remain visible |
| `GET /app/{id}/settings` | none | Native app's non-secret typed settings schema and current values |
| `POST /app/{id}/install/plan` | `{}` | Verified catalogue package and deterministic read-only install plan |
| `POST /app/{id}/install/apply` | `{ "plan_sha256": "…" }` | Re-resolves the trusted package, checks the reviewed digest, and submits through the signed policy lifecycle |
| `POST /app/{id}/upgrade/plan` | `{}` | Verified catalogue release plan with compatible local setting values carried forward |
| `POST /app/{id}/upgrade/apply` | `{ "plan_sha256": "…" }` | Revalidates the plan digest and submits through the signed policy lifecycle |
| `POST /app/{id}/remove/plan` | `{}` | Removal plan derived from the locally recorded native manifest |
| `POST /app/{id}/remove/apply` | `{ "plan_sha256": "…" }` | Revalidates the installed state and submits through the signed policy lifecycle |
| `POST /app/{id}/settings/plan` | `{ "values": { ... } }` | Validated settings diff plus generated config and service operations |
| `POST /app/{id}/settings/apply` | `{ "values": { ... }, "plan_sha256": "…" }` | Recomputes the plan and applies only if it still matches the reviewed digest |
| `POST /package/plan` | `{ "package": { ... } }` | Validated package identity, manifest digest, plan digest, and resource operations |

The package object follows the checked-in [JSON Schema](../schema/package.schema.json).
Invalid declarations return an API error envelope with `error` and `code`.
The request contains data only; it cannot provide a local path, shell command,
or arbitrary operation envelope.

All app writes re-resolve local state and the trusted catalogue where relevant,
then submit a server-derived plan through the signed operation and policy
lifecycle. A plan returned by a planning endpoint is not authorization to apply
it. Settings updates accept only declared, non-secret values; package config
templates receive those values under the reserved `settings` context.

## Follow-up contract work

- Publish typed OpenAPI contracts and generate the admin TypeScript client.
- Add system-health and operation-history screens against existing native
  endpoints.
- Test NIP-07 request signing and denial behavior through Caddy on Debian 12.
- Add plan refresh and durable local draft handling to the package authoring
  screen.
