# Architecture overview

NostrHost combines a YunoHost-derived server engine with Nostr identity,
policy, events, native app packages, and new user interfaces.

## Repository layout

```text
nostrhost/
├── forks/
│   ├── yunohost/       server engine and native CLI/API
│   ├── portal/         end-user web interface
│   ├── admin/          administrator web interface
│   └── installer/      Debian installer image
├── libs/
│   ├── nostrhost-auth/       identity and signed HTTP authentication
│   ├── nostrhost-policy/     roles, scopes, delegation, and approvals
│   ├── nostrhost-catalog/    package discovery, trust, and attestations
│   ├── nostrhost-control/    local relay and event model
│   ├── nostrhost-mcp/        native MCP adapter
│   ├── nostrhost-nsite/      Nostr site gateway
│   ├── nostrhost-agent/      optional resident agent
│   └── yunohost-mcp/         compatibility MCP implementation
├── packages/           example and test native apps
├── packaging/          Debian build, compatibility, and publication tools
├── schema/             native app manifest schema
├── baseline/           pinned component revisions
├── scripts/            repository verification tools
└── testbed/            VM and end-to-end tests
```

## Runtime request flow

```text
Portal / Admin / CLI / MCP / agent
                 │ signed request
                 ▼
          local Nostr relay
                 │
       identity and policy checks
                 │
        approval when required
                 │
                 ▼
             executor
                 │
       server-management services
                 │
 apps / domains / users / backups / systemd / Caddy
```

The relay is an authenticated, loopback-only event store and bus. Interfaces
publish requests and observe results rather than each implementing a separate
privileged backend. Projectors build convenient read models from signed events.

The executor is the single machine-state writer. It validates operation names
and arguments against the operation catalogue, checks policy, records start and
result events, and calls the underlying service layer.

## Identity and policy

Public keys identify people, automated clients, and server components. The
authentication layer verifies signatures and maps identities to accounts.
Policy combines roles, capabilities, delegation, operation risk, and approval
requirements. Relay permissions, server administration, and app access remain
separate checks.

Browser sessions, cookies, challenge state, and secrets stay in local protected
storage. Only security-relevant notices are represented in the event stream.

## Native app lifecycle

A native package declares users, directories, runtimes, databases, services,
web routes, settings, secrets, health checks, and backups. The package engine
validates the manifest and produces a deterministic, dependency-ordered plan.
Applying that plan is a separate policy-controlled operation.

Providers reconcile each resource type with the host and report enough state
for verification or rollback. Package content cannot gain an arbitrary shell
lifecycle hook.

## Web and network edge

Caddy terminates HTTPS, serves Portal and Admin assets, consults
`nostrhost-authd`, and proxies approved traffic to apps and APIs. CrowdSec reads
logs and sends decisions to the nftables bouncer. Internal relay, API, database,
and app-backend ports remain private.

## State and recovery

Configuration is versioned separately from application data. Signed events
record authority and operational history, the configuration repository records
desired state, and Restic archives hold data. Recovery combines all three with
a clean Debian host and off-server keys.

## Catalogue, notifications, and optional services

The catalogue resolves signed app declarations, publisher trust, release
metadata, and attestations into a local trusted view. The notification service
converts selected control events into encrypted administrator messages. The
nsite gateway serves signed Nostr site content on a dedicated domain. MCP and
the resident agent consume the same operation catalogue and policy system as
human interfaces; neither receives authority simply by being installed.

## Distribution

NostrHost ships as related Debian packages rather than one binary. The
top-level packaging manifest defines source components and dependencies. A
private Python environment supplies pinned dependencies that Debian 12 does not
provide at compatible versions; target machines should not be modified with
manual `pip` installs.

## Stable extension points

- the operation catalogue and its input/result schemas;
- signed control-plane events;
- native package manifests and resource providers;
- NIP-98 HTTP authentication;
- MCP tools derived from the operation catalogue; and
- read-only projectors and notification consumers.
