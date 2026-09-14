# Nsites Phase 0 spike harness

Runs the **pinned upstream** `hzrd149/nsite-gateway`
(`558326ae5bbaf209e63d5a3e53b6bbad508b336a`, v3.6.5) as a plain Deno process
(no Docker) behind Caddy, against a local fake relay and fake Blossom, and
records its behaviour on the conformance corpus and a real site.

See `docs/NSITES-DECISION-RECORD.md` §0.4 for the results and §0.5 for the
D1–D3 outcome. Prerequisite decisions: implementation plan §2 (D1–D9).

## Components

| File | Role |
|---|---|
| `build-gateway.sh` | Clone the pinned upstream at `upstream/nsite-gateway` and `deno cache` its deps |
| `run-gateway.sh` | Run the gateway with local relay/blossom/`PUBLIC_DOMAIN` env |
| `Caddyfile` | Gateway origin: `sites.nostrhost.test` + `*.` with `tls internal` (local CA), `:8443` |
| `fake-relay.py` | Minimal NIP-01 relay; seeds the corpus + generated manifests |
| `fake-blossom.py` | Minimal BUD-01/02 blob server; serves by sha256, supports a tamper file |
| `make_site.py` | Builds a real site, signs root/named/snapshot/private-hint manifests, seeds relay + blobs |

## Prereqs

- Deno 2.7.7 (`curl -fsSL https://deno.land/install.sh | sh` or the release zip)
- Python 3.11+ with `websockets` and `nostr-sdk` (for `make_site.py`)
- Caddy 2.9+ (the VM's NostrHost Caddy, or a stock binary)
- `git`

## Run

```bash
./build-gateway.sh                                   # clone pin + deno cache
python make_site.py                                  # site/, seed/, blobs/, tamper/
python fake-blossom.py --port 8787 --blobs blobs --tamper tamper &
python fake-relay.py --port 7777 --seed seed \
    --seed ../../tools/tests/nsites/corpus &
DENO_BIN=deno ./run-gateway.sh --port 3000 &
caddy run --config Caddyfile --adapter caddyfile &    # :8443, tls internal
```

`make_site.py` prints the spike addresses (root/named/snapshot/private). On the
VM bind Caddy on :443 instead of :8443 and point `run-gateway.sh` at the host's
Caddy.

## Observed results (2026-09-14, local Debian 12 host, Deno 2.7.7, Caddy 2.11.4)

TLS: `curl -ks --resolve <host>:8443:127.0.0.1 https://<host>:8443/...`.

| Check | Result | Notes |
|---|---|---|
| Root `/`, `/index.html`, `/about.html` | **200** | Correct blobs, `Content-Type: text/html` forwarded from Blossom |
| Root `/missing` | **404** | Serves the site's `/404.html` (`conformance 404`) |
| Named `blog` `/` | **200** | Correct named-site index |
| Snapshot `/` | **200** | Resolved by event id; `a`/`x` snapshot works |
| Apex `sites.nostrhost.test` `/` | **200** | Gateway host index (landing page) |
| Apex `/status` | **200** | **Public** page enumerating "Known sites" — disclosure surface |
| `ETag`, `Cache-Control` | present | `ETag: W/"<sha256>"`, `Cache-Control: public, max-age=3600` |
| `Set-Cookie` | **absent** | No cookies on the gateway origin |
| Traversal `/../etc/passwd`, `/..%2f..`, `/%2e%2e/`, `//`, `\`, `%00` | **404** | All hostile paths rejected |
| Bad label `bogus.`, 64-char label, unknown npub | **404** | No upstream fetch |
| `/nostrhost/admin`, `/package/session`, `/.well-known/nostr.json` | **404** | Gateway origin serves none of NostrHost's own paths |
| Restart with warm cache | root **200** | Deno KV cache persisted; site served after restart |
| Private-IP `server` hint (`http://127.0.0.1:9`) | **404** after a fetch attempt | Gateway **does attempt** private-address fetches (SSRF gap → Phase 2) |
| Hash mismatch (Blossom returns wrong bytes) | **1st request 200 with wrong bytes**, later **502** | See finding below |
| Control relay `:4848` | not configured, not contacted | `NOSTR_RELAYS`/`LOOKUP_RELAYS` only `ws://127.0.0.1:7777`; no `:4848` connection |

### Findings

1. **Hash verification is not blocking (verify-after-serve).** On the first
   request for a blob a compromised/malicious Blossom server returned the wrong
   bytes; the gateway streamed them to the client as **200** and only logged
   `[nsite:blossom:invalid-blob] Invalid blob from … expected sha256=… actual
   sha256=…` afterwards (4 ms response, verifier message later). Subsequent
   requests are correctly rejected (502) and the bad-source record survives a
   restart. NIP-5A says a host "SHOULD treat the site as not found" on a hash
   mismatch, and the implementation plan §2/§4.1 requires **verify before any
   byte is served**. The upstream gateway does not meet that bar as-is; this is
   a Phase 2 requirement for the native component, and evidence for D1.
2. **Private-address fetches are attempted.** A manifest whose only `server`
   hint is `http://127.0.0.1:9` was fetched (fast refusal → 404). The gateway
   does not block loopback/RFC1918/link-local destinations. Phase 2's SSRF
   policy (resolve-time rejection, redirect re-check) is required.
3. **Permissive CORS on site responses.** Responses carry
   `Access-Control-Allow-Origin: *` and `Access-Control-Expose-Headers: *`.
   Fine for public static content, but it is a blanket policy on the gateway
   origin, not a per-response decision.
4. **Public `/status` and apex host index.** The gateway exposes a status page
   listing known sites on the public origin. NostrHost should keep status on a
   separate origin/path (implementation plan §3.1); this is a deliberate
   upstream product choice, not a bug.
5. **Replaceable-event tie-break is unspecified.** Seeding several kind
   `15128` events for one pubkey with equal `created_at` (as the conformance
   corpus does) made root resolution pick an arbitrary one. The spike site was
   given a newer `created_at` to disambiguate. Worth a defined tie-break rule
   in the native resolver.

## Not exercised in this pass

- `MAX_FILE_SIZE` (default 2 MB) and request-rate limits.
- CNAME custom-domain resolution.
- `10063` (BUD-03) discovery ordering (server tags were always present).
- Multiple Blossom fallback ordering under partial failure.
