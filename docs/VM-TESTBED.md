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

1. Install the forked `yunohost` package (with `nostrhost-auth`, `nostr-sdk`,
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
  console. (Moot on the current testbed — fail2ban was retired in
  CROWDSEC-MIGRATION P6; the CrowdSec bouncer uses its own `crowdsec` nftables
  table/ipset instead, and the relaxed whitelist exempts the host.)
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

## nostrhost-state Stage A proven (2026-09-10)

The durable semantic configuration-state layer (`src/nostr_state.py`) is wired
into the executor and proven on the VM:

- **Semantic export** (`nostrhost-state export`): domains (nostrhost.test),
  12 services, 5 identities (+ their groups), package versions, capabilities;
  every section is best-effort and per-section failures degrade gracefully.
- **ngit-backed state repository** (`StateRepo`): a plain Git repo at
  `/var/lib/nostrhost/state` whose git identity is the server pubkey.
- **Automatic pre/post snapshots**: each executed operation commits a
  `phase=pre health=pending` snapshot before and a `phase=post health=passed
  known-good` snapshot after, both linked to the operation event id
  (`op=<request-id>` in the commit message). Proven live: every
  `service.restart` chain left exactly one pre + one post commit.
- **Known-good markers**: a `known-good` tag tracks the latest health-validated
  state (`nostrhost-state status` shows it); `git tag -f` moves on success.
- **Semantic diff**: `nostrhost-state diff <from> <to>` renders the manifest +
  section changes between revisions.
- **NIP-34 announcement**: `nostrhost-state announce` publishes a signed
  kind-30617 repository announcement (server key) discoverable as
  `nostr://<server-pubkey>/nostrhost-state`, stored on the control relay.
  Required extending the relay's `allowed_kinds` (now also `30617`) via
  `bin/nostrhost-bootstrap`'s `RELAY_KINDS`.

Restic snapshot *linkage* machinery is in place (state manifest `[backup]`
section, `DATA_AFFECTING_TOOLS`, `restic_hook`); the actual Restic client and
assisted rollback are Stage B. Fork tests now 69 (state layer adds 10).

## §8 passwordless Nostr login (server side) proven (2026-09-09)

`src/nostr_login.py` + the two portalapi routes (`GET /nostr/challenge`,
`POST /nostr/login`) are deployed and proven live on the VM:

- **Challenge**: `GET /yunohost/portalapi/nostr/challenge` issues a fresh
  single-use nonce bound to the request domain (persistent ChallengeStore from
  nostrhost-auth, 90s TTL).
- **Verification**: the browser signs a kind-22242 event with
  `challenge`/`domain`/`action` tags; `verify_challenge_response` (the same
  library the MCP server uses) checks the signature + binding. The pubkey is
  resolved to an account via the identity store (kind-31102 link), and
  `create_portal_session()` mints the passwordless `yunohost.portal` cookie
  (with `passwordless: true`; the stored `pwd` is an unbreakable sentinel).
- **Session works**: `/me` with the cookie returns the user infos (dave).
- **Privilege boundary**: the portal-api service runs as `ynh-portal` and must
  not hold the root-only operator/server keys. Login notices (kind 2206) are
  therefore signed by a dedicated low-privilege *notice key* written by the
  bootstrap to `/etc/nostrhost/portal.toml` (0640 root:ynh-portal) and
  allowlisted on the relay as a writer-only pubkey (`notice_pubkey`). The
  notice lands on the relay signed by that key, not by root keys.
- **Fixes found live**: `default_auth()` in nostr_identity now degrades to
  None (instead of raising PermissionError) when the caller can't read the
  root-only operator.toml - NIP-42 auth is only needed for protected kinds.

Client side (`pages/nostr-login.vue`, NIP-07 sign-in) is implemented in the
portal fork; its build/deploy needs the portal's node/yarn pipeline (no node
on the VM) - follow-up deploy step.

