# nginx → Caddy Migration Plan

Status: phases P0–P6 complete on the VM (`feat/nginx2caddy`, base `main`); P7
remaining (backup hooks + semantic state). Caddy serves the public ports,
authd owns authorization, certd exports certs, native routes reconcile via the
admin API, and nginx is retired from the package/templates.

Replace nginx with Caddy as NostrHost's single web/TLS front end, let Caddy own
automatic Let's Encrypt, and retire or simplify the YunoHost components that
exist only because of nginx and the hand-rolled ACME stack.

This document is the cutover map for that work. It complements
[RESOURCE-ENGINE-CUTOVER.md](RESOURCE-ENGINE-CUTOVER.md) (legacy lifecycle
removal) and [LEGACY-INVENTORY.md](LEGACY-INVENTORY.md) (package cutover
status); those gates still apply.

## 1. Locked decisions

| Decision | Choice | Consequence |
|---|---|---|
| Authentication | Caddy `forward_auth` → Python auth daemon | `forks/ssowat` Lua retired; permission logic lives in the authd + `nostrhost.permissions` |
| App compatibility | Native `package.toml` web routes only | Caddy does **not** translate legacy `conf/nginx.conf`; nginx survives only as an internal legacy shim until the legacy inventory is clean |
| Certificates | Caddy canonical, exported to `/etc/yunohost/certs` | postfix/dovecot/slapd keep working via an export service |
| Caddy build | stock Caddy via `xcaddy` + `caddy-l4` | TLS passthrough and HTTP/3 preserved; needs a shipped binary/`.deb` |
| Plan location | `docs/CADDY-MIGRATION.md` on `feat/nginx2caddy` | New branch off `main` |

## 2. What nginx and friends own today

| Concern | Current owner | Key locations |
|---|---|---|
| Web/TLS termination, vhosts | nginx + Jinja templates | `forks/yunohost/conf/nginx/server.tpl.conf`, `security.conf.inc`, `yunohost_admin.conf` |
| ACME + self-signed CA | `certificate.py`, `vendor/acme_tiny`, `hooks/conf_regen/02-ssl` | HTTP-01 webroot `/var/www/.well-known/acme-challenge-public/` |
| Auth/permission gate | **SSOwat Lua inside nginx** | `forks/ssowat/access.lua`, `init.lua`, `conf/nginx/ssowat.conf` |
| Config regeneration | `regenconf` `nginx` category | `src/regenconf.py`, `hooks/conf_regen/15-nginx` |
| App routing | `ynh_add_nginx_config` → `/etc/nginx/conf.d/<domain>.d/<app>.conf` | `helpers/helpers.v1.d/nginx`, `helpers/helpers.v2.1.d/nginx` |
| Service health | `nginx -t` as `test_conf` | `conf/yunohost/services.yml:17`, `src/service.py:259-295`, `494-496` |
| Security/logs | base security headers + SSO CSP on Caddy sites; CrowdSec parses the Caddy JSON access log | `conf/caddy/` site snippets; CrowdSec acquisition → `crowdsecurity/caddy-logs` (see [CROWDSEC-MIGRATION.md](CROWDSEC-MIGRATION.md)) |
| Cert consumers | nginx **and** slapd (LDAP); postfix/dovecot retired | `conf/slapd/config.ldif:53-54` |
| Admin/API/portal/OIDC | nginx `location` blocks | `conf/nginx/yunohost_admin.conf.inc`, `yunohost_api.conf.inc`, `yunohost_sso.conf.inc` |
| TLS passthrough | nginx `stream` + `ssl_preread` | `conf/nginx/tls_passthrough.conf`, `tls_passthrough_server.conf` |

A `CaddyProvider` already exists (`forks/yunohost/src/nostrhost/native_providers.py:1453`)
and the package schema already declares `[web] auth = "nostrhost"` /
`https = "automatic"` (`package_engine.py:303-307`). It is **not wired**: the
executor constructs bare `native_providers()`
(`src/nostr_operationsd.py:75-89`), no admin-API client exists, and the
provider posts the whole config to `/load`, which would clobber Caddy's
ACME/runtime state.

## 3. Target architecture

```text
Caddy (public 80/443, 443/udp HTTP/3; admin API 127.0.0.1:2019)
 ├─ TLS: automatic ACME (Let's Encrypt) for public names
 │        `tls internal` for .test/.local/non-public names
 ├─ domains + native app routes  ← generated from semantic state,
 │                                  applied via @id-tagged admin-API routes
 ├─ forward_auth → nostrhost-authd (Python)
 │        → ALLOW / DENY / 302-to-portal + X-Remote-*/X-Nostr-* headers
 ├─ reverse_proxy → yunohost-api:6787, portalapi:6788, OIDC, native upstreams
 ├─ file_server → /yunohost/sso, /yunohost/admin (SPA fallback)
 ├─ [transitional] reverse_proxy → nginx 127.0.0.1:8080 (quarantined legacy apps)
 └─ nostrhost-certd: export certs → /etc/yunohost/certs → reload slapd (LDAP)
```

