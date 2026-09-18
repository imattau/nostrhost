# Diagnosis engine

The diagnosis engine runs independent health-check categories and stores their
latest reports. Admin, CLI, API, and MCP read the same results.

## Report model

A category report has an ID, timestamp, cache age, and a list of findings.
Each finding has a status:

- `SUCCESS` — the check passed;
- `INFO` — useful context, not a problem;
- `WARNING` — degraded or risky behaviour; or
- `ERROR` — a check failed or needs prompt action.

Findings can include a summary, details, machine-readable metadata, and data
for support or automation.

## Dependencies and cache

Categories may depend on earlier checks. If a dependency has no report or a
blocking error, the dependent category is skipped rather than producing a
misleading result. Cached reports avoid repeating slow network and system
checks; a forced run refreshes them.

Reports are stored under `/var/cache/yunohost/diagnosis/`. Treat the cache as
derived evidence, not a backup or configuration source.

## Ignoring a finding

An ignore filter matches metadata on a current warning or error. Ignoring hides
the finding from normal issue summaries; it does not fix the condition or stop
the check. Success and informational items are not ignorable.

Adding or removing an ignore filter is an audited write requiring the
appropriate capability and approval. Review ignored findings periodically and
record the operational reason outside the filter itself.

## Interfaces

The shared operation catalogue includes:

- `diagnosis.run` to refresh selected categories;
- `diagnosis.ignored` to list filters;
- `diagnosis.ignore` to add a matching filter; and
- `diagnosis.unignore` to remove one.

Admin provides the normal report and filter interface. MCP offers additional
read-only incident composites described in
[MCP diagnosis tools](mcp-diagnosis-tools.md).

## Notifications

When an automatic run finds issues, NostrHost can publish a warning notice to
the local relay. Notification delivery is best-effort and never changes the
diagnosis result.
