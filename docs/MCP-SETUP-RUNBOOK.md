# MCP Endpoint Setup Runbook (testbed / self-hosted)

A step-by-step record of bringing the NostrHost MCP endpoint up behind Caddy
on a testbed node, publishing a native package to the catalogue through it,
and wiring the connect client to reach it. Written from the 2026-09-13 VM
proof so an end user (or a future automation script) can reproduce the whole
path without rediscovering the issues below.

Two code bugs were found and fixed while doing this — see the commits in
`forks/yunohost` (`catalog: pass --relay before the publish subcommand`) and
`libs/nostrhost-mcp` (`http: allow reverse-proxy Host headers + fix body
replay`). They are **not** reproduced here; this document is the operational
path only.

Reference environment:

- VM at `192.168.122.174`, serving the `nostrhost.test` domain (Caddy)
- `nostrhost-mcp` installed into `/opt/nostrhost/venv`
- Client: the `yunohost-mcp-connect` bridge (hosts file + key)
- Goal: `https://mcp.nostrhost.test/mcp` reachable, NIP-98 authenticated, and
  `catalog.publish` usable against it

---

## 1. Architecture

```text
client (opencode / yunohost-mcp-connect)
   │  NIP-98 Authorization per request
   ▼
https://mcp.nostrhost.test/mcp     (Caddy: tls internal)
   ▼  reverse_proxy (loopback)
nostrhost-mcp serve --http 8930    (loopback only, NIP-98 middleware)
   ▼
signed kind-2200 request
   ▼
control relay ws://127.0.0.1:4848  (nostrhost-control)
   ▼
nostr-operationsd                   (authorize, execute, 2201/2203/2204 chain)
```

The adapter binds loopback by design (`docs/MCP-TRANSITION.md §7`); Caddy is
the only way a remote client reaches it.

---

## 2. Server side: nostrhost-mcp on the node

1. Install the adapter package (it provisions `/opt/nostrhost/venv` with the
   MCP SDK wheels via `nostrhost-runtime` and installs the adapter into it):

   ```bash
   apt install python3-nostrhost-mcp
   ```

   (Manual/development path: `pip install "mcp[cli]>=2.1.1" "nostr-sdk>=0.45.1"`
   into the venv and copy the `nostrhost_mcp` source tree into the venv
   site-packages.) The adapter needs the installed fork
   (`yunohost.nostr_operations`), `nostrhost-policy`, and a running control
   relay + `nostr-operationsd`.

2. The package ships `nostrhost-mcp.service` (loopback HTTP on 127.0.0.1:8930)
   but does not auto-enable it. To run it under the public endpoint, set the
   proxy Host name in `/etc/nostrhost/mcp.env`:

   ```bash
   echo 'NOSTRHOST_MCP_ALLOWED_HOSTS=mcp.nostrhost.test' > /etc/nostrhost/mcp.env
   chmod 600 /etc/nostrhost/mcp.env
   systemctl enable --now nostrhost-mcp
   ```

   Without `NOSTRHOST_MCP_ALLOWED_HOSTS`, the MCP SDK's DNS-rebinding
   protection rejects proxied requests with 421 (see Issue 2).

3. Verify the tool catalogue before serving:

   ```bash
   /opt/nostrhost/venv/bin/nostrhost-mcp list-tools
   ```

4. Run it over loopback HTTP (equivalent of what the unit does):

   ```bash
   /opt/nostrhost/venv/bin/nostrhost-mcp serve --http 8930 \
       --http-allowed-hosts mcp.nostrhost.test
   ```

   `--http-allowed-hosts` is **required** when any reverse proxy fronts the
   adapter. See Issue 2 below for why.

5. Confirm the listener:

   ```bash
   ss -tlnp | grep 8930
   # unauthenticated request must return 401, not 421/000
   curl -s -o /dev/null -w "%{http_code}\n" \
       -X POST http://127.0.0.1:8930/mcp -H "Content-Type: application/json" -d '{}'
   ```

---

## 3. Caddy route + DNS + TLS

