# Native notification service (roadmap §18.1)

Phase 1 of mail-stack retirement (`docs/MAIL-RETIREMENT.md`): NostrHost stops
depending on email as its notification mechanism. Platform notifications
originate as structured local events and, where human delivery is required,
are delivered through encrypted Nostr messaging. This is the design for that
service, and the gating deliverable everything else in `MAIL-RETIREMENT.md`
waits on.

## 1. Scope

In scope:

- the event → notification pipeline (this document)
- the notification policy schema (recipient npub, event classes, severity
  threshold, immediate vs. summary delivery, local-only vs. external)
- how the service fits the existing control-plane architecture
  (`CONTROL-PLANE.md`) and state layer (`STATELAYER.md`)

Out of scope (tracked elsewhere):

- allocating the actual custom kind number(s) for structured system/service/
  security notices — that is a `nostrhost-control` event-protocol decision
  (`NIP-MAPPING.md` §3/§4 already reserves the category; the number itself is
  allocated in that component's `EVENT-PROTOCOL.md`, which lives in the
  `nostrhost-control` repo, not this one)
- the operation request/approval/execution chain (kinds 2200-2204) itself —
  unchanged; this service *consumes* those events, it doesn't replace them
- actually removing the mail stack (§18.2, phases 2+ of
  `MAIL-RETIREMENT.md`) — this is only the replacement channel

## 2. Architecture

```text
NostrHost subsystem
        |
        +-- backup result
        +-- health alert
        +-- approval required
        +-- operation result
        +-- security event
        +-- update available
        +-- recovery result
        |
        v
private NostrHost relay          (local control-plane bus, CONTROL-PLANE.md)
        |
        v
notification service              (new component: subscriber + policy + sender)
        |
        v
encrypted Nostr message           (NIP-17 private DM, NIP-59 gift-wrapped)
        |
        +--> owner
        +--> administrator
        +--> delegated operator
        +--> authorised agent
```

The notification service is a **relay subscriber**, not a new write path into
the control plane: it holds no privileged capability beyond `REQ`-subscribing
to the event kinds it cares about, and outbound connections to whichever
relays the recipient's NIP-65 list names. It never needs an inbound
Internet-accessible relay (roadmap architectural principle 17 / §18.1) —
delivery is always the service dialing *out* to a relay the recipient reads
from.

It sits alongside the other control-plane consumers, not inside them:

```text
          Portal       Admin        MCP        CLI
             \           |           |          /
              \          |           |         /
               └──── NostrHost Relay ────────┘
                          |
              +-----------+-----------+
              |                       |
        control executor      notification service
              |                       |
      YunoHost service layer   encrypted Nostr DM
```

## 3. Event classes

The seven classes from the roadmap map onto existing or already-reserved
control-plane sources — no new machinery is needed to *produce* the events,
only to *consume* them:

| class | source | today's mail-stack equivalent (from `MAIL-RETIREMENT.md`) |
|---|---|---|
| backup result | backup executor → backup-result event | row 10 (backup completion/failure mail) |
| health alert | diagnosis / health-check projector | — |
| approval required | operation-request event (kind 2200) awaiting kind 2201 | — |
| operation result | operation-execution/result events (kinds 2203/2204) | — |
| security event | security projector (roadmap §18.5; **CrowdSec** → structured event — fail2ban retired in `CROWDSEC-MIGRATION.md` P6) | — |
| update available | package/catalogue update check | — |
| recovery result | state/recovery executor (`STATELAYER.md`) | — |

Two more classes close the loop with the mail-retirement inventory and should
be added to the roadmap's list when the event protocol is finalised:

| class | source | mail-stack equivalent |
|---|---|---|
| certificate event | certificate diagnosis/renewal | row 9 (cert expiry/renewal mail) |
| system/cron notice | systemd/cron job failure | row 12 (`MAILTO=`/sendmail cron output) |

These all belong to the single "system / service / backup / security events
(regular)" custom-kind category already reserved in `NIP-MAPPING.md` §3 —
they are distinguished by a `class` tag/field, not by separate kinds, so no
new kind allocation is implied by adding them.

## 4. Notification policy

Policy determines, per roadmap §18.1: recipient npub, event classes,
severity threshold, immediate vs. summary delivery, local-only vs. external
delivery. Represented as state per §18.6:

```text
state/
└── notifications/
    ├── policy.toml
    └── recipients.toml
```

Draft shape (illustrative; finalised alongside the event-protocol kind
allocation):

```toml
# state/notifications/recipients.toml
[[recipient]]
npub = "npub1owner..."
role = "owner"

[[recipient]]
npub = "npub1admin..."
role = "administrator"
```

```toml
# state/notifications/policy.toml
[[rule]]
recipient = "npub1owner..."
classes = ["security", "recovery", "certificate"]
severity_min = "warning"
delivery = "immediate"
scope = "local-only"

[[rule]]
recipient = "npub1admin..."
classes = ["backup", "update", "system-cron"]
severity_min = "info"
delivery = "summary"          # batched, e.g. daily digest
scope = "local-only"
```

