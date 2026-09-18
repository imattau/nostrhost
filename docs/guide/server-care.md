# Looking after your server

A self-hosted server needs regular care. NostrHost provides a dashboard for
most of it, but someone still needs to notice warnings and act on them.

## Check the dashboard regularly

Open Admin and look for:

- services that have stopped;
- failed app or system updates;
- security warnings;
- low free storage;
- certificate or domain problems;
- failed backups; and
- actions still waiting for approval.

Check more often after an update or configuration change.

## Install updates carefully

Updates fix security problems and improve reliability, but they can also change
how an app works.

Before updating:

1. Check that the server is otherwise healthy.
2. Confirm that there is enough free storage.
3. Make a fresh backup.
4. Read the update summary.
5. Make sure you can reach the server console if the website stops working.

After updating, sign in again, open important apps, run the health checks, and
confirm that a new backup succeeds.

## Read notifications

NostrHost can send private Nostr messages about serious problems or requests
that need approval. In Admin, choose which administrators receive messages and
which warnings are sent immediately.

Send a test notification after setup or after changing an administrator. A
notification is only an alert; the dashboard and activity history remain the
main record of what happened.

## Watch storage use

Apps, logs, updates, and local backup copies all use storage. Low storage can
break databases and prevent backups or updates. Investigate steady growth
before the disk becomes full. Do not delete unfamiliar system or backup files
just to make space.

## Review access

From time to time, check:

- who is an owner or administrator;
- which devices and automated tools are still in use;
- who belongs to each group;
- which apps are public; and
- whether former users still have access.

Remove access that is no longer needed.

## Respond to a security warning

Do not immediately turn off the security protection. Note the time, address,
affected account or app, and what the server blocked. Check the activity
history for related changes. If an identity or secret may be compromised,
disable it and rotate the related credentials.

## Practise recovery

At regular intervals, restore a backup to a separate test machine. Check that
the data is present and an owner can sign in. Update your recovery notes after
every test.

## When to ask an experienced administrator

Get help if you need to change firewall or network settings, recover a whole
server, repair a damaged database, edit the resident-assistant configuration,
or expose MCP to another machine. Preserve logs and operation numbers before
making manual changes.
