# Mail stack retirement (roadmap §18.2 / §18.7)

This document tracks the work to remove the inherited YunoHost mail stack
from the default NostrHost installation. It is the working inventory and
phase plan called for by roadmap §18.7:

> Do not remove the mail stack until all NostrHost components that currently
> depend on local mail have been identified and migrated.

Scope note: the mail stack itself (Postfix, Dovecot, Rspamd, DKIM, mailbox
provisioning, diagnosis checks) lives in the `yunohost` core fork
(`imattau/nostrhost-yunohost`, checked out at `forks/yunohost`), not in this
umbrella repo. This document is the cross-repo plan; the actual package
removal/config changes land as commits in that fork once each dependency
below is classified and migrated.

## Target model (roadmap §18.2)

```text
Nostr  = native identity, native private messaging, native system notifications
Email  = optional external integration or separately installed application
```

Mail is not an optional *install profile* toggle on the core package — it is
removed from core entirely. Postfix/Dovecot/OpenDKIM are no longer a
NostrHost dependency at all; if a user wants local mail, they install it the
same way they'd install any other app. Applications that need email use an
external SMTP provider, a self-hosted mail application, a separately
installed mail app, or their own configuration — NostrHost stops assuming
every server is itself a mail server.

## Dependency inventory

Classification per dependency, per roadmap §18.7:

- **Replace with Nostr notification** — migrate to the notification service
  from §18.1 (encrypted Nostr DM to the relevant npub).
- **Remove entirely** — dropped from core outright (either superseded by
  native identity, §18.3, or — for the mail packages themselves — no longer
  a core dependency at all; installable afterward as an app like anything
  else, not a toggleable "optional install profile").
- **Retain (compatibility)** — kept as-is for Unix/legacy application needs.

| # | Dependency | Where | Classification | Notes |
|---|---|---|---|---|
| 1 | Postfix (SMTP) | `forks/yunohost` `debian/control`, `hooks/conf_regen/19-postfix` | Remove entirely (from core) | **Done** — dropped from core `Depends`; the conf_regen hook self-guards (`ynh_package_is_installed`) so it's a no-op unless a user has installed it separately. |
| 2 | Dovecot (IMAP, local mailboxes) | `forks/yunohost` `debian/control`, `hooks/conf_regen/25-dovecot` | Remove entirely (from core) | **Done** — same treatment as row 1. |
| 3 | Rspamd (spam filtering) | yunohost core | N/A | This fork never actually depended on rspamd (checked `debian/control` — not present); nothing to remove. |
| 4 | DKIM signing / key generation | `forks/yunohost` `debian/control`, `hooks/conf_regen/30-opendkim` | Remove entirely (from core) | **Done** — same treatment as row 1. |
| 5 | SMTP submission (587/465) | yunohost core, firewall/port defaults | Remove entirely (from core) | No explicit port-587/465 firewall default was found tied specifically to mail; port exposure is a consequence of Postfix being installed at all, which is now row 1's job. Revisit if a dedicated firewall rule turns up. |
| 6 | MX / SPF / DMARC domain-config assumptions | `forks/yunohost` `src/dns.py` domain DNS template generation | Remove entirely (from core) | **Not done** — DNS suggestion templates weren't touched in Phase 3; still assumes mail. Follow-up. |
| 7 | Mandatory mailbox per user (`yunohost user create`) | yunohost core `user.py` | Remove entirely | Superseded by §18.3 (npub-centred identity); a Unix-compatible username may remain without a mailbox. Not started (Phase 4) — `user.py`'s existing dovecot check already degrades gracefully in the meantime. |
| 8 | `root@`/`admin@` aliases to first user | yunohost core | Retain (compatibility) | Only meaningful once mail is installed; kept as alias config, not a mailbox requirement. |
| 9 | Certificate expiry/renewal notifications | `forks/yunohost` `src/certificate.py` `_email_renewing_failed()`, cron `yunohost-certificate-renew` | Replace with Nostr notification | **Done** — also publishes a kind-2210 `certificate` notice (`imattau/nostrhost-yunohost#1`). Mail send itself untouched. |
| 10 | Backup completion/failure notifications | yunohost core `backup` hooks | Replace with Nostr notification | **No existing mail producer found** in `forks/yunohost` (`src/backup.py`/`src/utils/*` have no `smtplib`/mail-notify call) — nothing to migrate here; if this gets added later it should publish a kind-2212 `backup` notice directly rather than mailing first. |
| 11 | Diagnosis mail-category checks (`24-mail.py`) | `forks/yunohost` `src/diagnosers/24-mail.py` | Remove entirely (skip when not installed) | **Done** — the diagnoser now returns immediately (yields nothing) unless `mail_stack_installed()`. `imattau/nostrhost-yunohost#2`. |
| 12 | System cron/systemd mail output (`MAILTO=`, sendmail-based cron mail) | `forks/yunohost` `src/diagnosis.py` `_email_diagnosis_issues()`, cron `yunohost-diagnosis` | Replace with Nostr notification | **Done** — same call site as row 9's diagnosis email; now also publishes a kind-2210 `diagnosis` notice. |
| 13 | Admin (webadmin) mail-status widgets and mail settings pages | `forks/admin` | Remove/hide | **Not done** — separate repo, not touched yet. |
| 14 | SSO/Portal identity assumptions (login by email, password reset by email) | `forks/portal`, `forks/ssowat` | Remove entirely (long-term) | Superseded by Nostr-native login (§4, §18.3); email becomes optional contact metadata. |
| 15 | App packaging helpers assuming a local mailbox/SMTP relay exists | YunoHost app helpers (`ynh_*` mail helpers) consumed by installed apps | Retain (compatibility) | Apps that genuinely need mail should be pointed at an external SMTP provider or an optional local mail app, not assume the platform provides one. |
| 16 | `nostrhost-catalog` / packaging assumptions about a working `mail@domain` for app maintainer contact | `libs/nostrhost-catalog` | Remove entirely | Catalogue metadata should not require a functioning mailbox to register a maintainer contact; an npub is sufficient. |

