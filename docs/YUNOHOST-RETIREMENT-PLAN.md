# YunoHost retirement plan (roadmap §21–§24, cross-cutting)

This document tracks the work to fully remove YunoHost-derived machinery from
NostrHost and make the native package system (`package.toml` +
`package_engine.py` + npack/npk distribution) the sole mechanism for app
packaging, installation and the app catalogue — with **no legacy-app
compatibility fallback**, matching the precedent already set by
`docs/LDAP-RETIREMENT.md` and `docs/MAIL-RETIREMENT.md`.

Scope note: most of NostrHost's own native code currently lives inside the
`forks/yunohost` fork alongside the inherited upstream YunoHost modules
(`app.py`, `domain.py`, `service.py`, `firewall.py`, `diagnosis.py`,
`regenconf.py`, `hook.py`, `dns.py`, `dyndns.py`, `ssh.py`, the Bash helper
library, and Debian packaging conventions). "Retiring YunoHost" in this
document means the inherited packaging/lifecycle/auth machinery specifically
— it does not mean deleting the fork or abandoning the Linux-management
subsystems the project has deliberately chosen to keep (see Non-goals).

**No legacy-app compatibility is being kept.** Apps that still rely on the
Bash-script `scripts/install`/`upgrade`/`remove`/`backup`/`restore` model are
out of scope going forward. Existing apps in that ecosystem are either
converted to native `package.toml` (by their publisher, in their own repo —
apps are not vendored inside this repo, only referenced from the catalogue by
git coordinate or signed npk release) or are not available.

## Target model

```text
Package format   = package.toml (declarative: app, runtime_instance, web,
                    permissions, health, backup, packages/apt, source,
                    database, config-file templating, hooks) — compiled and
                    reconciled by package_engine.py. Already proven
                    end-to-end on one real app (opencode-web_nh).

Distribution      = npk (signed tar+zstd artifact, kind-9900 release event,
                    depends/conflicts/requires/provides/post-install tags),
                    built via `nostrhost-package build-npk`, staged and
                    installed via `package.install` / `package.reconcile`.
                    General-purpose, already app-agnostic — not nsite-only.

Catalogue          = native Nostr catalogue (`catalog.list/get/publish/
                    verify`), git-repo + revision + package_path per entry
                    today. NOT YET carrying an npk coordinate per entry —
                    npk installs still require an operator to already know
                    the publisher/name/version coordinate.

Install/upgrade/
remove/backup      = package.plan / package.reconcile (bounded operations),
                    already the enforced path for any app whose catalogue
                    entry is source: nostr (app.py's
                    _reject_native_catalog_lifecycle hard-blocks the legacy
                    script path for these).

YunoHost machinery = retired outright once no live caller remains: Bash
                    helper library, app.py's script-execution path, the
                    legacy-catalogue fallback, SSOwat config generation,
                    mail conf_regen hooks + dovecot dependency.
```

## Why no compat fallback

Same rationale as LDAP retirement: keeping a legacy path "just in case" means
maintaining two install/catalogue mechanisms indefinitely, doubles the attack
surface (Bash scripts running as root vs. bounded, reconciled operations),
and blocks §24's boundary-shrink from ever reaching zero. The native format
is already expressive enough for real apps (apt deps, multi-runtime,
databases, config templating, arbitrary Python hooks for anything left over)
— the gap is tooling and catalogue breadth, not capability.

## Dependency inventory

Classification per item:

- **Already default / no change needed** — native path already wins by
  default where data exists; nothing to flip.
- **Delete (code)** — still executing; must be removed once no caller
  remains.
- **Build (new capability)** — doesn't exist yet; required for the cutover.
- **Kept by design** — explicitly retained per README/ROADMAP scope; not a
  retirement target of this plan.
- **Needs liveness check** — status unconfirmed; flagged for follow-up
  before classifying.

