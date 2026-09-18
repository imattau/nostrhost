# Control-plane events

NostrHost uses a local, authenticated Nostr relay as its administrative event
bus. Events are signed and linked, so every interface sees the same operation
history.

The custom kind numbers are an internal protocol contract and may change
before the first stable release.

## Operation chain

| Kind | Meaning | Required link |
|---:|---|---|
| 2200 | Operation request | Event ID becomes the request ID |
| 2201 | Approval | `e` tag refers to request |
| 2202 | Rejection | `e` tag refers to request |
| 2203 | Execution started | `e` tag refers to request |
| 2204 | Execution result | `e` tag refers to request |
| 2205 | Execution progress | `e` tag refers to request |

A request contains a registered tool name and JSON arguments. Policy decides
whether it can run immediately, needs approval, or must be rejected. Only the
configured server identity may publish execution and result events.

The terminal state is derived from the newest valid rejection or result. Event
arrival order alone is not authority; consumers validate signatures, authors,
references, and schemas.

## Definitions and delegation

| Kind | Meaning |
|---:|---|
| 31100 | Capability or role grant for a public key |
| 31101 | Trust or policy declaration |
| 31102 | Identity definition linking a public key and account |
| 27236 | Scoped, expiring capability delegation |
| 27237 | Delegation revocation |

Definition events are addressable: a newer valid event replaces the earlier
definition for the same address. Revoking an identity publishes a disabled
definition. A delegator cannot grant scopes it does not hold.

## Operational notices

| Kind | Meaning |
|---:|---|
| 2206 | Authentication or login notice |
| 2210 | General system event |
| 2211 | Service event |
| 2212 | Backup event |
| 2213 | Security event |

Notice content is a JSON object. Producers should include `class`, `severity`
(`info`, `warning`, or `critical`), and a short `summary`. Notification
consumers use these fields, while the raw event remains the audit source.

## Standard Nostr features

NostrHost uses standard features where they fit: kind 0 profiles, NIP-26
delegation concepts, NIP-34 repository announcements, NIP-42 relay
authentication, NIP-44 encryption, NIP-51 lists, NIP-65/66 relay metadata,
NIP-77 synchronisation, NIP-78 application data, NIP-86 relay management, and
NIP-98 HTTP authentication.

## Validation and access

The relay validates timestamps, size, kind policy, writer policy,
authentication, schema, and required references. Protected reads also require
authentication. Relay management requires a NIP-98 signature from a configured
administrator.

The relay binds to loopback. Sessions, cookies, CSRF tokens, login challenges,
plaintext secrets, and bulk app data are deliberately not relay events.
