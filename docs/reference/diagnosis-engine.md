# Diagnosis engine

The `yunohost diagnosis` system: a per-category health-check engine
inherited from stock YunoHost, largely unmodified by NostrHost. This page
documents its mechanics precisely enough that the webadmin UI, the MCP
tool surface, and any future diagnoser category can all be built against
it without reading `src/diagnosis.py` first. Source of truth:
[`../../forks/yunohost/src/diagnosis.py`](../../forks/yunohost/src/diagnosis.py)
and [`../../forks/yunohost/src/diagnosers/`](../../forks/yunohost/src/diagnosers/).

## Shape

Each diagnoser is a Python module under `src/diagnosers/`, named
`??-category.py` (a two-digit numeric prefix is required — it controls run
order and is how the engine discovers categories at all). It defines a
`MyDiagnoser` class subclassing `Diagnoser` and sets:

- `id_` — the category id (`ip`, `dnsrecords`, `mail`, …), taken from the
  filename after the prefix.
- `cache_duration` — seconds before a cached report is considered stale.
- `dependencies` — other category ids that must be error-free before this
  one runs (e.g. `apps` depends on `services`).
- `run(self)` — a generator yielding one dict per check performed.

```text
src/diagnosers/??-*.py  →  _list_diagnosis_categories()  →  category ids
                          (glob on the two-digit prefix, prefix stripped)
```

`_load_diagnoser(name)` re-globs for the exact `??-{name}.py` file,
imports it as `yunohost.diagnosers.{module_id}`, and instantiates
`MyDiagnoser()`. Exactly one file must match, or it's a hard error — so
two categories can never share an id, and a category can't be split
across files.

The current 10 categories, in run order:

| Prefix | Category | Checks |
|---|---|---|
| `00` | `basesystem` | Hardware/virtualization, kernel, Debian release, package-version consistency, Meltdown, repo hygiene, recent auth failures, known security advisories |
| `10` | `ip` | IPv4/IPv6 connectivity, DNS resolution, `resolv.conf` sanity, public IP discovery |
| `12` | `dnsrecords` | Expected vs. actual DNS records per domain, domain expiration |
| `14` | `ports` | Whether locally-listened ports are reachable from outside |
| `21` | `web` | Reverse-proxy config freshness per domain, special-use TLD detection, remote HTTP reachability, NAT hairpinning |
| `24` | `mail` | SMTP/IMAP reachability, EHLO banner, FCrDNS, DNSBL membership, mail queue size |
| `30` | `services` | systemd status + regen-conf state per managed service |
| `50` | `systemresources` | RAM/swap/disk free %, OOM-reaper kills |
| `60` | `mcp` | **NostrHost-native.** `nostr-operationsd` (the operation executor) and `nostrhost-catalog` (package publish daemon) systemd state, plus whether the control relay's `allowed_kinds` includes the catalogue-declaration kind (32267) |
| `70` | `regenconf` | Manually-modified conffiles, insecure `sshd_config`, sshd port consistency |
| `80` | `apps` | Installed apps' alpha/legacy status and security advisories |

`21-web.py` and `24-mail.py` carry NostrHost-specific logic changes (most
notably, `24-mail.py` now yields nothing unless `mail_stack_installed()` —
see [`../MAIL-RETIREMENT.md`](../MAIL-RETIREMENT.md)); the other seven
inherited categories are unmodified from stock YunoHost.

`60-mcp.py` is the one category NostrHost added outright, not just
modified — it follows the same `Diagnoser` contract as every stock
category (same file-naming convention, same report shape), so it shows
up in `diagnosis_show()`, the CLI, and any future webadmin UI with no
special-casing. Its own docstring is explicit about what it deliberately
does **not** check yet: the MCP HTTP endpoint itself, its reverse-proxy
route, DNS, or TLS (`docs/MCP-SETUP-RUNBOOK.md` §§2-4) — those depend on
a hostname `nostrhost-mcp` has no standard, discoverable config for yet
(see `../MCP-TRANSITION.md` Phase 6).

## Report format

`diagnose()` builds one report per category:

```jsonc
{
  "id": "ip",
  "cached_for": 86400,
  "description": "IP addresses and connectivity",   // added by Diagnoser.i18n()
  "items": [
    {
      "meta": { "version": 4 },        // identifies *what* was tested
      "status": "SUCCESS",             // SUCCESS | INFO | WARNING | ERROR
      "summary": "IPv4 is available",  // i18n key, or (key, {data}) tuple pre-translation
      "details": ["..."],              // optional, same key/tuple shape as summary
      "data": { "ipv4": "203.0.113.4" },  // optional raw values used to fill the summary/details
      "ignored": false                 // added by add_ignore_flag_to_issues(), WARNING/ERROR only
    }
  ],
  "timestamp": 1737331200              // added on read, from the cache file's mtime; -1 if never run
}
```

Only `WARNING` and `ERROR` items count as "issues" — for the CLI's
summary line, for `diagnosis_show(issues=True)`, and for the ignore-filter
mechanism below. `SUCCESS`/`INFO` items are never ignorable and never
counted.

## Caching

Reports are written to `/var/cache/yunohost/diagnosis/{id}.json`
(`DIAGNOSIS_CACHE`). `Diagnoser.diagnose(force=False)`:

