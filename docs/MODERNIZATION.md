# YunoHost Base — Modernization Assessment

Status legend: ✅ done · ◑ partial · ⏳ planned · ⏸ deferred

This document is the working assessment and tracking record for modernizing
the **residual upstream-YunoHost Python base** of the NostrHost fork
(`forks/yunohost`). It is deliberately scoped to the inherited base: the
NostrHost-native layers are already current-generation and are not changed
here.

See `ROADMAP.md` for the platform plan; this document covers the language,
library and framework modernization workstreams only.

---

## 1. What is already modern

The NostrHost-native stack is current and should be left alone:

| Area | Implementation |
|---|---|
| Daemons | `asyncio` + `websockets` + `nostr-sdk` (`nostr_operationsd`, `nostr_identityd`, `nostr_permissiond`) |
| Control plane / catalog / nsite / agent | Go 1.24 (`libs/nostrhost-control`, `-catalog`, `-nsite`, `-agent`) |
| MCP | official `mcp` Python SDK 2.x (`libs/nostrhost-mcp`) |
| CLI | `typer` |
| Web / TLS / reverse proxy | Caddy (nginx + SSOwat retired) |
| Intrusion detection | CrowdSec + nftables (fail2ban retired) |
| Backup | Restic + ngit/NIP-34 state |
| Admin SPA | Vue 3 + Vite 6 + TypeScript 5.7 |
| Portal SPA | Nuxt 3 / Vue 3 |
| Identity | Nostr keypairs; LDAP retired (§25) |
| Runtime packaging | private venv `/opt/nostrhost/venv` with bundled manylinux wheels (`nostrhost-runtime`) |

---

## 2. What is still legacy

The inherited base and its modernization status:

| # | Area | Evidence | Modern target | Status |
|---|---|---|---|---|
| L1 | HTTP API on **bottle + single-threaded wsgiref** | `src/nostrhost/api.py` (`app.run()`), `src/nostrhost/portal_api.py` (119 + n routes); admin SPA streams SSE `/package/events/<id>` | FastAPI/Starlette + uvicorn (async) | ✅ P2 |
| L2 | **ZeroMQ** XSUB/XPUB SSE log broker | `src/utils/sse.py` (`zmq.proxy`, `.logstreamcache`, `time.sleep(1)` connect hack) | native async SSE / drop | ✅ P2 |
| L3 | `pydantic` pinned to **v1** | `pyproject.toml` `<2.0`; code already imports `pydantic.v1` with fallbacks; venv ships 2.13 | v2 | ✅ P1 |
| L4 | `pyjwt` pinned to **v1** | `pyjwt>=1.7,<2.0`; `nostr_oidc.py`, legacy LDAP authenticators | v2 | ✅ P1 |
| L5 | `passlib` (unmaintained) | `src/utils/password.py` `sha512_crypt` for `/etc/shadow` | stdlib `crypt(3)` | ✅ P1 |
| L6 | `toml` (deprecated package) | `mcp_endpoint.py`, `file_utils.py`, `jinja_filters.py`, `native_providers.py` | `tomllib` + `tomli-w` | ✅ P1 |
| L7 | dual `requests` + `httpx` | 8 files used `requests`; 6 used an **undeclared** `httpx` | consolidate on `httpx2` | ✅ P1/P3 |
| L8 | vendored `acme_tiny` (2016-era ACME client) | `src/vendor/acme_tiny/`, used by `certificate.py` → `domain.cert.install` | delegate to Caddy / `acme` lib | ✅ P3 |
| L9 | vendored `spectre-meltdown-checker` (2018 shell) | `src/diagnosers/00-basesystem.py` Meltdown check | `/sys/devices/system/cpu/vulnerabilities/` | ✅ P3 |
| L10 | `aptitude` for package operations | only the historical 0027 bookworm migration (`utils/system.py` wrapper); no runtime/problem path uses it | retire with the pre-bookworm migration path | ⏸ assessed |
| L11 | gevent remnant / `ldap_admin` | `utils/process.py` gevent branch (dead); `authenticators/ldap_admin.py` still used by `log.py`/`user.py` | drop gevent branch; keep `ldap_admin` | ✅ P3 |
| L12 | flake8/black/isort tooling | `pyproject.toml` tox envs | ruff (+ uv) | ✅ P1 |

