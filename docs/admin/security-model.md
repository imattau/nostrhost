# Security model

NostrHost uses several independent layers. No single layer replaces host
patching, careful permissions, protected keys, and tested backups.

## Network defence

CrowdSec reads system and Caddy logs, detects abusive behaviour, and creates
decisions. The firewall bouncer enforces those decisions through nftables.
Community blocklist sharing is optional rather than required for local
protection.

Review decisions before removing them and keep the local CrowdSec API private.
Security events are projected into the audit and notification path.

## Web authentication

Caddy asks `nostrhost-authd` to authorise protected requests. The service can
allow, deny, or redirect the browser to sign in. It adds identity headers only
after a successful check; direct access to app backends would bypass this
boundary and must be blocked.

Browser sessions and CSRF state stay in the local authentication service. They
are not published as relay events.

## Identity

People and tools authenticate with Nostr signatures. Browser sign-in can use a
NIP-07 extension, NIP-46 remote signer, or passkey. API requests use NIP-98
signed HTTP authentication. Each automated client should have a separate key.

Private keys and recovery secrets must never enter logs, manifests, events, or
support reports.

## Authorisation

Relay permissions control who may read or write event kinds. NostrHost roles
and capabilities separately control what a key may do to the server. App
permissions control who can reach an app. Passing one of these checks does not
imply passing the others.

Sensitive changes can require an owner co-signature. Delegation narrows a
client's authority and should have the shortest practical lifetime and scope.

## Signed operation chain

Administrative work is represented as a request, optional approval, execution,
and result. Each stage refers to the original request and is signed by the
responsible identity. The server executor is the only component allowed to
turn an approved request into machine changes.

Audit events help establish who requested and approved an action. They do not
prove that application data was correct, so pair them with logs, diagnosis,
and backup verification during incident response.

## Secrets

Secrets stay in protected local storage or systemd credentials. The event
stream and configuration-state repository hold references and non-secret
configuration, not plaintext credentials. Rotate credentials after exposure,
restore, operator departure, or suspected host compromise.

## Operator baseline

- Expose only required ports.
- Patch the operating system and NostrHost packages.
- Require separate keys for people and automation.
- Grant least privilege and review it periodically.
- Monitor security events and failed operations.
- Keep encrypted, external backups and offline recovery material.
- Test restoration and key rotation.