| # | Item | Where | Classification | Notes |
|---|---|---|---|---|
| 1 | Catalogue backend selection | `forks/yunohost/src/app_catalog.py:330` (`_load_apps_catalog`, `NOSTRHOST_CATALOG_BACKEND`, default `nostr`) | Already default | Native catalogue entries already win on ID collision; legacy YunoHost catalogue is only consulted when the native catalogue is empty. No dispatch change required. |
| 2 | Legacy app lifecycle guard | `forks/yunohost/src/app.py` `_reject_native_catalog_lifecycle` | Already default (for native apps) | Blocks legacy `app_install`/`upgrade`/`remove`/`change_url` from touching any `source: nostr` app. Only a guard — the code it guards still exists (row 3). |
| 3 | Legacy app lifecycle execution | `forks/yunohost/src/app.py` (2653 lines) — `app_install`/`app_upgrade`/`app_remove`/`app_change_url`, Bash `scripts/*` execution via `hook_exec_with_script_debug_if_failure` | **Delete (code)** | Live for any app not flagged native. Cannot be deleted until every installable app is native (row 8) and the legacy-catalogue fallback (row 1's fallback branch) is removed. |
| 4 | Bash helper library | `forks/yunohost/helpers/helpers.v2.1.d/` — 120 `ynh_*` functions, 25 files, 5276 lines | **Delete (code)**, tracked §22/§24 | Matches ROADMAP §24's "122 helpers" figure. Only callable from legacy install scripts (row 3); dies with it. |
| 5 | SSOwat config generation | `app.py:app_ssowatconf()`, called live from `domain.py`, `app.py`, `settings.py` | **Delete (code)** | Roadmap/README currently describe SSOwat as retired; the *auth* purpose is retired (Caddy `forward_auth` replaced it), but this generator still runs on every relevant write. Docs currently overstate completion here — correct the record when this is deleted. |
| 6 | Mail conf_regen hooks | `hooks/conf_regen/19-postfix`, `25-dovecot`, `30-opendkim` + `dovecot-core` hard dependency in `debian/control:43` | **Delete (code)**, tracked §18.7/§18.8 | Mail retirement is genuinely incomplete, not cosmetic — `dovecot-core` is still a hard install-time Debian dependency. |
| 7 | npk-in-catalogue | `nostr_catalog_provider.py` (git+revision+package_path only) vs `package.install`/`_safe_package_install_npk` (explicit coordinate only) | **Build (new capability)** | The two native mechanisms don't reference each other. Extend the catalogue entry schema to optionally carry an npk coordinate; extend `package.install` (or a catalogue-aware wrapper) to resolve straight from a catalogue hit instead of requiring a hand-supplied coordinate. |
| 8 | Catalogue population | No vendored production catalogue in this repo (only test fixtures: `test_app_catalog.py`, `test_nostr_catalog_provider.py`, `test_catalog_tools.py`) | **Build (external, by design)** | Apps are independently maintained and published into the catalogue via signed events, not vendored here — consistent with the project's own architecture. In-repo work is limited to rows 3–7 plus §22's migration tooling to help external publishers convert existing Bash-script apps; authorship itself is out of scope for this repo. |
| 9 | Migration analyser (Bash → declarative) | §22, unstarted. `package_engine.py:migrate_manifest_file()` exists but refuses any package with `scripts/install\|upgrade\|remove\|backup\|restore\|change_url\|config\|check_process\|diagnosis` present | **Build (new capability)** | Only migrates YunoHost apps already using the newer declarative `resources:` table with zero Bash — a narrow subset. Needs a Bash-AST analyser mapping common `ynh_*` helper calls (`ynh_setup_source`, `ynh_install_app_dependencies`, `ynh_mysql_setup_db`, `ynh_add_config`, `ynh_permission_create`, `useradd`) onto existing `package.toml` resource types, plus a `HookResource`-wrapped fallback for residual imperative logic. |
| 10 | Behavioural-equivalence gate | §23, unstarted (VM A/B comparison + confidence attestation) | **Build (new capability)** | Required before trusting any auto-converted package (row 9's output) enough to make it the only install path for that app. |
| 11 | Rollback provenance gap | ROADMAP §9 — "reverse steps for app reinstall/upgrade stay manual pending install-arg provenance" | **Needs liveness check** | Unclear whether this gap is itself YunoHost-shaped (tied to legacy install-arg tracking) or independent of this retirement. Verify before assuming it resolves automatically once row 3 is gone. |
| 12 | `certificate.py` | `forks/yunohost/src/certificate.py` (788 lines), called from `domain.py` and `nostrhost/native_ops.py` | **Needs liveness check** | Caddy already provides automatic TLS (§12 ✓); unconfirmed whether this module is dead or still load-bearing for manual/custom certificate upload. |
| 13 | `backup.py` | `forks/yunohost/src/backup.py` (2589 lines) | **Needs liveness check** | Native state + Restic (§7/§9) is the documented primary path; unconfirmed how much of this legacy module still executes vs. is dead. |
| 14 | `ldap_ynhuser.py` filename/class naming | `forks/yunohost/src/authenticators/ldap_ynhuser.py` (391 lines) | Cosmetic only, not a retirement target | Confirmed no `import ldap`/functional LDAP dependency (see `docs/LDAP-RETIREMENT.md`) — pure JWT/session logic under a stale name. Rename is optional cleanup, not part of this plan's phases. |
| 15 | `user.py` / `permission.py` YunoHost-era API shape | `forks/yunohost/src/user.py` (1745), `src/permission.py` (969) | Kept by design (API shape), underlying store already native | LDAP backend already replaced (§25 done); these modules are the surface wrapping the native projection, not a functional YunoHost dependency. Not a retirement target unless the API shape itself becomes a maintenance burden. |
| 16 | Domains, services, firewall, diagnosis, regenconf, hook, DNS/dynDNS, SSH, Debian packaging | `domain.py` (980), `service.py` (875), `firewall.py` (588), `diagnosis.py` (725), `regenconf.py` (732), `hook.py` (609), `dns.py` (1050), `dyndns.py` (530), `ssh.py` (207) — ~5800 lines total | **Kept by design** | README explicitly retains these as mature Linux-management functionality. Not a retirement target of this plan regardless of origin. |

## Phased plan

1. **Phase 0 — Inventory (this document).** Done, kept up to date. Rows 12
   and 13 (certificate/backup liveness) are open and should be resolved
   before Phase 3 finalizes scope.
2. **Phase 1 — Catalogue/npk unification (rows 7–8).** Extend the native
   catalogue schema to carry an optional npk coordinate; wire
   `package.install` to resolve directly from a catalogue hit. No change to
   existing dispatch precedence (row 1) — this only closes the gap between
   the two native mechanisms.
3. **Phase 2 — Migration tooling (rows 9–10).** Build the Bash-AST analyser
   and `HookResource`-fallback converter (§22), gated by the VM A/B
   behavioural-equivalence check (§23) before any converted package is
   trusted as someone's only install path. This is what unblocks external
   publishers converting real apps at scale — not in-repo app authorship.
4. **Phase 3 — Delete legacy execution paths (rows 3–6).** Once no
   catalogue entry can resolve to a non-native app (the legacy-catalogue
   fallback in row 1 is provably unreachable), delete `app.py`'s
   script-execution machinery, the Bash helper library, `app_ssowatconf()`,
   and the mail conf_regen hooks + `dovecot-core` dependency. Update
   README/ROADMAP language that currently overstates SSOwat/mail retirement
   as already complete.
5. **Phase 4 — Close open provenance gap (row 11).** Resolve whether
   install-arg provenance for rollback reverse-steps is YunoHost-shaped;
   fix or reclassify as independent of this plan.
6. **Phase 5 — Boundary-shrink verification (§24).** Confirm the tracked
   helper count (122 → ... → 0) actually reaches zero; update ROADMAP §24
   from "measurable shrink" framing to "done."

## Status

| Phase | Status |
|---|---|
| 0 — Inventory | ✓ this document (2026-09-23) |
| 1 — Catalogue/npk unification | ⏳ not started |
| 2 — Migration tooling (§22/§23) | ⏳ not started |
| 3 — Delete legacy execution paths | ⏳ not started (blocked on Phase 1–2) |
| 4 — Rollback provenance gap | ⏳ not started, unclassified |
| 5 — Boundary-shrink verification (§24) | ◑ tracked, count not yet at zero |

## Non-goals

- This does not aim to preserve compatibility for YunoHost apps still built
  on the traditional Bash-script packaging model. There is no fallback
  install path once Phase 3 lands.
- This does not touch the subsystems README/ROADMAP explicitly retain
  (domains, services, firewall, diagnosis, DNS, SSH, Debian packaging) —
  those are kept by design, independent of package/catalogue origin.
- This does not include authoring or converting third-party app packages
  in this repo — apps are independently maintained and published into the
  catalogue by their own publishers, matching the existing architecture
  (row 8). This plan's scope is the in-repo mechanism, not catalogue
  breadth.
- This does not revisit LDAP or mail retirement's own phase plans in detail
  — see `docs/LDAP-RETIREMENT.md` and `docs/MAIL-RETIREMENT.md` for those;
  this document only references the mail conf_regen hooks (row 6) insofar
  as they overlap with the YunoHost machinery being retired here.
