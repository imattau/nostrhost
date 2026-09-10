# Portal §8 browser E2E (headless)

Proves the portal Nostr login flows in a real browser against the testbed.
See `docs/VM-TESTBED.md` for the full runbook; this directory holds the
harness used for the 2026-09-10 proof.

## Components

- `portal-e2e.py` — Playwright harness. Modes:
  - `nip07`  inject a `window.nostr` shim (dave key) and drive the NIP-07
    sign-in; the challenge GET passes through to the real server and the
    login POST is re-signed (Schnorr) then forwarded, so the real
    passwordless cookie is minted.
  - `nip46`  paste a `bunker://` URI pointing at the local NIP-46 bunker and
    drive the deployed remote-signer flow end-to-end.
  - `passkey` verify `window.NostrPasskey` loads and the "Use passkey"
    button/unlock path is reachable once a stored identity exists.
  - `launch` NIP-07 login then open the SSO-protected test app with the
    session cookie (the full portal milestone).
- `nip46-bunker.js` — minimal NIP-46 bunker (nostr-tools 2.25.2) that signs
  with the account key. Uses raw `ws` because the relay expects the flat
  `["REQ", id, {filter}]` envelope.
- `nip46-client-test.js` — standalone bunker round-trip check (no browser).

## Prerequisites on the testbed

- Playwright + chromium (`python3 -m pip install --break-system-packages playwright && python3 -m playwright install chromium`; plus the chromium system libs).
- A loopback NIP-46 relay (permissive, `allowed_kinds = [24133]`) on 7448,
  e.g. a second `nostrhost-control` instance with `allowlist_mode = false`.
- `nostr-tools` + `ws` in the bunker directory (`/opt/node22/bin/npm install nostr-tools ws`).
- The SSO CSP must include `connect-src 'self' ws: wss:` (fork
  `yunohost_sso.conf.inc`) or the browser blocks the bunker relay.

## Run

```sh
export NOSTR_TEST_SECRET=$(head -1 /tmp/login_test_key)   # dave hex secret
python3 testbed/e2e/portal-e2e.py nip07
python3 testbed/e2e/portal-e2e.py nip46     # with the bunker running
python3 testbed/e2e/portal-e2e.py passkey
python3 testbed/e2e/portal-e2e.py launch
```