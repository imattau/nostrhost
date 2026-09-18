# Getting started

This guide installs NostrHost on a test server. The installation still uses a
terminal, but normal use happens in a web browser.

## Before you begin

You need:

- a spare amd64 computer or virtual machine running Debian 12;
- administrator access to that machine;
- a domain name that points to it;
- a Nostr public key beginning with `npub`; and
- safe storage away from the server for recovery information.

Use a new test machine. Installation changes web, security, and server
settings, so do not try it on a computer that already hosts important services.

## Protect your Nostr identity

Your public key is safe to share. Your private key, often shown as an `nsec`,
is not. Keep the private key in a trusted signer such as a browser extension,
remote signer, or supported passkey. The installation command needs your
`npub`, never your `nsec`.

## Point your domain to the server

At your domain provider, create an `A` record for the server's IPv4 address.
Create an `AAAA` record only if the server has working IPv6. DNS changes can
take time to appear.

The server must accept web traffic on ports 80 and 443. If you are using a
home connection, your router may need to forward those ports.

## Install NostrHost

Sign in to the server and run:

```bash
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://imattau.github.io/nostrhost/debian/nostrhost.asc \
  | sudo tee /etc/apt/keyrings/nostrhost.asc >/dev/null

echo "deb [signed-by=/etc/apt/keyrings/nostrhost.asc] https://imattau.github.io/nostrhost/debian/ bookworm main" \
  | sudo tee /etc/apt/sources.list.d/nostrhost.list

sudo apt update
sudo apt install nostrhost
```

Then replace the example domain and public key with your own:

```bash
sudo nostrhost postinstall new \
  --domain example.org \
  --admin-npub npub1...
```

## Save the recovery information

Setup creates a recovery file containing sensitive server keys. Copy it to
encrypted storage away from the server. Do not leave the only copy on the
server, upload it to a support ticket, or store it in an ordinary notes app.

Without this file and your backup credentials, rebuilding a lost server may be
impossible.

## Open the dashboard

Visit `https://your-domain` in a browser. Your browser should show a valid
secure connection. Choose the available Nostr sign-in method and approve the
request in your signer.

After signing in, check that your identity is shown as the owner.

## Check that setup worked

In Admin:

1. Open the health or diagnosis page and run the checks.
2. Confirm that the main services are running.
3. Check that the correct domain is listed.
4. Create a first backup.
5. Test that you can sign out and sign back in.

If the dashboard does not open, go to [Troubleshooting](troubleshooting.md).

## Restoring an existing server

Do not use `postinstall new` when replacing a lost NostrHost server. The new
command creates a different server identity. Recovery uses the restore command
and your saved keys and backups. Follow [Backups and recovery](backups-and-recovery.md)
before attempting it.

## Next step

Continue with [Apps](apps.md).