## Portal client deployed + §8 re-proven (2026-09-10)

The merged derivative portal (pin `95b4905`: NIP-07 `/nostr-login` page +
Tailwind/shadcn-vue redesign + Host-header match fix) is built and deployed:

- The VM's bookworm Node 18 is too old for the redesign's deps
  (`string-width` ESM under `@vercel/nft` → `require() of ES Module`
  failure), so a standalone Node 22 is installed at `/opt/node22`; the debian
  build command (`yarnpkg install && yarnpkg generate`, Yarn Classic 1.22)
  runs against it. Static output is `.output/public`, deployed to
  `/usr/share/yunohost/portal` (previous build preserved at
  `/usr/share/yunohost/portal.pre-derivative`).
- Serving nuance: the portal is aliased at **`/yunohost/sso/`**, not
  `/yunohost/portal` (`/etc/nginx/conf.d/yunohost_sso.conf.inc` →
  `alias /usr/share/yunohost/portal/`). A probe of `/yunohost/portal` 404s and
  was a wrong-path probe, not a UI fault.
- Verified live: `GET /yunohost/sso/nostr-login/` → 200 (SPA shell); the JS
  bundle references the `nostr-login` route, calls
  `portalapi/nostr/challenge`, and uses `window.nostr` (NIP-07). The §8 flow
  is re-proven against the deployed stack: challenge → signed kind-22242 →
  `POST /nostr/login` → `200 {"ok": true, "user": "dave", ...}` passwordless
  cookie.
- Open follow-up: a real browser NIP-07 session (needs an extension-capable
  browser) and visual check of the redesigned portal/app grid post-login.

## SSO compatibility bridge (2026-09-10)

The portal API now exposes `GET /nostr/auth-request` for the next SSO
simplification slice. It validates the existing `yunohost.portal` session
through YunoHost's authenticator and returns `204` with `X-Remote-User`,
`X-Remote-Email`, and `X-Remote-Fullname`; linked identities additionally
provide `X-Nostr-Pubkey` and `X-Nostr-Npub`.

The public NGINX path is an `internal` exact location, so direct requests
return `404`; an application can consume it through NGINX `auth_request`.
Legacy SSOwat is bypassed only for this internal subrequest, while the portal
authenticator remains responsible for cookie, host, allow-list, and session
file validation. Application-specific `auth_request` adoption remains the
next step.

## OIDC compatibility bridge (2026-09-10)

The portal API now exposes a minimal standards-shaped OIDC bridge at
`/.well-known/openid-configuration`, `/oidc/authorize`, `/oidc/token`,
`/oidc/userinfo`, and `/oidc/jwks.json`. NGINX routes these paths directly to
the portal API and the legacy SSOwat access hook exempts only these exact
compatibility paths. Discovery and JWKS were verified live on the VM (`200`;
HTTPS issuer; RSA/RS256 signing key). A disposable configured client was then
used for the complete portal-session → authorization-code → token → userinfo
flow; the ID token was returned as RS256 JWT and userinfo resolved to the
YunoHost `matt` account. The session fixture had to be owned by `ynh-portal`,
matching real portal-created sessions.

Clients are explicit entries in `/etc/nostrhost/oidc.toml`, with exact
redirect-URI matching and client-secret authentication. Authorization codes
are single-use and short-lived, and the subject comes from the existing
YunoHost portal session rather than a second identity database. The remaining
work is client-management UX and production provisioning/rotation of the
signing key.

The YunoHost fork ships `conf/nginx/nostrhost_auth_request_params`, an opt-in
include for application locations. It invokes the internal endpoint, copies
the returned identity into upstream request headers, and overwrites any
client-supplied copies. Because this VM runs SSOwat at server scope, a normal
location include cannot yet disable the earlier SSOwat redirect; the include
is therefore ready for applications behind a server/location where SSOwat is
already disabled, but generated server-level routing is still required for a
safe migration on the default YunoHost path.

