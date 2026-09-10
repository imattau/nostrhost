# Caddy P4 spike — native web routes via the admin API

Status: passing. Branch `feat/nginx2caddy` (base `main`).

Proves the P4 slice of [CADDY-MIGRATION.md](CADDY-MIGRATION.md): native apps get
Caddy routes reconciled through the admin API with `@id`-tagged granular calls
— no whole-config `/load` — and static (`file_server`) and `reverse_proxy`
apps both serve through Caddy.

## What changed (`forks/yunohost`)

- `src/nostrhost/caddy_admin.py` (new):
  - `CaddyAdminClient` — talks to `127.0.0.1:2019`:
    - `ensure_route(route)`: `GET /id/<id>`; identical route → no-op; else
      delete + `PUT /config/apps/http/servers/srv0/routes/0` (PUT to an array
      *index* inserts — this puts the app route in front of the
      Caddyfile-generated routes, safe because its host+path matchers are
      precise).
    - `delete_route(id)`: `DELETE /id/<id>` (404 → no-op). Reversible.
  - `build_web_route(desired)` — Caddy JSON route for a `[web]` resource:
    - `@id` = `nostrhost-web:<app>`;
    - matcher = `host` + `path/*`;
    - `auth = "nostrhost"` → a `forward_auth` handler first (so the authd sees
      the original, prefix-bearing URI for permission matching);
    - then a `rewrite strip_path_prefix` (like Caddyfile `handle_path`);
    - then `file_server` (when `file_root` set) or `reverse_proxy` to
      `upstream`.
  - `_forward_auth_handler()` replicates the Caddyfile `forward_auth` adapter
    output exactly: it is **not** a `forward_auth` module — it is a
    `reverse_proxy` whose 2xx `handle_response` deletes client-supplied
    identity headers and re-sets them from the authd only when non-empty.
- `src/nostrhost/native_providers.py`: `CaddyProvider.apply` now calls
  `ensure_route`/`delete_route` (was `POST /load`); `native_providers()`
  default-constructs the real client + builder on the real host (`root == "/"`),
  so `YnhExecutorBackend`'s bare call registers `web.route`.
- `src/nostrhost/package_engine.py`: `WebResource` gained `path` (default `/`)
  and `file_root`; validation requires `upstream` *or* `file_root`; the
  `web.route.ensure` args carry `app`.
- `tests_nostr/test_native_providers.py`: caddy tests updated to the new
  interface + `build_web_route` shape tests.

## Validation (nostrhost.test VM, live Caddy admin API on 2019)

| Case | Outcome |
|---|---|
| reverse_proxy route (`spike-rp` → portalapi 6788) | served via Caddy, 200 (challenge JSON) |
| file_server route (`spike-static` → /var/www/nostrhost-test) | served via Caddy, 200 (index.html) |
| auth route (`auth = "nostrhost"`) no cookie | 302 to portal (authd gates it) |
| re-ensure identical | no-op, single `@id` route |
| remove all | `DELETE /id` → routes gone (reversible) |
| converted app (`nostrhost-test` native route) | no cookie 302; dave cookie serves index.html |

`load_package(package.toml)` parses; the plan contains `web.route.ensure`.
Fork test suites: `test_native_providers.py` 53 passed, `test_package_engine.py`
27 passed (run on the VM with the matching pydantic).

## Findings worth recording

- **Caddy admin API semantics**: POST to an array *appends*; **PUT to an array
  index *inserts***; PATCH replaces; `@id` objects are addressable via `/id`.
- **`forward_auth` is not a JSON handler module** — the Caddyfile directive
  expands to a `reverse_proxy` + `handle_response`. The builder mirrors that.
- **App routes must be inserted, not appended**: the Caddyfile site's
  catch-all `handle` shadows appended routes. Insert-at-front with precise
  host+path matchers avoids it.
- **Prefix stripping order**: the authd must see the original URI (permission
  matching), so `forward_auth` runs before the `strip_path_prefix` rewrite.
- The top-level `nostrhost` package on the VM is a separate install target from
  `yunohost.nostrhost` — both were synced for the tests.

## Gate

- Static (`file_server`) and reverse-proxy native apps serve via Caddy. ✔
- Route add/remove is idempotent (re-ensure no-op) and reversible (delete). ✔
- `web.route` registered by default in `native_providers()`. ✔