# Notifications

NostrHost does not rely on email for administrative notifications — see
[`../MAIL-RETIREMENT.md`](../MAIL-RETIREMENT.md) for the wider mail-stack
retirement. Instead, platform events are delivered as **encrypted Nostr
direct messages**. Full design: [`../NOTIFICATION-SERVICE.md`](../NOTIFICATION-SERVICE.md).

## How it works

```text
NostrHost subsystem
    │
    ├── backup result        ├── operation result
    ├── health alert         ├── security event
    ├── approval required    ├── update available
    │                        └── recovery result
    ▼
private NostrHost relay        (the local control-plane bus)
    │
    ▼
nostrhost-notify                (subscriber + policy + sender)
    │
    ▼
encrypted Nostr message          NIP-17 private DM, NIP-59 gift-wrapped
    │
    ├──→ owner
    ├──→ administrator
    ├──→ delegated operator
    └──→ authorised agent
```

`nostrhost-notify` is a **relay subscriber**, not a new write path into the
control plane — it only `REQ`-subscribes to the event kinds it cares about
and dials *out* to whichever relays the recipient's own NIP-65 relay list
names. It never needs to be Internet-reachable itself.

## Configuring who gets notified about what

Notification policy is state (see [backup-and-recovery.md](backup-and-recovery.md)
for how state changes are versioned) with two files:

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

- **`classes`** filters which event categories a recipient hears about:
  `backup`, `health`, `approval`, `operation`, `security`, `update`,
  `recovery`, `certificate`, `system-cron`.
- **`severity_min`** sets the floor — anything below it is not delivered
  to that recipient.
- **`delivery`**: `immediate` sends as each matching event arrives;
  `summary` batches matching events into a single periodic digest.
- **`scope`**: `local-only` restricts delivery to relays explicitly
  configured for this purpose; `external` permits bridging a notification
  out to a relay the recipient actually reads from (their NIP-65 list).
- No credentials or private keys are ever stored in this state — only
  npubs and policy.

Changes to notification policy go through the same signed
request → pre-change snapshot → policy evaluation → executor → health
validation → post-change state lifecycle as any other configuration
change.

## What you actually receive

The encrypted DM is a **human-readable summary** derived from the
underlying structured event (class, severity, short description, and a
reference to the full event id) — it is never a replacement for the
structured event, which remains the system of record and audit trail. If a
recipient's relay is unreachable, delivery simply fails/retries; the
underlying event stays in the audit chain regardless.

## Status

The notification service (`nostrhost-notify`) is implemented and has been
verified end to end on the test VM: a login failure triggering a CrowdSec
ban produces a security event, which is delivered as an immediate NIP-17/59
DM to the configured relay and successfully decrypted with the operator
key. Wiring for certificate/backup/cron event sources is still in progress
— see the status table in [`../NOTIFICATION-SERVICE.md`](../NOTIFICATION-SERVICE.md)
for exactly what's live versus pending.

## Remote signers (NIP-46) for approvals

A DM tells an admin that approval is needed, but they still have to open the
console to sign. If an admin has a NIP-46 remote signer, the node can push the
unsigned approval to it directly, over the relays the signer already listens
on:

```bash
# preferred: pair by scanning a nostrconnect:// URI (no secret stored)
nostrhost notify signer pair --relay wss://relay.example.com

# alternative: register a bunker:// URI (carries the pairing secret; stored 0600)
nostrhost notify signer add "bunker://<signer-pubkey>?relay=wss://...&secret=..."

# after adding/removing an admin or linking/unlinking an identity
nostrhost notify sync
```

The Operations page shows whether the node pushes to your signer (and whether
any signer is registered), and its list refreshes automatically while open.

When the executor parks a request it publishes an explicit kind-2210 notice
(class `approval`); `nostr-signerd` consumes that notice and, for every
registered admin signer, sends a NIP-46 `sign_event` request for the 2201
approval to the signer's relays. The signer's owner approves on their signer,
and the node validates and publishes the returned event. The node holds only
its own `signer_client_sk` (it never signs the approval itself), and a signer
that returns an event from the wrong identity is ignored. A request that
auto-executes (the actor already has approval authority) never produces a
notice, so it is never pushed.

If no signer is registered or the signer is offline, the NIP-17 DM from the
notification service is the fallback: the admin opens the console and signs
there.

## Related reading

- [`security-model.md`](security-model.md) — where the `security` event
  class comes from (the CrowdSec projector).
- [`backup-and-recovery.md`](backup-and-recovery.md) — where `backup` and
  `recovery` events come from.
