# Troubleshooting

When something goes wrong, collect information before restarting or changing
things. Repeated changes can hide the cause or make recovery harder.

## The dashboard does not open

Check these in order:

1. Does the domain point to the server's current internet address?
2. Is the server switched on and connected?
3. Can web traffic reach ports 80 and 443?
4. Does the browser show a certificate or secure-connection error?
5. Can you reach the server through its console or SSH connection?

Do not expose internal NostrHost services directly to the internet to work
around a dashboard problem.

## I cannot sign in

- Make sure your signer is unlocked.
- Check that it is using the expected public key.
- Check that the phone or computer time is correct.
- Read and approve the exact request shown by the signer.
- Try signing out of other sessions and opening a fresh browser window.

Many repeated failures may temporarily trigger the server's security
protection. An administrator can review the security events in Admin.

## A change says it is waiting for approval

This is normal for sensitive actions. Open the request in Admin, read what it
will do, and approve it with an authorised owner identity. Starting the same
action again will not avoid approval.

## An app does not work

In Admin, check:

- whether the app service is running;
- whether the server has free storage;
- whether the app's domain is correct;
- whether your account has permission to use it; and
- whether a recent install or update failed.

If an update caused the problem, do not remove the app. Keep the operation
number and consider restoring its pre-update backup.

## A backup fails

Check that the backup destination is reachable, its password or key still
works, and both the server and destination have free space. Do not delete an
unfamiliar backup lock unless an administrator has confirmed that no backup or
restore is still running.

## The AI assistant behaves unexpectedly

Disable it:

```bash
sudo nostrhost agent disable
```

Do not give it more permissions to make the error disappear. Keep its activity
journal and related operation number for review. See [AI assistant](ai-assistant.md).

## Asking for help

Include:

- what you expected and what happened;
- the approximate time and your time zone;
- the affected app or domain;
- the operation number shown by Admin; and
- the relevant health-check summary.

Never share private keys, recovery files, passwords, browser cookies, signed
login requests, backup credentials, or private user data.
