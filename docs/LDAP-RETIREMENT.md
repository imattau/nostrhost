# LDAP retirement (roadmap §25)

This document tracks the work to fully remove LDAP from NostrHost. It is the
working inventory and phase plan called for by roadmap §25:

> With SSOwat gone, LDAP's purpose is shrinking. Do not rip it out
> immediately; first inventory what genuinely still needs it.

**No legacy-app compatibility provider is being kept.** LDAP is retired
outright, not demoted to an opt-in service — there is no requirement to
support YunoHost apps still built on the traditional `ynh_permission_*`/LDAP
packaging model. Any such app is out of scope for NostrHost going forward.

Scope note: LDAP (`slapd`, `python-ldap`) lives in the `yunohost` core fork
(`imattau/nostrhost-yunohost`, checked out at `forks/yunohost`), not in this
umbrella repo. This document is the cross-repo plan; the actual package
removal/config changes land as commits in that fork once each dependency
below is migrated. It follows the same pattern as `docs/MAIL-RETIREMENT.md`.

## Correction (2026-09-13): LDAP is already out of the auth path

An earlier draft of this document assumed LDAP was still an active
*authentication* mechanism — reachable via moulinette's `Authenticator`
framework — and planned a "Phase 1: build a Nostr-backed moulinette
authenticator" as the first step. Rechecking the actual code shows that
premise was wrong in a way that **simplifies** the remaining work:

- `forks/yunohost/src/__init__.py` states outright: *"The legacy YunoHost
  framework entry points (`cli` / `api` / `portalapi` via moulinette) have
  been retired: the native administration surface is the `nostrhost` CLI and
  the `nostr-api` HTTP API."* `moulinette` is not a dependency in
  `debian/control` at all anymore.
- `_authenticate_credentials()` — the actual LDAP-bind/password-check logic
  in `src/authenticators/ldap_admin.py` and `ldap_ynhuser.py` — had **zero
  callers anywhere in the repo**. Nothing invokes
  `Authenticator().authenticate_credentials()`/`._authenticate_credentials()`
  any more; it was dead code left over from the pre-native framework.
  **Removed** in this pass (see below).
- `share/actionsmap.yml` / `share/actionsmap-portal.yml` (the moulinette
  config that used to wire `api: ldap_admin` / `api: ldap_ynhuser` into the
  HTTP layer) were **not read by anything** — no systemd unit, no packaging
  reference. **Deleted** in this pass.
- The real, live admin/API auth today is already Nostr-native:
  `forks/yunohost/src/nostrhost/api.py` is a from-scratch Bottle app
  ("Moulinette API replacement, Stage 5") authenticated with **NIP-98**
  (signed `Authorization: Nostr <event>` headers, no passwords at all), and
  `forks/admin/app/src/api/nativePackages.ts` already signs every request
  with a NIP-07 browser extension against it. Portal end-user login already
  has a passwordless Nostr challenge/response path
  (`forks/yunohost/src/nostr_login.py`, kind-22242 challenge/response via
  `nostrhost_auth`).
- What the two `Authenticator` classes still legitimately do — and why they
  weren't deleted outright — is **session-cookie management**
  (`set_session_cookie`/`get_session_cookie`/`delete_session_cookie`), which
  is plain JWT+cookie code with no LDAP in it, and is actively imported by
  `nostr_login.py`, `nostr_account.py`, `nostr_oidc.py`, `portal.py`,
  `user.py`, `log.py`. `ldap_ynhuser.py`'s `user_is_allowed_on_domain()` is
  also still live and still reads LDAP — but as a **permission-membership
  read**, not a credential check. That function is the real target of
  Phase 2 below (it's today's stand-in for the NIP-51 projection).

Net effect: there is no "build a CLI/API authenticator" phase left to do —
that surface is already Nostr-native. The remaining LDAP dependency is
narrower than previously scoped: LDAP as a **data store** for accounts,
groups and permission membership, plus the `slapd` infrastructure itself.

## Target model (roadmap §25, refined)

