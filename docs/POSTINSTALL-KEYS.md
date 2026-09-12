# Postinstall Key Generation, Safe-Keeping and Restore

> Working spec for the postinstall key work. Plan/status is tracked in
> `ROADMAP.md` §19 (native bootstrap) and §27 (secrets / key lifecycle).

## Problem

`postinstall --new` currently generates **three** keys (server, operator,
notice) via `bootstrap_node()`, writes them to root-only config, and shows only
npubs/pubkeys in its summary. Two things are wrong for a shippable alpha:

1. **No safe keeping** — the secret keys are never presented to the installer
   (no show-once bundle, no recovery file, no export), so a fresh node's keys
   exist only on-disk at `/etc/nostrhost/operator.toml` / `portal.toml`. They
   cannot be recovered from ngit state (secrets never live there).
2. **Incomplete key set** — the platform expects a catalogue **publisher** key
   (`catalog.publish`, MCP transition Phase 5) and a **notifier** key
   (`nostrhost-notify` requires `notifier_private_key`, distinct from
   server/operator). Neither is generated or configured today.

## Decisions (2026-09-13)

- Dedicated **publisher** key (not the operator key); publisher is a
  writer-only relay identity, never a NIP-86 admin.
- Generate the **notifier** key too.
- Publisher/notifier keys live in `operator.toml` (root-only) alongside
  server/operator; `notify.toml` and `catalogue.env` are rendered from them.
- Safe keeping: **print the five `nsec1` keys once** at install AND write a
  root-only `/etc/nostrhost/keys.recovery` file. No export command.
- Restore: **all five keys are required** (no fallback to the operator key),
  accepted as 64-hex **or** `nsec1...`, or loaded in one shot via
  `--keys-file PATH`.

## Key inventory (post-change)

| Key | Role | Storage |
|---|---|---|
| `operator_sk` | primary admin / owner — approvals, grants, identity defs | `operator.toml` (0600) |
| `server_sk` | server machine key — signs execution events 2203/2204 | `operator.toml` (0600) |
| `notice_sk` | portal low-privilege notice key | `portal.toml` (0640, ynh-portal) |
| `publisher_sk` | catalogue publisher — signs catalogue declarations | `operator.toml` (0600) |
| `notifier_sk` | notification service — reads notices, sends NIP-17 DMs only | `operator.toml` (0600); `notify.toml` rendered with `notifier_private_key` |

Security posture: operator = admin (NIP-86 authority); server/notice/publisher =
allowlisted writers only; notifier = read-notices + send-DMs only. All five are
allowlisted on the control relay.

## Changes

### 1. Fork — `src/nostr_identity.py`

- `bootstrap_node()` gains `publisher_sk` / `notifier_sk` params (default
  `_gen_sk()`), validates all five hex64, writes them into `operator.toml`,
  writes `publisher_pubkey` into the relay config (`write_relay`), and returns
  all five sk/pubkey pairs.
- `OperatorConfig` gains `publisher_sk` / `notifier_sk` (consumed by the
  future `catalog.publish` op and restore).

### 2. Fork — `src/nostrhost/cli.py`

- `_normalize_sk(value)`: 64-hex or `nsec1...` (via
  `nostrhost_policy.auth.npub.nsec_to_hex`), else raise.
- `_render_notify_config(notifier_sk, relay)`: writes `/etc/nostrhost/notify.toml`
  (0600) with `notifier_private_key`, `relay_url`, and absolute
  recipients/policy/state paths under `/var/lib/nostrhost/state/notifications/`.
- `_render_catalogue_env(publisher_pubkey)`: writes `/etc/nostrhost/catalogue.env`
  (0600) with `NOSTRHOST_CATALOG_PUBLISHERS`, relays, state path.
- `_postinstall_new`: after bootstrap, render both configs, then print the
  five-key `nsec1` recovery bundle once (labelled store-offline) and write
  `/etc/nostrhost/keys.recovery` (0600 TOML). JSON summary stays pubkeys-only.
- `_postinstall_restore`: all five `--*-sk` required (no operator fallback),
  `--keys-file PATH` alternative; normalize hex/nsec1; render both configs.
- CLI: `postinstall restore` gains `--server-sk`, `--notice-sk`,
  `--publisher-sk`, `--notifier-sk` (required) and `--keys-file`.

### 3. Control plane — `libs/nostrhost-control`

- `internal/config/config.go`: add `PublisherPubkey string \`toml:"publisher_pubkey"\``.
- `internal/relay/server.go` `New()`: `pol.Allow(cfg.PublisherPubkey, "publisher")`
  (writer-only, mirrors server/notice).

### 4. Tests

- `test_bootstrap_node_generates_three_keys` → five keys; relay asserts
  `publisher_pubkey`; operator.toml asserts `publisher_sk`/`notifier_sk`.
- New: nsec1 acceptance in `_normalize_sk`; `keys.recovery` round-trip; notify/
  catalogue rendering (notify config never contains operator/server keys);
  restore requires all five.

### 5. Docs

- ROADMAP §19: five-key bootstrap + recovery bundle.
- ROADMAP §27: key inventory + safe-keeping (show-once + `keys.recovery`) +
  recovery (explicit flags or `--keys-file`).

## Verification

- Fork suite green + flake8/mypy.
- VM: `--new` prints bundle + writes `keys.recovery`; `--restore --keys-file`
  recovers; relay allowlists five keys; `catalogue.env` + `notify.toml` present.

## Notes

- `keys.recovery` is the full machine identity (0600, store offline); a leak
  means node takeover — warn in the bundle.
- `catalog.publish` (MCP Phase 5) reads `publisher_sk` from `operator.toml`.
- Confirm `nostrhost-notify.service` packaging wires `-config /etc/nostrhost/notify.toml`
  (tracked under alpha W2).