1. Skips re-running if `cached_time_ago() < cache_duration`, unless
   `force=True`.
2. Checks every id in `dependencies` via `get_cached_report()`; if any
   dependency has no cache yet, or has an `ERROR` item, this category's
   run is skipped entirely (return code `1`, empty report) rather than
   producing a possibly-nonsensical result.
3. Runs `self.run()`, strips empty `details`, writes the new report to
   cache, translates it (`Diagnoser.i18n()`), and flags ignored items.
4. Logs one summarized `success`/`warning`/`error` line for the whole
   category.

`Diagnoser.get_cached_report(id_, item=None)` is how every read path
(`diagnosis_get`, `diagnosis_show`, dependency checks) fetches a report —
it returns a stub `{"id", "cached_for": -1, "timestamp": -1, "items": []}`
if nothing has ever been cached for that category, rather than raising.

## The ignore-filter workflow

Filters live in `/etc/yunohost/diagnosis.yml` (`DIAGNOSIS_CONFIG_FILE`),
under `ignore_filters: {category: [criteria_dict, ...]}`:

```yaml
ignore_filters:
  ip:
    - version: 6              # ignore all issues where meta.version == 6
  dnsrecords:
    - domain: yolo.test
      category: xmpp          # ignore only this domain+category combo
    - {}                      # ignore *all* dnsrecords issues
```

`issue_matches_criterias(issue, criterias)` matches a criteria dict
against an issue's `meta` dict — every key in the criteria must be present
in `meta` with an equal (string-compared) value. An empty criteria dict
(`{}`) matches every issue in that category.

`add_ignore_flag_to_issues(report)` runs on every report generation *and*
every cached-report read, setting `item["ignored"] = True/False` on every
`WARNING`/`ERROR` item. `SUCCESS`/`INFO` items never get an `ignored` key
touched beyond the base loop, since they're skipped by the `status not in
["WARNING", "ERROR"]` guard.

**Adding a filter only succeeds if it currently matches a real issue** —
`diagnosis_ignore` re-fetches the category's current issues and refuses
with `diagnosis_ignore_no_issue_found` if the new criteria don't match
anything, so you can't accumulate filters for problems that don't exist
(or don't exist *yet*, which is the tradeoff: fixing an issue and having
it recur later means re-adding the filter).

## CLI / API surface

| Function | Decorator | Does |
|---|---|---|
| `diagnosis_get(category, item)` | — | Fetch one cached item by category + criteria dict (`key=value` list, converted to a dict). |
| `diagnosis_show(categories, issues, full, share, human_readable)` | — | Assemble reports across categories. `full=False` (default) strips `meta`/`ignored`/`data` and drops ignored items; `issues=True` filters to `WARNING`/`ERROR` only; `share=True` uploads a plaintext dump via yunopaste; `human_readable=True` prints instead of returning. |
| `diagnosis_run(categories, force, except_if_never_ran_yet, email)` | `@is_unit_operation(sse_only=True)` | Runs one or more categories via `_load_diagnoser(...).diagnose(force=force)`; aggregates `WARNING`/`ERROR` items into `issues`; emails on completion if `email=True`. **Streamed over SSE, not written as a classic operation-log file** — this matters for anything calling it out-of-band (see the [MCP tool reference](mcp-diagnosis-tools.md#diagnosis_run) for what that requires in practice). |
| `diagnosis_ignore(filter, list=False)` / `diagnosis_unignore(filter)` | `@is_unit_operation(flash=True)` | Add/remove an ignore-filter criteria list; `filter` is `[category, "key=value", ...]`. |

There is **no moulinette `actionsmap.yml`** for this surface in this fork
— moulinette was removed entirely (see commits `bcb549d41`, `db3aa65d2`).
`diagnosis.py` imports `nostrhost.core.Moulinette` and
`nostrhost.i18n.tr` as its own compatibility shims, and the functions
above are dispatched through NostrHost's own registry
(`forks/yunohost/src/nostrhost/native_ops.py` — the `_safe_diagnosis_*`
wrappers — reachable from both `nostrhost/cli.py` and `nostrhost/api.py`),
not a stock actionsmap.

## The notification hook

`_email_diagnosis_issues()` keeps its stock behavior (build a plaintext
summary via `_dump_human_readable_reports`, send through local
`smtplib`), but now also calls, before sending mail:

```python
from .nostr_notify import SEVERITY_WARNING, publish_notice
publish_notice("diagnosis", SEVERITY_WARNING, f"Automatic diagnosis found {issue_count} issue(s); ...")
```

This publishes a signed kind-2210 "system event" notice to the local
control relay (see `EVENT-PROTOCOL.md §2.3` for the content convention).
It's additive by design — `nostr_notify.py`'s own docstring states the
mail path is untouched, and publish failures are swallowed so an
unreachable relay never blocks the underlying diagnosis run.

## Related

- [MCP diagnosis tools](mcp-diagnosis-tools.md) — the LLM/agent-facing
  surface built on top of everything above.
- [`../MAIL-RETIREMENT.md`](../MAIL-RETIREMENT.md) — the `24-mail.py`
  changes referenced above.
- [`../ADMIN-FEATURE-MATRIX.md`](../ADMIN-FEATURE-MATRIX.md) — tracks that
  the webadmin has no diagnosis screen yet.