`scope = "external"` permits bridging a notification out to a relay the
recipient actually reads from (their NIP-65 list); `local-only` restricts
delivery to relays explicitly configured for this purpose. No credentials or
private keys are ever stored in this state — only npubs and policy, per the
`state/` rule in §18.6.

Changes to this state follow the standard lifecycle (§7.3/§7.8, `STATELAYER.md`):
signed request → pre-change snapshot → policy evaluation → executor → health
validation → post-change state.

## 5. Delivery

- **Wire format:** NIP-17 (private direct messages) wrapped per NIP-59 (gift
  wrap), matching the "Administrative notifications" row already recorded in
  `NIP-MAPPING.md` §1.
- **Content:** human-readable summary of the source event (class, severity,
  short description, reference to the underlying event id for anyone who
  wants to pull the full structured record). The private message is *derived
  from* the structured event, never a replacement for it — the structured
  event remains the system-of-record / audit trail (§18.1, "do not turn the
  administrative event protocol into a chat protocol").
- **Batching:** `delivery = "summary"` rules accumulate matching events and
  send a single digest DM on the configured interval; `delivery = "immediate"`
  rules send as each event arrives.
- **Failure handling:** delivery failure (recipient's relay unreachable) does
  not affect the underlying event — it stays in the relay's audit chain
  regardless of whether the notification was successfully delivered. Retries
  are the notification service's concern, not the event source's.

## 6. Relationship to mail retirement

This service is what rows 9, 10 and 12 of `MAIL-RETIREMENT.md`'s inventory
migrate onto (certificate/backup/cron mail → structured event → this
service). It must exist and be operational before Phase 2 of that document
(migrating those internal dependencies) can start.

## 7. Open items for Phase 2 (event-protocol allocation)

- Confirm the `class`/severity tag schema against whatever
  `nostrhost-control/EVENT-PROTOCOL.md` already defines for kinds 2200-2204,
  so system/service notices reuse the same tagging conventions.
- Decide the exact digest cadence default (roadmap doesn't mandate one).
- Decide whether `security` class notifications from §18.5 need a distinct
  minimum-severity default from the others, given they may indicate an
  active compromise.

## 8. Status

| Item | Status |
|---|---|
| Architecture / event class mapping (this document) | ✓ done |
| Notification policy state schema | ✓ implemented (as local TOML; `state/` wiring per §18.6 still open) |
| Notice class/severity/summary convention on kinds 2210-2213 | ✓ implemented — `nostrhost-control` `EVENT-PROTOCOL.md` §2.3, `eventmodel.Notice`/`Validate` |
| Notification service implementation | ✓ `nostrhost-notify` binary (`nostrhost-control` repo, `main`) — subscribes to the operation chain + notices, matches policy, delivers via NIP-17/59 |
| Wired to certificate/backup/cron sources (Mail phase 2) | ⏳ blocked on those subsystems actually publishing 2210-2213 events; the service itself is ready to consume them |
| Wired to a security-event source | ✓ the **security projector** (`nostrhost-securityd`, `forks/yunohost` `src/nostr_security.py`) is live: CrowdSec alert → kind-2213 `class="security"` published on the local relay. **`nostrhost-notify` is deployed and verified end to end on the testbed** (2026-09-11): a login-401 ban → 2213 (recurring `critical`) → immediate NIP-17/NIP-59 DM delivered to the configured outbound relay and unwrapped with the operator key. Deployment fixes: NIP-42 read auth (notifier key) since `ProtectedKinds` guard the notice kinds, and a persisted last-seen cursor (`state_path`, 0600) so restarts don't replay history into DMs; the relay now rejects protected kinds with the `auth-required:` prefix so go-nostr clients retry. |

No new kind numbers were needed: `update available`, `recovery result`,
`certificate event` and `system/cron notice` all ride on the existing
`2210` (system) / `2211` (service) kinds, distinguished by the `class` field
in content, per `NIP-MAPPING.md`'s "minimal custom kind surface" principle.

Open follow-ups, tracked in `nostrhost-control` and `docs/ROADMAP.md` §1.1:

- Wire `recipients.toml`/`policy.toml` through `nostrhost-state` (§18.6)
  instead of being read as plain local files.
- Add `approval`/`operation` policy classes so kind-2200 requests and
  kind-2204 results notify the admin (the classifier already emits them).
- Decide the default digest cadence and whether `security` needs a lower
  default `severity_min` than other classes (§7 above).
- Point `outbound_relays` at real relays the admin's client can reach.

Done during deployment (2026-09-11): integration test against a live relay —
`internal/notify/service_integration_test.go` boots the real relay and proves
the authenticated subscription reads a protected kind-2213, and the deployed
service was verified end to end (ban → 2213 → NIP-17/NIP-59 DM, unwrapped
with the operator key).
