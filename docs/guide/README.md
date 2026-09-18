# User guide

NostrHost is a control panel for a server you own. It helps you run web apps
without handing your data and identity to a hosting company.

## What makes it different?

Most server dashboards use an administrator name and password. NostrHost uses
a Nostr identity instead. You approve sign-ins and important actions with a
signer on a device you trust.

Behind the dashboard, NostrHost keeps a signed record of important changes.
This makes it easier to see who requested a change, who approved it, and
whether it succeeded.

## What can I manage?

From the Admin dashboard you can:

- install and update apps;
- add domains and choose app addresses;
- add people and decide which apps they can use;
- check whether services are working;
- make and restore backups;
- review security warnings and recent changes; and
- configure private administrator notifications.

## What should I understand first?

### Your key is your administrator identity

Keep your private key in a trusted signer. Never paste it into the server,
email, chat, a support ticket, or an AI assistant. NostrHost normally needs
your public key only.

### The server has its own identity

During setup, NostrHost creates a separate identity for the server. This lets
the server sign its own results and notices. It is not a second personal
account and should not be used for login.

### Some changes need approval

A person or tool may be allowed to suggest a change without being allowed to
carry it out. For example, an assistant might suggest restarting a service,
but the owner may still need to approve it.

### Backups must live somewhere else

A backup kept only on the same machine will be lost if that machine fails.
Keep backups and recovery information in separate, protected storage.

## Follow the guide

1. [Getting started](getting-started.md)
2. [Apps](apps.md)
3. [Identity and access](identity-and-access.md)
4. [Backups and recovery](backups-and-recovery.md)
5. [Looking after your server](server-care.md)
6. [AI assistant](ai-assistant.md)
7. [Troubleshooting](troubleshooting.md)
