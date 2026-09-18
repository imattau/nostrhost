# Backups and recovery

A backup is your way back after an update fails, data is deleted, or the server
is lost. NostrHost backups are encrypted, but you must keep them somewhere
other than the server they protect.

## What recovery needs

A complete recovery needs:

- recent backups of apps and system information;
- the recovery file created during first-time setup;
- the password or credentials for the backup location;
- access to your domain and DNS account; and
- an owner identity that still works.

Keep these items in protected storage away from the server. Consider giving an
appropriate trusted person instructions for accessing them in an emergency.

## Make a backup

1. Open **Admin** and choose **Backups**.
2. Choose the apps and system information to include.
3. Start the backup.
4. Wait for it to finish.
5. Open its details and confirm the expected items are listed.
6. Confirm that a copy exists at your separate backup location.

Make an extra backup before updating or removing an app, changing many users,
or making a major server change.

## Restore one app

If one app is damaged:

1. Stop using it so new changes do not conflict with the restore.
2. Choose a backup made before the problem.
3. Check that it contains the app and its data.
4. Restore only that app when possible.
5. Test its web address, sign-in, permissions, and important data.

Keep the failed operation number and logs until you understand what happened.

## Replace a lost server

Full recovery is an administrator task because it can replace everything on a
machine. At a high level, you will:

1. Install Debian 12 and NostrHost on a clean replacement machine.
2. Use the saved recovery file to restore the existing server identity.
3. Connect to the backup location.
4. Restore the chosen backup.
5. Check domains, secure connections, identities, permissions, and apps.
6. Make a new backup after the restored server is healthy.

Do not set the replacement up as a brand-new server. That creates new keys and
can prevent it from using the old server's identity and history.

The detailed procedure is in
[Backup and disaster recovery](../admin/backup-and-recovery.md).

## Test your backups

A completed backup message is not proof that recovery works. Periodically
restore to a separate test machine. Check that the backup can be opened, the
apps contain their data, and an owner can sign in without using the original
server.