1. Caddy config (one per node, e.g. `/etc/caddy/conf.d/mcp.nostrhost.test.conf`):

   ```caddyfile
   mcp.nostrhost.test {
       tls internal
       reverse_proxy 127.0.0.1:8930
   }
   ```

   Do **not** wrap it in a global `{ ... }` block — this Caddy's `Caddyfile`
   imports `conf.d/*.conf` after its own global options block, so a second
   global block breaks adaptation ("server block without any key is global
   configuration, and if used, it must be first").

2. Validate and reload:

   ```bash
   caddy validate --config /etc/caddy/Caddyfile
   caddy reload --config /etc/caddy/Caddyfile
   ```

3. DNS — the node itself must resolve its own name (Caddy issues the cert
   against it), and the client must resolve it too:

   - node: `echo "127.0.0.1 mcp.nostrhost.test" >> /etc/hosts`
   - client host: `echo "<node-ip> mcp.nostrhost.test" >> /etc/hosts`

   (On the testbed the node is reached directly by IP, so `/etc/hosts` on the
   client is the DNS; in production point a real A record at the node.)

4. The internal cert is signed by Caddy's local CA. The client must trust it.
   Extract the root and build a combined bundle (system CAs + Caddy root):

   ```bash
   # on the node:
   cat /var/lib/caddy/pki/authorities/local/root.crt   # Caddy internal root

   # on the client:
   cat /etc/ssl/certs/ca-certificates.crt <node-root.crt> \
       > ~/.config/yunohost-mcp/vm-combined-ca.crt
   ```

   Then make the connect client use it via `SSL_CERT_FILE` (the bridge honors
   `SSL_CERT_FILE` / `SSL_CERT_DIR` before falling back to the system trust
   store).

---

## 4. Client side: connect bridge

1. `opencode.jsonc` (the MCP server entry that launches the bridge) must pass
   both the hosts file and the CA bundle:

   ```jsonc
   "yunohost": {
     "type": "local",
     "command": ["/home/lostcause/.local/bin/yunohost-mcp-connect"],
     "environment": {
       "YUNOHOST_MCP_CLIENT_HOSTS_FILE": "/home/lostcause/.config/yunohost-mcp/opencode-hosts.toml",
       "SSL_CERT_FILE": "/home/lostcause/.config/yunohost-mcp/vm-combined-ca.crt"
     }
   }
   ```

2. `opencode-hosts.toml` — add a host entry for the node:

   ```toml
   [[host]]
   name = "nostrhost-vm"
   remote_url = "https://mcp.nostrhost.test/mcp"
   key_file = "/home/lostcause/.config/yunohost-mcp/opencode.key"
   ```

   Host names must be dot-free (they are spliced into bridge resource URIs).

3. The bridge process reads the hosts file at startup. Adding a host requires
   restarting the MCP connection (or the opencode session), not just editing
   the file.

---

## 5. Authorizing the client on the node

`nostr-operationsd` authorizes the operation **actor** (the NIP-98 client
pubkey) against its capability grants. `catalog.publish` needs
`catalog.publish`; the read op needs `catalog.inspect` — note the scope
names are not the op names.

1. Derive the client's pubkey from its key file.

2. Grant the scopes on the node (signs a kind-31100 as the operator):

   ```bash
   nostrhost capability grant <client-pubkey> \
       catalog.inspect catalog.verify catalog.publish
   ```

3. The daemon reads kind-31100 from the control relay, so the grant lands
   without a restart (a moment's delay).

---

## 6. Making a package appear in the catalogue (publish path)

`catalog.publish` re-declares an app that must **already** be in the trusted
native catalogue projection (`/var/lib/nostrhost/catalogue.json`). To get it
there durably:

1. **Enable the sync daemon** so the projection is maintained from the relay
   rather than only from a one-off `ingest`:

   ```bash
   systemctl enable --now nostrhost-catalog
   ```

   It syncs `ws://127.0.0.1:4848` trusting the publisher keys in
   `/etc/nostrhost/catalogue.env` (`NOSTRHOST_CATALOG_PUBLISHERS`). On the
   testbed that trusted publisher is the node's own `publisher_sk`.

2. **Allowlist kind-32267 on the control relay.** Without this, publishing
   the declaration to the relay fails with "blocked: kind not allowed", the
   declaration is not durable, and the next sync **wipes** the projection
   back to empty. Add `32267` to `allowed_kinds` in
   `/etc/nostrhost/relay.toml` and restart `nostrhost-control`:

   ```toml
   allowed_kinds = [ ..., 32267]
   ```

3. **Build and publish a signed kind-32267 declaration** for the package,
   signed with the node's `publisher_sk` (the trusted publisher). The tags
   must match the catalog provider's expectations:

   ```text
   d            = app_id
   platform     = yunohost
   repository   = <git URL>
   version      = <package version>
   commit       = <git commit sha>
   manifest     = sha256:<package.toml sha256>
   content      = sha256:<tar sha256 of package payload>
   package      = package.toml
   ```

   The content hash is the byte-for-byte tar:

   ```bash
   tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
       --exclude=./catalog.toml -C <dir> -cf - .
   ```

4. **Publish to the relay, then ingest** (ingest applies it to the projection):

   ```bash
   echo '<signed event JSON>' | \
     /usr/bin/nostrhost-catalog \
       --state /var/lib/nostrhost/catalogue.json \
       --publishers <trusted-publisher-hex> \
       --relay ws://127.0.0.1:4848 publish

   echo '<signed event JSON>' | \
     /usr/bin/nostrhost-catalog \
       --state /var/lib/nostrhost/catalogue.json \
       --publishers <trusted-publisher-hex> ingest
   ```

5. Verify it survives a sync daemon restart (i.e. it is durable on the relay),
   and confirm via the MCP `catalog.list` / `catalog.get`.

---

## 7. End-to-end test

With the VM registered as a host and a per-request NIP-98 client (the connect
bridge already does this):

```text
initialize                 → ok
tools/list                 → catalog.list / catalog.get / catalog.publish / catalog.verify present
catalog.list               → the declared app appears
catalog.publish            → approval_required + operation_id
(operator) approve 2201    → op transitions to started, then a terminal 2204
```

`catalog.publish` is approval-gated by design (`require_approval=True`), so a
successful request returning `approval_required` is the correct observable.

---

## 8. Issues encountered (and the operational workaround)

These are the non-code operational findings. The two code-level fixes they
motivated live in the fork/lib commits named at the top; a deployment that
already has those fixes only needs the operational steps above.

### Issue 1 — `ModuleNotFoundError: No module named 'mcp'`

The node venv ships `nostr-sdk` and `nostrhost-*` but not the MCP SDK, so
`nostrhost-mcp serve` died at import.

- Fix: `pip install "mcp[cli]>=2.1.1"` into `/opt/nostrhost/venv`.

### Issue 2 — `421 Misdirected Request / Invalid Host header` behind Caddy

The MCP SDK's `streamable_http_app()` defaults `host="127.0.0.1"`, which
auto-enables DNS-rebinding protection with only loopback `allowed_hosts`.
Requests arriving through Caddy carry `Host: mcp.nostrhost.test`, which the
middleware rejects before the app runs — even though the request reaches
Caddy fine and an unauthenticated `curl` to the same URL returns 401.

Additional subtlety: the middleware's `base:*` pattern only matches a host
*with* a port, but a reverse proxy forwards `Host` without a port. The
allowlist must contain **both** the bare hostname and `host:*`.

- Fix (runtime flag, no code): serve with
  `--http-allowed-hosts mcp.nostrhost.test`; the adapter then passes an
  explicit `TransportSecuritySettings` including loopback + the named host.
- Observable symptom if missed: `curl` to the Caddy URL returns 401
  (reaching uvicorn), but a proper NIP-98 MCP client gets `421 Invalid Host
  header`, and the server log shows
  `transport_security.py: Invalid Host header: mcp.nostrhost.test`.

### Issue 3 — "ASGI callable returned without completing response"

The NIP-98 middleware buffered the request body and replayed a single
`http.request` followed immediately by `http.disconnect`, which terminates
the long-lived SSE stream the streamable-HTTP transport opens. Sessions were
created then immediately torn down.

- Fixed at the code level (the middleware now forwards the original
  `receive()` after replay).
- Operational check: a working session must survive past `initialize`; a
  server log full of `Terminating session` right after `Created new
  transport` is the failure signature.

### Issue 4 — DNS only resolves with a manual `/etc/hosts` entry

`mcp.nostrhost.test` is a test-only name. Both the node (for cert issuance)
and the client need resolution. On the testbed this means editing
`/etc/hosts` on both sides (root on the client).

- Workaround: add the two `/etc/hosts` lines shown in §3.
- Automation note: this is the one step that needs root on the client; an
  installer script should detect a missing entry and ask.

### Issue 5 — TLS: internal cert not trusted by the bridge

The connect client uses httpx2, which honors `SSL_CERT_FILE` before the
system trust store. Without it, connecting to `https://mcp.nostrhost.test/mcp`
fails verification (the CA is Caddy's internal root, not a public CA).

- Workaround: build the combined bundle (§3.4) and set `SSL_CERT_FILE` on the
  bridge process (opencode.jsonc environment).

### Issue 6 — `catalog.list` returns `unauthorized` even after granting

The scope names differ from the op names. `catalog.list`/`catalog.get`
require scope `catalog.inspect` (not `catalog.list`), `catalog.verify`
requires `catalog.verify`, `catalog.publish` requires `catalog.publish`.

- Workaround: grant the correct scope strings (§5).

### Issue 7 — `catalog.publish` always fails: "publish requires --relay URL"

The `_safe_catalog_publish` op invoked the Go CLI as
`nostrhost-catalog ... publish --relay <url>`. Go's `flag.Parse` stops at the
first non-flag token (`publish`), so `--relay` was silently dropped and every
publish op failed.

- Fixed at the code level (flags now precede the subcommand).
- Runtime check: the direct CLI invocation
  `nostrhost-catalog --publishers <hex> --state <path> --relay <url> publish`
  must succeed (modulo event validation) — if it reports the same error the
  installed fork is missing the fix.

### Issue 8 — Projection silently resets to empty

The sync daemon (`nostrhost-catalog`) rebuilds the projection from the relay
on restart. A declaration that was only `ingest`ed (never published to the
relay) survives until the next sync, then disappears. Two separate problems:

- kind-32267 was not in the relay `allowed_kinds`, so publish was blocked
  (`blocked: kind not allowed`);
- after allowlisting, the declaration must be **published** to the relay so
  the sync daemon can replay it.

### Issue 9 — `nostr-operationsd` crashes under relay restarts

The daemon's websocket receiver hit
`AssertionError: protocol.state is CLOSED` in `websockets/sync/client.py`
after the control relay was restarted several times, leaving the daemon
inactive and MCP op calls hanging.

Two root causes, both now fixed (fork commit
`operationsd: fix relay-drop crash and progress-publish stall`):

1. **websockets < 14.2 race.** The 13.x sync client called
   `protocol.receive_eof()` in `close_socket()` without the protocol mutex
   (python-websockets e7a098e), so a connection dropped abruptly while
   closing raced the background `recv_events` thread and raised the assert.
   Fixed by requiring `websockets>=14.2` (fork `pyproject.toml` and the
   bundled `nostrhost-runtime` wheel; 13.1 was previously pinned).
2. **kind-2205 missing from the relay allowlist.** `CONTROL_KINDS` (which
   generates `allowed_kinds` in `/etc/nostrhost/relay.toml`) omitted 2205
   (execution.progress). The relay runs in allowlist mode and silently drops
   disallowed kinds without responding `OK`, so every progress publish from
   the daemon blocked the full publish timeout — each op stalled ~30s and
   looked hung.

- Workaround (if still on an unfixed build): `systemctl restart
  nostr-operationsd` (Restart=on-failure usually covers it, but a manual
  restart after relay churn is reliable), and confirm 2205 is in the relay's
  `allowed_kinds` before restarting `nostrhost-control`.
- Automation note: sequence relay config changes (e.g. allowlist edits) so
  `nostrhost-control` is restarted once, then restart
  `nostr-operationsd` + `nostrhost-catalog` after it, and give the daemon a
  few seconds to re-subscribe before submitting ops.
- Checkpoint: after a clean install, `grep allowed_kinds
  /etc/nostrhost/relay.toml` must include 2205, and
  `/opt/nostrhost/venv/bin/pip show websockets` must report 14.2 or newer.

### Issue 10 — bridge `doctor` reports `identity_not_enrolled` for this endpoint

The connect bridge's `doctor` health check calls `whoami`, which the thin
`nostrhost-mcp` adapter does not expose (it only generates tools from the
native operation catalogue). This is expected, not a connection failure —
TLS, NIP-98, and transport all work (the error is specifically that the
`whoami` tool is absent). Verify with an actual tool call (`catalog.list`)
instead.

---

## 9. Checkpoints for an automation script

1. `nostrhost-mcp serve --http <port> --http-allowed-hosts <name>` is up and
   loopback-request returns 401.
2. `caddy validate` passes; Caddy route present; node resolves `<name>`.
3. `SSH_CERT_FILE`/`SSL_CERT_FILE` bundle includes the node Caddy root; host
   `/etc/hosts` has `<name>`.
4. `capability grant` applied for `catalog.inspect catalog.verify catalog.publish`.
5. `nostrhost-catalog` service active; relay `allowed_kinds` includes 32267.
6. Declared app survives `systemctl restart nostrhost-catalog` (durable).
7. MCP `catalog.list` returns the app; `catalog.publish` returns
   `approval_required` with an `operation_id`.