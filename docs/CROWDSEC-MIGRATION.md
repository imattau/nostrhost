# fail2ban → CrowdSec Migration Plan

Status: proposed. Branch: `feat/fail2ban2crowdsec` (base `main`).

Replace fail2ban with CrowdSec as NostrHost's host intrusion-protection layer,
keeping **nftables** as the enforcement backend (roadmap §18.4 — nftables is
not up for replacement, only the detection/decision layer above it). This is
the implementation of roadmap §18.4/§18.7 ("evaluate CrowdSec against
fail2ban" → "adopt winner with nftables backend"), tied into the security
event integration required by §18.5.

This document is the cutover map for that work. It complements
[RESOURCE-ENGINE-CUTOVER.md](RESOURCE-ENGINE-CUTOVER.md) (legacy lifecycle
removal), [LEGACY-INVENTORY.md](LEGACY-INVENTORY.md) (package cutover
status), and [CADDY-MIGRATION.md](CADDY-MIGRATION.md) §5 P5 (which currently
lists fail2ban replacement as an open fork of that plan — this document is
the canonical one; CADDY-MIGRATION.md P5 should link here once this lands).

## 1. Locked decisions

| Decision | Choice | Consequence |
|---|---|---|
| Enforcement backend | nftables (unchanged) | Roadmap §18.4 explicitly retains nftables; only the detection/decision layer changes |
| Decision engine | CrowdSec (`crowdsec` daemon, local API only) | fail2ban's per-jail regex+ban loop is replaced by CrowdSec's parser/scenario/decision pipeline |
| Enforcement mechanism | `crowdsec-firewall-bouncer` (nftables mode) | Bouncer owns a dedicated nftables set (`crowdsec-blacklists`); does not touch YunoHost's `inet filter` table (`conf/nftables/nftables.conf`) |
| Threat intelligence | **Local scenarios only by default**; CAPI (Central API / community blocklist) is opt-in, off until evaluated | Roadmap §18.4 flags "external threat-intelligence dependency" and "privacy implications" as evaluation criteria; default install must not phone home without consent |
| Gate before cutover | Evaluation report against roadmap §18.4 criteria, run in parallel with fail2ban still enforcing | Matches the "conditional, not mandatory" framing in §18.4 — this plan produces the evidence, then a go/no-go decision, not an unconditional rip-out |
| Plan location | `docs/CROWDSEC-MIGRATION.md` on `feat/fail2ban2crowdsec` | New branch off `main` |

## 2. What fail2ban owns today

| Concern | Current owner | Key locations |
|---|---|---|
| Jail definitions (sshd, postfix, sasl, dovecot, pam-generic, recidive) | `jail.conf` (upstream, vendored) + `jail.d/yunohost-jails.conf` | `forks/yunohost/conf/fail2ban/jail.conf`, `yunohost-jails.conf` |
| YunoHost-specific filters (API/portal login failures) | Custom regex filters | `forks/yunohost/conf/fail2ban/yunohost.conf`, `yunohost-portal.conf`, `postfix-sasl.conf` |
| Ban action | `nftables-multiport` / `nftables-allports` fail2ban actions | `jail.conf:208-212,369,825,835,901,976`; binds/reloads on nftables via `systemd-override-bind-nftables.conf` |
| Config regeneration | `regenconf` `fail2ban` category | `forks/yunohost/hooks/conf_regen/52-fail2ban`, `src/regenconf.py` |
| Setting-driven reconfig | `ssh_port` change → regen fail2ban + reload firewall | `src/settings.py:349-353` |
| Service health/status | `fail2ban-server --test`, `/var/log/fail2ban.log` | `conf/yunohost/services.yml:8-11`, `src/service.py` |
| App-packaging helper (legacy/v1+v2.1) | `ynh_config_add_fail2ban` / `ynh_config_remove_fail2ban` | `helpers/helpers.v1.d/fail2ban`, `helpers/helpers.v2.1.d/fail2ban` — used by essentially every `_ynh` app package that has an auth surface |
| Native resource engine | `PolicyResource(type: "fail2ban")`, `PolicyProvider` renders `jail.d/nostrhost-<name>.local` | `forks/yunohost/src/nostrhost/package_engine.py:335`, `native_providers.py:924-945` |
| Service readiness check | Waits on `nginx`/`fail2ban` service status before app operations | `forks/yunohost/src/utils/app_utils.py:1359` |
| Debian dependency | Hard dependency, min version pinned | `forks/yunohost/debian/control:26,49` |
| Backup/restore | No dedicated hook; fail2ban config is host state, not per-app backup data | (confirmed: no `hooks/backup|restore` reference — nothing to port) |

## 3. Target architecture

```text
journald + app/service logs (nginx today, Caddy once CADDY-MIGRATION lands)
      |
      v
crowdsec (LAPI, local only)
  acquis.yaml: journald sshd/postfix/dovecot/PAM units
             + file: /var/log/nginx/*.log (yunohost/yunohost-portal filters ported as parsers)
  parsers + scenarios (crowdsecurity/sshd, postfix, linux collections
             + custom nostrhost-yunohost-auth, nostrhost-portal-auth parsers)
      |
      v
  decisions (local API, sqlite by default)
      |
      v
crowdsec-firewall-bouncer (nftables mode)
      |
      v
nftables set crowdsec-blacklists  ← referenced from `inet filter / input`
             (existing YunoHost nftables table is NOT replaced, only extended)
      |
      v
security projector (roadmap §18.5) → local Nostr relay → audit + admin npub notification
```

CrowdSec's own **CAPI / community blocklist** is a separate, explicitly
opt-in decision stream feeding the same LAPI; it must default OFF (see §1)
and be surfaced as a NostrHost setting, not silently enabled by the
`crowdsecurity/*` collections.

## 4. Component disposition

| Component | Action |
|---|---|
| `forks/yunohost/conf/fail2ban/*` | **Retire** once cutover completes; content ported to CrowdSec `acquis.yaml` + parsers/scenarios below |
| `yunohost.conf` / `yunohost-portal.conf` filters | **Port** to custom CrowdSec parsers (`nostrhost-yunohost-auth.yaml`, `nostrhost-portal-auth.yaml`) — same failregex logic, YAML parser DSL instead of fail2ban's filter format |
| `postfix-sasl.conf` | **Port**; likely covered by `crowdsecurity/postfix` collection, verify SASL variant is included or needs a local parser override |
| `hooks/conf_regen/52-fail2ban` | **Replace** with `hooks/conf_regen/52-crowdsec` rendering `acquis.yaml`, local parsers/scenarios, and bouncer config |
| `conf/fail2ban/systemd-override-bind-nftables.conf` | **Replace**: `crowdsec-firewall-bouncer` ships its own nftables binding; verify ordering against `nftables.service` the same way |
| `src/settings.py:349-353` (`reconfigure_ssh_and_fail2ban`) | **Rename/rework** to regen CrowdSec's sshd acquisition (port is read from journald unit, not a jail `port=` field — likely simplifies, may become a no-op) |
| `conf/yunohost/services.yml` fail2ban entry | **Replace** with `crowdsec` (`cscli version`/`systemctl status crowdsec` as `test_conf` equivalent — CrowdSec has no config-syntax-check CLI equivalent to `fail2ban-server --test`; use `cscli hub list` sanity or a wrapper) |
| `helpers/helpers.v1.d/fail2ban`, `helpers.v2.1.d/fail2ban` | **Compatibility shim, not removal**: keep `ynh_config_add_fail2ban`/`ynh_config_remove_fail2ban` helper *names* (app packages call them unconditionally), reimplement internals to emit a CrowdSec parser+scenario pair instead of a fail2ban jail/filter. This is the highest-blast-radius item — see §7 Risk 1 |
| `src/nostrhost/package_engine.py:335` `PolicyResource.type` | **Extend**: `Literal["fail2ban", "crowdsec", "logrotate"]` during transition, then drop `"fail2ban"` once no native package declares it |
| `src/nostrhost/native_providers.py:924-945` `PolicyProvider` | **Extend** `directories` map with a `crowdsec` entry (parsers/scenarios under `/etc/crowdsec/{parsers,scenarios}/nostrhost-<name>.yaml`, no `.local` suffix convention needed) |
| `src/utils/app_utils.py:1359` service-wait list | **Update**: `["nginx", "crowdsec"]` (and later `["caddy", "crowdsec"]` post CADDY-MIGRATION) |
| `debian/control:26,49` | **Replace** `fail2ban` dependency with `crowdsec`, `crowdsec-firewall-bouncer` |
| `docs/NOTIFICATION-SERVICE.md`, `docs/ROADMAP.md` §18.5 | **Update** "fail2ban/CrowdSec → structured event" language once CrowdSec is the sole source; wire the security projector to CrowdSec's decision/alert API (`cscli alerts list -o json` or LAPI websocket) instead of fail2ban's log/`fail2ban-client` polling |

## 5. Phased plan

fail2ban keeps enforcing (both may run in parallel from P2 onward; CrowdSec
runs in **detect-only** mode — no bouncer — until P4's gate passes) until the
Phase 4 gate. This mirrors CADDY-MIGRATION's "old system keeps serving until
its phase gate" pattern.

### P0 — Evaluation spike (the roadmap §18.4 gate)
- Create `feat/fail2ban2crowdsec`.
- Install CrowdSec + `crowdsec-firewall-bouncer` on the VM testbed alongside
  the existing fail2ban, CrowdSec in detect-only mode (no bouncer enabled,
  or bouncer pointed at a throwaway nftables set).
- Enable `crowdsecurity/sshd`, `crowdsecurity/linux`, `crowdsecurity/postfix`
  collections; leave CAPI/community blocklist disabled.
- Measure against every roadmap §18.4 criterion: idle memory/CPU footprint,
  package/dependency footprint (crowdsec ships a Go binary + local SQLite;
  compare install size to fail2ban+python-systemd), offline behaviour with
  CAPI disabled, false-positive rate on the existing jail set over a
  representative log sample, IPv4/IPv6 parity, nftables integration
  cleanliness (separate set vs. touching `inet filter`), upgrade/maintenance
  burden (hub update cadence for collections/parsers).
- Gate: written evaluation report committed to this doc (§8) with an
  explicit go/no-go. **If CrowdSec does not materially improve the model,
  stop here and close this branch without merging** — per roadmap §18.4,
  adoption is conditional.

### P1 — Parser parity
- Port `yunohost.conf` and `yunohost-portal.conf` fail2ban filters to
  CrowdSec parsers (`nostrhost-yunohost-auth.yaml`,
  `nostrhost-portal-auth.yaml`), same failregex semantics, YAML parser DSL.
- Port `postfix-sasl.conf`; confirm/extend the `crowdsecurity/postfix`
  collection covers SASL auth failures the same way.
- Write scenarios mirroring current jail `maxretry`/`findtime`/`bantime`
  values (`yunohost-portal` at `maxretry=20`, `recidive` behaviour, etc.).
- Gate: `cscli explain` / replay against captured fail2ban-triggering log
  samples reproduces the same detections (same or better precision).

### P2 — acquis.yaml + regenconf
- Write `hooks/conf_regen/52-crowdsec`: renders `acquis.yaml` (journald units
  for sshd/postfix/dovecot/PAM + file acquisition for nginx logs, matching
  today's `logpath` entries), installs the local parsers/scenarios from P1,
  reloads `crowdsec`.
- Wire `settings.py` (`ssh_port` post-change hook) to regen the relevant
  acquisition, not the whole jail set.
- CrowdSec still runs detect-only (no bouncer); compare its decisions log
  against fail2ban's actual bans over a soak period.
- Gate: decisions generated by CrowdSec for real traffic match fail2ban bans
  for the soak period, with an acceptable (documented) false-positive delta.

### P3 — App-packaging helper compatibility shim
- Reimplement `ynh_config_add_fail2ban`/`ynh_config_remove_fail2ban`
  (`helpers.v1.d/fail2ban`, `helpers.v2.1.d/fail2ban`) to emit a CrowdSec
  parser+scenario pair from the same `--logpath`/`--failregex` arguments (or
  the app-provided `f2b_jail.conf`/`f2b_filter.conf` templates), instead of a
  fail2ban jail/filter. **Helper names and call signature stay unchanged** —
  every existing `_ynh` app install script calls these helpers and must not
  need modification.
- Extend `PolicyResource.type` (`package_engine.py:335`) with `"crowdsec"`
  and the corresponding `PolicyProvider.directories` entry
  (`native_providers.py:924`) for native packages.
- Gate: a representative sample of existing `_ynh` apps (pick 3-5 with
  fail2ban jails, e.g. from this workspace's `*_ynh` packages) install/reload
  cleanly and produce a working CrowdSec scenario with zero changes to their
  install scripts.

### P4 — Bouncer cutover
- Enable `crowdsec-firewall-bouncer` for real, owning its own nftables set
  (`crowdsec-blacklists`) referenced from the existing `inet filter / input`
  chain (`conf/nftables/nftables.d/yunohost-firewall.tpl.conf`) — additive,
  not a replacement of YunoHost's firewall management.
  `firewall_reload`/`firewall_list` (`src/firewall.py`) must keep working
  unmodified; the bouncer set is orthogonal to the port-based rules YunoHost
  manages.
- Disable fail2ban's `nftables-*` ban actions (or stop the fail2ban service
  entirely) once the bouncer is confirmed enforcing.
- `conf/yunohost/services.yml`: add `crowdsec` (and `crowdsec-firewall-bouncer`
  if run as a separate unit) with a working `test_conf` equivalent.
- Gate: a live ban test (deliberate repeated auth failure from a test source)
  is blocked by nftables via the CrowdSec path with fail2ban's ban action
  disabled; `yunohost diagnosis` clean.

### P5 — Security event integration (roadmap §18.5)
- Security projector consumes CrowdSec alerts/decisions (LAPI, not log
  scraping) and emits structured audit events + admin npub notifications per
  §18.5's pipeline, matching `docs/NOTIFICATION-SERVICE.md`'s existing
  "security event" row.
- Record CrowdSec config (collections enabled, CAPI opt-in state, bantime
  policy) under `state/security/intrusion-protection.toml` per roadmap
  §18.6; no credentials/keys in ngit.
- Gate: a triggered ban produces an audit event and (if configured) an
  encrypted Nostr notification to the admin npub.

### P6 — Retire fail2ban
- Stop/disable/remove the fail2ban service and package.
- Remove `forks/yunohost/conf/fail2ban/`, `hooks/conf_regen/52-fail2ban`,
  the `fail2ban` entry from `services.yml`, `debian/control` dependency, and
  the now-dead `PolicyResource.type` literal `"fail2ban"` (only after
  confirming no shipped/native package still declares it).
- Update `src/utils/app_utils.py:1359` service-wait list.
- Update tests referencing fail2ban (`test_regenconf.py`, `test_service.py`,
  `test_settings.py` if `reconfigure_ssh_and_fail2ban` is renamed).
- Gate: `scripts/verify-clean.sh` green, VM e2e passes with fail2ban absent
  from the system.

### P7 — Docs
- Update `docs/ROADMAP.md` §18.4/§18.7/§18.8 milestone checkboxes with the
  evaluation outcome and adoption status.
- Update `docs/NOTIFICATION-SERVICE.md` security-event row to name CrowdSec
  specifically (drop the "fail2ban/CrowdSec" either-or framing).
- Cross-link from `docs/CADDY-MIGRATION.md` §5 P5 to this document (that
  plan's fail2ban-replacement line becomes "see CROWDSEC-MIGRATION.md";
  Caddy's log format change in P5 of that plan must be reflected in this
  plan's P1 parser work if the two land out of order — whichever lands
  second updates its log-acquisition config to match the other's actual
  format, nginx or Caddy).

## 6. New artifacts

| Artifact | Purpose |
|---|---|
| `forks/yunohost/conf/crowdsec/acquis.yaml.tpl` | Log/journald acquisition template (rendered by the regen hook) |
| `forks/yunohost/conf/crowdsec/parsers/nostrhost-yunohost-auth.yaml` | Port of `yunohost.conf` filter |
| `forks/yunohost/conf/crowdsec/parsers/nostrhost-portal-auth.yaml` | Port of `yunohost-portal.conf` filter |
| `forks/yunohost/conf/crowdsec/scenarios/*.yaml` | Port of jail `maxretry`/`findtime`/`bantime` semantics |
| `forks/yunohost/hooks/conf_regen/52-crowdsec` | CrowdSec regen category (replaces `52-fail2ban`) |
| `helpers/helpers.v1.d/fail2ban`, `helpers.v2.1.d/fail2ban` (modified in place) | Same public helper API, CrowdSec-backed implementation |
| `forks/yunohost/tests_nostr/test_crowdsec_*.py` | Provider/parser/regen tests, mirroring the resource-engine test conventions |
| `state/security/intrusion-protection.toml` | Semantic-state record of CrowdSec policy (roadmap §18.6) |

## 7. Risks

1. **App-packaging helper compatibility is the highest-blast-radius item.**
   Every `_ynh` app package with an auth surface calls
   `ynh_config_add_fail2ban` unmodified; the reimplementation must accept the
   exact same `--logpath`/`--failregex` arguments and `f2b_jail.conf`/
   `f2b_filter.conf` template convention, or every such app breaks on next
   install/upgrade. Test against real packages in this workspace (`*_ynh`
   dirs), not just synthetic fixtures.
2. **CrowdSec's decision store and fail2ban's ban table are not the same
   thing.** During the P2-P3 parallel-run window, both engines may generate
   independent state referencing the same source IPs; the cutover in P4 must
   not double-ban or leave a gap where neither engine's rule is active for a
   given IP.
3. **CAPI / community blocklist opt-in must not become opt-out by accident.**
   `crowdsecurity/*` collection installs via `cscli hub install` do not
   themselves push decisions to CAPI, but enabling the `crowdsecurity/capi`
   bouncer/notification integrations does — the regen hook and any admin UI
   toggle must make this an explicit, off-by-default setting per §1.
4. **nftables set collision.** The bouncer must own a set that YunoHost's
   `firewall_reload`/`nftables` regenconf category never clobbers on
   reload; verify `conf/nftables/nftables.conf`'s `include
   "/etc/nftables.d/*.conf"` ordering doesn't race the bouncer's own file.
5. **Log-format dependency on CADDY-MIGRATION.** The `yunohost`/
   `yunohost-portal` parsers currently target nginx's log format
   (`/var/log/nginx/*.log`). If `CADDY-MIGRATION.md` lands first, P1's
   parsers must target Caddy's log format/path instead; if this plan lands
   first, Caddy's migration must update the acquisition path when nginx is
   retired. These two branches should not both assume nginx logs
   indefinitely.
6. **No `fail2ban-server --test` equivalent.** `services.yml`'s `test_conf`
   check has no direct CrowdSec analogue (`cscli` validates the hub, not a
   rendered acquisition/parser set end-to-end); P4 needs a concrete decision
   on what health check substitutes for it, not a silent drop of the check.
7. **Evaluation may return "no."** Per roadmap §18.4 this adoption is
   conditional; P0's gate can legitimately end the effort. Do not treat
   later phases as committed work before P0's report lands.

## 8. Evaluation report (filled in during P0)

*(Not yet started — this section is populated with the go/no-go decision and
supporting measurements once the P0 spike runs.)*
