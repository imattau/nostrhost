# Deployment and network layout

NostrHost is designed as a single-server platform. One machine runs the web
edge, control plane, server-management engine, interfaces, and supporting
services.

## Request path

```text
Internet
   │
   ▼
Caddy on ports 80 and 443
   ├── HTTPS certificates and redirects
   ├── authentication check through nostrhost-authd
   ├── Admin and Portal static files and APIs
   └── reverse proxy to hosted apps
```

Caddy is the only public web entry point. Its administration endpoint, the
NostrHost APIs, and the control relay are loopback-only.

## Main services

| Service | Purpose |
|---|---|
| Caddy | HTTPS, certificates, routing, static files, and reverse proxying |
| `nostrhost-authd` | Per-request identity and access checks |
| `nostrhost-control` | Local Nostr relay and administrative event bus |
| `nostrhost-core` | Apps, domains, users, services, backups, and diagnosis |
| `nostrhost-catalog` | Trusted app discovery and package metadata |
| `nostrhost-notify` | Encrypted administrator notifications |
| CrowdSec and nftables | Detection, decisions, and network enforcement |
| Restic | Deduplicated, encrypted backup storage |
| Portal and Admin | User and operator web interfaces |
| `nostrhost-nsite` | Optional NIP-5A site gateway on a dedicated domain |

The optional `nostrhost-agent` and `nostrhost-mcp` services are not required
for a normal server.

The nsite gateway is also optional. When enabled with `nostrhost nsite`, it
receives its own managed Caddy route and serves signed Nostr site content. Keep
it on a dedicated registered domain so its public content boundary is clear.

## Network exposure

- TCP 80 and 443 are public for HTTP and HTTPS.
- UDP 443 is optional for HTTP/3.
- SSH should be restricted by firewall, source network, or another controlled
  access path where possible.
- Internal APIs, relay endpoints, databases, Caddy administration, and app
  backends must not be exposed directly.

The control relay is local by design. Selective outbound relay connections may
publish or fetch catalogue, state, or trust information, but external clients
do not connect directly to the internal control plane.

## Domains and certificates

Each public domain must resolve to the server before Caddy can obtain a public
certificate. Keep both IPv4 and IPv6 records accurate. Non-public development
names use locally trusted certificates and are unsuitable for ordinary public
browsers without additional trust configuration.

DNS provider credentials are handled through the credential broker and should
not be stored in package manifests, shell scripts, or the event stream.

## App routing

Native app routes are generated from declared package resources. Access checks
run before traffic reaches a protected app. Compatibility apps can be served
through an internal legacy web backend, but that backend remains private and
new packages should use native routes.
