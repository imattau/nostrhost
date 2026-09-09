# VM Testbed

The derivative is verified against an isolated, local VM built from the stock
YunoHost image before anything touches a production server. This gives a
reference "stock YunoHost" environment that every later Nostr-native change is
diffed against.

## Reference image

- `yunohost-bookworm-12.0-amd64-stable.iso` (Debian 12 Bookworm, YunoHost 12)
  is the baseline image this stage pins against.
- The live reference servers run YunoHost `12.1.x stable` on bookworm; the
  pins in `baseline/pins.yml` correspond to that stack.

## Recommended workflow (local)

1. Boot the ISO in a VM (QEMU/KVM or VirtualBox) with NAT networking.
2. Complete the YunoHost first-boot setup (admin user, domain).
3. Record a clean snapshot of the booted state — this is the **reference
   baseline** used to prove "behaves identically" at each later stage:
   `yunohost --version`, installed packages, services list
   (`yunohost service list`), diagnosis (`yunohost diagnosis run`),
   webadmin/portal smoke.
4. Snapshot before and after every derivative change so any regression is
   immediately revertible.

## Stage 1 usage

Stage 1 introduces no derivative code, so the VM is only used to (a) capture
the reference baseline and (b) run upstream's own test suites against the
pinned forks when a build pipeline exists. No fork modification is expected
or allowed in Stage 1.

## Phase 2 usage: the control plane

Phase 2 (the internal relay) is additive and is exercised on the testbed
before any fork change:

1. Build and run `nostrhost-control` on the VM with a generated operator key
   (`config.example.toml` → `config.toml`, set `operator_pubkey`).
2. Verify the local relay end-to-end with a go-nostr/nostr-sdk client:
   - publish + query a regular event (NIP-01)
   - confirm control kinds (`2200`-`2204`, `31100` …) are rejected until
     NIP-42 AUTH, then accepted for the authenticated operator
   - exercise NIP-86 as the operator (`banpubkey`, `allowkind`,
     `listallowedkinds`) and confirm the relay enforces it
   - confirm loopback-only binding (`ss -ltnp | grep <port>`)
3. Record the relay's behaviour (NIP-11 document, policy state) as the
   Phase-2 reference for later phases.

`nostrhost-control`'s own integration tests (NIP-11/42/86) run in CI
(`.github/workflows/libraries.yml`); the VM adds the "on a real host" check.

## Phase 3 usage: identity events + projection

The first fork modification (`yunohost` → `nostrhost` branch) adds the native
identity layer. End-to-end on the testbed:

1. Install the forked `yunohost` package (with `nostrhost-auth`, `coincurve`,
   `websockets`) on the VM, and run `nostrhost-control` with
   `require_auth_kinds = []` (loopback posture) + allowlist mode.
2. Configure `/etc/nostrhost/operator.toml` (operator key, control relay,
   admins) — root-only (`0600`).
3. Start `nostr-identityd` (projector).
4. Provision an identity: `nostr-identity-admin link --username matt --pubkey npub1…`
5. Verify: the relay stored the kind-31102 event (`REQ` kind 31102 returns
   it), the projector created the LDAP compat account
   (`yunohost user list` / `slapcat | grep matt`), and
   `resolve_pubkey(np1…)` returns the mapping.
6. Revoke (`nostr-identity-admin revoke --pubkey …`) and confirm
   `resolve_pubkey` no longer resolves, and the account remains in LDAP
   (revocation is of the link, not the account).

CI covers the projector/authoring logic as unit tests
(`fork-identity` job); the VM validates real LDAP account creation.

## Phase 3 operation vertical slice

The control executor (`nostr-operationsd`) proves the architectural claim —
signed Nostr events drive YunoHost through a controlled execution boundary:

```text
agent key ──2200 request──▶ relay ──policy──▶ 2201 approval ──▶ executor ──▶ safe op ──▶ 2204 result
```

The full loopback path was proven against a real `nostrhost-control` in
development (fresh relay, allowlist + NIP-86 `allowpubkey` for the agent):
grant 31100 (`server.read`) → request `system.version` → admin approval →
executor published 2203 then 2204 `{"ok": true}` → both persisted on the
relay as the audit trail; `nostr-opctl status` rendered
`REQUESTED → APPROVED → EXECUTING → DONE`. The state machine refuses any
non-legal transition even when correctly signed.

Remaining on the VM (real YunoHost in the loop):

1. Start `nostr-operationsd` (executor daemon).
2. `nostr-opctl grant --pubkey <agent> --scopes server.read` (or reuse the
   operator key as an admin agent).
3. `nostr-opctl request --tool system.version --agent-sk <agent>` then
   `nostr-opctl approve <request-id>`.
4. Verify `nostr-opctl status` shows the full chain, and — with a read-only
   tool that returns real data — that the result content matches the host
   (`app.list` should enumerate the VM's installed apps).

CI covers the engine/state machine as unit tests (same `fork-identity` job,
now 50 tests); the VM validates real YunoHost tool execution.

## Notes

- Prefer snapshots over reinstalls; reinstalling is slow and loses the
  reference state.
- Keep the VM on a private network; it is for controlled testing, not
  exposure.
- When the derivative build pipeline lands, this VM becomes the place its
  installer image is first tested (fresh install + upgrade path).