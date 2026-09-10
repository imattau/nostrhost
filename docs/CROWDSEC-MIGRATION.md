# fail2ban → CrowdSec Migration Plan

Status: proposed. Branch: `feat/fail2ban2crowdsec` (rebased onto `main`
after the nginx→Caddy migration merged — Caddy owns 80/443, nginx is retired).

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
| App-packaging integration | **Native-only.** CrowdSec is exposed exclusively as a `PolicyResource(type: "crowdsec")` in `package.toml`, reconciled by an extended `PolicyProvider`. No CrowdSec-backed Bash helper is written | Matches `RESOURCE-ENGINE-CUTOVER.md` §1: "[the helper tree] must not be a dependency of native providers." `ynh_config_add_fail2ban`/`ynh_config_remove_fail2ban` (`helpers.v1.d`/`v2.1.d`) are left untouched, stay fail2ban-only, and remain a legacy compatibility surface governed by that doc's existing removal gate — not extended into a second backend |
| Package source | CrowdSec daemon + bouncer from **CrowdSec's official apt repo** (current 1.x), with hub collections vendored into the image | Debian bookworm ships `crowdsec`/`crowdsec-firewall-bouncer` (bouncer `0.0.25-4~deb12u1`) but the daemon is the old 0.1.x-era line, which may not satisfy `crowdsecurity/*` collection requirements; vendoring also makes first-boot offline (hub downloads otherwise need network) |
| Plan location | `docs/CROWDSEC-MIGRATION.md` on `feat/fail2ban2crowdsec` | New branch off `main`, rebased after CADDY-MIGRATION merged |

## 2. What fail2ban owns today

| Concern | Current owner | Key locations |
|---|---|---|
| Jail definitions (sshd, postfix, sasl, dovecot, pam-generic, recidive) | `jail.conf` (upstream, vendored) + `jail.d/yunohost-jails.conf` | `forks/yunohost/conf/fail2ban/jail.conf`, `yunohost-jails.conf` |
| YunoHost-specific filters (API/portal login failures) | Custom regex filters targeting **nginx access logs** — nginx is retired post-Caddy, so these jails are already inert | `forks/yunohost/conf/fail2ban/yunohost.conf`, `yunohost-portal.conf`, `postfix-sasl.conf` |
| Ban action | `nftables-multiport` / `nftables-allports` fail2ban actions | `jail.conf:208-212,369,825,835,901,976`; binds/reloads on nftables via `systemd-override-bind-nftables.conf` |
| Config regeneration | `regenconf` `fail2ban` category | `forks/yunohost/hooks/conf_regen/52-fail2ban`, `src/regenconf.py` |
| Setting-driven reconfig | `ssh_port` change → regen fail2ban + reload firewall | `src/settings.py:349-353` |
| Service health/status | `fail2ban-server --test`, `/var/log/fail2ban.log` | `conf/yunohost/services.yml:8-11`, `src/service.py` |
| App-packaging helper (legacy/v1+v2.1) | `ynh_config_add_fail2ban` / `ynh_config_remove_fail2ban` — **fail2ban-only, out of scope for this migration** | `helpers/helpers.v1.d/fail2ban`, `helpers/helpers.v2.1.d/fail2ban` — a legacy compatibility surface owned by `RESOURCE-ENGINE-CUTOVER.md`, used by any remaining legacy `_ynh`-style package |
| Native resource engine | `PolicyResource(type: "fail2ban")`, `PolicyProvider` renders `jail.d/nostrhost-<name>.local`. **Confirmed unused today** — `packages/nostrhost-native-example/package.toml` declares no policy resource, so there is no live `type: "fail2ban"` consumer to migrate | `forks/yunohost/src/nostrhost/package_engine.py:349`, `native_providers.py:932` |
| Service readiness check | Waits on `nginx`/`fail2ban` service status before app operations — `nginx` is already retired (Caddy owns 80/443); this line is a Caddy leftover this plan folds into `["caddy", "crowdsec"]` in one change | `forks/yunohost/src/utils/app_utils.py:1359` |
| Debian dependency | Hard dependency, min version pinned | `forks/yunohost/debian/control:26,49` |
| Backup/restore | No dedicated hook; fail2ban config is host state, not per-app backup data | (confirmed: no `hooks/backup|restore` reference — nothing to port) |

## 3. Target architecture

