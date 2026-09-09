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
## VM proof results (2026-09-09, real VM)

Both Phase-3 vertical slices were exercised end-to-end on a fresh VM:
Debian 12 bookworm (KVM/libvirt) + stock YunoHost 12.1.41.2 postinstall
(main domain `nostrhost.test`, admin `ynhadmin`), with the derivative fork
overlaid on `/usr/lib/python3/dist-packages/yunohost` and
`nostrhost-control` (loopback:4848, allowlist mode, `require_auth_kinds = []`)
running as systemd services, operator key + `/etc/nostrhost/operator.toml`.

### Identity slice

- `nostr-identity-admin link --username matt --pubkey npub1jxv… --signer-type nip07`
  published a kind-31102 event; `nostr-identityd` projected it: LDAP account
  `uid=matt,ou=users,dc=yunohost,dc=org` + YunoHost user `matt@nostrhost.test`
  created; `resolve_pubkey(np…)` returned the enabled mapping.
- `nostr-identity-admin revoke --pubkey …` → `resolve_pubkey` → `None`, LDAP
  account retained (revocation is of the link, not the account); re-link
  re-enabled.

### Operation slice

Agent key grant (`nostr-opctl grant … --scopes server.read,apps.read,services.read`
→ kind 31100), agent allowlisted via NIP-86 `allowpubkey`, then for each tool
`nostr-opctl request` → `nostr-opctl approve` → chain observed
`REQUESTED → APPROVED → EXECUTING → DONE` with **real host data** in the
signed 2204:

- `system.version` → `{"ok": true, "result": {"yunohost": {"version": "12.1.41.2", "repo": "stable"}}}`
- `service.status` → `{"ok": true, "result": {"dnsmasq": {"status": "running", …}, …}}`
- `app.list` → `{"ok": true, "result": {"apps": []}}`

### Bugs surfaced by the real host (all fixed, tests added)

1. `_store()` required `db_path` but `run()` called it bare → daemon crashed at
   startup (TypeError). Added default.
2. Calling YunoHost user machinery from a daemon needs moulinette + m18n +
   `init_logging` initialised (`_init_headless_yunohost()`); otherwise the
   operation logger crashes with `'NoneType' object has no attribute 'type'`
   when `user_create` runs (only `.type` is ever read off the interface — a
   tiny headless shim suffices).
3. `service.status` results carry `datetime` objects; the 2204 content build
   (`json.dumps`) raised `TypeError` and left the chain stuck in EXECUTING.
   Event authoring now serialises via `_json_default` (datetime → isoformat).
4. The relay rejected revocation events: `validateIdentityDefinition` required
   a non-empty username even for `enabled:false`. Now only required when
   `enabled != false`.
5. Relay fresh-connect replay order is not guaranteed for same-second events;
   on a daemon restart an in-flight request could be re-evaluated before its
   grant was projected → wrongly rejected as `unauthorized`. Both daemons now
   buffer the replay until EOSE and feed a stable sort (grants before
   requests before approvals).

### VM access notes (for future runs)

- Debian genericcloud images only apply NoCloud cloud-init from a **virtio
  (scsi)** cdrom, not AHCI; `virt-install --cloud-init` deletes its seed ISO
  after defining the domain.
- YunoHost's postinstall creates its own LDAP `admin`; the cloud-init local
  `admin` user collides with it and breaks login — use a distinct local
  username (`opsuser`).
- YunoHost's sshd `AllowGroups` (ssh.main sftp.main ssh.app sftp.app admins
  root) locks out non-LDAP local users; keep root SSH keyed via
  `/root/.ssh/authorized_keys` for management access.
- YunoHost nftables (fail2ban `f2b-table`/`addr-set-sshd`) rejects the host IP
  after repeated failed SSH; unban with
  `nft delete element inet f2b-table addr-set-sshd { <host-ip> }` from the
  console.
- `yunohost tools postinstall` prompts interactively even with `--ignore-dyndns`
  (ToS + admin full name): pass `--i-have-read-terms-of-services --fullname …`
  and drive any residual prompt via `expect` over a pty.

## Identity bootstrap hardening (2026-09-10)

The VM proof used a single operator key for everything. The hardened model
splits three roles and adds an explicit bootstrap action:

- `server_sk` (machine key, signs `2203`/`2204`), `operator_sk` (primary
  admin, signs approvals/grants/identity), `admins` (accepted event authors).
- `nostrhost-bootstrap` (root) generates/imports the keys and writes
  `/etc/nostrhost/operator.toml` (0600), and can write a relay config with
  `operator_pubkey` + `server_pubkey` (the server is allowlisted as a
  *writer only*, not a relay admin).
- `is_bootstrapped()` / `_require_bootstrapped()`: pre-bootstrap the daemons
  refuse to start and the mutating CLI tools fail with a pointer to
  `nostrhost-bootstrap`; post-bootstrap authority flows through the
  configured admins.
- Legacy single-key configs still work (server key falls back to the
  operator key); `nostrhost-bootstrap --force` upgrades them.

Re-prove on the VM after hardening: regenerate the operator config with a
distinct server key, add `server_pubkey` to the relay config, restart the
daemons, and re-run the identity + operation slices.

## Minimal control executor: write operation E2E (2026-09-10)

The tool registry gained one write-capable operation, `service.restart`
(scoped `services.write`, approval-gated, bounded to a single known service
name). The executor remains the only path to machine state.

Proven on the VM through the full signed chain:

- an agent WITHOUT `services.write` is denied at the scope gate (unit-tested),
  and a non-allowlisted pubkey is rejected at the relay
- grant `services.write` → request `service.restart {"name":"dnsmasq"}` →
  admin approval → the chain ran REQUESTED(agent) → APPROVED(operator) →
  EXECUTING/DONE signed by the **server** key, result
  `{"ok": true, "result": {"service": "dnsmasq", "status": "running"}}`
- `dnsmasq` was genuinely restarted (systemd `ActiveEnterTimestamp`
  14:15:54 → 21:01:38), so the write reached real machine state.

## NIP-42 restored and proven (2026-09-10)

The loopback `require_auth_kinds = []` bypass was removed — the relay now
enforces NIP-42 on the default protected set (control kinds 2200-2204,
31100, 31102, …). The fork's clients gained NIP-42 client auth:

- `publish_to_relay` signs a kind-22242 AUTH event (operator key), waits for
  its acknowledgement, then re-sends the EVENT (ignoring the pre-auth
  rejection). khatru applies the authenticated pubkey in a per-message
  goroutine, so re-sending without waiting races the auth state.
- daemon subscribe loops and `nostr-opctl status` answer the read-side AUTH
  challenge, wait for the AUTH OK, and re-send the REQ before processing the
  replay.

Proven on the VM: an unauthenticated REQ/EVENT for a control kind is
rejected with an AUTH challenge; with auth, the identity slice (link → LDAP →
resolve) and the operation slice (service.restart through the signed chain,
server-key-signed result) both work end-to-end. Fork tests now 60.

Also during this run: the rebuilt VM disk had lost its 30G size (3G root was
100% full) — `qemu-img resize disk.qcow2 24G` + `growpart`/`resize2fs` fixed
it.