---

## 3. Phase 1 — dependency hygiene ✅

Landed in fork `d2ac24ad5` (superproject bump + `packaging/*` alongside).

- **L3 pydantic → v2.** `pyproject.toml` pin changed to `>=2.0`. No code
  change was required: the tree already uses the `try: from pydantic.v1 … /
  except: from pydantic …` shim, which resolves under both lines, and the
  runtime venv already ships pydantic 2.13.5 (ROADMAP W1;
  `nostrhost-policy` requires `>=2.13.5`).
- **L4 pyjwt → v2.** Pin changed to `>=2.0`; the two `jwt.decode` call sites
  are in the retired LDAP authenticators.
- **L6 toml → `tomllib` + `tomli-w`.** Reads use the stdlib `tomllib`
  (Python ≥3.11); writes use `tomli-w` (`mcp_endpoint.write_endpoint_config`,
  `native_providers` crowdsec config, `jinja_filters.to_toml`). `tomli-w` is
  bundled into `nostrhost-runtime` (`packaging/runtime/requirements.txt`,
  runtime bumped to `0.1.7`); `python3-toml` dropped from `debian/control`.
- **L5 passlib → `crypt(3)`.** `_hash_user_password` now uses the C library's
  `crypt(3)` (`crypt.mksalt(METHOD_SHA512, rounds=656000)`), byte-identical to
  passlib's output (verified). `passlib` is retained **only** as the Python
  3.13+ fallback, because PEP 594 removed the stdlib `crypt` module; see §5.
- **L7 (part) `httpx` fix.** The six `httpx` import sites (DNS providers +
  native source download/health client) were importing an **undeclared**
  module — nothing in the Debian deps or the venv provides `httpx`. They now
  use `httpx2`, the HTTP client the runtime already bundles (via the MCP SDK).
  The `requests` → `httpx2` consolidation is deferred to Phase 3 so the
  `requests` dependency can be dropped in the same change that removes
  `acme_tiny` (its last consumer).
- **L12 ruff.** Replaced flake8 + black + isort with ruff: `[tool.ruff]`
  lint config (`select = ["E","F","W"]`, matching the old flake8 ignore set),
  tox `py311-lint`/`py311-format` envs, and the `auto-lint` workflow. Fixed
  the 13 findings it surfaced (9 missing EOF newlines, an unused f-string, a
  `not in`, an unused import, an unused variable). Formatting is *not* gated:
  the tree is not `ruff format`-clean and the existing auto-format workflow
  owns formatting. `ruff` added to the test dependency group.
- **L9 (assessed, kept).** `spectre-meltdown-checker` is *actively used* by
  the Meltdown diagnosis, so it was **not** removed. Modern replacement:
  read `/sys/devices/system/cpu/vulnerabilities/meltdown` (kernel ≥4.15)
  instead of running the 2018 shell script — deferred pending a diagnosis
  behaviour/translation review.

`requests` remains a declared dependency until Phase 3.

### Verification
- Fork suite: **991 passed**, same 3 pre-existing failures
  (`test_agent_lifecycle`, `test_native_ops`, `test_portal_projection` — all
  environment/pre-existing, unrelated).
- `ruff check src bin doc maintenance` → clean.

---

## 4. Phase 2 — HTTP layer ✅

**Problem.** Both internal HTTP services ran on bottle's built-in server
(`bottle.WSGIRefServer` → `wsgiref.simple_server`), which is
**single-threaded**: one request at a time, no keep-alive.