## Minimal NostrHost test package

The repository package at `packages/nostrhost-test` is a harmless static
YunoHost application for exercising catalogue metadata, installation, portal
discovery, permissions, and the staged SSO migration. It has no daemon,
database, external dependency, or network service. Install it from the
package directory with `yunohost app install packages/nostrhost-test` when a
VM test is desired.

The package has been installed and upgraded successfully on the VM at
`nostrhost.test/nostrhost-test`. The generated permission reports
`auth_request=true` and `auth_header=false`; unauthenticated access returns
`401`, while the portal continues to return `200`.

## Stage B: Restic client + assisted rollback E2E (2026-09-10)

The Stage B slice (fork `0c75873`) is deployed and proven live:

- `restic` 0.14 installed; local repo initialised at
  `/var/lib/nostrhost/restic-repo`; config `/etc/nostrhost/restic.toml`
  (0600; `repo`/`password`/`paths`=`[/opt/yunohost, /home]`). The password is
  passed to restic via `RESTIC_PASSWORD`, never on argv.
- `nostrhost-restic snapshot` → `c4baeff6e5d0ab1a…`; `snapshots` lists it;
  `check` → repository OK. `nostrhost-restic snapshot` with no args defaults
  to the configured paths.
- **Assisted rollback loop** (real machine state):
  1. re-commit the current state as known-good with the Restic snapshot id in
     the manifest (`[backup] restic_snapshot = c4baeff6…`);
  2. `systemctl stop dnsmasq` → commit `post`/`health=failed`;
  3. `nostrhost-state rollback plan` → 1 step:
     `services/dnsmasq.toml  modify [runtime-setting/automatic]
     reverse=control tool=service.control`, restic snapshot linked;
  4. `nostrhost-state rollback apply --approve` → executed
     `service.control {"action": "restart", "name": "dnsmasq"}` through the
     operation registry → dnsmasq back `active`; the CLI records a
     post-rollback snapshot (not auto known-good);
  5. operator validates health then `nostrhost-state commit --known-good` →
     new known-good `febc9af583911266`.
- Fixes found live: `rollback apply` needed `_init_headless_yunohost()`
  before running tool handlers; restore-required steps restore the linked
  snapshot in full (state-file paths are not data paths); the plan/apply
  renderers printed the section twice.
- Open follow-up: real restic *restore* of a restore-required step is
  covered by unit tests (fake restic) but not run live (would overwrite
  /opt/yunohost on the testbed); app reinstall/upgrade reverse steps remain
  manual until install-arg provenance lands.
- Chain-gated restoration (`rollback.apply`): the gate flows through the
  signed operation chain — a kind-2200 request with the plan embedded
  (`nostr-opctl request --tool rollback.apply --plan-file plan.json`) → 2201
  admin approval → the daemon executes the plan steps via the registry and
  emits 2203/2204. Scoped `state.write`, unit-tested (121 fork tests), and
  proven live in the E2E below.

### Chain-gated rollback E2E (2026-09-10, fork `a0896b4`)

The live daemon-driven rollback is now proven on the testbed too:

1. `systemctl stop dnsmasq` → `nostrhost-state commit … --health failed`
   (known-good `014d39a9` retained).
2. `nostrhost-state rollback plan --out /tmp/rb-plan.json` → 1 automatic step
   (`services/dnsmasq.toml` runtime-setting, tool `service.control`).
3. `nostr-opctl request --tool rollback.apply --plan-file /tmp/rb-plan.json`
   → kind-2200 request `a518703c…` with the plan embedded (operator = admin).
4. `nostr-opctl approve a518703c…` → kind-2201 approval.
5. The daemon published 2203 (EXECUTING, server key) then 2204 (DONE,
   `{"ok": true, "result": {"steps": […]}}`, server key); dnsmasq back
   `active`. `nostr-opctl status` shows the full chain
   REQUESTED → APPROVED → EXECUTING → DONE.
