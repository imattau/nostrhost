# Apps

An app is a service that runs on your NostrHost server. It might be a website,
notes tool, file-sharing service, or another web application.

## Before installing an app

Open the app in the Admin catalogue and check:

- who published it;
- whether NostrHost trusts or has tested that publisher;
- which domain or web address the app will use;
- what storage and services it needs;
- whether its data is included in backups; and
- who will be allowed to open it.

NostrHost shows the changes an app wants to make before applying them. Read the
summary, especially warnings about data removal, public access, or changes that
may be difficult to undo.

## Install an app

1. Open **Admin**.
2. Choose **Apps** and open the catalogue.
3. Select an app.
4. Choose its domain, address, and access settings.
5. Review the proposed changes.
6. Approve the installation if everything looks correct.
7. Wait for the result and open the app to test it.

Some actions require the server owner to approve a signed request. This is a
security check, not an error.

## Decide who can use it

An installed app can be private, shared with selected people or groups, or
public. Start private unless the app is meant for everyone on the internet.

See [Identity and access](identity-and-access.md) before making an app public
or sharing it with a large group.

## Update an app

Before an update:

1. Check that the server is healthy and has enough free space.
2. Read the update summary.
3. Make a fresh backup of the app.
4. Confirm that the backup completed.
5. Apply the update.
6. Open the app and check its important features.

If the app stops working, keep the operation number shown by Admin. It helps
connect the failure to the correct logs and backup.

## Remove an app

Removing an app may also remove its data. Make and verify a final backup first.
Read the removal summary carefully, then keep the backup until you are certain
the app and its data are no longer needed.

## For package authors

Creating app packages is a developer task. It is covered separately in
[Writing a native app package](../dev/native-app-packages.md).
