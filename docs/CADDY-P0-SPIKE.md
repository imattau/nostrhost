# Caddy P0 spike results

Date: 2026-09-10. Branch: `feat/nginx2caddy`. Plan:
[CADDY-MIGRATION.md](CADDY-MIGRATION.md) §5 P0.

Goal: prove a stock Caddy build with `caddy-l4` can serve the portal, admin,
and the API/portalapi/OIDC proxies on alternate ports, with `tls internal` for
`nostrhost.test`, **without disturbing the nginx instance on 80/443**.

## Build

- `xcaddy` v0.4.7, Go 1.22.2, Caddy **v2.11.4**.
- `caddy-l4` compiled in (`caddy listen-modules` reports `layer4.*`; 180
  modules total).
- `GOFLAGS=-buildvcs=false` is required: xcaddy builds in a temp dir where
  Go's VCS stamping fails.
- Reproducible via `testbed/caddy-p0/build.sh`.

## VM layout (spike)

| Path | Purpose |
|---|---|
| `/opt/caddy-p0/caddy` | spike binary |
| `/etc/caddy-p0/Caddyfile` | spike config (`testbed/caddy-p0/Caddyfile`) |
| `/etc/systemd/system/caddy-p0.service` | spike unit (`testbed/caddy-p0/caddy-p0.service`) |

Ports: **8080** (HTTP→HTTPS redirect), **8443** (HTTPS), **2019** (admin API,
loopback only). nginx still owns 80/443.

`tls internal` issued a certificate from *Caddy Local Authority - ECC
Intermediate* (no ACME; that is P2).

## Results

Requests used `curl -k --resolve nostrhost.test:8443:127.0.0.1`.

| Path | Result |
|---|---|
| `/yunohost/sso/` | **200**, SPA served |
| `/yunohost/sso/assets/<hash>.js` | **200** |
| `/yunohost/sso` (no slash) | **301** → `/yunohost/sso/` |
| `/yunohost/admin/` | **200** |
| `/yunohost/api/` | **405** (proxy reaches Moulinette; GET on a POST-only root) |
| `/yunohost/portalapi/nostr/challenge` | **200** `{"challenge": "..."}` |
| `/.well-known/openid-configuration` | **200** |
| `http://nostrhost.test:8080/` | **308** → HTTPS |

`caddy validate` passes; the unit is `active` and `enabled`.

## Notes / follow-ups for P1

1. Curl must match the site name (SNI/Host); a bare `127.0.0.1` request is not
   served because there is no default site. P1 should decide whether to add a
   catch-all.
2. The 8080→HTTPS redirect emitted `https://nostrhost.test/` without `:8443`.
   Confirm redirect-host/port behaviour before the real cutover.
3. **No authentication yet.** Caddy currently serves the portal and proxies
   the API with SSOwat entirely bypassed; `forward_auth` is P3. Do not expose
   these ports publicly.
4. The admin API is bound to loopback only and is unauthenticated on that
   interface (Caddy default); treat it as root-equivalent.
5. Spike runs as root; the production unit should drop privileges and use a
   dedicated `caddy` user with read access to the served paths.

## Gate status

- Caddy binary reproducible: **yes** (`testbed/caddy-p0/build.sh`).
- Spike notes committed: **yes** (this file).
- P1 (portal e2e against Caddy): **passing** (see below).

## P1 addendum — portal e2e green on Caddy

The full `testbed/e2e/portal-e2e.py` matrix passes against Caddy on **8443**
(`NOSTR_TEST_PORT=8443`) and still passes on the default nginx path (443).

| Mode | Result on Caddy |
|---|---|
| `nip07` | login POST 200, `yunohost.portal` cookie `Domain=.nostrhost.test`, dashboard as dave |
| `nip46` | real NIP-46 bunker round-trip through Caddy (no interception), logged in |
| `passkey` | `window.NostrPasskey` served via Caddy; full use still needs a PRF-capable real browser (documented limitation) |
| `launch` | app `nostrhost-test-catalog/` served via the Caddy→nginx shim route; session cookie crosses, status 200 |

Changes that made this work (all committed on `feat/nginx2caddy`):

1. **Portal** (`forks/portal`, `2d415f8`): build the portalapi URL from
   `window.location.host` instead of `hostname`, so a portal served on a
   non-default port talks to the same origin.
2. **Portal-api** (`forks/yunohost`, `eb07045d2`): strip the `:port` from the
   Host header when it is used as a domain — the session cookie `Domain`
   attribute (browsers reject ports there), the JWT `host` claim (SSOwat
   compares it to port-stripped `$host`), and the
   `user_is_allowed_on_domain` allow-check.
3. **Harness** (`testbed/e2e/portal-e2e.py`): `NOSTR_TEST_PORT` env; the
   Python-side `http()` connects to loopback and SNIs `nostrhost.test` via a
   TLS socket injection (avoids Caddy rejecting SNI `127.0.0.1`); it echoes
   the port-bearing Host so the challenge/domain binding matches.
4. **Caddyfile** (`testbed/caddy-p0/Caddyfile`): `handle
   /nostrhost-test-catalog/*` reverse-proxies to nginx:443 (`Host:
   nostrhost.test`, `tls_insecure_skip_verify`) so the launch mode exercises
   the legacy-shim path with SSOwat still enforcing.