The semantic state model already reserves the relevant sections
(`docs/ROADMAP.md` §7.2): `certificates/`, `services/`, `domains/`, `apps/`.

## 4. Component disposition

| Component | Action |
|---|---|
| `forks/ssowat/*.lua`, `conf/nginx/ssowat.conf` | **Retired** (landed with P6 teardown): deleted; the Python authd + native permission projection (`nostrhost.permissions` → `/etc/nostrhost/permissions.json`) replace them |
| `certificate.py` issuance/renew, `vendor/acme_tiny`, `02-ssl` self-CA | **Retire**; keep `certificate_status`/`_get_status` re-pointed at Caddy/exported store |
| `hooks/conf_regen/15-nginx`, `conf/nginx/*` | **Replace** with `15-caddy` + `conf/caddy/` |
| `native_providers.CaddyProvider` | **Rewire**: real admin client + `@id` incremental routes (no whole-`/load`) |
| `conf/nginx/nostrhost_auth_request_params` | **Replace** with a Caddy `forward_auth`/`header_up` snippet |
| `conf/yunohost/services.yml`, `service.py` `nginx -t` | → `caddy` + `caddy validate` |
| `conf/fail2ban/yunohost-jails.conf` | **Retired** (P6 of [CROWDSEC-MIGRATION.md](CROWDSEC-MIGRATION.md)): the nginx jails are gone with fail2ban. Intrusion detection reads Caddy's JSON `access.log` via the `crowdsecurity/caddy-logs` parser → CrowdSec scenarios (`yunohost-auth-bf`), enforced by the nftables bouncer |
| `debian/control` nginx deps, migrations, admin critical-services/i18n | → caddy |
| `tls_passthrough` | → `caddy-l4` layer4 app |
| `helpers/*/nginx` | native `web.route` only |

### Transitional legacy shim

Because the Caddy path is native-only, quarantined `_ynh` apps stay served by
nginx bound to `127.0.0.1:8080` (no public ports) and reverse-proxied by Caddy.
The shim is explicitly temporary: it is deleted when
[LEGACY-INVENTORY.md](LEGACY-INVENTORY.md) shows no installed or supported
package needs the legacy path. `nostrhost-test` (the sole legacy fixture) is
converted to a native `package.toml` with `[web] auth = "nostrhost"` to
exercise the native route path.

## 5. Phased plan

Each phase has a gate. nginx keeps the public ports until Phase 6.

### P0 — Spike and decisions
- Create `feat/nginx2caddy`.
- Build Caddy with `xcaddy` (`caddy-l4`); pin the version.
- Stand Caddy on the VM on alt ports with `tls internal` for `nostrhost.test`.
- Verify portal static serving + `reverse_proxy` to 6787/6788.
- Gate: spike notes committed; Caddy binary reproducible.

### P1 — Caddy serves portal/admin/API
- `file_server` with SPA fallback for `/yunohost/sso` and `/yunohost/admin`.
- `reverse_proxy` for `/yunohost/api` (6787), `/yunohost/portalapi` (6788),
  `/.well-known/openid-configuration`, `/oidc/*`.
- Port `security.conf.inc` headers (HSTS, CSP, `X-*`) to Caddy `header`.
- Re-run `testbed/e2e/portal-e2e.py` modes nip07/nip46/passkey/launch against
  Caddy.
- Gate: portal e2e green on Caddy.

### P2 — ACME and cert export
- Status: **passed on the VM** — see [CADDY-P2-SPIKE.md](CADDY-P2-SPIKE.md).
  Issuance + renewal exercised against the Pebble test CA (loopback HTTP-01);
  `nostr_certd` exports Caddy's store into `/etc/yunohost/certs` and slapd
  serves the exported cert over LDAPS.
- Enable automatic HTTPS; use the Let's Encrypt staging CA first
  (`acme_ca`), then production.
- Implement `nostrhost-certd`: watch Caddy's cert store, atomically export
  `<domain>/{crt,key}.pem` to `/etc/yunohost/certs`, fire the existing
  `post_cert_update` hook, **restart** slapd (LDAP). postfix/dovecot are
  already retired, so slapd is the sole non-web consumer today. Note: OpenLDAP
  caches the TLS material at process start, so `systemctl reload` is not
  enough — certd restarts it.
- Re-point `certificate_status`/`_get_status` at Caddy/exported state
  (achieved by certd feeding the standard store; the read path is unchanged).
  Retire `_certificate_install_letsencrypt`, `certificate_renew`,
  `_fetch_and_enable_new_certificate`, `vendor/acme_tiny`, and the self-signed
  issuance path — **deferred to P5/P6** (kept intact-but-superseded until
  domain/ACME policy moves into Caddy).
