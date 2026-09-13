# Security model

The layers that protect a NostrHost server, from network-edge intrusion
detection down to who is authorised to perform which administrative
action. Written from [`../CROWDSEC-MIGRATION.md`](../CROWDSEC-MIGRATION.md),
[`../CONTROL-PLANE.md`](../CONTROL-PLANE.md),
[`../ROLE-AND-APP-ACCESS-DESIGN.md`](../ROLE-AND-APP-ACCESS-DESIGN.md) and
[`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md) — read those for full
rationale and status detail.

## Layer 1: intrusion detection and enforcement (CrowdSec)

fail2ban has been fully retired and replaced by **CrowdSec**, with
**nftables** unchanged as the enforcement backend (only the
detection/decision layer changed):

```text
journald + Caddy access log
      │
      ▼
crowdsec (local API only — no inbound network exposure)
  acquis.yaml: journald sshd/postfix/dovecot/PAM units + Caddy log
  parsers + scenarios (crowdsecurity/sshd, postfix, linux collections
             + custom nostrhost-yunohost-auth, nostrhost-portal-auth parsers)
      │
      ▼
  decisions (local API, sqlite by default)
      │
      ▼
crowdsec-firewall-bouncer (nftables mode)
      │
      ▼
nftables set `crowdsec-blacklists`  (extends, doesn't replace, the
                                      existing YunoHost nftables table)
      │
      ▼
security projector → local Nostr relay → audit trail + admin notification
```

Key properties:

- **Local scenarios only by default.** CrowdSec's CAPI (Central API /
  community blocklist) is opt-in and off by default — a fresh install does
  not "phone home" without explicit consent.
- **Native-only app integration.** CrowdSec is exposed to app packages
  exclusively as a `PolicyResource(type: "crowdsec")` in `package.toml`,
  reconciled by the native `PolicyProvider`. There is no Bash-callable
  CrowdSec helper — matching the resource engine's "no Bash or legacy-script
  capability" rule (see [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md)).
- Every CrowdSec decision (e.g. banning an IP after repeated failed logins)
  is picked up by a **security projector**, published as a structured event
  on the local relay, and can trigger an encrypted admin notification — see
  [notifications.md](notifications.md).

## Layer 2: request-time authorization (Caddy `forward_auth`)

Every request Caddy proxies to an app or the admin/portal APIs is gated by
`forward_auth` to `nostrhost-authd`, which returns ALLOW/DENY plus
compatibility headers (`X-Remote-User`, `X-Remote-Email`, `X-Nostr-Pubkey`,
`X-Nostr-Npub`) that existing YunoHost-style apps expect. This replaced
SSOwat's Lua-in-nginx enforcement point entirely — see
[`../CADDY-MIGRATION.md`](../CADDY-MIGRATION.md).

## Layer 3: identity

Every administrative identity is a **Nostr keypair** (`npub`/`nsec`), not a
username/password:

- Login/authentication uses NIP-01 + BIP-340 signatures, via NIP-07 (browser
  extension), NIP-46 (remote signer), or a passkey.
- The native admin API authenticates HTTP requests with **NIP-98** (signed
  `Authorization: Nostr <event>` headers) — no passwords or API keys.
- LDAP is **being fully retired**, not kept as a fallback (see
  [`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md)) — the only remaining
  LDAP dependency is as the underlying Unix account/group directory
  (`libnss-ldapd`/`libpam-ldapd`), not as an authentication or authorization
  mechanism; that too is scheduled for removal.

## Layer 4: authorization (roles, capabilities, groups)

- **Relay-level access** (who may read/write the local control-plane relay)
  is **NIP-42** (client auth) + **NIP-86** (allow/ban pubkeys and kinds,
  relay-scoped roles) — see [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md).
- **NostrHost-level authorization** (who may install an app, approve an
  operation, manage another user) is a separate, **server-authoritative
  capability model** on top of relay-level roles — evaluated by the policy
  engine (`nostrhost-policy`), not by the relay itself. See
  [`../ROLE-AND-APP-ACCESS-DESIGN.md`](../ROLE-AND-APP-ACCESS-DESIGN.md) for
  the full role/permission design.
- **Groups and app-permission membership** ("which principals may use which
  app/domain") are moving to **NIP-51 lists** — a standard, signed,
  addressable Nostr primitive — replacing LDAP's `ou=permission` membership
  entries. See [`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md) §"Why NIP-51
  for groups".
- **Delegated/agent access** uses **NIP-26** for signing delegation plus a
  small NostrHost capability event for scope grants (e.g. the optional
  resident agent — see [`../../packaging/README.md`](../../packaging/README.md)'s
  `nostrhost-agent` section). Privileged or high-risk actions require
  explicit owner approval, typically via a NIP-46 signature.

## Layer 5: the audit chain

Every administrative action — install an app, approve an operation, grant a
capability — is a **signed, immutable Nostr event** forming a
request → approval → execution chain:

```text
REQUEST    npub-agent   app.upgrade   ditto
APPROVAL   npub-admin   request-id
EXECUTION  npub-server  request-id   started
RESULT     npub-server  request-id   success
```

There is no separate bespoke audit database — the signed event chain *is*
the audit trail; a projector builds a queryable index for admin reporting
on top of it. See [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md) §2.1 and
[`../NIP-MAPPING.md`](../NIP-MAPPING.md) §4.5.

## What this replaced

| Historical component | Replaced by |
|---|---|
| fail2ban | CrowdSec (nftables enforcement unchanged) |
| SSOwat (Lua-in-nginx) | Caddy `forward_auth` → `nostrhost-authd` |
| Username/password login | Nostr keypair (NIP-07/46/passkey) |
| LDAP as auth/authorization store | Nostr identity + NIP-51 group/permission lists (LDAP retirement in progress; see status below) |
| Bespoke audit database | Signed operation-chain events + derived read model |

## Status

Fully landed: CrowdSec migration (P0–P7 complete), Caddy migration (P0–P6;
P7 remaining is backup hooks/semantic state), request-time `forward_auth`.
In progress: LDAP retirement — authentication is already fully Nostr-native;
the remaining work is replacing LDAP's role as the Unix account/group
directory and app-permission-membership store. See
[`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md) "Status" for the current
phase.

## Related reading

- [`deployment-topology.md`](deployment-topology.md) for where each of
  these layers physically sits.
- [`../ROLE-AND-APP-ACCESS-IMPLEMENTATION-PLAN.md`](../ROLE-AND-APP-ACCESS-IMPLEMENTATION-PLAN.md)
  for the implementation-level detail behind the role/permission design.
