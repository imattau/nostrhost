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
is a separate signature. `nostr-signerd` pushes parked approvals to any
registered NIP-46 signer whose identity is a configured administrator, so an
approval can be signed in the signer app without a particular browser session
open.

There are two ways an administrator can give the node a signer:

- **Approve from anywhere (recommended).** In the admin console's **Operations**
  screen, open **Approve from anywhere** and either scan the generated
  `nostrconnect://` QR or paste a `bunker://` URI. The node's own NIP-46 client
  key is what the signer authorises, so the signer's signing key never reaches
  the server; with `nostrconnect` no secret is stored at all. Only the
  signed-in administrator's own identity can be registered.
- **CLI.** The same targets can be managed head-lessly:

  ```bash
  nostrhost notify signer pair      # node-initiated nostrconnect pairing
  nostrhost notify signer add ...   # register a bunker:// URI
  nostrhost notify signer list
  nostrhost notify signer remove ...
  ```

`nostr-signerd` re-reads the target file before each notice, so a registration
or removal made in the console takes effect immediately (no service restart).
Prefer `nostrconnect` pairing, protect any stored bunker secret, and remove
unused targets. A browser can also connect a signer just for itself (the
"Remote signer (this browser)" card); that connection is stored in the browser
and is intentionally **not** shared across browsers.

## Troubleshooting

Check that the daemon is running, the recipient public key is correct, the
external relay is reachable, the event class passes policy, and the recipient
client supports the encryption format. A notification failure must not block
the underlying server operation; use local logs and the audit trail as the
authoritative record.
