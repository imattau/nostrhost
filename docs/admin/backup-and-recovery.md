# Backup and disaster recovery

NostrHost separates **who changed something**, **what should exist**,
**what data existed**, and **what is actually running** into four distinct
layers. Understanding that split is the key to understanding backup and
recovery. Full design: [`../STATELAYER.md`](../STATELAYER.md).

```text
Nostr events            → WHO changed it?     (identity, authority, audit)
ngit / NIP-34 + Git      → WHAT should exist?  (durable semantic config state)
Restic                   → WHAT data existed?  (application/filesystem data)
Linux / YunoHost         → WHAT is running?    (actual runtime state)
```

## Configuration state (ngit / NIP-34)

Server configuration — not application data — is tracked as a git
repository whose identity, ownership and discovery align with Nostr
identities via **NIP-34**:

```text
Server npub
    │
    ▼
NIP-34 repository announcement (kind 30617)
    │
    ▼
nostrhost-state              nostr://<server-npub>/nostrhost-state
    │
    ├── signed repository state
    ├── PRs / patches (e.g. from an agent proposing a change)
    └── CI results
    │
    ▼
Git objects
```

The repository stores **semantic intent** ("nginx should be enabled"), not
a raw copy of `/etc` and not runtime observation ("nginx is running" is
Linux/systemd's job, not this layer's):

```text
state/
├── manifest.toml
├── system/
├── apps/
├── domains/
├── services/
├── network/
├── dns/
├── certificates/
├── identities/
├── capabilities/
├── backups/
├── schedules/
└── package-versions/
```

Secrets are never stored in plaintext here — state references secret
identifiers backed by systemd credentials or a dedicated encrypted store.

### Every change gets a pre/post snapshot

```text
operation request → pre-change snapshot → execute → post-change snapshot → health validation
```

Each state commit is linked to the Nostr operation event that caused it, so
history reads as an audit trail, not just a diff log:

```text
A  known-good state
B  install Alby Hub
C  reverse-proxy change
D  permission update
```

### Known-good state and rollback

NostrHost tracks a validated **known-good** state distinct from the current
desired state:

```text
main       → current desired state
known-good → latest health-validated state
previous   → previous accepted state
```

Rollback is **assisted**, not a blind `git revert` — different change
classes have different reversibility:

| Change class | Example | Automatic rollback |
|---|---|---:|
| Declarative config | firewall rule, service enabled | Usually |
| Runtime setting | systemd unit state | Usually |
| Package install | new app | Often |
| Package upgrade | version bump | Conditional |
| Database migration | schema change | Only with a known procedure/backup |
| Data deletion | app removal | Restore required |
| External side effect | DNS API, payment, external message | Often impossible |
| Credential rotation | replace key | Special handling |

The rollback flow: select a previous state → show a semantic diff →
generate a rollback plan → policy/approval → execute → health check.
`rollback.apply` runs as a policy-gated chain operation (`state.write`
scope + admin approval), restoring via the linked Restic snapshot where
data is involved.

## Application data (Restic)

Git/ngit is configuration-state history — it is **not** a data backup
system. Application and filesystem data recovery is **Restic**'s job. For
any operation that can affect app data, the configuration-state commit and
the data snapshot are linked:

```text
pre-change state commit S1
        │
        ├──→ Restic snapshot R1
        ▼
     execute
        ▼
   health check
```

A machine-readable manifest records the relationship:

```toml
[state]
schema = 1
known_good = true

[operation]
event = "<nostr-event-id>"

[backup]
restic_snapshot = "<snapshot-id>"
required = true

[health]
result = "passed"
```

This produces a single restore point that describes **both** the intended
configuration **and** the associated data — restoring one without the
other would leave the server in an inconsistent state.

## Full disaster recovery

A server rebuilt from nothing but its own identity, its published state
repository, and its Restic backup:

```text
new machine
    │
install NostrHost
    │
restore / authorise server identity
    │
discover NIP-34 state repository
    │
retrieve latest known-good state
    │
retrieve linked Restic snapshot
    │
install required apps/packages
    │
restore application data
    │
reconcile configuration
    │
validate
```

This is what `nostrhost postinstall --restore` automates (see
[`../guide/getting-started.md`](../guide/getting-started.md)). The state
repository is published outbound from the local relay to external Nostr
relays specifically so it can be rediscovered after total loss of the
original machine — no central git forge is authoritative.

## Repository authority is not operational authority

A change proposed through the state repository (by a human or an agent)
**never bypasses policy**:

```text
NIP-34 change → verify repository authority → NostrHost policy →
risk classification → approval if required → executor / reconciler
```

ngit establishes *who proposed this state and where it came from*;
`nostrhost-policy` still decides whether it may actually be applied to the
machine.

## Status

The design is staged (Stage A: state history — done; Stage B: assisted
rollback with Restic linkage — done; Stage C: ngit replication/DR — outbound
publication implemented; Stage D: full automatic declarative reconciliation
— deliberately not yet enabled). See
[`../STATELAYER.md`](../STATELAYER.md) §8.9 for the staged rollout and
[`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) for what's proven end-to-end on a
test VM today versus still in progress.

## Related reading

- [`../guide/getting-started.md`](../guide/getting-started.md) — the
  `postinstall --new`/`--restore` flow from a user's perspective.
- [`security-model.md`](security-model.md) — how proposed state changes are
  authorised before being applied.
- [`../VM-TESTBED.md`](../VM-TESTBED.md) — exercising install/backup/restore
  end-to-end on a disposable VM before relying on this in production.