| Service | Unit | Port | Entry |
|---|---|---|---|
| native admin API | `nostr-api.service` | 127.0.0.1:8190 | `src/nostrhost/api.py:run` |
| portal auth API | `nostr-portal-api.service` | 127.0.0.1:6788 | `src/nostrhost/portal_api.py` |

The admin SPA consumes **SSE** (`/package/events/<request_id>`,
`useOperation.ts`), so a single open stream blocked every other request.

**Done.** Both services are now **FastAPI on uvicorn** (fork `f7b031d06`,
`affd321ea`); bottle is removed from the tree and all manifests.

- `nostrhost/api.py` — `_AuthErrorsPlugin` → `_ApiRoute` (a per-route
  `APIRoute` wrapper): authorizes before the endpoint (NIP-98 / portal session
  / CSRF / nsite scope rules unchanged), stores the admin pubkey on
  `request.state`, and maps `ApiError` / operation errors / unexpected
  exceptions to the `{"error", "code"}` envelope. The simple GET-forward table
  is a route-registration loop reading `request.path_params`; `/events` is a
  Starlette `StreamingResponse` (exact `text/event-stream` header preserved);
  `uvicorn.run` replaces `app.run`.
- `nostrhost/portal_api.py` — `build_app` → FastAPI; `_WebRoute` binds the
  request context, drains queued cookies/status, and maps a raised
  `HTTPResponse` / unexpected error. All 22 portal routes unchanged.
- `nostrhost/web.py` — new shared per-request context (request ContextVar,
  `request`/`response` proxies, `HTTPResponse`, pending-cookie queue) used by
  both APIs and by the session authenticator, so the deep cookie-refresh path
  keeps working and now attaches to the FastAPI response.
- `backup.py` archive download / `user.py` CSV export return Starlette
  responses instead of bottle `static_file`/`HTTPResponse`.
- `fastapi` added to the runtime wheel set (runtime `0.1.8`); `python3-bottle`
  dropped from `debian/control`, `packages.yml`, `compatibility.yml`.

**L2 ZeroMQ SSE log broker — retired ✅.** `utils/sse.py` streamed operation
logs to the retired `yunohost-admin`; `start_log_broker` only ran under the
retired `interface == "api"`, every parent `OperationLogger` still built the
handler (opening a socket to a broker that never starts and sleeping 1s), and
its `.logstreamcache`/`get_current_operation` had no callers. Removed it and
the `zmq` dependency (fork `886b0f1cf`).

**Notes / deviations from the draft plan.**
- NIP-98 became a per-route `APIRoute` wrapper (not an async dependency) to
  keep the exact authorize→endpoint→error-map ordering and the single-process
  `ReplayCache` semantics.
- SSE uses a plain Starlette `StreamingResponse` (the runtime already ships
  `sse-starlette` via the MCP SDK, but the existing frame generator needed no
  change).
- Request/response JSON shapes are byte-compatible; existing clients are
  unaffected.

### Acceptance for Phase 2
- Both apps verified over ASGI; the 133 admin-API tests + portal tests pass.
- Single-worker uvicorn keeps the `ReplayCache` semantics.
- Remaining VM check: concurrent requests + multiple simultaneous SSE streams
  behind Caddy, and the admin SPA / portal end-to-end.

---

## 5. Phase 3 — system internals

1. **L7 `requests` → `httpx2` ✅.** The 8 remaining files (`diagnosis`,
   `dyndns`, `caddy_admin`, `app_catalog`, `diagnosers/21-web`, `yunopaste`,
   `file_utils`, `resources`) and `bin/yunopaste` now use `httpx2` (with
   `follow_redirects=True` where `requests` followed by default; exception
   types mapped: `TimeoutException`/`ConnectError`/`RequestError`). `requests`
   is dropped from the runtime deps (`debian/control`, `packages.yml`,
   `compatibility.yml`) and kept only as a test-only dep for the legacy
   upstream `tests/`.
