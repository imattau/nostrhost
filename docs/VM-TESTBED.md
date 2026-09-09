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

## Notes

- Prefer snapshots over reinstalls; reinstalling is slow and loses the
  reference state.
- Keep the VM on a private network; it is for controlled testing, not
  exposure.
- When the derivative build pipeline lands, this VM becomes the place its
  installer image is first tested (fresh install + upgrade path).