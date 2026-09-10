# Caddy P3 spike — auth cutover (forward_auth → nostr_authd)

Status: passing. Branch `feat/nginx2caddy` (base `main`).

Proves the P3 slice of [CADDY-MIGRATION.md](CADDY-MIGRATION.md): the SSOwat
authorization decision is ported to Python (the extended `nostr/auth-request`
endpoint — `nostr_authd`) and Caddy's `forward_auth` enforces it on protected
routes, delivering identity headers to apps and refusing client-supplied
copies.

## What changed

`forks/yunohost/src/nostr_login.py`:

- `auth_request_route()` now has two modes:
  - **Caddy `forward_auth`** (`X-Forwarded-Uri` present): the full
    authorization decision — permission matching, public routes, allowed
    users, redirect-to-portal.
  - **Legacy nginx `auth_request`** (no `X-Forwarded-Uri`): unchanged
    cookie-only validation; nginx/SSOwat still does the permission check on
    that front end.
- `_load_ssowat_permissions()` reads `/etc/ssowat/conf.json` (the same data
  SSOwat uses, so the two front ends cannot drift). Re-pointed at the semantic
  permission state when SSOwat is retired (P6).
- `_match_permission()` ports `access.lua` §3: longest URI match, `re:`
  prefixes anchored. The match host is port-stripped (`_host_domain`) because
  the conf URIs are bare DNS names while `X-Forwarded-Host` carries the port.
- `_authorize()` ports `access.lua` §4+6: no permission → deny; public →
  allow; protected → cookie auth + allowed-users, else redirect (`?r=`
  login callback or `?msg=access_denied`).
- `_identity_headers()` returns the header set on the response object. **This
  fixed a latent bug**: bottle drops headers set on the global `response` when
  a route returns a fresh `HTTPResponse`, so the old endpoint never actually
  delivered `X-Remote-*`/`X-Nostr-*` (the 302 `Location` worked because it was
  set on the response itself). Headers are always present (empty when unknown)
  so `copy_headers` unconditionally overwrites client forgeries.

`testbed/caddy-p0/pebble/caddyfile.acme-test` — the app route now has:

```
forward_auth 127.0.0.1:6788 {
    uri /nostr/auth-request
    copy_headers X-Remote-User X-Remote-Email X-Remote-Fullname X-Nostr-Pubkey X-Nostr-Npub
}
```

`forward_auth` adds `X-Forwarded-Method/Proto/Host/Uri`, preserves the original
Host (so the cookie host-claim check passes), and copies the listed response
headers onto the upstream request — overwriting anything the client sent.

Also re-landed (they had been reverted when the shared submodule was reset
after the P1 commit): the `_host_domain` port-strip helper in `ldap_ynhuser.py`
and its use in `nostr_login.create_portal_session`.

## Validation (nostrhost.test VM, Caddy :8443)

| Case | Outcome |
|---|---|
| dave (in allowed users) + cookie, protected app URI | `204` + identity headers |
| forged `X-Remote-User: admin` / `X-Remote-Email` / `X-Nostr-Pubkey` | overwritten; app sees `dave` / `dave@nostrhost.test` / real pubkey |
| no cookie, protected app URI | `302` → portal `?r=<b64 back-url>` |
| logged in, no matching permission | `302` → portal `?msg=access_denied` |
| public route (`core_skipped` admin/api), no cookie | `204` |
| `auth_request` flag end-to-end | app served via Caddy `forward_auth` → nginx shim, `200` |

Portal e2e matrix on Caddy `:8443` (now behind `forward_auth`): nip07 ✅,
nip46 ✅, passkey ✅, launch ✅ (app page reads "…verifies catalog
installation, portal discovery, and auth-request headers"). nip07 regression
on nginx `:443` ✅ (the header-delivery fix also helps the nginx path, which
reads `X-Remote-*` via `auth_request_set`).

## Findings worth recording

- **bottle drops `response.headers` on a returned `HTTPResponse`** — identity
  headers must be set on the returned response object.
- **Caddy `forward_auth` preserves the original Host** on the subrequest (like
  `reverse_proxy`), so the portal cookie's `host` claim matches; the authd
  falls back to `X-Forwarded-Host`/`Host` for the match URL, port-stripped.
- **Permission URIs are bare hostnames** — the match URL must strip the port.
- `forward_auth`'s `uri` must be the authd's own route (`/nostr/auth-request`,
  directly on 6788), not the nginx-mounted path.
- SSOwat retirement is deferred to P6 (nginx front end still uses it until
  nginx is retired); the authd shares SSOwat's conf so decisions agree today.

## Gate

- Permission matrix (allow / redirect-login / access-denied / public) passes. ✔
- App-header proof: identity headers delivered via `forward_auth` +
  `copy_headers`; forged copies refused. ✔
- `auth_request` permission flag enforced end to end. ✔
- Portal e2e matrix + nginx regression green. ✔