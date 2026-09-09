# Extraction (roadmap stage 2)

The existing Nostr projects are treated as reference implementations and
implementation bases — not discarded prototypes. Their reusable cores are
being extracted into three canonical component libraries under `libs/`, while
the reference implementations (and the `_ynh` packages that ship them) remain
fully operational.

> "Initially preserve the current policy implementation. Do not introduce a
> new policy engine while restructuring the whole system." — roadmap §2.2

## Repos

| library | extracted from | reusable core | left behind (for now) |
|---|---|---|---|
| `imattau/nostrhost-auth` | `imattau/yunohost-nostr-auth` | `auth` (challenge, NIP-01/42 verify), `identity` (npub, mappings, relays, relay cache), `nip05`, `web` (login/account/admin pages + JS) | `ynh/` (session minting, portal client/cookie, LDAP), `server.py`, `admin_cli.py`, `auth/login.py`, `identity/linking.py` — re-homed once native identity API + session creation land (stages 3–5) |
| `imattau/nostrhost-policy` | `imattau/yunohost-mcp` | `policy` (roles, scopes, rules, confirmation, locks, package sessions), `auth` (identity, NIP-98, nostr, npub, replay, owner, delegation, signing, revocation, groups, server identity), `audit`, `redaction` | MCP transport glue: `policy/enforcement.py`'s `translate_known_errors` (MCP `ToolError`), `auth/middleware.py`, `auth/nostr_auth*_lookup.py`, `yunohost/adapter.py`, broker/concord layers — re-homed once the native service layer consumes this library (stage 11) |
| `imattau/nostrhost-catalog` | `imattau/nostr-yunohost` | `internal/` `protocol`, `verification`, `relay`, `publisher`, `curation`, `repository`, `trust`, `ciresult` (Go) | daemon state + CLI: `internal/catalog`, `attestation`, `localstate`, `announce`, `reverify`, `cmd/*` — re-homed once the fork's native catalogue provider lands (stage 9) |

## Migration model

Extraction is copy-then-rewire, deliberately duplicating code during the
transition so nothing breaks:

1. **Extract (this stage):** reusable cores copied into the libraries with
   their reference test suites adapted (import prefixes re-prefixed from
   `yunohost_nostr_auth`/`yunohost_mcp`/`github.com/imattau/nostr-yunohost`).
   Each library is self-contained, framework-free, and test-green on its own:
   - `nostrhost-auth`: 51 pytest
   - `nostrhost-policy`: 167 pytest
   - `nostrhost-catalog`: `go build` + `go test ./...` across 8 packages
2. **Rewire (later stages):** consumers (fork's identityd/policy/catalogue
   provider, and ultimately the reference implementations) depend on the
   libraries and their local copies are deleted. The roadmap's stage 11
   ("Make MCP a Native Interface") and stage 9 (native catalogue) are the
   natural rewiring points.
3. **Retire:** transitional `_ynh` packages (roadmap §13) are retired only
   once their functionality exists natively.

## What "reference remains operational" means

- `yunohost-nostr-auth`, `yunohost-mcp` and `nostr-yunohost` are untouched by
  this stage — no behaviour change, no deleted files.
- The `nostr_auth_ynh`, `yunohost-mcp_ynh` and `nostr_catalog_ynh` packages
  keep shipping the reference implementations for stock YunoHost.

## Deviations from the roadmap's names

The roadmap proposed `nostr-yunohost-auth` / `-policy` / `-catalog`. These
were renamed to `nostrhost-*` to match the umbrella brand and avoid
collision with the existing `imattau/nostr-yunohost` catalogue repo.