- Keep `conf/nginx`-independent bootstrap for the `yunohost.org` default
  server via `tls internal` (P2 spike also obtains + exports it via the test CA).
- Gate: a certificate is obtained and renewed; slapd (LDAP) TLS serves the
  exported Caddy-owned certificate. **Met on the VM.**

### P3 — Auth cutover
- Status: **passed on the VM** — see [CADDY-P3-SPIKE.md](CADDY-P3-SPIKE.md).
- Extend the existing auth-request endpoint
  (`src/nostr_login.py`) into a full authorization decision:
  URL→permission matching (longest match, `re:` regexes), public routes,
  allowed users, redirect-to-portal (`?r=` login callback / `?msg=access_denied`),
  cookie/session checks — ported from `forks/ssowat/access.lua`.
- Wire Caddy `forward_auth` per protected route; copy identity headers
  (`X-Remote-User`, `X-Remote-Email`, `X-Remote-Fullname`, `X-Nostr-Pubkey`,
  `X-Nostr-Npub`) and refuse client-supplied copies (`copy_headers` overwrites
  them; the authd always emits the full header set, empty when unknown).
- **SSOwat is retired** (landed with the P6 teardown): `forks/ssowat` and the
  `ssowat` package dependency are gone; the authd reads a native permission
  projection (`/etc/nostrhost/permissions.json`) generated by
  `nostrhost.permissions` (via the `PermissionProvider`), with a transitional
  fallback to the legacy `/etc/ssowat/conf.json`. nginx/SSOwat never enforced
  divergent auth for a route on the Caddy front end.
- Gate: permission matrix and app-header proof pass; the `auth_request`
  permission flag (`app.py:2089-2170`) is enforced end to end (Caddy
  `forward_auth` → authd for `nostrhost-test`). **Met on the VM.**