2. **L11 gevent/moulinette cleanup ✅.** `utils/process.py` dropped its dead
   gevent branch (`gevent` was never a declared dep, so the import always
   failed) for a plain `threading.Thread`; `types-gevent` removed. There are
   **no real `moulinette` imports** left (only logger names / historical
   comments), and `authenticators/ldap_admin.py` is **not dead** — it is used
   by `log.py` and `user.py` — so it stays (now on `nostrhost.web`).
3. **L8 ACME → Caddy ✅ (VM-verified).** Caddy owns platform TLS (ACME for
   public domains, its local CA otherwise) and `nostr_certd` exports the certs
   into `/etc/yunohost/certs`; `certificate.py` still ran the vendored
   `acme_tiny` and restarted the retired nginx/dovecot. Now
   `_fetch_and_enable_new_certificate` ensures the domain's Caddy site (which
   triggers provisioning) and polls `nostr_certd.export_domain`; the CSR/SAN
   builder, account-key/key generation, nginx ACME-challenge check and
   nginx/dovecot restarts are removed, and `src/vendor/acme_tiny` is deleted
   (`src/vendor` is now empty). `_get_status` also stopped misreporting a
   still-valid short-lived cert as "expired". Verified on the clean7 testbed:
   `certificate_install('nostrhost.test')` ensured the Caddy site, exported the
   cert, and status moved from `expired` → `abouttoexpire`. The
   `domain.cert.install`/`info` native ops delegate to Caddy and tolerate a
   not-yet-provisioned cert. (The legacy `cert_alternate_names` CSR hook is
   retired with the CSR builder; SANs now come from Caddy config.)
4. **L10 aptitude → reassessed: no work needed for supported systems.**
   `aptitude` is invoked by exactly one caller — the historical
   `migrations/0027_migrate_to_bookworm.py` (via
   `utils/system.py:aptitude_with_progress_bar`). No runtime, app-install or
   upgrade path uses it, and bookworm+ systems have already run 0027. So the
   target is not "rewrite on `python3-apt`" but "drop the aptitude dependency
   when the pre-bookworm migration path is retired" (a separate, small
   cleanup once migrations ≤0027 are dropped).
5. **L9 Meltdown → `/sys` interface ✅.**
   `is_vulnerable_to_meltdown` now reads
   `/sys/devices/system/cpu/vulnerabilities/meltdown` (kernel ≥ 4.15) instead
   of running the vendored 2018 shell script (and caching it in `/tmp`); the
   `src/vendor/spectre-meltdown-checker` tree is removed. Absent interface
   (x86-specific) ⇒ nothing to diagnose. Unit-tested.

---

## 6. Cross-cutting follow-ups

- **`passlib` / Python 3.13 (trixie).** The sha512crypt path now uses `crypt`
  (3.11/3.12). On Python 3.13 the stdlib `crypt` module is gone (PEP 594), so
  the passlib fallback is used. Before moving the target to trixie, adopt a
  maintained `libxcrypt` binding (or yescrypt/argon2, if PAM/shadow
  compatibility is confirmed).
- **`uv`.** The umbrella/library workflows already use `uv`; the fork still
  uses pip/tox. Aligning the fork on `uv` is optional and independent of the
  lint change.
- **`types-toml`** stub removed with the `toml` dependency.

---

## 7. Sequencing

```text
Phase 1  dependency hygiene                        ✅
Phase 2  FastAPI/uvicorn both APIs + retire zmq    ✅
Phase 3  requests→httpx2, gevent cleanup,          ✅
         Meltdown /sys check, ACME→Caddy (VM-verified)
         aptitude                                  ⏸ assessed (migration-only)
```

Phase 2 depends on Phase 1's pydantic v2 alignment. Phase 3's `requests`
removal depends on the `acme_tiny` replacement landing in the same change.
