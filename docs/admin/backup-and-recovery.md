# Backup and disaster recovery

Recovery combines four layers: signed operational history, versioned
configuration state, Restic data archives, and the Debian host itself. None is
a complete backup on its own.

## Configuration state

NostrHost records desired configuration in a versioned repository. Changes can
be compared, marked healthy, and reconciled with the machine. The repository
must not contain private keys, passwords, tokens, or raw backup data.

Before a high-risk operation, record the current state. Afterward, run health
checks before treating the new state as known-good. A state rollback restores
configuration intent; a Restic restore recovers files and app data.

## Data backups

Restic encrypts and deduplicates system and application data. Configure a
destination that survives loss of the server. Monitor backup completion,
repository growth, retention, and integrity.

Use Admin for normal backup work or inspect:

```bash
nostrhost backup --help
nostrhost app backup --help
```

## Backup policy

A practical policy defines:

- which apps and system parts are included;
- backup frequency and retention;
- where the repository is stored;
- who controls its credentials;
- acceptable recovery-point and recovery-time objectives; and
- how often restoration is tested.

Create an on-demand backup before app upgrades, schema changes, bulk user or
permission changes, and major package updates.

## Restore a single app

Choose the smallest archive and scope that solve the problem. Prevent new
writes, preserve evidence, verify the archive, restore, and then check the app
service, route, permissions, health, and data. Record the restore as an
operation and investigate the original failure.

## Rebuild the server

1. Isolate the failed host if compromise is possible.
2. Prepare a clean Debian 12 target and confirm storage capacity.
3. Install the trusted NostrHost package source.
4. Transfer the recovery bundle and backup credentials through a secure path.
5. Use `nostrhost postinstall restore --help` to select the existing identity,
   configuration state, and Restic snapshot.
6. Reconcile the host, run diagnosis, and inspect failed services.
7. Verify DNS, HTTPS, sign-in, roles, apps, scheduled jobs, notifications, and
   a new backup.
8. Rotate exposed credentials and retain incident evidence.

Never run the new-server setup when the replacement must assume an existing
identity.

## Recovery test

Perform restores in an isolated VM. A passing exercise proves that off-server
material is accessible, credentials work, the repository is readable, the
configuration reconciles, data is present, and an owner can authenticate.
Document the observed recovery time and any manual steps.
