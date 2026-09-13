# Deployment topology

How a single NostrHost server is laid out: what listens where, what
terminates TLS, and how a request reaches an app. This is a summary of
[`../CADDY-MIGRATION.md`](../CADDY-MIGRATION.md); read that for the full
phased history and rationale.

> **Status.** NostrHost targets a **single-server** deployment model — one
> machine running the full stack, not a multi-node cluster. Multi-host/fleet
> projection is a later idea (see `../MCP-TRANSITION.md` §7) and not part of
> the current architecture.

## Request path

```text
Internet
   │
   ▼
Caddy (public 80/443, 443/udp for HTTP/3; admin API on 127.0.0.1:2019)
   ├─ TLS: automatic ACME (Let's Encrypt) for public domain names
   │        `tls internal` (self-signed) for .test/.local/non-public names
   ├─ domains + native app routes, generated from semantic state
   ├─ forward_auth → nostrhost-authd (Python) → ALLOW / DENY /
   │        302-to-portal, with X-Remote-*/X-Nostr-* compatibility headers
   ├─ reverse_proxy → the native API, portal API, OIDC, native app upstreams
   └─ file_server → the Portal and Admin single-page apps
```

Caddy is the **single web/TLS front end** — nginx and SSOwat have been
retired (see the "Component disposition" table in
[`../CADDY-MIGRATION.md`](../CADDY-MIGRATION.md)). All access control that
used to live in SSOwat's Lua now lives in `nostrhost-authd`, evaluated per
request via Caddy's `forward_auth` directive.

## What runs on the box

| Layer | Component(s) | Role |
|---|---|---|
| Web/TLS | Caddy (+ `caddy-l4` for TLS passthrough) | Public-facing termination, routing, certificates |
| Auth | `nostrhost-authd` | Per-request ALLOW/DENY decision behind `forward_auth` |
| Control plane | `nostrhost-control` (khatru relay) | Local Nostr relay — the control-plane bus (see [`architecture-overview.md`](../dev/architecture-overview.md)) |
| Core engine | `nostrhost-core` (the YunoHost-derived engine) | App lifecycle, domains, backups, services, diagnosis |
| Security | CrowdSec + `crowdsec-firewall-bouncer` (nftables mode) | Intrusion detection/decision + enforcement (see [security-model.md](security-model.md)) |
| Catalogue | `nostrhost-catalog` | App discovery/resolution over Nostr |
| Notifications | `nostrhost-notify` | NIP-17/59 encrypted admin notifications |
| Runtime | `/opt/nostrhost/venv` (`nostrhost-runtime`) | Private venv for Python deps not in Debian bookworm |

See [`../../packaging/README.md`](../../packaging/README.md) for the
complete package → dependency graph, and
[`architecture-overview.md`](../dev/architecture-overview.md) for how these
talk to each other via the relay.

## Domains and DNS

Every domain served by NostrHost needs to resolve to the server's public IP
before Caddy can obtain a certificate for it. During evaluation, a
dynamic-DNS domain (e.g. DuckDNS) works; for a real deployment, point your
own domain's A/AAAA record at the server. Native DNS-provider integration
(Cloudflare, deSEC, DuckDNS, manual) is a later-phase item — see the "Later
phase" section of [`../ALPHA-PLAN.md`](../ALPHA-PLAN.md) (§26).

## Network exposure

- **Public:** Caddy's 80/443 (and 443/udp for HTTP/3) — this is the only
  inbound surface a NostrHost server needs.
- **Loopback-only:** the control-plane relay (`nostrhost-control`), Caddy's
  admin API (`127.0.0.1:2019`), the native API and portal API upstreams
  Caddy reverse-proxies to.
- **No inbound relay port.** The control-plane relay is never
  Internet-reachable; selective outbound sync publishes catalogue/trust
  events to external relays, and pulls in the other direction, but nothing
  external can connect to the local relay directly. See
  [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md) §3 and
  [`../STATELAYER.md`](../STATELAYER.md) for why this boundary matters for
  the audit/identity model.

## Legacy app compatibility (transitional)

Apps still built on the traditional `_ynh`/Bash packaging model are served
by a legacy nginx instance bound to `127.0.0.1:8080` (no public ports),
reverse-proxied by Caddy. This shim is explicitly temporary — see
[`../LEGACY-INVENTORY.md`](../LEGACY-INVENTORY.md) for what's still on it
and the removal gate. New apps should use the native `package.toml` model
described in [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md).

## Related reading

- [`security-model.md`](security-model.md) — what protects this topology
  from abuse.
- [`upgrades-and-migrations.md`](upgrades-and-migrations.md) — how this
  topology got here (nginx → Caddy, fail2ban → CrowdSec) and what upgrading
  across those changes involves.
