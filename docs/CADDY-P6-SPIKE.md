# Caddy P6 spike — retire nginx

Status: operational teardown passing on the VM; test-suite updates pending.
Branch `feat/nginx2caddy` (base `main`).

Proves the P6 slice of [CADDY-MIGRATION.md](CADDY-MIGRATION.md): Caddy takes
the public ports, the legacy nginx shim is removed, apps are served natively,
and the repo drops the nginx packaging/templates.

## VM operational teardown

1. **Caddy moved to 80/443** (`http_port 80` / `https_port 443` in the
   Caddyfile) — the real public ports.
2. **nginx stopped + disabled** (`systemctl stop/disable nginx`).
3. **Legacy shim removed**: the `/nostrhost-test-catalog/*` reverse-proxy-to-
   nginx route was replaced with native static routes serving
   `/var/www/nostrhost-test__2` and `/var/www/nostrhost-test` directly —
   `forward_auth` (authd) → `uri strip_prefix` → `file_server`.
4. **Pebble httpPort moved to 80** (its HTTP-01 validation now hits Caddy's
   HTTP listener on the real port).

The full portal e2e matrix passes against **Caddy :443 with nginx off**:
nip07 ✅, nip46 ✅, passkey ✅, launch ✅ (app title "NostrHost test app", body
"…verifies catalog installation, portal discovery, and auth-request headers").

### Findings

- **Caddyfile directive ordering**: `uri`/`rewrite` run *before* `forward_auth`
  in Caddy's built-in directive order, so a bare `uri strip_prefix` in the same
  route strips the prefix before the authd sees it → permission matching fails
  (`uri='/'` in the authd log). Fix: nest the strip + `file_server` inside a
  `handle { }` subroute after `forward_auth`. (The P4 JSON builder is immune —
  JSON handlers run in array order.)
- `apt remove nginx` on the VM cascades to the installed `yunohost` (its
  `debian/control` still declares the dependency), so the "package removed"
  gate is the repo `debian/control` change, not a live purge on the testbed.

## Repo teardown (`forks/yunohost` @ `2391130af`)

- `debian/control`: `nginx` + `nginx-extras` dependencies removed.
- `conf/yunohost/services.yml`: the `nginx` service entry removed (Caddy is the
  web service).
- `hooks/conf_regen/15-nginx` deleted.
- `conf/nginx/` templates deleted (the Caddy front end + native `web.route`
  providers supersede them).

## Follow-ups

- Update the nginx-referencing test files: `test_regenconf.py`,
  `test_service.py`, `test_apps.py`, `test_changeurl.py`,
  `test_backuprestore.py`, `test_sso_and_portalapi.py`.
- Remove the legacy nginx helpers (`helpers/helpers.v1.d/nginx`,
  `helpers/helpers.v2.1.d/nginx`, `ynh_add_nginx_config`).
- Drop remaining migration/nginx references; `scripts/verify-clean.sh` green.

## Gate

- nginx package removed: repo `debian/control` ✔ (live purge cascades to the
  testbed yunohost).
- `verify-clean.sh` green: pending (with the test-file follow-ups).
- VM e2e passes: ✔ on Caddy :443, nginx off.