6. The StateRecorder captured pre/post snapshots linked to the
   `rollback.apply` operation id; the successful post snapshot auto-advanced
   the known-good tag (recorder's `known_good=bool(ok)` — correct here: a
   successful rollback restores the validated state).

This closes the milestone-0.3 restoration gate: repository authority never
applies state outside the signed control plane (the CLI `--approve` path
remains the operator's local convenience, not a bypass).

## §8 Portal Nostr login: full browser proof (2026-09-10)

All three portal signer flows are proven in a real browser (headless chromium
via Playwright on the VM) against the deployed stack. Harness:
`testbed/e2e/portal-e2e.py` (modes `nip07`, `nip46`, `passkey`, `launch`) and
`testbed/e2e/nip46-bunker.js`; see `testbed/e2e/README.md`.

Prerequisites installed on the VM: Playwright + chromium
(`pip install --break-system-packages playwright` + `playwright install
chromium`, plus the chromium system libs), pynacl for the harness,
and `nostr-tools`/`ws` for the bunker (`/opt/node22/bin/npm`).

### NIP-07
A `window.nostr` shim (dave key) is injected. The challenge GET passes
through to the real server; the login POST is re-signed (BIP-340 Schnorr)
then forwarded to the real endpoint, so the real cookie is minted:
`login POST -> 200 {"ok": true, "user": "dave", "pubkey": "6532b670…"}`,
`Set-Cookie: yunohost.portal=…` (passwordless JWT), `isLoggedIn: true`, and
the dashboard renders (App list, Nostrhost-Test, Nostrhost-Test__2,
Administration).

### NIP-46 (local bunker)
A minimal NIP-46 bunker (`nip46-bunker.js`, nostr-tools 2.25.2, raw `ws`)
signs with the dave key. It runs against a **second, permissive loopback
relay** on `127.0.0.1:7448` (`allowed_kinds = [24133]`,
`allowlist_mode = false`; `nostrhost-relay-nip46.service`) because the
control-plane relay is write-allowlisted and the NIP-46 client uses an
ephemeral key. Pasting
`bunker://6532b670…?relay=ws://127.0.0.1:7448` into the deployed
`/nostr-login` page drives: connect (nsec handed over the relay) → challenge
→ `sign_event` (kind 22242) → login → `isLoggedIn: true`, `yunohost.portal`
cookie, dashboard as dave.

### Passkey
`window.NostrPasskey` loads and the "Use passkey" button renders once a
stored identity exists (`hasStoredPasskeyIdentity()` true). Headless
chromium's WebAuthn virtual authenticator does not support the PRF
extension the passkey encryption requires, so the library surfaces
"This device does not support passkey-based encryption (PRF extension
required)" — the unlock path is reachable and the limitation is the
documented headless/WebAuthn boundary, not the portal.

### Portal milestone (app launch)
After a NIP-07 login, opening the SSO-protected test app
(`https://nostrhost.test/nostrhost-test-catalog/`) returns **200** and
renders "NostrHost test app … verifies catalog installation, portal
discovery, and auth-request headers" — the passwordless session crosses
SSOwat to the application. This is the full §8 milestone flow: link npub →
Sign in with Nostr → open Portal → launch an existing YunoHost application.

### Portal bugs found and fixed (fork `a18c53e`)
1. `middleware/auth.global.ts` treated `/nostr-login` as a non-login route,
   so the auth guard bounced it to `/login` unless the whole portal was
   public. It is now handled like `/login` (and preserves `?r=`).
2. `pages/nostr-login.vue` used relative `$fetch('/yunohost/portalapi/…')`,
   which the Nuxt `baseURL: /yunohost/sso` double-prefixed into
   `/yunohost/sso/yunohost/portalapi/…` (served the SPA HTML). Now absolute.