```text
journald + app/service logs (Caddy — nginx retired by CADDY-MIGRATION, which has landed)
      |
      v
crowdsec (LAPI, local only)
  acquis.yaml: journald sshd/postfix/dovecot/PAM units
             + Caddy unit (or a configured file log — see P1 spike)
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
| `yunohost.conf` / `yunohost-portal.conf` filters | **Port** to custom CrowdSec parsers (`nostrhost-yunohost-auth.yaml`, `nostrhost-portal-auth.yaml`) — same detection logic, but rewritten for **Caddy's** log output (nginx is retired; the old regexes were nginx-format), YAML parser DSL instead of fail2ban's filter format |
| `postfix-sasl.conf` | **Port**; likely covered by `crowdsecurity/postfix` collection, verify SASL variant is included or needs a local parser override |
| `hooks/conf_regen/52-fail2ban` | **Replace** with `hooks/conf_regen/52-crowdsec` rendering `acquis.yaml`, local parsers/scenarios, and bouncer config |
| `conf/fail2ban/systemd-override-bind-nftables.conf` | **Replace**: `crowdsec-firewall-bouncer` ships its own nftables binding; verify ordering against `nftables.service` the same way |
| `src/settings.py:349-353` (`reconfigure_ssh_and_fail2ban`) | **Rename/rework** to regen CrowdSec's sshd acquisition (port is read from journald unit, not a jail `port=` field — likely simplifies, may become a no-op) |
| `conf/yunohost/services.yml` fail2ban entry | **Replace** with `crowdsec` (`cscli version`/`systemctl status crowdsec` as `test_conf` equivalent — CrowdSec has no config-syntax-check CLI equivalent to `fail2ban-server --test`; use `cscli hub list` sanity or a wrapper). The `caddy` entry stays; the retired `nginx` entry is already gone |
| `helpers/helpers.v1.d/fail2ban`, `helpers.v2.1.d/fail2ban` | **Leave untouched.** Not reimplemented, not extended to target CrowdSec. Stays fail2ban-only, exactly as `RESOURCE-ENGINE-CUTOVER.md` already treats the helper tree — a legacy surface removable only when "no installed or supported package... sources the helper tree." CrowdSec is deliberately *not* added as a second bash-helper backend; see the "App-packaging integration" row in §1 |
| `src/nostrhost/package_engine.py:349` `PolicyResource.type` | **Extend**: `Literal["fail2ban", "crowdsec", "logrotate"]`. No transition/drop step needed for `"fail2ban"` — it has no live consumer (§2) — but the literal is left in place since removing it is `RESOURCE-ENGINE-CUTOVER.md`'s call, not this plan's |
| `src/nostrhost/native_providers.py:932` `PolicyProvider` | **Extend** `directories` map with a `crowdsec` entry (parsers/scenarios under `/etc/crowdsec/{parsers,scenarios}/nostrhost-<name>.yaml`, no `.local` suffix convention needed). This is the **only** app-packaging integration point CrowdSec gets — native `package.toml` declares `[[policy]] type = "crowdsec"`; there is no Bash-callable equivalent, matching "There is no Bash or legacy-script capability in this engine" (`RESOURCE-ENGINE.md`) |
| `src/utils/app_utils.py:1359` service-wait list | **Update** to `["caddy", "crowdsec"]` — nginx is already retired, so this folds in the Caddy-side leftover in the same change |
| `debian/control:26,49` | **Replace** `fail2ban` dependency with `crowdsec`, `crowdsec-firewall-bouncer` (source: official CrowdSec apt repo — see §1 package-source decision) |
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
- **Comparison set is the live jails only** (sshd/postfix/sasl/dovecot/
  recidive via journald + `/var/log/mail.log`). The `yunohost`/`yunohost-portal`
  jails read nginx logs that no longer exist, so they have no fail2ban
  baseline — CrowdSec fills that gap, which the report should state
  explicitly.
- Gate: written evaluation report committed to this doc (§8) with an
  explicit go/no-go. **If CrowdSec does not materially improve the model,
  stop here and close this branch without merging** — per roadmap §18.4,
  adoption is conditional.

### P1 — Parser parity
- **Log-source spike first. Confirmed in P0 (§8.3):** nginx is retired, the
  `yunohost`/`yunohost-portal` jails read dead nginx logs, and the testbed
  Caddyfile has **no `log` directive**, so Caddy emits no `http.access`
  entries at all — web-layer auth failures are currently invisible to any
  detector. P1's first deliverable is a **Caddy packaging change** adding
  `log { output file … }` (file-acquire it) or a journald acquisition of the
  caddy unit, then confirming the authd 401/redirect from `forward_auth`
  surfaces as a Caddy access entry (portal login failures land here, not in
  an nginx log).
- Port `yunohost.conf` and `yunohost-portal.conf` detection logic to CrowdSec
  parsers (`nostrhost-yunohost-auth.yaml`, `nostrhost-portal-auth.yaml`),
  rewritten for **Caddy's log format** (not nginx), same maxretry/detection
  semantics, YAML parser DSL. `crowdsecurity/caddy-logs` (v1.1) already
  parses Caddy's JSON format and maps 401+Basic to `auth_fail` (§8.3).
- Port `postfix-sasl.conf`; **confirmed in P0 (§8.2):** the `crowdsecurity/
  postfix` collection already covers SASL auth failures (`postfix-spam` on
  `log_type_enh: spam-attempt`) — align its threshold to fail2ban's `[sasl]`
  jail (maxretry 5) rather than re-deriving the parser.
- Write scenarios mirroring current jail `maxretry`/`findtime`/`bantime`
  values (`yunohost-portal` at `maxretry=20`, `recidive` behaviour, etc.).
- Gate: `cscli explain` / replay against captured auth-failure log samples
  produces the expected detections (same or better precision than the old
  nginx-format filters).

### P2 — acquis.yaml + regenconf
- Write `hooks/conf_regen/52-crowdsec`: renders `acquis.yaml` (journald units
  for sshd/postfix/dovecot/PAM + the Caddy unit — or a file path if P1's
  spike adds a `log` directive — replacing today's `/var/log/nginx` logpath
  entries), installs the local parsers/scenarios from P1, reloads `crowdsec`.
- Wire `settings.py` (`ssh_port` post-change hook) to regen the relevant
  acquisition, not the whole jail set.
- CrowdSec still runs detect-only (no bouncer); compare its decisions log
  against fail2ban's actual bans over a soak period.
- Gate: decisions generated by CrowdSec for real traffic match fail2ban bans
  for the soak period, with an acceptable (documented) false-positive delta.

### P3 — Native policy resource (no Bash helper)
- Extend `PolicyResource.type` (`package_engine.py:349`) with `"crowdsec"`,
  taking a parser/scenario `content` payload (mirroring the existing
  `content: str` field used for fail2ban jail text).
- Extend `PolicyProvider.directories` (`native_providers.py:932`) with a
  `crowdsec` entry; `inspect`/`plan`/`apply`/`remove` render/remove
  `/etc/crowdsec/{parsers,scenarios}/nostrhost-<name>.yaml` and trigger a
  `cscli` hub refresh + `crowdsec` reload, following the same
  inspect→plan→apply→verify shape as the other native providers (no shell
  helper indirection).
- Update `packages/nostrhost-native-example/package.toml` (or a new example
  package) to declare `[[policy]] type = "crowdsec"` as the reference usage,
  since §2 confirmed no package exercises the `PolicyResource` type today.
- **Explicitly no work on `helpers/helpers.v1.d/fail2ban` or
  `helpers.v2.1.d/fail2ban`.** They keep targeting fail2ban unmodified. Any
  legacy (non-native) package that needs CrowdSec-backed protection must be
  converted to a native `package.toml` — the same path `CADDY-MIGRATION.md`
  P4 already takes for `nostrhost-test`'s web routes — not served through a
  new bash entry point.
- Gate: the reference native package's `crowdsec` policy resource
  round-trips through `package.plan`/`package.reconcile` (install, verify,
  remove) with a real parser/scenario file, exercised by
  `tests_nostr/test_crowdsec_*.py`.

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
- **Pre-condition, not just a nice-to-have:** confirm via
  `tools/legacy_inventory.py` (or its successor) that no supported package
  still sources `helpers/helpers.v1.d/fail2ban` / `helpers.v2.1.d/fail2ban`.
  Per `LEGACY-INVENTORY.md`, `nostrhost-test` is currently the sole legacy
  fixture; if it (or anything else) still calls `ynh_config_add_fail2ban` at
  this point, either convert it to the native `crowdsec` policy resource
  from P3 first, or explicitly accept it loses intrusion-protection coverage
  — do not silently strand a package calling a helper that now targets a
  removed daemon.
- Stop/disable/remove the fail2ban service and package.
- Remove `forks/yunohost/conf/fail2ban/`, `hooks/conf_regen/52-fail2ban`,
  the `fail2ban` entry from `services.yml`, `debian/control` dependency, and
  (once the pre-condition above holds) the `helpers.v1.d/fail2ban` /
  `helpers.v2.1.d/fail2ban` files and the `PolicyResource.type` literal
  `"fail2ban"`. Helper-tree removal still follows
  `RESOURCE-ENGINE-CUTOVER.md`'s general gate — this phase only removes the
  fail2ban-specific slice of it, once that gate is met for this slice.
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
  plan already names this branch as the owner of fail2ban→CrowdSec; the
  remaining work is pointing its P5 line at this doc). Caddy has landed, so
  this plan's P1 parser work targets Caddy's actual log format per the spike
  — no out-of-order reconciliation left.

## 6. New artifacts

| Artifact | Purpose |
|---|---|
| `forks/yunohost/conf/crowdsec/acquis.yaml.tpl` | Log/journald acquisition template (rendered by the regen hook) — Caddy-unit/file acquisition, not nginx |
| `forks/yunohost/conf/crowdsec/parsers/nostrhost-yunohost-auth.yaml` | Port of `yunohost.conf` filter |
| `forks/yunohost/conf/crowdsec/parsers/nostrhost-portal-auth.yaml` | Port of `yunohost-portal.conf` filter |
| `forks/yunohost/conf/crowdsec/scenarios/*.yaml` | Port of jail `maxretry`/`findtime`/`bantime` semantics |
| `forks/yunohost/hooks/conf_regen/52-crowdsec` | CrowdSec regen category (replaces `52-fail2ban`) |
| `forks/yunohost/tests_nostr/test_crowdsec_*.py` | Provider/parser/regen tests, mirroring the resource-engine test conventions |
| `packages/nostrhost-native-example/package.toml` (extended) or a new example package | Reference `[[policy]] type = "crowdsec"` declaration exercising the new `PolicyProvider` path |
| `state/security/intrusion-protection.toml` | Semantic-state record of CrowdSec policy (roadmap §18.6) |

## 7. Risks

1. **Legacy packages get no automatic CrowdSec coverage.** Because CrowdSec
   is native-only (§1), any package still calling `ynh_config_add_fail2ban`
   keeps working against fail2ban right up until P6 removes it, then loses
   intrusion-protection entirely unless converted to a native
   `package.toml` with a `crowdsec` policy resource first. This is a
   one-time migration cost concentrated on legacy packages, not an ongoing
   dual-backend maintenance burden — confirm the P6 pre-condition (no
   package still sources the fail2ban helper) before removing anything.
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
5. **Log-source dependency on CADDY-MIGRATION — now landed.** The `yunohost`/
   `yunohost-portal` jails targeted nginx's log format (`/var/log/nginx/*.log`);
   nginx is retired on `main`, so those jails are already inert and P1 must
   target **Caddy's** log output (default: stderr/journald; file `log` only
   if added). This is no longer conditional — see P1's log-source spike.
6. **No `fail2ban-server --test` equivalent.** `services.yml`'s `test_conf`
   check has no direct CrowdSec analogue (`cscli` validates the hub, not a
   rendered acquisition/parser set end-to-end); P4 needs a concrete decision
   on what health check substitutes for it, not a silent drop of the check.
7. **Evaluation may return "no."** Per roadmap §18.4 this adoption is
   conditional; P0's gate can legitimately end the effort. Do not treat
   later phases as committed work before P0's report lands.
8. **CrowdSec version/source skew.** (Corrected by the P0 spike, §8.1:)
   bookworm main actually ships `crowdsec` **1.4.6** (a current 1.x line,
   not the old 0.1.x as this risk originally claimed), while the official
   apt repo carries **1.8.1**; the `crowdsec-firewall-bouncer` (0.0.25) is
   only in bookworm main, so daemon and bouncer come from different sources.
   Mixing a vendored hub (collections) with a system package from a
   different source can silently fail on parser/scenario API drift — P0 pins
   the official repo for the daemon; resolve the daemon/bouncer skew before
   the P4 cutover.
9. **Caddy emits no HTTP access logs today** (§8.3). With no `log` /
   `access_log` directive in the Caddyfile, per-request access entries are
   absent, so neither fail2ban's nginx-reading jails nor CrowdSec's
   `caddy-logs` parser can see web-layer auth failures. Adding
   `log { output file … }` to the Caddy app is a prerequisite for any
   web-layer detection — a packaging change, independent of the
   fail2ban→CrowdSec decision.

## 8. Evaluation report (filled in during P0)

*Status: **P0 complete.** Go/No-Go: **GO** (with the two prerequisites in
§8.5 below satisfied). Measurements below were taken on the `nostrhost-vm`
testbed (Debian 12 bookworm, kernel 6.1.0-53-cloud-amd64) with CrowdSec
1.8.1 running detect-only alongside fail2ban 1.0.2, CAPI/console disabled.

### 8.1 Package source and version (corrects risk #8)

- Official CrowdSec apt repo (`packagecloud.io/crowdsec/crowdsec`) carries
  `crowdsec` 1.8.1 (current 1.x line).
- **Risk #8's premise was wrong:** bookworm main does **not** ship the "old
  0.1.x" line — it carries `crowdsec 1.4.6` (still a 1.x daemon). So both
  candidate sources are viable 1.x; the official repo is simply newer.
- The official repo does **not** carry `crowdsec-firewall-bouncer`. The
  bouncer (`0.0.25-4~deb12u1`, depends `nftables | iptables, nftables |
  ipset, libc6`) is only in bookworm main. Daemon (official repo, 1.8.1) and
  bouncer (bookworm main, 0.0.25) therefore come from **different sources** —
  a real version-skew risk to resolve in P4 (§8.5).
- `crowdsec` installs standalone (simulate showed no extra deps; `Depends:
  coreutils` only).

### 8.2 Detection parity (the core test)

Controlled bursts of auth failures were injected into the live log streams
that fail2ban's sshd/sasl jails and CrowdSec's sshd/postfix collections both
read, and each engine's decision was recorded. CrowdSec's default private-IP
whitelist (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`) was relaxed to
loopback-only for the test so LAN test sources would be evaluated; that
whitelist behaviour is itself a finding (§8.4).

| Source | fail2ban decision | CrowdSec decision | Notes |
|---|---|---|---|
| sshd auth.log, 11 fails from `198.51.100.77` | `[sshd]` ban (maxretry 10 / findtime 600) | `ssh-bf` + `ssh-slow-bf` ban (capacity 5 / leakspeed 10s) | both engines ban the same IP |
| mail.log SASL, 6 fails from `198.51.100.9` | `[sasl]` ban (maxretry 5) | `postfix-spam` ban (6 events) | CrowdSec maps SASL `spam-attempt` → `postfix-spam` |

**P1 question answered for the mail path:** the `crowdsecurity/postfix`
collection **does** cover SASL auth failures — `postfix-logs.yaml` grok
(`SASL ... authentication failed`) sets `log_type_enh: spam-attempt`, which
`postfix-spam.yaml` acts on. No parser parity gap for SMTP/SASL.

**Threshold semantics differ from fail2ban defaults:** CrowdSec's `ssh-bf`
is capacity 5 (5 failures within ~50s) vs fail2ban `[sshd]` maxretry 10
within 600s; default bantime ~4h vs fail2ban 600s. CrowdSec is more
sensitive with a longer default ban. The plan's P1/P3 scenario work must pin
these to the current jail values (§18.4) rather than accept CrowdSec
defaults.

**IPv6 parity:** confirmed — `2001:db8::77` parses through `sshd-logs` and
evaluates in `ssh-bf` identically to IPv4 (CrowdSec scopes are
family-agnostic). No IPv4/IPv6 divergence.

### 8.3 Log-source spike (Caddy) — the decisive gap

The plan's P1 spike premise is **confirmed and sharpened**:

1. The active testbed Caddyfile (`/etc/caddy-p0/Caddyfile`, 113 lines) has
   **no `log` / `access_log` directive**. `journalctl -u caddy-p0` shows
   only `admin`, `admin.api`, `http.acme_client`, `http.auto_https`,
   `tls.*` loggers — **zero `http.access` entries** over the whole retained
   journal. Caddy is not emitting per-request access logs at all, so
   HTTP-level auth failures are currently **invisible** to any detector.
2. The `yunohost` / `yunohost-portal` / `nginx-http-auth` fail2ban jails read
   `/var/log/nginx/*.log`, which Caddy never writes; those logs are stale
   (last mtime 2026-09-10, pre-migration) and the jails are inert. This is
   the gap §5 P0 already stated — now verified at the log level.
3. `crowdsecurity/caddy-logs` (v1.1) **does parse** Caddy's JSON access
   format once a line exists (`--type caddy` → `non-syslog` → `caddy-logs`
   🟢), and maps `status 401` + `Www-Authenticate: Basic` to
   `sub_type: auth_fail`. So the parser is fit for purpose — but it has
   nothing to consume today.

**Consequence (a required prerequisite, not a nice-to-have):** restoring
web-layer auth-failure detection — under *either* engine — requires adding a
`log { output file … }` directive to the Caddy app's Caddyfile template (a
Caddy packaging change, part of risk #5/#8's follow-through). Without it,
the SSO-wat / portal auth-failure surface stays dark for both fail2ban and
CrowdSec. P2's acquis and the authd/`forward_auth` 401 path both depend on
this first.

### 8.4 Roadmap §18.4 criteria

| Criterion | fail2ban 1.0.2 | CrowdSec 1.8.1 |
|---|---|---|
| Idle memory (RSS) | ~49 MB | ~194–249 MB (Go runtime) |
| Package footprint (disk) | ~2.1 MB | ~315 MB (`Installed-Size: 322091 KB`) |
| Dependencies | python3 | coreutils |
| Local store | n/a (log+config) | SQLite `crowdsec.db` + hub (`/etc/crowdsec/hub`, 1.1 MB) |
| Network at install | none | apt repo + hub + GeoLite2 mmdb (63+11 MB) fetched from `hub-data.crowdsec.net` |
| Network at runtime | none (mail/auth logs only) | **persistent outbound TLS to CrowdSec cloud** even with CAPI off |
| Hub/collection updates | n/a | `cscli hub update`; vendor into package for offline first-boot |

CrowdSec is roughly **150x the disk** and **4–5x the idle RAM** of fail2ban.
That is a real footprint cost, acceptable only if the §18.4 value (decision
store, parser ecosystem, structured events for §18.5) justifies it.

**Offline behaviour:** with CAPI/console fully disabled (no `capi.yaml`,
no console enrollment), the daemon still opens and holds an outbound TLS
connection to `52.51.22.15:443` (CrowdSec AWS eu-west-1) — the
`online_client` (`/etc/crowdsec/online_api_credentials.yaml` is auto-created
at install) plus geoip enrichment. So "detect-only, CAPI off" is **not**
network-free: the host phones home by default. Offline first-boot requires
pre-baking the hub collections **and** the GeoLite mmdb (or disabling
`geoip-enrich`) into the package, and explicitly closing the `online_client`
outbound — a config the package must ship, not rely on defaults.

**Private-IP whitelist finding:** CrowdSec ships a whitelist that ignores
`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, `127.0.0.0/8`. fail2ban on
this testbed was actively banning `192.168.122.1` (the KVM host) — CrowdSec
would silently not. That is arguably a *good* property (no self-lockout of
LAN admin/gateway), but it is a behavioural divergence to document and pin
per-server, not assume.

**nftables integration (P4):** the bouncer ships `nftables | iptables` and
owns a dedicated set (e.g. `crowdsec-blacklists`) — additive to YunoHost's
port-based `inet filter / input` chain, matching P4's plan. (Side-observation
from the testbed: fail2ban's own `nftables-multiport` unban was throwing
"Could not process rule: No such file or directory" — an existing fail2ban
nftables quirk, moot once fail2ban is retired.)

### 8.5 Go/No-Go and prerequisites

**Go.** CrowdSec matches fail2ban detection on the live sshd and
postfix/sasl jails (same source IPs, same decisions), covers SASL within the
postfix collection, and adds a SQLite decision store + parser ecosystem that
§18.5's structured-event pipeline needs. The footprint and network behaviour
above are the real costs to budget, not blockers.

Two prerequisites gate P1/P2, not the go/no-go itself:

1. **Caddy `log { output file … }` directive must land** (a Caddy packaging
   change) before any web-layer parser (CrowdSec `caddy-logs` or a
   ported `yunohost-portal`) can be acquired — §8.3.
2. **Pin one package source** per risk #8. Daemon comes from the official
   repo (1.8.1); the bouncer is only in bookworm main (0.0.25) — resolve the
   daemon/bouncer skew before P4 cutover, and vendor hub + GeoLite mmdb into
   the package for offline first-boot (§8.4).
