# Updates and routine maintenance

Treat an update as a controlled server change with a backup, observable result,
and recovery path.

## Before updating

1. Check diagnosis, failed services, free space, and backup health.
2. Read the package changes and compatibility information.
3. Create a fresh backup of affected apps and system state.
4. Confirm console access and the rollback method.
5. Test the update on a representative VM when the server matters.

Check available updates with Admin or:

```bash
nostrhost updates check --output-as json
```

## Apply updates

Use Admin or the normal Debian package tools for the supported NostrHost
repository. Do not install Python packages manually into the managed runtime;
its dependencies are supplied by Debian packages and the NostrHost runtime
package.

Update native apps through NostrHost so the package plan, approval, safety
backup, execution, and audit checks remain intact.

## Verify afterwards

- confirm all expected services are running;
- run diagnosis and inspect new warnings;
- test owner sign-in and one protected app;
- verify HTTPS certificates and routing;
- inspect failed operations and security decisions; and
- create a successful post-update backup.

## Compatibility services

Some installations may still contain a legacy web backend or transitional
package names. Keep those services private, allow the packaged upgrade path to
manage them, and do not build new dependencies on compatibility interfaces.

## If an update fails

Stop further changes, retain the operation ID and logs, and determine whether
the failure affected packages, configuration, or app data. Prefer the narrowest
recovery: retry a safe package configuration step, reconcile configuration,
restore one app, or rebuild from backup. Do not mark a failed state as healthy.
