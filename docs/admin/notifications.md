# Notifications

`nostrhost-notify` turns important system events into encrypted Nostr direct
messages for administrators. Notifications complement monitoring; they do not
replace local logs or audit events.

## How delivery works

The daemon reads selected events from the local control relay, applies the
notification policy, and sends encrypted NIP-17/NIP-59 messages to configured
recipients through the chosen external relay path. It holds only the authority
needed to read notification sources and send messages.

## Configure recipients and policy

Use the Admin interface or inspect the installed CLI:

```bash
nostrhost notify --help
```

Configure at least two appropriate recipients for an important server. Choose
which event classes and severities are immediate and which may be grouped into
a digest. Typical sources include:

- failed operations and diagnoses;
- backup failure or missed backup;
- certificate and domain problems;
- security decisions and repeated login failures;
- service failure and resource exhaustion; and
- requests waiting for approval.

After changing identities or recipients, synchronise the notification
configuration and send a test event.

## Remote signers for approvals

Notifications can tell an owner that an operation needs approval, but approval
is a separate signature. Configure NIP-46 signer targets with:

```bash
nostrhost signer --help
```

Prefer `nostrconnect` pairing, protect any stored bunker secret, and remove
unused targets.

## Troubleshooting

Check that the daemon is running, the recipient public key is correct, the
external relay is reachable, the event class passes policy, and the recipient
client supports the encryption format. A notification failure must not block
the underlying server operation; use local logs and the audit trail as the
authoritative record.
