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

The remaining legacy is the **Python core inherited from YunoHost**, plus a
few vendored artifacts:

| # | Area | Evidence | Modern target |
|---|---|---|---|
| L1 | HTTP API on **bottle + single-threaded wsgiref** | `src/nostrhost/api.py` (`app.run()`), `src/nostrhost/portal_api.py` (119 + n routes); admin SPA streams SSE `/package/events/<id>` | FastAPI/Starlette + uvicorn (async) |
| L2 | **ZeroMQ** XSUB/XPUB SSE log broker | `src/utils/sse.py` (`zmq.proxy`, `.logstreamcache`, `time.sleep(1)` connect hack) | native async SSE / drop |
| L3 | `pydantic` pinned to **v1** | `pyproject.toml` `<2.0`; code already imports `pydantic.v1` with fallbacks; venv ships 2.13 | v2 |
| L4 | `pyjwt` pinned to **v1** | `pyjwt>=1.7,<2.0`; `nostr_oidc.py`, legacy LDAP authenticators | v2 |
| L5 | `passlib` (unmaintained) | `src/utils/password.py` `sha512_crypt` for `/etc/shadow` | stdlib `crypt(3)` |
| L6 | `toml` (deprecated package) | `mcp_endpoint.py`, `file_utils.py`, `jinja_filters.py`, `native_providers.py` | `tomllib` + `tomli-w` |
| L7 | dual `requests` + `httpx` | 8 files use `requests`; 6 used an **undeclared** `httpx` | consolidate on `httpx2` |
| L8 | vendored `acme_tiny` (2016-era ACME client) | `src/vendor/acme_tiny/`, used by `certificate.py` → `domain.cert.install` | delegate to Caddy / `acme` lib |
| L9 | vendored `spectre-meltdown-checker` (2018 shell) | `src/diagnosers/00-basesystem.py` Meltdown check | `/sys/devices/system/cpu/vulnerabilities/` |
| L10 | `aptitude` for package operations | `src/utils/system.py` (20 refs) | `python3-apt` |
| L11 | moulinette/gevent + dead LDAP authenticator remnants | `utils/process.py` (annotated legacy), `log.py`, `authenticators/ldap_*` | delete |
| L12 | flake8/black/isort tooling | `pyproject.toml` tox envs | ruff (+ uv) |

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

## 4. Phase 2 — HTTP layer (planned) ⏳

**Problem.** Both internal HTTP services run on bottle's built-in server
(`bottle.WSGIRefServer` → `wsgiref.simple_server`), which is
**single-threaded**: it serves one request at a time with no keep-alive.

| Service | Unit | Port | Entry |
|---|---|---|---|
| native admin API | `nostr-api.service` | 127.0.0.1:8190 | `src/nostrhost/api.py:run` |
| portal auth API | `nostr-portal-api.service` | 127.0.0.1:6788 | `src/nostrhost/portal_api.py` |

The admin SPA consumes **SSE** (`/package/events/<request_id>`,
`useOperation.ts`), so a single open stream blocks every other request on that
server.

**Plan (decision: go straight to FastAPI, both APIs).**

1. Replace bottle with **FastAPI/Starlette + uvicorn** for **both**
   `nostr-api` and `nostr-portal-api`.
   - NIP-98 auth (`_AuthErrorsPlugin`, `verify_nip98_request`, `ReplayCache`)
     becomes an async dependency/HTTPBearer; the replay cache stays
     single-process (uvicorn single worker) to preserve semantics.
   - `_SIMPLE_GET_FORWARDS` → a route-registration loop; JSON schemas via
     pydantic v2 models, aligning the API with the `operation_catalog()` typing
     already shared by MCP/Admin.
   - Preserve the existing error JSON shape (`{"error", "code"}`) via
     exception handlers; `_json_safe` becomes unnecessary.
   - SSE via `sse-starlette` (`EventSourceResponse`) — already in the runtime
     wheel set (`starlette==1.6.0`, `sse-starlette==3.4.11`, `uvicorn`).
2. Keep host/port identical so Caddy routes and systemd units barely change
   (only the `ExecStart` server entry if it changes).
3. **L2:** retire the ZeroMQ SSE log broker (`utils/sse.py`) after
   inventorying its consumers; drop `zmq` if nothing else uses it.
4. Add `fastapi` to the runtime wheel set (`packaging/runtime/requirements.txt`)
   and bump `nostrhost-runtime`.

### Acceptance for Phase 2
- Concurrent requests served in parallel; multiple simultaneous SSE streams.
- Admin SPA end-to-end (vitest, `vue-tsc`, `vite build`) and portal login.
- NIP-98 auth + CSRF behaviour unchanged (existing API tests ported to the
  FastAPI TestClient).

---

## 5. Phase 3 — system internals (planned) ⏳

1. **L8 ACME → Caddy.** `domain.cert.install` (`native_ops.py:1697`) and the
   compat `certificate.py` still issue via the vendored `acme_tiny`. Decision:
   delegate issuance to **Caddy** for native domains and remove the vendored
   client. This is also what lets `requests` be removed entirely (L7).
2. **L7 (finish) `requests` → `httpx2`.** Migrate the 8 remaining files
   (`diagnosis`, `dyndns`, `caddy_admin`, `app_catalog`, `diagnosers/21-web`,
   `yunopaste`, `file_utils`, `resources`); drop `python3-requests` from
   `debian/control` and the fork deps.
3. **L10 aptitude → `python3-apt`.** Evaluate/migrate `utils/system.py`
   package operations; retain aptitude only if a dependency-solving behaviour
   genuinely requires it.
4. **L11 dead-path cleanup.** Remove the gevent branch in `utils/process.py`
   (already annotated legacy), moulinette references in `log.py`/`logging.py`,
   and the dead `authenticators/ldap_*` modules.
5. **L9 (optional).** Replace the vendored Meltdown checker with the
   `/sys/.../vulnerabilities` interface.

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
Phase 2  FastAPI/uvicorn both APIs + retire zmq    ⏳
Phase 3  Caddy ACME, requests→httpx2, python-apt,  ⏳
         dead-path cleanup
```

Phase 2 depends on Phase 1's pydantic v2 alignment. Phase 3's `requests`
removal depends on the `acme_tiny` replacement landing in the same change.
