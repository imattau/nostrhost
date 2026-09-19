# Native Admin API

**Platform baseline:** Debian 12 (Bookworm)
**Native API:** `127.0.0.1:8190`
**Admin SPA:** `/nostrhost/admin/`

The admin SPA uses native NostrHost endpoints exclusively and does not call
the YunoHost admin API. Caddy serves the SPA from `/usr/share/nostrhost/admin`
at `/nostrhost/admin/` and proxies `/package/*` on the same host to the
loopback native API at port 8190, preserving the request URL, method, and
scheme for NIP-98 verification.

## Authentication

Two mutually exclusive paths, handled by `default_authorizer()` in
`forks/yunohost/src/nostrhost/api.py`:

- **Portal session (primary).** The admin SPA is single sign-on: once a user
  signs in at the portal (`/nostrhost/sso/login`), the `nostrhost.portal`
  session cookie authenticates every native API request. The server resolves
  the session's linked identities and requires one to be an admin (the
  operator or a configured admin npub).
- **NIP-98 (`Authorization: Nostr <base64-event>`, fallback).** Used when
  there is no portal session (e.g. a CLI-style caller). The signed event is
  verified, the signer pubkey resolved to a linked identity, and that
  identity must be an admin. The app keeps only the public key in memory and
  never receives or stores a private key.

`GET /package/session` is the one route excluded from this gate — it is how
the SPA decides whether to show the console, redirect to the portal login, or
refuse a signed-in non-admin. It never leaks anything beyond the session
user's username, pubkey, and admin flag.

## Route groups

The route table in `forks/yunohost/src/nostrhost/api.py` (`build_app()`) is
the source of truth — this is a summary of what exists per resource, not an
exhaustive list. Reads generally execute directly (`_run_tool`); writes with
real consequences go through the signed operation and policy lifecycle
(`_run_lifecycle`) — the response's `ok: false` (rejected, failed, or pending
approval) must be checked, HTTP 200 does not mean success.

| Prefix | Covers |
| --- | --- |
| `/package/session`, `/package/healthz`, `/package/events/<id>` | Session probe (public), health probe (public), SSE operation progress |
| `/package/operations` | Audit history (`GET /package/operations[/<id>]`), approve/reject a pending operation |
| `/package/system` | Version, status (host snapshot), updates check/refresh/apply, migrations, reboot/shutdown |
| `/package/app` | Catalogue+installed inventory, install/upgrade/remove/settings plan-and-apply |
| `/package/catalog` | Catalogue list/get |
| `/package/user` | User and group CRUD, permissions |
| `/package/identity` | Linked-identity list/link/revoke |
| `/package/domain` | Domain list/inspect/add/remove |
| `/package/dns` | DNS record plan/apply/verify, provider credential refs |
| `/package/credential` | Stored DNS credential list |
| `/package/firewall` | Port/UPnP list, open, close, reload |
| `/package/backup` | Restic restore points: list, info, create, restore, delete (forget/prune), check, stats, retention policy, schedule |
| `/package/state` | State repository (ngit/NIP-34): status, history, diff, rollback plan/apply, reconcile plan, publish |
| `/package/diagnosis` | Run, ignored list, ignore/unignore |
| `/package/service` | Status, control (start/stop/restart) |
| `/package/settings` | Global settings list/get/set/reset/reset-all |
| `/package/agent` | Resident admin agent status/mode, MCP capability grants, local model management, contribution export/submit |
| `/package/mcp` | MCP endpoint config, CA bundle export |
| `/package/capability` | Capability grant/list/revoke, delegation |
| `/package/notify` | Remote-signer push targets: list, register the caller's own signer (`bunker://`), remove it, and node-initiated `nostrconnect://` pairing (start + poll). Admin-only; never returns a signer secret |
| `/package/plan` | Package manifest planning (read-only; `docs/../schema/package.schema.json`) |
| `/package/network`, `/package/reconcile` | Public IP lookup, state reconciliation |

## Package planning

`POST /package/plan` validates a package manifest against the checked-in
[JSON Schema](../schema/package.schema.json) and returns a deterministic,
read-only resource plan (identity, manifest digest, plan digest, operations).
It never applies anything — the request contains data only, never a shell
command, local path, or arbitrary operation envelope. App install/upgrade/
remove/settings follow the same plan-then-apply shape: an `apply` call
revalidates local state and the trusted catalogue, checks the reviewed plan
digest, and only then submits through the signed operation and policy
lifecycle.

## Follow-up contract work

- Publish typed OpenAPI contracts and generate the admin TypeScript client
  (currently hand-written adapters per resource in `forks/admin/app/src/api`).
- Logs (`logs.read`, `logs.web`, `service.history` tools exist) and
  certificates (`domain.cert.info`/`install`) have no HTTP route yet.
- `Idempotency-Key` is sent by the client on every write
  ([client.ts](../forks/admin/app/src/api/client.ts)) but not yet
  deduplicated server-side.
- Test NIP-07 request signing and denial behavior through Caddy on Debian 12.
