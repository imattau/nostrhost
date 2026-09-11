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
| Package source | CrowdSec daemon + bouncer from **the Debian repo** (`crowdsec` 1.4.6 + `crowdsec-firewall-bouncer` 0.0.25, both bookworm main). Offline hub shipped by the Debian package at `/usr/share/crowdsec/hub`; CAPI is **opt-out-by-emptying** `online_api_credentials.yaml` (README.Debian's `# no thanks` mechanism) | One source for daemon and bouncer — no version/source skew (P0 confirmed the official repo lacks the bouncer), and a clean bookworm→trixie upgrade path since Debian carries both packages in both releases. P0 re-verified detection parity on 1.4.6. The Debian daemon is a current 1.x line (1.4.6), not an old 0.1.x; its offline hub satisfies `crowdsecurity/*` collection requirements without first-boot network |
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
| `yunohost.conf` / `yunohost-portal.conf` filters | **Done (P1).** Ported to **scenario-level path filters** (`nostrhost-yunohost-auth-bf.yaml`, `nostrhost-yunohost-portal-auth-bf.yaml`) — not custom parsers (local parsers don't load, §8.6). Same detection logic, rewritten for Caddy's log output via the `caddy-logs` metas |
| `postfix-sasl.conf` | **Done (P1).** `nostrhost-postfix-sasl-bf.yaml` reuses the `crowdsecurity/postfix` collection's `postfix-logs` parser; narrows with `log_type_enh == 'spam-attempt' && evt.Parsed.message_failure != ''` (no parser override needed) |
| `hooks/conf_regen/52-fail2ban` | **Done (P2).** Replaced with `hooks/conf_regen/52-crowdsec` rendering `acquis.yaml` + installing local scenarios + reloading `crowdsec` (bouncer config deferred to P4) |
| `conf/fail2ban/systemd-override-bind-nftables.conf` | **Replace**: `crowdsec-firewall-bouncer` ships its own nftables binding; verify ordering against `nftables.service` the same way (P4 — nftables set/rule layout validated in §8.8) |
| `src/settings.py:349-353` (`reconfigure_ssh_and_fail2ban`) | **Done (P2).** Renamed `reconfigure_ssh_and_crowdsec`; `ssh_port` change regens `["ssh", "crowdsec"]`. sshd acquisition is a journald unit (port-agnostic), so crowdsec regen is a consistency no-op |
| `conf/yunohost/services.yml` fail2ban entry | **Done (P4).** Replaced with `crowdsec` + `crowdsec-firewall-bouncer` entries. `test_conf` substitute decision (risk #6): `cscli config show >/dev/null 2>&1` for the daemon (validates the config file parses; CrowdSec has no `fail2ban-server --test` equivalent) and a config-file-exists check for the bouncer. The `caddy` entry stays; the retired `nginx` entry is already gone |
| `helpers/helpers.v1.d/fail2ban`, `helpers.v2.1.d/fail2ban` | **Leave untouched.** Not reimplemented, not extended to target CrowdSec. Stays fail2ban-only, exactly as `RESOURCE-ENGINE-CUTOVER.md` already treats the helper tree — a legacy surface removable only when "no installed or supported package... sources the helper tree." CrowdSec is deliberately *not* added as a second bash-helper backend; see the "App-packaging integration" row in §1 |
| `src/nostrhost/package_engine.py:349` `PolicyResource.type` | **Done (P3).** Extended to `Literal["fail2ban", "crowdsec", "logrotate"]`. No transition/drop step needed for `"fail2ban"` — it has no live consumer (§2) — but the literal is left in place since removing it is `RESOURCE-ENGINE-CUTOVER.md`'s call, not this plan's |
| `src/nostrhost/native_providers.py:932` `PolicyProvider` | **Done (P3).** `directories` gains a `crowdsec` entry (`/etc/crowdsec/scenarios/`); `_suffix()` maps `fail2ban`→`.local`, `crowdsec`→`.yaml`, `logrotate`→`""`; apply/remove render `/etc/crowdsec/scenarios/nostrhost-<name>.yaml` + `systemctl reload crowdsec` + a state snapshot (`state/security/intrusion-protection.toml`). This is the **only** app-packaging integration point CrowdSec gets — native `package.toml` declares `[policies.<name>] type = "crowdsec"`; there is no Bash-callable equivalent, matching "There is no Bash or legacy-script capability in this engine" (`RESOURCE-ENGINE.md`) |
| `src/utils/app_utils.py:1359` service-wait list | **Done (P4).** Updated to `["caddy", "crowdsec"]` — nginx is already retired, so this folds in the Caddy-side leftover in the same change |
| `debian/control:26,49` | **Done (P4).** `fail2ban` dependency and the `fail2ban (>= 1.1)` Conflicts entry replaced with `crowdsec`, `crowdsec-firewall-bouncer` (source: Debian repo — §1 package-source decision; both are bookworm main). Note the §4 reference to "official CrowdSec apt repo" predates the §1 Debian-source decision and is superseded by it |
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
- **Ported via scenario-level path filters, NOT custom parsers.** The
  packaged CrowdSec 1.4.6 does **not** load parsers placed in
  `/etc/crowdsec/parsers/` (verified: even a `filter: "true"` marker parser
  never runs in the daemon or `cscli explain`, because they're absent from
  the hub index `/var/lib/crowdsec/hub/.index.json`; there is no
  `cscli parsers add` / local-path install in this version). Local **scenarios**
  in `/etc/crowdsec/scenarios/` DO load. So the correct architecture is
  scenario-level path filters on the metas `crowdsecurity/caddy-logs` (s01) +
  `crowdsecurity/http-logs` (s02) already set — no custom parser needed.
- Two leaky scenarios reproduce the retired nginx-format filters directly on
  Caddy's JSON metas (fail2ban regex `^<HOST> -.*"POST …" 401` ⇔
  `evt.Meta.http_verb == 'POST' && evt.Meta.http_path == '<path>' && evt.Meta.http_status == '401'`):
  - `nostrhost-yunohost-auth-bf` → `POST /yunohost/api/login 401`, capacity
    10 / leakspeed 60s (= `maxretry 10`, `findtime 10m`).
  - `nostrhost-yunohost-portal-auth-bf` → `POST /yunohost/portalapi/login 401`,
    capacity 20 / leakspeed 30s (= `maxretry 20`, `findtime 10m`).
  Keying on the exact path keeps each scenario narrow (fail2ban parity) and
  avoids the broad `LePresidente/http-generic-401-bf` (any POST 401).
  `groupby: evt.Meta.source_ip` keeps the bucket per attacker. **Do not add a
  `distinct:` on the same field as `groupby`** — it pins the bucket's distinct
  count at 1/IP and the leaky bucket never fills (found and fixed during
  validation).
- **Installed `crowdsecurity/caddy-logs` is v0.4**, not the plan's v1.1. It
  still sets `log_type=http_access-log`, `http_status`, `http_path` (from
  `request.uri`), `http_verb` (from `request.method`), `source_ip`; it sets
  `sub_type='auth_fail'` only on 401+Basic (YunoHost's JSON login sends no
  Basic, so we key on path/verb/status, which is moot with no custom parser).
- Port `postfix-sasl.conf` as `nostrhost/postfix-sasl-bf.yaml`; **confirmed in
  P0 (§8.2):** the `crowdsecurity/postfix` collection already tags SASL
  failures (`postfix-logs` grok `SASL … authentication failed` →
  `log_type_enh: spam-attempt`), so the scenario **reuses that parser** rather
  than re-deriving one. It filters on `log_type_enh == 'spam-attempt'` **and**
  `evt.Parsed.message_failure != ''` — `message_failure` is set only by the
  SASL grok, which keeps the scenario narrow to the `[sasl]` jail (the broad
  `postfix-spam` also fires on "lost connection" spam and postfix `reject`).
  Threshold aligned to fail2ban `[sasl]`: `maxretry 5` → capacity 5,
  `findtime 10m` → `leakspeed 120s`.
- Decision duration (fail2ban `bantime`) is set by the **bouncer (P4)**, not a
  per-scenario field — consistent with every stock scenario.
- Gate: `cscli explain` / replay against captured auth-failure log samples
  produces the expected detections (same or better precision than the old
  nginx-format filters). **Verified on a Debian 12 test host:** each scenario
  fired a `ban` after capacity rapid 401 logins on its own path (see §8.6).

### P2 — acquis.yaml + regenconf
- **Done:** `hooks/conf_regen/52-crowdsec` replaces `52-fail2ban`. In
  `pre_regen` it renders `acquis.yaml` and installs the packaged local
  scenarios to `/etc/crowdsec/scenarios/`; in `post_regen` it chmod/chowns
  and `systemctl reload crowdsec` only when files actually changed. The base
  hub collections that provide the required parsers
  (`crowdsecurity/caddy`, `/sshd`, `/postfix`, `/linux`) are installed at
  package install time, not by the hook.
- **Done:** `conf/crowdsec/acquis.yaml` (static — no render variables needed).
  Sources: Caddy access log `/var/log/caddy/access.log` as `type: caddy`
  (a **file** path, since P1's `log` directive is in effect, replacing the
  nginx logpath entries); sshd/postfix/dovecot as journald units; and
  `/var/log/auth.log` + `/var/log/syslog` as `type: syslog`.
- **Done:** `src/settings.py` — `reconfigure_ssh_and_fail2ban` renamed to
  `reconfigure_ssh_and_crowdsec`; `ssh_port` change now regens
  `["ssh", "crowdsec"]`. The sshd acquisition is a journald unit
  (port-agnostic), so the regen mainly rewrites sshd config; crowdsec regen
  is kept for consistency.
- CrowdSec still runs detect-only (no bouncer); compare its decisions log
  against fail2ban's actual bans over a soak period.
- Gate: decisions generated by CrowdSec for real traffic match fail2ban bans
  for the soak period, with an acceptable (documented) false-positive delta.

### P3 — Native policy resource (no Bash helper)
- **Done:** `PolicyResource.type` (`package_engine.py:349`) extended with
  `"crowdsec"`, taking a scenario `content` payload (mirroring the existing
  `content: str` field used for fail2ban jail text). Note: CrowdSec uses a
  **single** `scenarios` directory (`/etc/crowdsec/scenarios/`), so a policy
  resource declares exactly one scenario — the plan's earlier "parsers +
  scenarios" split did not materialize (local parsers don't load, §8.6), and
  the ported detection lives entirely at the scenario level.
- **Done:** `PolicyProvider` (`native_providers.py`) extended for CrowdSec:
  - `directories` gains `"crowdsec": /etc/crowdsec/scenarios`.
  - `_suffix(type_)` maps `fail2ban` → `.local`, `crowdsec` → `.yaml`,
    `logrotate` → `""` (no suffix); the target file is always
    `nostrhost-<name><suffix>`.
  - `__init__` now takes `command` (for `systemctl`) and `state_dir`
    (defaulting to `/var/lib/nostrhost/state` for `root=/`, else
    `<root>/var/lib/nostrhost/state`).
  - `_reload(type_)` runs `systemctl reload crowdsec` for `crowdsec`
    resources (local scenarios load on daemon reload — validated in P2);
    no network-dependent `cscli hub update`. fail2ban/logrotate apply with
    no reload command.
  - `apply`/`remove` write/remove the scenario file, then reload + snapshot.
  - **Snapshot:** after apply/remove the provider writes
    `state/security/intrusion-protection.toml` listing the currently-enabled
    `nostrhost-*.yaml` scenario stems, via `toml.dumps` (atomic
    tmp+replace). This is a lightweight direct write by the provider; wiring
    it through `StateRecorder`/`Backend.security()` (the full P5 semantic
    tree) is deferred to P5.
- **Done:** `native_providers()` factory wires
  `PolicyProvider(root=..., command=command, state_dir=<root or />/var/lib/nostrhost/state)`.
- **Done:** `packages/nostrhost-native-example/package.toml` declares two
  `[policies.<name>]` tables (`example-auth-bf`, `example-login-bf`) with
  `type = "crowdsec"` and inline scenario `content` as the reference usage.
  (Dict-shaped TOML, not `[[policy]]` array-of-tables — `policies` is
  `dict[str, PolicyResource]` keyed by name, so each table carries `type`,
  `name`, and `content`.)
- **Done:** Gate — `tests_nostr/test_crowdsec.py` (8 tests) covers the
  `crowdsec` literal, `.yaml` render + `systemctl reload crowdsec` on
  apply/remove, no-reload for non-crowdsec types, suffix selection, the
  state snapshot, a full `package.plan` → reconcile round-trip, and type
  rejection. Passes alongside the pre-existing 81 provider/engine tests
  (`test_native_providers.py`, `test_package_engine.py`).
- **Explicitly no work on `helpers/helpers.v1.d/fail2ban` or
  `helpers.v2.1.d/fail2ban`.** They keep targeting fail2ban unmodified. Any
  legacy (non-native) package that needs CrowdSec-backed protection must be
  converted to a native `package.toml` — the same path `CADDY-MIGRATION.md`
  P4 already takes for `nostrhost-test`'s web routes — not served through a
  new bash entry point.

### P4 — Bouncer cutover
- **Done (packaging + config):**
  - `debian/control` replaces the `fail2ban` dependency and its Conflicts
    entry with `crowdsec` + `crowdsec-firewall-bouncer` (both bookworm main).
  - New `conf/crowdsec-firewall-bouncer/crowdsec-firewall-bouncer.yaml`
    template: nftables mode, local LAPI (`127.0.0.1:8080`), `__API_KEY__`
    placeholder substituted at install. Schema matches the Debian 0.0.25
    package's nested `nftables: {ipv4, ipv6}` blocks.
  - `debian/postinst` `provision_crowdsec()` (idempotent, runs on fresh
    install and upgrade): (1) ships the `# no thanks` CAPI opt-out — on
    **fresh install** it *forces* it and purges the ~15k CAPI community
    decisions the crowdsec package's auto-registration already pulled
    (§8.8); (2) installs the base hub collections (`crowdsecurity/caddy`,
    `/sshd`, `/postfix`, `/linux`) from the vendored offline hub via
    `cscli collections install` (1.4.x has no `cscli hub install`); (3)
    renders the bouncer config, reusing the Debian package's auto-registered
    `.local` API key when present (else registers its own bouncer) and drops
    the `.local` override so the rendered config is authoritative; (4)
    enables + restarts `crowdsec-firewall-bouncer`.
  - `conf/yunohost/services.yml`: fail2ban entry replaced with `crowdsec`
    (`test_conf: cscli config show >/dev/null 2>&1`) and
    `crowdsec-firewall-bouncer` (`test_conf: test -f <bouncer config>`).
  - `src/utils/app_utils.py:1359` service-wait list → `["caddy", "crowdsec"]`.
  - `hooks/conf_regen/15-caddy` fixed (it was a silent no-op: missing the
    `do_$1_regen` dispatch, missing `do_post_regen`, and rendering in a
    `do_regen` function regenconf never calls — rendering now happens in
    `do_pre_regen`, mirroring 40-nftables/52-crowdsec). The base Caddyfile
    with the access-log directive therefore never rendered before this fix.
  - `conf/caddy/caddy_domain.conf` gains `reverse_proxy` for `/yunohost/api`
    (6787) and `/yunohost/portalapi` (6788), mirroring the retired nginx
    `location` blocks.
  - `conf/crowdsec/acquis.yaml`: the journald `ssh.service` source was
    dropped — `/var/log/auth.log` already carries every sshd line (any port),
    and acquiring both double-counted failures (§8.8).
  - `debian/postinst` fresh-install init list: `15-nginx` → `15-caddy` (a
    Caddy-migration leftover; nginx's regen hook was retired).
- **Done (validated, §8.8):** bouncer enforced live on the fresh testbed VM
  in nftables mode, owning its own `crowdsec`/`crowdsec6` tables +
  `crowdsec-blacklists` sets hooked via `crowdsec-chain` (set-only: false).
  It is additive — it never touches YunoHost's `inet filter` table, and
  `firewall_reload`/`firewall_list` + a full `regen-conf nftables` leave it
  (and its enforced set) intact. fail2ban is stopped + disabled.
- Gate (§8.8): a live ban test (12× `POST /yunohost/api/login` 401 from a
  test source) fired `nostrhost/yunohost-auth-bf`, the bouncer added the
  source to the nftables set, and traffic from it was dropped — with the
  management host untouched. `yunohost diagnosis` clean of any
  CrowdSec-related issue.

### P5 — Security event integration (roadmap §18.5)
This is the concrete replacement of the mail-based security notifications:
the security event class is the *first* real producer for the `2210-2213`
notice pipeline, so P5 proves the mail-stack removal end to end. There is
**no dual mail+nostr path** for security events.

- **Producer = `publish_notice()` on kind 2213.** A `security_projector`
  consumes CrowdSec alerts/decisions from **LAPI** and emits via the existing
  `nostr_notify.publish_notice(class_="security", severity=...,
  summary=..., kind=KIND_SECURITY_EVENT)` path
  (`forks/yunohost/src/nostr_notify.py:46`). Content `{class, severity,
  summary}` already matches `EVENT-PROTOCOL.md` §2.3; kind 2213 is
  validated, NIP-42-protected on the control relay, and consumed by
  `nostrhost-notify` unchanged. Server-signed (`server_sk`) like the
  existing `certificate`/`diagnosis` notices.
  - **Consumption mode (default: polling).** Poll `cscli alerts list -o
    json` on a short interval, tracking seen alert IDs; this matches how the
    notify service already consumes the control plane and needs no new LAPI
    client. A push-based LAPI websocket is a later optimization, not P5.
- **Coalesce CrowdSec's duplicate decisions.** P0 showed CrowdSec can emit
  overlapping decisions for one IP (e.g. `ssh-bf` *and* `ssh-slow-bf` for
  the same source). The projector must fold a ban's multiple decisions into
  **one** alert (source IP + merged scenario reasons) so a single ban yields
  a single DM — otherwise every ban double-notifies.
- **Severity mapping.** Default a `ban` decision to `SEVERITY_WARNING`
  (matching `policy.toml`'s default `severity_min = "warning"`, so a first
  ban notifies). A recurring source (an IP already banned that triggers
  again after expiry) escalates to `SEVERITY_CRITICAL`. Expose the mapping
  as config so the notify `policy.toml` `severity_min` can tune it (§4 of
  NOTIFICATION-SERVICE.md).
- **State record.** Extend `nostr_state.export_state()`
  (`nostr_state.py:342`) with a `security` section (add a
  `Backend.security()` accessor) rendering
  `state/security/intrusion-protection.toml`: collections enabled, CAPI
  opt-in state, bantime policy, and last-alert bookkeeping. Committed
  through the existing `StateRecorder` pre/post lifecycle on config
  change/`package.reconcile` — no new machinery. Reconciliation of this
  section stays report-only (`_reconciliation_tool` treats non-services/apps
  sections as high risk); document that.
- Gate: a triggered ban produces exactly one kind-2213 audit event, a
  `state/security/intrusion-protection.toml` record, and (if the policy
  allows) one encrypted Nostr DM to the admin npub.

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
| `forks/yunohost/conf/crowdsec/acquis.yaml` | Acquisition sources (rendered by the regen hook) — Caddy access log as `type: caddy` (file, since P1's `log` directive writes `/var/log/caddy/access.log`) plus sshd/postfix/dovecot journald units and auth.log/syslog as `type: syslog`; replaces the retired nginx logpath entries |
| `forks/yunohost/conf/crowdsec/scenarios/nostrhost-yunohost-auth-bf.yaml` | Port of `yunohost.conf` filter as a leaky scenario (capacity 10 / leakspeed 60s) on Caddy metas |
| `forks/yunohost/conf/crowdsec/scenarios/nostrhost-yunohost-portal-auth-bf.yaml` | Port of `yunohost-portal.conf` filter (capacity 20 / leakspeed 30s) |
| `forks/yunohost/conf/crowdsec/scenarios/nostrhost-postfix-sasl-bf.yaml` | Port of `postfix-sasl.conf` (`[sasl]` jail) — reuses `postfix-logs` parser; capacity 5 / leakspeed 120s |
| `forks/yunohost/conf/crowdsec/scenarios/*.yaml` (further ports) | Any remaining jail-semantics ports |
| `forks/yunohost/conf/crowdsec-firewall-bouncer/crowdsec-firewall-bouncer.yaml` | Bouncer config template (nftables mode, local LAPI); `__API_KEY__` substituted by `debian/postinst` on install |
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
   only in bookworm main. The §1 package-source decision resolves this by
   taking **daemon + bouncer both from the Debian repo** (single source, no
   cross-source drift, clean bookworm→trixie upgrade). Mixing a vendored hub
   with a system package from a different source can still silently fail on
   parser/scenario API drift — P0 validated the detection pipeline against
   the Debian 1.4.6 daemon + offline hub (§8.2) rather than the newer build.
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
running detect-only alongside fail2ban 1.0.2, CAPI/console disabled. The
parity tests were run twice — first on the packagecloud **1.8.1** build, then
re-verified unchanged on the **Debian-repo 1.4.6** build after the §1 package
source decision switched to the Debian repo (both are current 1.x; §8.1).

### 8.1 Package source and version (corrects risk #8)

**Decision (locked in §1): daemon + bouncer from the Debian repo.**

- **Risk #8's premise was wrong:** bookworm main does **not** ship the "old
  0.1.x" line — it carries `crowdsec 1.4.6`, a current 1.x daemon. The
  packagecloud repo carries 1.8.1. Both are viable 1.x.
- The official packagecloud repo does **not** carry
  `crowdsec-firewall-bouncer`; the bouncer (`0.0.25-4~deb12u1`, depends
  `nftables | iptables, nftables | ipset, libc6`) is only in bookworm main.
  Mixing the two sources would split daemon (1.8.1) from bouncer (0.0.25) —
  the skew risk §8.5 flags. **The Debian repo ships both, so it is the
  chosen single source**, and it gives a clean bookworm→trixie upgrade since
  Debian carries both packages in both releases.
- The Debian 1.4.6 package has two favourable packaging traits:
  - **Offline hub** at `/usr/share/crowdsec/hub` (collections/parsers/
    scenarios/patterns vendored) — first-boot needs no internet for hub
    items. Default-enabled collections are `linux`, `apache2`, `nginx`,
    `sshd` (nginx removed on this testbed as dead post-Caddy; `postfix`
    enabled explicitly). The offline hub includes `postfix`, `dovecot`,
    `caddy`, `whitelist-good-actors`, etc.
  - **CAPI opt-out by default-controllable file:** README.Debian specifies
    creating `/etc/crowdsec/online_api_credentials.yaml` containing only a
    comment (e.g. `# no thanks`) to skip CAPI registration; the package
    honours it on install and on purge. This gives an explicit, on-disk
    opt-out that survives reinstall — the §1 "CAPI off until evaluated"
    requirement, cleanly.
- `crowdsec` installs standalone (simulate showed no extra deps; `Depends:
  coreutils` only).
- Detection parity was **re-verified byte-for-byte on 1.4.6** after the
  source switch (§8.2): SSH tight/spread bursts → `ssh-bf`/`ssh-slow-bf`,
  SASL realistic burst → `postfix-spam`, IPv6 → `ssh-bf`.

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

**Re-verified on 1.4.6 (Debian repo).** The three parity runs reproduce on
the Debian build: tight ssh burst → `ssh-bf`; spread ssh burst →
`ssh-slow-bf`; realistic SASL burst → `postfix-spam`; IPv6 → `ssh-bf`. Two
test-hygiene notes that surfaced during re-verification:

- **The 1.4.6 `postfix-logs` grok is stricter than 1.8.1's.** It only sets
  `spam-attempt` when the line names a mechanism and carries a trailing
  reason (`SASL LOGIN|PLAIN|(CRAM|DIGEST)-MD5 authentication failed: …`);
  the bare `SASL authentication failed` (no mechanism, no reason) matched on
  1.8.1 but not 1.4.6. Real postfix always emits the mechanism + reason, so
  this is not a practical gap — but a synthetic-bare-line test would
  false-negative on 1.4.6. Any replay fixture in P2/P3 must use the realistic
  `SASL <MECH> authentication failed: <reason>` shape.
- **Which ssh scenario fires depends on burst timing, not version.** Both
  `ssh-bf` (capacity 5 / 10s) and `ssh-slow-bf` (capacity 10 / 60s) are
  enabled and byte-identical in semantics on 1.8.1 and 1.4.6. A tight burst
  fires `ssh-bf`; failures spread >10s apart fall to `ssh-slow-bf`. Either
  way the same source IP is banned, matching fail2ban's `[sshd]`.

**Threshold semantics differ from fail2ban defaults:** CrowdSec's `ssh-bf`
is capacity 5 (5 failures within ~10s) vs fail2ban `[sshd]` maxretry 10
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

Footprint measured on the **chosen Debian 1.4.6 package** (the heavier
packagecloud 1.8.1 build is noted where it differs).

| Criterion | fail2ban 1.0.2 | CrowdSec 1.4.6 (Debian) |
|---|---|---|
| Idle memory (RSS) | ~49 MB | ~77 MB idle (`MemoryCurrent=76.9 MB`) — 1.8.1 measured ~203 MB |
| Package footprint (disk) | ~2.1 MB | ~108 MB (`Installed-Size: 110742 KB`); `/var/lib/crowdsec` 14 MB, offline hub 4.1 MB; binaries 36+29 MB — 1.8.1 measured ~315 MB |
| Dependencies | python3 | `ca-certificates, libc6, libsqlite3-0` |
| Local store | n/a (log+config) | SQLite `crowdsec.db` (WAL enabled by Debian postinst) + offline hub at `/usr/share/crowdsec/hub` |
| Network at install | none | apt repo only; **hub + GeoLite mmdb are not fetched** — offline hub ships in-package (§8.1) |
| Network at runtime | none (mail/auth logs only) | **none external with the CAPI opt-out** (§8.1 `# no thanks`); only loopback LAPI. The 1.8.1 build held a persistent outbound to `52.51.22.15:443` even with CAPI off |
| Hub/collection updates | n/a | `cscli hub update` optional (moves off the offline hub); vendored offline hub means no first-boot network |

CrowdSec 1.4.6 is ~**52x the disk** and ~**1.6x the idle RAM** of fail2ban —
a real but modest footprint cost on the chosen source (the 1.8.1 build would
have been ~150x disk / 4x RAM). It is acceptable only if the §18.4 value
(decision store, parser ecosystem, structured events for §18.5) justifies it.

**Offline behaviour — materially better on the Debian source.** With the
§8.1 CAPI opt-out (an `online_api_credentials.yaml` containing only
`# no thanks`), the 1.4.6 daemon makes **no external outbound connection**
at all: after install and a settle window only loopback LAPI sockets exist,
no GeoLite mmdb is downloaded, and geoip enrichment is absent. The hub is
offline/vendored, so first-boot needs no network. Contrast the 1.8.1
packagecloud build, which auto-created `online_api_credentials.yaml`,
fetched the GeoLite mmdb, and held a persistent outbound to
`52.51.22.15:443` even with CAPI off. The package must ship the `# no
thanks` opt-out file explicitly (and the regen hook must not recreate
`capi.yaml`/empty it) to keep §1's "CAPI off until evaluated" honest on the
Debian source.

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
2. **Ship the Debian-source package with its offline/opt-out traits intact.**
   The source decision (§1) now resolves the daemon/bouncer skew: both come
   from bookworm main (1.4.6 + 0.0.25), so there is no cross-source
   mismatch. The remaining packaging work is to (a) ship the `# no thanks`
   CAPI opt-out file so the daemon stays network-quiet (§8.4), (b) keep the
   vendored offline hub (`/usr/share/crowdsec/hub`) on first-boot, and
   (c) re-verify `cscli hub` against 1.4.6 — P0 already validated the
   detection pipeline on it (§8.2).

### 8.6 P1 scenario validation (fail2ban → CrowdSec, Caddy format)

Validated end-to-end on the Debian 12 test host (bookworm, CrowdSec 1.4.6).
Replayed Caddy JSON access-log lines (`crowdsecurity/caddy-logs` format) via a
file acquisition pointing at a scratch log, then watched the alert/decision
store:

| Scenario | Replay | Result |
|---|---|---|
| `nostrhost/yunohost-auth-bf` | 12× `POST /yunohost/api/login` 401 from one IP | fired after 11 events; **ban** decision |
| `nostrhost/yunohost-portal-auth-bf` | 22× `POST /yunohost/portalapi/login` 401 from one IP | fired after 21 events; **ban** decision |
| `nostrhost/postfix-sasl-bf` | 6× `SASL … authentication failed` from one IP | fired at capacity 5; **ban** decision (6 events) |
| `nostrhost/postfix-sasl-bf` (negative) | 7× `lost connection` spam from one IP | **did not fire** — only `postfix-spam` (fail2ban `[sasl]` parity) |

`cscli explain` confirmed each line only matched its intended path-specific
scenario (plus the broad `LePresidente/http-generic-401-bf`, which coexists
unchanged). Two packaging facts established here:

- **Local scenarios load; local parsers do not.** Scenarios under
  `/etc/crowdsec/scenarios/` are picked up and run (both `nostrhost/*` fired),
  whereas parsers under `/etc/crowdsec/parsers/s01-parse/` are ignored at
  runtime because they are not in the hub index — the reason P1 uses
  scenario-level path filters instead of a custom parser.
- **`groupby` + `distinct` on the same field is a bug.** Adding
  `distinct: evt.Meta.source_ip` alongside `groupby: evt.Meta.source_ip` pins
  each bucket's distinct count at 1, so the leaky bucket never reaches
  capacity. Removed `distinct`; scenarios then fired as expected.

### 8.7 P2 acquisition validation (regen `acquis.yaml`)

Applied the packaged `conf/crowdsec/acquis.yaml` and the three scenarios to
the Debian 12 test host (CrowdSec 1.4.6) and restarted `crowdsec`; it came up
clean (only the expected offline CAPI-credentials warning). Appending 12×
`POST /yunohost/api/login` 401 lines to the live `/var/log/caddy/access.log`
produced:

| Source | Result |
|---|---|
| Caddy file acquisition (`type: caddy` on `/var/log/caddy/access.log`) | `nostrhost/yunohost-auth-bf` fired after 11 events; **ban** decision — confirms the file-path acquisition flows through `caddy-logs` into the scenario |
| sshd/postfix/dovecot journald + auth.log/syslog sources | loaded with no errors; `type: syslog` sources inert until real traffic |

All `nostrhost/*` scenarios listed as `enabled,local`; the `crowdsecurity/caddy`
collection (and its `caddy-logs` parser) is installed alongside.

### 8.8 P4 bouncer cutover validation (fresh VM, 2026-09-11)

Validated on a **freshly rebuilt** testbed VM (the previous `nostrhost-vm`
disk lived in `/tmp/opencode`, which was cleared — a rebuild was required;
the disk now lives in the repo at `testbed/vm/`, gitignored). Debian 12
bookworm + stock YunoHost 12.1.41.2 postinstall (`nostrhost.test`, admin
`ynhadmin`) with the derivative fork overlaid, Caddy 2.6.2 (Debian) owning
80/443 (nginx stopped+disabled), CrowdSec 1.4.6 + bouncer 0.0.25 (both
bookworm main).

**Packaging findings fixed during validation:**

1. **CAPI auto-registration.** The Debian `crowdsec` package's postinst
   auto-registers with CAPI (writes a real `online_api_credentials.yaml`)
   *before* yunohost's postinst runs — and pulls ~15k community decisions
   into LAPI. `provision_crowdsec force` (fresh install) therefore now
   *forces* the `# no thanks` opt-out and purges those decisions; the
   upgrade path still leaves an existing file (a deliberate opt-in) alone.
2. **`cscli hub install` does not exist in 1.4.6.** It silently failed in
   the first provisioning draft; collections install under
   `cscli collections install`. Fixed.
3. **Bouncer config schema + `.local` convention.** The Debian bouncer ships
   `crowdsec-firewall-bouncer.yaml` (a template with `${BACKEND}`/`${API_KEY}`
   placeholders) plus a `.local` override carrying the key it auto-registered.
   Provisioning now reuses that key and drops the `.local` so the rendered
   config is authoritative; the template matches the package's nested
   `nftables: {ipv4, ipv6}` schema.
4. **`15-caddy` regen hook was a silent no-op** — no dispatch line, no
   `do_post_regen`, and the render code sat in a `do_regen` function
   regenconf never invokes (regenconf drives hooks with `pre`/`post` only).
   Without it, the base Caddyfile (with the access-log directive) never
   rendered. Fixed to render in `do_pre_regen`; `regen-conf caddy` now
   produces `/etc/caddy/Caddyfile` + `/etc/caddy/conf.d/nostrhost.test.conf`.
5. **sshd double-counting.** The acquis acquired sshd via *both* the journald
   `ssh.service` unit and `/var/log/auth.log`; the same sshd failure counted
   twice (3 real failures → 6 events), tripping `ssh-bf` (capacity 5) early
   and **banning the LAN management host** once the private-IP whitelist was
   relaxed. Dropped the journald `ssh.service` source (auth.log carries every
   sshd line on any port).

**The live ban test (the §5 P4 gate):**

Test source = the VM's own IP `192.168.122.175` (chosen so the block can be
demonstrated without locking out the management host `192.168.122.1`); the
whitelist was adjusted to keep `10.0.0.0/8` + `172.16.0.0/12` + the
management host, removing only `192.168.0.0/16`.

| Step | Result |
|---|---|
| 12× `POST /yunohost/api/login` 401 (bad `credentials`) from `.175` via Caddy | `nostrhost/yunohost-auth-bf` fired; **ban** decision for `.175` in LAPI |
| Bouncer sync | `192.168.122.175` in `table ip crowdsec` `set crowdsec-blacklists` (nftables) |
| Post-ban probe from `.175` (curl to own IP) | **connection dropped** (`BLOCKED`) |
| Management SSH from host `.1` | unaffected |
| `yunohost firewall reload` + `firewall_list` | work unmodified; crowdsec table + enforced set survive; bouncer re-syncs if ever flushed |
| `regen-conf nftables --force` (full ruleset regen) | crowdsec table survives; set restored; block still enforced |
| fail2ban | stopped + disabled (CrowdSec is the enforcement path) |
| `yunohost diagnosis` | no CrowdSec-related issues (only testbed-environment warnings: no public IP/port exposure, no reverse DNS, nginx-retired diagnostic leftover) |

**nftables integration (risk #4) confirmed additive:** the bouncer creates
its own `table ip crowdsec` + `table ip6 crowdsec6` with base chains
(`crowdsec-chain`, hook input) that drop `ip saddr @crowdsec-blacklists`; it
never edits YunoHost's `inet filter` table, and it does not use an
`/etc/nftables.d/*.conf` include, so there is no include-ordering collision
with `conf/nftables/nftables.conf`. `firewall_reload` and a full nftables
regen leave the enforcement intact (the bouncer's update loop re-syncs the
sets).

**Caveats / follow-ups (testbed-specific, not committed):** the testbed
site block carries `tls internal` (rendered `/etc/caddy/conf.d/
nostrhost.test.conf`, so the gate ran over HTTPS without ACME); the
whitelist adjustment and fail2ban disable are VM state, not packaging. The
CAPI purge is bounded to the fresh-install path so an upgrade never removes
decisions belonging to a deliberate opt-in. The `15-caddy` hook fix and the
`caddy_domain.conf` API/portal proxies are fork changes (part of the P4
commit); a real deployment uses ACME for the site certs.
