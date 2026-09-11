# Caddy P5 spike — domains, service, diagnosis, security

Status: partial (web-facing items passing). Branch `feat/nginx2caddy`
(base `main`).

Proves the P5 slice of [CADDY-MIGRATION.md](CADDY-MIGRATION.md) that is
web-facing and testable now; the deferred items are listed at the bottom.

## Security headers ported to Caddy

The Caddy sites (`testbed/caddy-p0/pebble/caddyfile.acme-test`) now send the
headers from `conf/nginx/security.conf.inc` (base, non-experimental set) plus
the SSO portal CSP from `yunohost_sso.conf.inc`:

```
Strict-Transport-Security: max-age=31536000
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: no-referrer
Permissions-Policy: interest-cohort=()
Content-Security-Policy: upgrade-insecure-requests; default-src 'self';
  connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline';
  script-src 'self' 'unsafe-inline'; object-src 'none'; img-src 'self' data:;
```

Verified with `curl -D -` on `/yunohost/sso/` and the app shim route, and the
portal e2e (nip07 / passkey / launch) still passes under the CSP.

## Domain sites + ACME policy via the admin API

`caddy_admin` gained:

- `build_domain_site(domain)` — `@id: nostrhost-domain:<domain>`, matcher
  `host` + `path "/"` (root only, so it never shadows app routes), respond 200.
- `CaddyAdminClient.ensure_domain_site(domain)` / `remove_domain_site(domain)`.

Validated with a fresh `test-new.test`:

1. `ensure_domain_site("test-new.test")` → route inserted at front.
2. First HTTPS handshake lazily triggers ACME — Caddy obtained a Pebble cert
   for it (HTTP-01 on loopback) and served `200`.
3. `certd` exported the new domain's cert to `/etc/yunohost/certs/test-new.test/`.
4. `remove_domain_site` → `DELETE /id` → route gone. Re-ensure idempotent.

This is the `domain_add`/`domain_remove` create/remove-site + ACME-policy
behaviour; wiring it into `domain.py` (and removing the nginx force-clear
hacks at `domain.py:393,580`) is a follow-up.

## `caddy` service

`conf/yunohost/services.yml` gained:

```
caddy:
  log: /var/log/caddy
  test_conf: caddy validate --config /etc/caddy/Caddyfile
  needs_exposed_ports: [80, 443]
  category: web
```

`caddy validate --config /etc/caddy-p0/Caddyfile` returns "Valid
configuration" on the VM. Wiring the admin-API reload into `service.py` is a
follow-up (nginx `test_conf` remains the default for now).

## Diagnosis

`diagnosers/21-web.py` replaces the `/etc/nginx/conf.d/<domain>.conf`
existence check with `_domain_has_caddy_site(domain)`, which queries the
Caddy admin API for any route matching the domain host. Verified: served
domains → True, unknown domain → False.

## Deferred to follow-ups

- `domain.py` wiring + nginx force-clear hack removal.
- TLS passthrough via `caddy-l4`.
- HTTP/3 + firewall `443/udp`.
- Stricter admin CSP + `criticalServices`/i18n strings.
- fail2ban→CrowdSec — owned by the concurrent `feat/fail2ban2crowdsec`
  (landed: P4–P6 of [CROWDSEC-MIGRATION.md](CROWDSEC-MIGRATION.md); the
  `crowdsecurity/caddy-logs` parser reads the Caddy JSON access log and
  fail2ban is retired).

## Gate

- `yunohost diagnosis` clean: partially met — the site check is proven; a full
  diagnosis run lands with the deferred `domain.py`/i18n items.
- fail2ban bans work: deferred (concurrent branch). → **Resolved** by CrowdSec:
  login-401 brute force bans proven end to end on the VM (CROWDSEC-MIGRATION
  §8.9/§8.10).

## Tests

`test_native_providers.py`: 54 passed (added `build_domain_site` shape test).