```text
Identity     = Nostr keypair (npub), verified by challenge/response or
               NIP-98 (nostrhost-auth: NIP-01 + BIP-340, NIP-07/NIP-46,
               passkey) — already the live mechanism for the native admin
               API, portal login, and MCP/broker access.
Groups /
permissions  = NIP-51 lists (kind 30000 follow sets / app-defined list
               kinds), signed by the owner or an authorized delegate —
               NOT YET BUILT. This replaces LDAP's remaining real job:
               backing `_sync_permissions_with_ldap()` /
               `user_is_allowed_on_domain()`.
Projection   = Nostr identity + NIP-51 membership
                 -> local Unix account/group projection (already mostly
                    true: nostr_identityd.py treats Nostr identity as
                    authoritative and LDAP as a derived fallback)
                 -> app permission projection (already the authd/JSON path
                    from the Caddy migration for request-time authz; the
                    LDAP sync that feeds it is what Phase 2 replaces)
LDAP         = removed. slapd, python-ldap, and the LDAP schema/hooks are
               deleted from core; no compatibility fallback.
```

## Why NIP-51 for groups

LDAP's `ou=permission` entries (`_sync_permissions_with_ldap`,
`forks/yunohost/src/permission.py:616`) and `user_is_allowed_on_domain`'s
admin-group/email-domain checks (`ldap_ynhuser.py`) are fundamentally
membership lists: "which principals may use which app/domain." NIP-51 lists
are a standard Nostr primitive for exactly this shape (a signed, replaceable,
addressable set of members/references), and the roadmap already commits to
primitive-first design (`docs/ROADMAP.md`, NIP-51 listed alongside
NIP-86/NIP-42/NIP-78 as in-scope primitives). Using NIP-51 instead of a
bespoke kind means:

- Group/permission membership is a signed Nostr event, auditable and
  replicable through the same relay infrastructure as identity events.
- Membership changes flow through the same "WHO changed it? -> Nostr" model
  the architecture already uses (`docs/ROADMAP.md` control/state layers).
- No new kind allocation needed for the common case; custom kinds stay
  reserved for genuine NostrHost-specific semantics per `NIP-MAPPING.md`.

## Dependency inventory

Classification per dependency:

- **Delete now** — confirmed dead code with zero callers; safe, no
  functional change.
- **Replace with Nostr-native equivalent** — still a real, load-bearing
  LDAP read/write; needs the NIP-51 projection or equivalent before removal.
- **Delete outright (infra)** — no remaining consumer once the above lands.

