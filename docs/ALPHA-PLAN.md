# Alpha Execution Plan — "make it a product"

> **Plan and status are consolidated in `ROADMAP.md` (§ "Alpha Execution
> Plan"). This document is the working detail — workstream acceptance criteria,
> sequencing and the later-phase scope.**

Status: current plan (2026-09-12). Scope agreed: **docs + python-deps distribution +
native bootstrap + end-to-end native app lifecycle** as the near-term path to the
0.1 alpha. LDAP demotion (§25) and native DNS + secrets (§26/§27) are the later phase.

The threshold this plan targets:

```text
Fresh Debian 12 VM
   ↓
install NostrHost APT repo
   ↓
apt install nostrhost
   ↓
nostrhost postinstall --new | --restore
   ↓
Nostr owner login
   ↓
Admin works
   ↓
install native app
   ↓
app works over HTTPS
   ↓
backup
   ↓
upgrade
   ↓
deliberately break it
   ↓
restore/rollback
```

If that works repeatedly from a blank VM, NostrHost 0.1 alpha is real, even with
LDAP and some YunoHost compatibility code still underneath.

---

## Workstream 0 — Documentation truth

Target: the top-level docs describe what actually exists (Caddy, CrowdSec,
native package engine, ngit/Restic state, renamed `nostrhost-core`, native apt
packaging) instead of the nginx/SSOwat/source-identical Stage-1 baseline.

- Rewrite `README.md` (architecture, layout without `ssowat`, packaging/,
  core rename, PyPI-deps note).
- Rewrite `docs/BASELINE.md` (derivative baseline, pins table without
  ssowat/moulinette, `yunohost` → `nostrhost-core`).
- Sweep `.github/workflows/baseline.yml`, `scripts/verify-clean.sh`,
  `scripts/pin-forks.sh` for stale ssowat/moulinette/source-identity references.
- Verify `docs/ROADMAP.md` §1–52 objective is current.

Acceptance: no stale nginx/SSOwat/"source-identical"/moulinette claims in
top-level docs.

---

## Workstream 1 — `nostrhost-runtime` deb (private venv, bundled wheels)

Problem: `nostr-sdk`, `pydantic>=2` are not in Debian
bookworm (pydantic ships v1 there) and are currently PyPI-provisioned globally.
That is the weakest distribution-quality point.

Target: reproducible, pip-free installs. A `nostrhost-runtime` deb:

- Bundles pinned wheels (`pip download --only-binary=:all:
  --platform manylinux_2_17_x86_64 --python-version 3.11` of a pinned
  requirements file) staged at `/usr/share/nostrhost/wheels`.
- postinst: creates `/opt/nostrhost/venv` with `--system-site-packages` (sees
  the dist-packages debs: `yunohost`, `nostrhost`, `nostrhost_auth`,
  `nostrhost_policy`, typer, bottle), then
  `pip install --no-index --find-links=/usr/share/nostrhost/wheels ...`.
- Daemons/units (`nostr-identityd`, `nostr-operationsd`, `nostr-securityd`,
  `nostr-api`) run on `/opt/nostrhost/venv/bin/python`.
- `nostrhost-core-system` / `nostrhost-core` Depends on `nostrhost-runtime`.

Acceptance: blank VM `apt install nostrhost` → no manual `pip`; the venv
interpreter imports `nostr_sdk`, `pydantic`; CI builds
the wheels-deb.

---

## Workstream 2 — Native bootstrap / postinstall (§19)

Target: `apt install nostrhost` → `nostrhost postinstall --new|--restore` → READY.

1. **Systemd wiring**
   - Add `libs/nostrhost-control/deploy/nostrhost-control.service` (the
     control-relay unit `packaging/packages.yml` already declares but the
     submodule does not ship).
   - Add fork units `conf/yunohost/nostr-{identityd,operationsd,securityd,api}.service`
     + `services.yml` entries; copy+enable via postinst / `01-yunohost` hook.
2. **`nostrhost postinstall --new`** (Typer, `cli.py`)
   - Refactor `bin/nostrhost-bootstrap` key-gen into a callable.
   - Write `/etc/nostrhost/operator.toml` + `policy.toml` (owner npub + initial
     capability grants).
   - Ensure control relay running; Caddy base config; `current_host`/domain/
     network; portal/admin access; **state S0** (`export_state` → git init);
     touch `/etc/yunohost/installed`.
3. **`nostrhost postinstall --restore`** — authorise/restore server identity →
   discover state repo (kind 30617) → clone ngit state → restore known-good +
   linked Restic snapshot → reconcile → validate (§7.6 / §15).
4. Retire/bypass the legacy `tools_postinstall` path; a fresh install no longer
   depends on the interactive admin/password flow.

Acceptance: blank VM → `postinstall --new` → `nostrhost identity list`, relay
up, `policy.toml` present, daemons running, `nostrhost system version` + API
respond.

---

## Workstream 3 — End-to-end native app lifecycle (§21)

1. **`app install <coordinate>`** (`cli.py`): catalogue coordinate
   (`native_catalog_coordinate`) → fetch/verify `package.toml`
   (`manifest_sha256`) → `plan_package` → `apply_reconciled_plan` through the
   signed request → policy → approval chain; Caddy route, permissions, health,
   Restic pre/post state, admin result.
2. **Native `app remove`** via `plan_package_removal`; **`app upgrade`**
   planner (diff installed vs new manifest, conservative data-preserving
   re-apply); minimal `change_url` (Caddy route update).
3. **Backup/restore linkage**: `BackupProvider` registration → Restic snapshot
   + state on install/reconcile; native `app backup/restore` via restic + state.
4. **Proof**: full signed loop on `nostrhost-test`, then port **one real app**
   to `package.toml` and repeat.

Acceptance: the §21 vertical loop works signed end-to-end on the VM for both
apps; fork suite stays green (348 + new), flake8/mypy clean.

---

## Sequencing

```text
W0 docs → W1 runtime deb (+CI) → W2 bootstrap (needs W1 interpreters + units)
→ W3 app lifecycle (needs a ready node)
```

Each workstream ends green on CI. Final gate is the alpha acceptance loop.

## Later phase (not in near-term scope)

- **§25 LDAP demotion**: native user/group store behind `user.py`/`domain.py`/
  `permission.py`, optional `LDAPInterface`, native authenticator replacing LDAP
  `simple_bind`, slapd/nslcd/nsswitch hooks → optional package, LDAP `Depends`
  stack demoted to Recommends/Suggests.
- **§26/§27 Native DNS + secrets**: `DnsResource` + provider adapters
  (cloudflare/deSEC/duckdns/manual) behind the capability model; SecretBroker
  consolidation (systemd credentials store; DNS/app credentials out of
  plaintext YAML).
