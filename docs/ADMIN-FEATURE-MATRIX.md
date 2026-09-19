# Native Admin Feature Matrix

**Status:** current as of the UI rectification pass (see
[`UI-REVIEW-AND-RECTIFICATION-PLAN.md`](UI-REVIEW-AND-RECTIFICATION-PLAN.md)).
**Target:** Debian 12; native NostrHost UI and API only.

The admin console (`forks/admin/app`) is a single-sign-on SPA: the portal
session cookie (`nostrhost.portal`) authenticates every native API request,
with a NIP-07 browser signer as a fallback. Its route table
(`forks/admin/app/src/router/routes.ts`) is the source of truth for what
ships; this table tracks each routed screen against the native capability it
exercises (`forks/yunohost/src/nostrhost/api.py`, the `ToolSpec` registry in
`native_ops.py`).

| Screen | Route | Native capability | State |
| --- | --- | --- | --- |
| Overview | `/` | `system.status`, `/package/healthz`, `system.version`, identity list, `audit.list` | Host status strip, recent operations, versions, linked identities. |
| Applications | `/apps` | catalogue + installed inventory, install/upgrade/remove/settings plan-and-apply | Combined trusted-catalogue/installed view; typed plan review before apply. |
| Catalogue | `/catalogue` | `catalog.list`/`catalog.get` | Read-only browse; installs hand off to Applications. |
| Package authoring | `/packages` | `package.plan` | Read-only manifest editor + deterministic resource plan; never installs. |
| Users | `/users` | `user.list/create/update/delete`, identity linking | Create/edit/delete accounts; link a Nostr identity per account. |
| Identities | `/identities` | `identity.list`, link/revoke | Linked-identity administration independent of the owning user. |
| Groups & permissions | `/groups` | `user.group.*`, `user.permission.*` | Group membership and per-permission access; core groups protected from deletion. |
| Domains & DNS | `/domains` | `domain.*`, `dns.*`, credential store | Domain lifecycle, DNS records, free-hostname claims, credential refs. |
| Firewall | `/firewall` | `firewall.list/open/close/reload` | Port/UPnP management; closing 22/80/443 requires typing the port to confirm. |
| Services | `/services` | `service.status/control` | Status-aware start/stop/restart; disruptive actions confirm first. |
| Updates | `/updates` | `updates.check/refresh/apply`, `system.migrations/migrate` | Pending package updates and platform migrations. |
| Backups | `/backups` | `backup.list/create/info/restore/delete/check/stats/policy.read/policy.set/schedule` | Restic restore points, create/restore/forget, integrity check, retention policy and scheduled backups. |
| Recovery | `/recovery` | `state.status/history/diff/rollback.plan/reconcile.plan/publish`, `rollback.apply` | Known-good marker, history/diff, assisted rollback plan-and-apply, disaster-recovery readiness and state replication. |
| Diagnosis | `/diagnosis` | `diagnosis.run/ignored/ignore/unignore` | Per-category health checks; admin-gated ignore-filter controls. |
| Settings | `/settings` | `settings.list/get/set/reset/reset_all` | Global YunoHost settings; reset-all requires typed confirmation. |
| Power | `/power` | `system.reboot/shutdown` | Reboot (disruptive) and shutdown (destructive, typed confirmation). |
| History & approvals | `/operations` | `audit.list/get`, approve/reject, `/package/notify/signers` | Every submitted operation with its outcome; approve or reject anything parked pending approval. Register the node with the admin's own NIP-46 signer (`bunker://` or `nostrconnect://` QR) so approvals reach it from any browser/session. |
| AI management | `/ai` | agent status/mode, MCP capability grants, model download, contribution settings | Resident admin agent control, MCP-connected agent scopes, local model management, data-sharing settings. |

## Known gaps

These native capabilities exist (CLI/`ToolSpec` registry or core) but have no
browser route or screen yet:

- **Logs** — `logs.read`, `logs.web`, `service.history` tools exist; no
  `/package/logs/*` route or `/logs` screen.
- **Certificates** — `domain.cert.info`/`domain.cert.install` exist; no route
  or Domains tab.
- **Legacy app operations** — `app.change_url`, `app.config.read/set` exist
  for apps installed outside the catalogue; Applications has no actions for
  `installed-unlisted` apps.
- **Mail-optional user creation** — `user.create` still requires a mail
  domain and password even though sign-in is Nostr-only
  (`docs/MAIL-RETIREMENT.md`); blocked on the native account model described
  in `docs/LDAP-RETIREMENT.md`.
- **Capability-aware navigation** — the session response carries `admin`
  only, not a capability list, so the sidebar and route guard are all-or-
  nothing rather than gated per capability (`docs/ROLE-AND-APP-ACCESS-DESIGN.md`
  §UI).

## Design constraints carried forward

1. No browser key persistence — the portal session cookie or a NIP-07/NIP-46
   signer authenticates every request.
2. Package authoring stays read-only: manifest validation and planning only,
   never an install button.
3. Every write goes through the signed operation chain
   (`nostr_operations.run_signed_chain`); the API never accepts the browser's
   proposed operation objects as authority, and a lifecycle response's
   `ok: false` (rejected, failed, or pending approval) is surfaced to the
   operator rather than treated as success.