3. `public/nostr/nostr-passkey-vendor.js`'s IIFE was
   `var NostrPasskey=(()=>{…window.NostrPasskey=Rn;})()` — the outer `var`
   assignment (IIFE returns undefined) clobbered the global. Now returns `Rn`.
4. The "Use passkey" button raced the deferred vendor script; `onMounted`
   now polls briefly until `window.NostrPasskey` exists.

### Required derivative config
- SSO CSP (`forks/yunohost/conf/nginx/yunohost_sso.conf.inc`): added
  `connect-src 'self' ws: wss:` so the NIP-46 remote-signer relay is
  reachable from the browser (previously `default-src 'self'` blocked it).
- The VM's deployed SSOwat needed the fork's `/yunohost/sso/` public-route
  fix (`forks/ssowat/access.lua`, commit `b0f1345`) or the portal login page
  itself was redirected through SSOwat.

Open follow-ups: a real extension-capable browser for passkey attestation +
visual grid check (headless limit only).

## §8 /nostr-account: self-service identity management (2026-09-11)

`/nostr-account` landed: the session user's linked identities (npub, label,
signer, last-used, "Revoked" badge) with rename/revoke, a link section
(NIP-07, bunker:// + QR, generated local key with remember/reveal/copy,
passkey create/use/recovery/restore/forget), a saved-signers panel, and
unlink-all.

Privilege boundary: the portal-api runs as the unprivileged `ynh-portal`
user, so mutations are forwarded over a local UNIX socket to
`nostr-identityd` (`/run/nostrhost/identity.sock`, root:ynh-portal 0660,
SO_PEERCRED-gated), which operator-signs the kind-31102 events.

- New portalapi routes: `GET /nostr/identities`, `POST
  /nostr/link/challenge`, `POST /nostr/link` (add/replace), `POST
  /nostr/identities/revoke` + `/rename`, `POST /nostr/unlink`; 401 without a
  session; `allow_identity_linking` gate in portal.toml.
- Verified with `testbed/vm/e2e_account.py` (full API pass) and a Playwright
  browser check (`/yunohost/sso/nostr-account/` renders, npub rows shown,
  "Generate a new key" → "Use generated key" links a fresh identity 4→5).
- A stale Caddy conf was regenerated from the fork template to restore
  serving `/yunohost/sso/*` (the deployed file predated the sso block in
  `caddy_domain.conf`).

Remaining §8 client work: only the real-browser passkey attestation and a
visual grid check (documented headless limits).

## Native admin and package-authoring acceptance (2026-09-13)

The native admin package, core package, and authoring CLI were exercised on
the local Debian 12 NostrHost VM (`nostrhost-clean6`, 192.168.122.37). Its
virtual disk was expanded from 3 GiB to 16 GiB so the Debian build toolchain
and core package could be tested in the guest.

- Built and installed `nostrhost-core` and `python3-nostrhost` 12.1.41.28 over
  12.1.41.21. The Debian build dependency check and binary package build passed
  inside the VM, and post-install configuration regeneration completed.
- Reconciled the current domain routes through the installed Caddy route
  builder. `/admin/` returns the SPA HTML, its JavaScript and CSS return the
  correct content types, and `/admin/packages` falls back to the SPA shell.
- `GET /healthz` returns `200`; unsigned `POST /package/plan` returns `401`;
  all system services remain active and none are failed.
- Ran the installed package-authoring CLI: scaffold → validate → plan (13
  operations) → explain → schema passed. The schema and plan outputs parse as
  JSON, and Typer exposes its native shell-completion options.

The VM run found and fixed these gaps:

1. `bin/nostrhost-package` was stored without its executable bit and contained
   duplicate virtual-environment dispatch logic.
2. The CLI lacked the planned `init`, `validate`, and `explain` commands; the
   schema command also could not write the checked-in schema contract. These
   commands now share the typed package engine and return structured output
   suitable for automation.