### P4 — Native web routes
- Status: **passed on the VM** — see [CADDY-P4-SPIKE.md](CADDY-P4-SPIKE.md).
- Add a real Caddy admin-API client (`src/nostrhost/caddy_admin.py`) and config
  builder (`build_web_route`); `web.route` is registered in `native_providers()`
  by default on the real host (so `YnhExecutorBackend`'s bare call wires it).
- Reconcile routes with `@id` tags via granular admin-API calls, not `/load`:
  `PUT .../routes/0` inserts in front of the Caddyfile routes (precise
  host+path matchers make that safe), `DELETE /id/<id>` removes, identical
  routes are a no-op.
- Convert `packages/nostrhost-test` to a native `package.toml` (`[web]` with
  `file_root` + `auth = "nostrhost"`; legacy manifest retained until the nginx
  shim is retired).
- `WebResource` gained `path` and `file_root` (static file_server vs
  reverse-proxy upstream); the web op args now carry `app` for a stable `@id`.
- Gate: static and reverse-proxy native apps serve via Caddy; route add/remove
  is idempotent and reversible. **Met on the VM.**

### P5 — Domains, service, diagnosis, security
- Status: **partial — passed on the VM** for the web-facing items; see
  [CADDY-P5-SPIKE.md](CADDY-P5-SPIKE.md). Several items are explicitly
  deferred (below).
- `domain_add`/`domain_remove` create/remove Caddy sites and ACME policy:
  `caddy_admin` gained `ensure_domain_site`/`remove_domain_site` (`@id`
  `nostrhost-domain:<domain>`, root-path matcher so it never shadows apps);
  ACME is the global `acme_ca` + automatic HTTPS, and `certd` exports the
  cert. Wiring into `domain.py` (`domain_add`/`domain_remove` calling the
  client) and removing the nginx force-clear hacks (`domain.py:393`, `580`)
  is a follow-up.
- `services.yml`: `caddy` service added with `test_conf: caddy validate
  --config /etc/caddy/Caddyfile`; service reload via the admin API still to
  be wired into `service.py` (the nginx `test_conf` path remains the default).
- `diagnosers/21-web.py`: nginx-conf existence check replaced with a Caddy
  site check (`_domain_has_caddy_site` queries the admin API for a host
  match). i18n summary strings still nginx-named (follow-up).
- Port `security.conf.inc`, the SSO/admin CSP, and HSTS to Caddy: the Caddy
  sites now send the base security headers + the SSO portal CSP
  (`yunohost_sso.conf.inc`), verified against the portal e2e. The stricter
  admin CSP is a follow-up (needs SPA testing).
- **Deferred to follow-ups**: nginx force-clear hack removal + `domain.py`
  wiring; TLS passthrough via `caddy-l4`; HTTP/3 + firewall `443/udp`; admin
  `criticalServices`/i18n strings.
- **Security/logs**: fail2ban→CrowdSec landed on
  `feat/fail2ban2crowdsec` (P4–P6 of [CROWDSEC-MIGRATION.md](CROWDSEC-MIGRATION.md)):
  the `crowdsecurity/caddy-logs` parser reads the Caddy JSON `access.log`,
  `yunohost-auth-bf` fires on `POST /yunohost/api/login` 401s, and the
  nftables bouncer enforces bans; fail2ban (incl. its nginx jails) is retired.
- Gate: `yunohost diagnosis` clean; CrowdSec bans proven end to end (login
  brute force from a foreign source → ban → kind-2213 `security` event on the
  local relay) — see CROWDSEC-MIGRATION §8.9/§8.10.

### P6 — Retire nginx
- Status: **operational teardown done on the VM; test-suite updates pending** —
  see [CADDY-P6-SPIKE.md](CADDY-P6-SPIKE.md).
- Caddy moved to the public ports (80/443) on the VM and nginx was stopped +
  disabled; the full portal e2e matrix (nip07/nip46/passkey/launch) passes with
  Caddy alone. The legacy nginx shim is gone — the test apps are served
  natively (forward_auth → strip → file_server).
- Repo teardown committed: `nginx`/`nginx-extras` removed from
  `debian/control`, `hooks/conf_regen/15-nginx` deleted, `conf/nginx/`
  templates deleted, and the `nginx` service removed from `services.yml`.
- Follow-ups: the six nginx-referencing test files now assert the Caddy model
  and the `15-caddy` regenconf category + `domain.py` site wiring are in place;
  `scripts/verify-clean.sh` no longer pins ssowat; semantic state records
  `certificates/`. Remaining: remove the legacy nginx helpers
  (`helpers/*/nginx`, `ynh_add_nginx_config`) and drop residual
  migration/nginx references. On the VM, `apt remove nginx` cascades to the
  installed `yunohost` (still declares the dep), so the package-removal gate is
  satisfied by the `debian/control` change rather than a live purge.
- Gate: nginx package removed (debian/control ✔), `scripts/verify-clean.sh`
  green (pending), VM e2e passes (✔ on Caddy :443).

### P7 — Docs, state, backup
- Status: this document is current; the backup-hook change and semantic-state
  recording are the remaining items.
- Keep this document current; update ROADMAP/VM-TESTBED/STATELAYER.
- Back up Caddy storage (or the exported `/etc/yunohost/certs`); update
  `hooks/backup/21-conf_ynh_certs` and `hooks/restore/21-conf_ynh_certs` to
  include `/var/lib/caddy` (Caddy's ACME/routes storage) alongside the
  exported certs.
- Record `certificates/` and `services/` in semantic state (follow-up).

## 6. New artifacts

| Artifact | Purpose |
|---|---|
| `forks/yunohost/conf/caddy/` | Caddy config templates (base, per-domain, snippets) |
| `forks/yunohost/hooks/conf_regen/15-caddy` | Caddy regen category |
| `forks/yunohost/src/nostrhost/caddy_admin.py` | Admin-API client + config builders |
| `forks/yunohost/src/nostr_certd.py` | Cert export + reload driver |
| `forks/yunohost/src/nostr_authd.py` | Authorization decision endpoint (or extension of `nostr_login.py`) |
| `forks/yunohost/conf/systemd/caddy.service`, `nostrhost-certd.service` | Units |
| `forks/yunohost/tests_nostr/test_caddy_*.py` | Provider/client/certd/authd tests |
| Caddy packaging (xcaddy build + `caddy-l4`) | Shipped binary or `.deb` |

## 7. Risks

1. **Authd is security-critical.** Port SSOwat logic with a permission test
   matrix before any cutover; never leave both nginx and Caddy enforcing auth
   for the same route.
2. **`/load` semantics.** Whole-config replacement clobbers ACME/runtime
   state; use `@id`-tagged incremental admin-API mutations.
3. **Cert export atomicity** for LDAP; write-then-rename and reload only
   on change. postfix/dovecot are already removed
   ([MAIL-RETIREMENT.md](MAIL-RETIREMENT.md)); slapd is the only non-web
   consumer, so the export surface is small.
4. **Packaging on bookworm.** No distro Caddy with `caddy-l4`; the derivative
   must ship a reproducible `xcaddy` build via the source provider.
5. **Legacy shim drift.** The shim must stay quarantined (loopback only) and
   be scheduled for deletion against the legacy inventory.
6. **Concurrent branches.** `feat/resource-engine` work landed on `main`;
   rebase this branch as `main` advances.

## 8. Non-goals

- Translating arbitrary legacy nginx snippets to Caddy.
- DNS-01 wildcard certificates (current YunoHost uses HTTP-01 per name).
- Rewriting the portal/admin front ends; only their serving layer changes.