Each row above is a placeholder classification pending confirmation against
the current `forks/yunohost` source at its pinned commit (`baseline/pins.yml`);
treat this table as the starting inventory, not a final audit — update it as
each dependency is actually located and migrated in the fork.

## Phased plan (roadmap §18.7 implementation sequence)

Mail retirement is gated on the native notification service (§18.1) and on
Portal/Admin + state/recovery being operational (§7–§10), per the roadmap's
sequencing. Phases below track that ordering:

1. **Phase 0 — Inventory (this document).** Enumerate and classify every
   mail dependency (table above); keep it updated as the fork is audited.
2. **Phase 1 — Native notification service (§18.1).** Land the
   event → private-relay → notification-service → encrypted Nostr message
   pipeline. Nothing in mail retirement can proceed before this exists,
   since it is the replacement channel for rows 9, 10 and 12 above. Design
   in progress: `docs/NOTIFICATION-SERVICE.md`.
3. **Phase 2 — Migrate internal notification dependencies.** Re-point
   certificate, backup, and cron/systemd notifications (rows 9, 10, 12) at
   the notification service. Mail stack still installed by default at this
   point; this phase only removes *internal* reliance on it. Implemented for
   rows 9 and 12 (certificate renewal and diagnosis-cron mail both now also
   publish a structured notice); row 10 turned out to have no existing mail
   producer to migrate. See `imattau/nostrhost-yunohost#1`.
4. **Phase 3 — Remove mail from core.** Not a toggleable install profile —
   Postfix/Dovecot/OpenDKIM (rows 1, 2, 4) are dropped from core's hard
   package dependencies outright; every code path that assumed they were
   always present (domain add/remove, settings post-change hooks, the
   "mail" app resource) now checks `mail_stack_installed()` first and
   degrades gracefully. The mail diagnoser (row 11) skips entirely when not
   installed. Done for rows 1, 2, 4, 11 — see `imattau/nostrhost-yunohost#2`.
   Still open: DNS MX/SPF/DMARC templates (row 6) and Admin UI mail panels
   (row 13, `forks/admin`).
5. **Phase 4 — Remove the mandatory-mailbox assumption (§18.3).** Stop
   requiring a mailbox on user creation (row 7); keep alias compatibility
   (row 8) conditional on the mail stack being present.
6. **Phase 5 — Identity model follow-through.** Remove SSO/Portal email-based
   login/reset assumptions (row 14) and catalogue maintainer-contact
   assumptions (row 16) once native Nostr login and npub-based catalogue
   metadata are in place.
7. **Phase 6 — State integration (§18.6).** Represent the resulting
   optional-mail configuration in `nostrhost-state` under
   `state/integrations/email.toml`, following the standard state lifecycle
   (signed request → policy evaluation → executor → health validation →
   post-change state).

## Status

| Phase | Status |
|---|---|
| 0 — Inventory | ⏳ in progress (this document) |
| 1 — Native notification service | ✓ implemented in `nostrhost-control` (`nostrhost-notify` binary, branch `claude/mail-stack-removal-notify-service`); see `docs/NOTIFICATION-SERVICE.md` |
| 2 — Migrate internal notifications | ✓ done (rows 9, 12; row 10 had nothing to migrate) — `imattau/nostrhost-yunohost#1`, branch `claude/mail-stack-removal-phase2` |
| 3 — Remove mail from core | ⏳ mostly done (rows 1, 2, 4, 11) — `imattau/nostrhost-yunohost#2`, branch `claude/mail-stack-removal-phase3`; rows 6, 13 still open. **Not VM-tested** — see PR's Risk section. |
| 4 — Remove mandatory mailbox | ⏳ not started |
| 5 — Identity model follow-through | ⏳ not started |
| 6 — State integration | ⏳ not started |

## Non-goals

- This does not prevent applications from sending or receiving email.
  External SMTP providers, self-hosted mail applications, and optional local
  mail packages remain fully supported; only the *mandatory, default*
  platform mail server is being removed.
- No change to `forks/yunohost`'s pinned baseline (`baseline/pins.yml`)
  happens here — the fork remains source-identical until Phase 1 lands and
  the fork's `derivative` flag is set, matching the pattern already used for
  the identity layer (`BASELINE.md`).