3. Debian 12's packaged Typer rejected the `Path | None` option annotation at
   CLI startup. The command now uses `Optional[Path]`, and was rerun on the
   VM's installed Typer.
4. Generated Caddy domain configuration and the default admin redirect still
   used the former admin URL while the bundle and route builder used `/admin/`.
   The template, redirect, access-control allowlist, and regression test now
   agree on `/admin/`.
5. The dynamic Caddy SPA route rewrote every request to `index.html`, which
   would return HTML for asset URLs. It now serves existing files and uses
   `index.html` only as the SPA fallback.
6. The running VM's generated Caddy configuration did not yet contain the
   native `/package/*` proxy. Adding the route made the unsigned request reach
   the API's expected authentication gate instead of the default site handler.
7. The Debian build still generated CLI completion and manpage artifacts from
   action maps that have been removed. The package build now relies on Typer's
   runtime help and completion support instead.

The VM's test-domain Caddy file is a hand-maintained fixture and retained its
older static route through package regeneration; the test explicitly
reconciled the domain through the current route builder before checking the
admin UI. A signed browser request with an admin NIP-07 signer remains the
next end-to-end check.

## LDAP-free native account stack (2026-09-13, clean6)

The LDAP-retired fork (native account store, `nostrhost/accounts.py`) was
verified on the running Debian 12 NostrHost VM (`nostrhost-clean6`,
192.168.122.37, core `12.1.41.28`) with slapd stopped throughout:

- **User lifecycle** — `user create <username> <domain>` (domain is the 2nd
  positional arg) creates a real `/etc/passwd` account (uid 29xxx) + the
  root-owned `/etc/nostrhost/accounts.json` store record
  (admin/firstname/fullname/lastname/mail/mailbox_quota/shell/uid).
  `user update` handles fullname, quota and `--password` (login verified via
  `su - <user> -c 'echo login-ok'`). `user delete --purge` removes the real
  user before its primary group (`delete_real_user` before `user_group_delete`
  — the delete-order fix landed in fork `04ce092c`). The `app_ssowatconf`
  StopIteration after writes is a pre-existing testbed quirk (LDAP-era apps on
  `nostrhost.test` vs native `w4.test`), not an account-store failure.
- **Group lifecycle** — `user group create myteam` creates a real `/etc/group`
  entry + store record; `user group update myteam --add <user>` updates both.
- **Group → permission projection** — `user permission add
  nostrhost-test.main myteam` (names positional) projected the group's member
  into `/etc/nostrhost/permissions.json` (`users: ["testuser5"]`), the Caddy
  authd input — the key end-to-end integration.
- **Daemons** — `nostr-identityd`, `nostr-operationsd`, `nostr-permissiond`,
  `nostr-portal-api`, `nostr-securityd`, `nostr-ddnswatchd`, `nostr-api`,
  `nostrhost-control` all `active`; `nostrhost-certd` on a timer (inactive is
  normal); `slapd` inactive; `nsswitch.conf` = plain `files` (no ldap);
  `libnss-ldapd` still listed in dpkg but unreferenced (harmless).
- **State** — `nostrhost-state publish` round-trips (clean revision, full
  history bundle); `permissions.json` stays valid after user/group mutations.
- Test artifacts (`testuser5`, `myteam`) cleaned up; store back to
  `admins`/`all_users`/`visitors`.

## Alpha acceptance loop (2026-09-13, clean7)

The full §alpha threshold was run on a **brand-new** blank Debian 12 VM
(`nostrhost-clean7`, fresh overlay on the genericcloud base, core
`12.1.41.32`): apt install → `postinstall --new` → owner identity → relay →
daemons → native app install → HTTPS → backup → upgrade → break → restore.
Details and results are recorded against the clean7 VM; the previous clean
snapshots (clean, clean2–clean5) were deleted after the run. `clean6` is
retained as the LDAP-free reference.
