# Identity and access

NostrHost uses Nostr identities to recognise people and approved tools.

## Public and private keys

Your public key begins with `npub`. It identifies you and is safe to share.
Your private key often begins with `nsec`. It proves that you are you and must
remain secret.

Use a signer to hold the private key. When NostrHost asks you to sign in or
approve a change, read the request and approve it in the signer.

Never give your private key to:

- the NostrHost server;
- another person;
- a support site;
- a script or AI assistant; or
- a browser page you do not trust.

## Owners, administrators, and users

**Owners** have final control and approve the most sensitive actions.

**Administrators** look after the server but may still need an owner's approval
for high-risk changes.

**Users** can open the apps shared with them but do not manage the server.

Give people only the access they need. Having permission to use an app does not
automatically make someone an administrator.

## Add a person

In Admin:

1. Add the person's account.
2. Link their Nostr public key.
3. Add them to any suitable groups.
4. Choose which apps they can use.
5. Ask them to sign in and confirm their access.

Do not reuse one identity for several people. Separate identities make access
easier to remove and the activity history easier to understand.

## New phones and computers

Connect the new device to your existing signer when possible. Avoid copying
the private key between devices. Remove old or lost devices from the signer and
review recent activity after a device goes missing.

## Apps, assistants, and automated tools

Give every automated tool its own identity. Begin with read-only access and
add individual permissions only when required. Never configure an unattended
tool with the owner's personal key.

## When someone leaves

Disable their identity, remove group and app access, end active sessions, and
review any shared secrets they knew. Keep the signed activity history.

## If a key may be stolen

Use another owner identity or the offline recovery process to disable the key
immediately. Review recent changes, rotate related credentials, and check apps
and backups for unexpected activity.
