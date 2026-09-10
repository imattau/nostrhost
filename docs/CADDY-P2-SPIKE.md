# Caddy P2 spike — ACME issuance, renewal and cert export

Status: passing. Branch `feat/nginx2caddy` (base `main`).

Proves the P2 slice of [CADDY-MIGRATION.md](CADDY-MIGRATION.md): Caddy owns ACME
issuance + renewal, and `nostr_certd` exports Caddy's certificates into the
standard `/etc/yunohost/certs` store so non-web consumers keep working. The VM
has no public DNS, so the Let's Encrypt test CA
([Pebble](https://github.com/letsencrypt/pebble)) stands in for LE on loopback —
which exercises Caddy's *real* ACME code path (order/challenge/finalize/renew).

## Layout

```
testbed/caddy-p0/pebble/
  build-pebble.sh        # host-side: go install pebble@v2.10.1 -> ./pebble
  setup-certs.sh         # openssl: Pebble CA + HTTPS endpoint cert + trust store
  pebble-config.json     # httpPort 8080 (HTTP-01 hits Caddy's listener), 5-min certs
  pebble.service         # systemd unit (PEBBLE_VA_NOSLEEP / WFL_NOSLEEP)
  caddyfile.acme-test    # the validated Caddyfile (Pebble CA, storage, yunohost.org)
  deploy.sh              # VM orchestrator (trust, hosts, units, Caddyfile swap)
```

Supporting code that landed in the yunohost fork:

- `src/nostr_certd.py` — exporter daemon (see below)
- `conf/yunohost/nostrhost-certd.service` + `.timer` — oneshot every 5 min

## How it was validated (nostrhost.test VM)

1. **Pebble** runs as `pebble -config /etc/pebble/pebble-config.json` on
   `0.0.0.0:14000` (ACME) with a 5-minute `profiles.default.validityPeriod` so
   renewal is observable in-session. Its VA does HTTP-01 against `:8080`
   (Caddy's `http_port`), resolving `nostrhost.test`/`yunohost.org` to
   `127.0.0.1` via `/etc/hosts`, so validation never touches nginx on 80/443.
2. **Caddy** (`caddyfile.acme-test`): global `storage file_system
   { root /var/lib/caddy }` + `acme_ca https://127.0.0.1:14000/dir`; the Pebble
   CA was added to the system trust store so Caddy accepts the endpoint.
3. **Issuance**: `caddy reload` does not obtain immediately — Caddy issues
   lazily on the first TLS handshake, so
   `curl -k --resolve nostrhost.test:8443:127.0.0.1 https://nostrhost.test:8443/`
   triggers the order. Log confirms `http-01` challenge served on `127.0.0.1`,
   `authorization finalized` → `certificate obtained successfully`, stored at
   `/var/lib/caddy/certificates/127.0.0.1-14000-dir/<domain>/<domain>.{crt,key,json}`.
4. **certd export**: `python3 -m yunohost.nostr_certd --once` writes a new
   generation under `/etc/yunohost/certs/<domain>-history/<ts>-caddy/` and
   atomically re-points the `<domain>` symlink, mirroring
   `certificate.py::_enable_certificate` minus the retired nginx/dovecot
   restarts. It restarts slapd and fires `hook_callback("post_cert_update")`.
5. **Renewal**: Pebble certs live 5 minutes but Pebble's renewal-info tells
   Caddy `recheck_after` ≈ 6 h, so natural auto-renewal is slow here. The
   deterministic renewal test drops the stored cert, restarts Caddy and
   re-handshakes; Caddy obtains a fresh cert and certd re-exports a new
   generation (idempotent second pass is a no-op).
6. **slapd (LDAP) is the proof consumer**: after the export it serves the
   *newest* Caddy-owned cert on `:636` (`openssl s_client`). OpenLDAP caches the
   TLS material at process start, so certd *restarts* slapd (`systemctl reload`
   alone does not pick up a rotated cert).

## Findings worth recording

- **`acme_ca` is a global option**, not a `tls` subdirective (a `tls { acme_ca … }`
  block fails `caddy adapt`).
- **Caddy issues lazily**; a handshake (or `caddy renew` equivalent traffic) is
  what triggers the first obtain.
- **`systemctl restart caddy` reverts to the unit's `--config` path** — the
  active `/etc/caddy-p0/Caddyfile` must be the ACME variant for reload/restart
  to agree (the P1 file is kept as `Caddyfile.p1`).
- **certmagic JSON is metadata only**; the current cert is the `.crt`/`.key`
  pair in the domain dir, so the exporter keys off file fingerprints.
- **`_get_status`/`certificate_status` keep working unchanged**: they read
  `/etc/yunohost/certs/<domain>/crt.pem`, which certd maintains. (For the
  5-minute test certs `_get_status` reports `validity: 0`/`expired` — an
  integer-days artifact of the short lifetime, not an exporter bug.)
- The legacy issuance path (`_certificate_install_letsencrypt`,
  `certificate_renew`, `_fetch_and_enable_new_certificate`, `vendor/acme_tiny`,
  self-signed issuance) is left intact-but-superseded; deletion is deferred to
  the P5/P6 retirement, after domain/ACME policy moves into Caddy.

## Gate

- A certificate is **obtained** via the real ACME flow (Pebble standing in for
  Let's Encrypt, HTTP-01 on loopback). ✔
- A certificate is **renewed** (fresh order + re-export + slapd re-serve). ✔
- The only non-web consumer (**slapd**) serves the exported Caddy-owned
  certificate over LDAPS. ✔
- Portal e2e sanity (nip07) still green against Caddy `:8443` with the
  Pebble-issued cert. ✔