| # | Dependency | Where | Classification | Notes |
|---|---|---|---|---|
| 1 | Moulinette LDAP-bind credential check | `forks/yunohost/src/authenticators/ldap_admin.py`, `ldap_ynhuser.py` (`_authenticate_credentials`) | **Done — deleted** | Confirmed zero callers (moulinette itself is retired). Removed in this pass; the `Authenticator` classes remain for their still-live session-cookie methods. |
| 2 | Moulinette actionsmap config | `forks/yunohost/share/actionsmap.yml`, `share/actionsmap-portal.yml` | **Done — deleted** | Confirmed unread by anything (no systemd unit, no packaging reference); referenced `ldap_admin`/`ldap_ynhuser` as HTTP-layer authenticators for a framework that no longer runs. |
| 3 | Session-cookie management | `ldap_admin.py`, `ldap_ynhuser.py` (`set_session_cookie`/`get_session_cookie`/`delete_session_cookie`) | Retain — not LDAP | Plain JWT+cookie code, no LDAP inside it. Actively used by `nostr_login.py` and others. Out of scope for LDAP retirement; a future rename away from the `ldap_*` module names (now misleading) is cosmetic cleanup, not urgent. |
| 4 | Portal authorization read (`user_is_allowed_on_domain`) | `ldap_ynhuser.py:92-159` | ◑ admin-group LDAP read demoted; email-domain LDAP read remains | The admins-group check now tries `is_admin_user()` (native, no LDAP) first and only falls back to the LDAP `cn=admins,ou=groups` read for admins with no linked identity yet -- additive, same philosophy as row 6/the NIP-51 merge. The other LDAP read in this function (matching a user's email address to the domain) is untouched: it's a mail/account concept, not a membership-list concept NIP-51 fits, and mail is being retired separately (`docs/MAIL-RETIREMENT.md`) -- out of scope here. |
| 5 | Low-level LDAP client (`LDAPInterface`) | `forks/yunohost/src/utils/ldap.py` | Delete outright (infra) | Removable once rows 4, 6, 7 no longer call it. |
| 6 | App permission sync (`ou=permission`) | `forks/yunohost/src/permission.py:616` `_sync_permissions_with_ldap()`, called from lines 332, 453, 610 | Replace with NIP-51 projection, then delete | The authd JSON permission file used by Caddy `forward_auth` is sourced from this LDAP sync today. No NIP-51 projector code exists anywhere in the repo yet. Build the NIP-51-list -> permission-projection path first, cut it over as the only writer, then delete `_sync_permissions_with_ldap()` and its call sites. |
| 7 | User/group CRUD (Unix account store) | `forks/yunohost/src/user.py` | Mostly done — LDAP already secondary | `nostr_identityd.py` already treats the kind-31102 identity event as authoritative and materializes it into the native `nostrhost_auth.identity.mappings` projection store; the LDAP/Unix account (`YnhAccountBackend.ensure_user`) is only created as a *derived* compatibility artifact when a not-yet-existing username is named (`handle_identity_event`, lines 86–156). Remaining work is `user.py`'s own direct CRUD surface. |
| 8 | LDAPS certificate reload (`slapd`) | `forks/yunohost/src/nostr_certd.py`, `docs/CADDY-MIGRATION.md:118-135` | Delete outright (infra) | No `slapd` process to reload once it's uninstalled; remove the reload logic. |
| 9 | LDAP schema/config | `forks/yunohost/conf/slapd/*.ldif`, `conf/slapd/ldap.conf`, `conf/yunohost/services.yml` (registers `slapd` service) | Delete outright (infra) | Remove the schema/config and drop the `slapd` service registration. `python3-ldap`/`slapd` are still hard `Depends:` in `debian/control` today. |
| 10 | Mail stack LDAP lookups | `forks/yunohost/conf/dovecot/dovecot-ldap.conf`, `conf/postfix/plain/ldap-*.cf` | Delete outright | Subsumed by mail retirement (`docs/MAIL-RETIREMENT.md`); Postfix/Dovecot are already dropped from core's `Depends:`, so this config has no consumer already — verify and delete the leftover files. |
| 11 | Backup/restore hooks | `forks/yunohost/hooks/backup/05-conf_ldap`, `hooks/restore/05-conf_ldap` | Delete outright (infra) | No LDAP state to back up once `slapd` is gone. |
| 12 | Migrations referencing LDAP structure | `forks/yunohost/src/migrations/0027_migrate_to_bookworm.py`, `0028_delete_legacy_xmpp_permission.py`, `0033_rework_permission_infos.py` | Retain (historical) | Migration history for pre-existing installs; not touched. A final migration should be added to clean up any residual LDAP state on upgrade (see Phase 5). |
| 13 | `yunohost-mcp` user/permission tools | `libs/yunohost-mcp/src/yunohost_mcp/yunohost/adapter.py` (`user_create`, `user_permission_*`, `domain_list`) | No change required directly | Thin proxy over fork code; inherits whatever rows 4/6/7 land on. `broker/helper.py:415`'s "LDAPInterface authenticates the root connection through SASL-EXTERNAL" is the broker's *own* privileged connection to LDAP for writes it performs (a service-account bind), not caller auth — the broker's caller auth is already NIP-98/pubkey-based (`NostrAuthMiddleware`) and unaffected by this plan. |
| 14 | Policy engine irreversibility flag | `libs/nostrhost-policy/.../rules.py:194` (mirrored `forks/yunohost` `policy/rules.py:190`) | Update | Domain removal is flagged irreversible partly because it deletes an LDAP entry; domains are already LDAP-free by default (§W4), so update this rationale regardless of LDAP retirement timing. |
| 15 | Legacy moulinette-era test suite | `forks/yunohost/tests/test_ldapauth.py`, `test_sso_and_portalapi.py` (and others importing `moulinette`) | Flagged separately | These import `moulinette`, which is no longer a dependency — already uncollectable by pytest. Tracked as a standalone cleanup task, not part of this plan's phases. |

## Phased plan

Rows 1–2 (dead credential-check code and its unread config) are done as of
this revision. What's left is narrower than originally scoped:

1. **Phase 0 — Inventory (this document).** Done, kept up to date.
2. **Phase 1 — Delete dead moulinette auth code (done).** Removed
   `_authenticate_credentials` from `ldap_admin.py`/`ldap_ynhuser.py` (zero
   callers) and deleted `share/actionsmap.yml`/`actionsmap-portal.yml`
   (unread by anything). Session-cookie methods and `user_is_allowed_on_domain`
   were left untouched — they're still live and not part of this phase.
3. **Phase 2 — NIP-51 permission projection (◑ additive projector landed).**
   `nostrhost.nip51_permissions` defines the list shape (kind 30000, `d` tag
   = permission name, `p` tags = member pubkeys, optional `public` tag) and
   a `PermissionStore` + `merge_projection()` that unions NIP-51-resolved
   usernames into the existing projection; `nostr_permissiond` is the relay
   projector daemon (mirrors `nostr_identityd`'s structure), wired into
   `nostrhost.permissions.build_permissions_projection()` so every
   projection rebuild picks up NIP-51 grants automatically. **Deliberately
   additive**: it unions on top of the LDAP-sourced membership from
   `user_permission_list()`/row 6 and never removes access or unsets
   `public` — this is a safe, gradually-adoptable path, not the cutover
   itself. `nostrhost user permission grant-nostr <permission> <pubkey>...
   [--public]` / `clear-nostr <permission>` (CLI) publish the operator-signed
   kind-30000 event, mirroring `identity link`/`revoke`. `is_admin_user()`
   (native, no LDAP) now runs ahead of the LDAP admins-group read inside
   `user_is_allowed_on_domain()` (row 4) -- additive, same as the permission
   merge. Still open: (a) the *email-domain* LDAP read in the same function
   is untouched (a mail concept, not a membership one -- see row 4's note);
   (b) no Admin UI (web) exposes grant-nostr yet, CLI-only for now; (c) the
   actual cutover (stop writing/reading LDAP membership once grants have
   moved to NIP-51 in practice) is not done, by design, until NIP-51 is the
   primary path in real use.
4. **Phase 3 — Unix account store cleanup (mostly done already).** The
   identity projector already treats Nostr identity as authoritative and
   LDAP as a derived fallback (row 7); once Phase 2 lands, nothing needs
   that fallback to exist, so remove the LDAP compat-account write and any
   remaining direct LDAP CRUD in `user.py`.
5. **Phase 4 — Delete `slapd` and its config from core.** Remove
   `slapd`/`python-ldap` from core's dependency set entirely (not opt-in —
   deleted), drop the schema/config (row 9), the cert-reload logic (row 8),
   and the backup/restore hooks (row 11).
6. **Phase 5 — Cleanup migration + policy update.** Add a migration that
   removes any residual LDAP state (`slapd` data directory, stale service
   registration) from upgraded installs, and update the domain-removal
   irreversibility rationale (row 14).

## Status

| Phase | Status |
|---|---|
| 0 — Inventory | ✓ maintained (this document) |
| 1 — Delete dead moulinette auth code | ✓ done (this revision) |
| 2 — NIP-51 permission projection | ◑ additive projector + CLI authoring + native admin check landed (`nip51_permissions.py`, `nostr_permissiond`, `user permission grant-nostr`/`clear-nostr`, `is_admin_user()`); the email-domain LDAP read, Admin (web) UI, and actual LDAP cutover remain |
| 3 — Unix account store cleanup | ◑ mostly done — identity projector already treats LDAP as a derived fallback; remaining work is removing that fallback + `user.py`'s direct LDAP CRUD |
| 4 — Delete `slapd` and config | ⏳ not started |
| 5 — Cleanup migration + policy update | ⏳ not started |

## Non-goals

- This does not aim to preserve compatibility for YunoHost apps still built
  on the traditional `ynh_permission_*`/LDAP packaging model — such apps
  are out of scope for NostrHost; there is no fallback LDAP service to
  install afterward.
- No change to `forks/yunohost`'s pinned baseline (`baseline/pins.yml`)
  happens here — the fork remains source-identical until the `derivative`
  flag is set, matching the pattern used for Caddy and mail retirement.
- SSOwat/web request-auth is already retired (`docs/CADDY-MIGRATION.md`),
  and moulinette's own CLI/API/portalapi framework is already retired
  (see the correction above); this document does not revisit that work,
  only LDAP's remaining role as a data store.
- Choosing NIP-51 for group/permission membership does not preclude a
  custom kind later if NIP-51's list semantics prove insufficient for a
  specific permission shape — see `NIP-MAPPING.md` before allocating one.
