# NostrHost UI review and rectification plan

**Date:** 2026-09-14
**Scope:** every shipped UI surface — the admin console (`forks/admin/app`, 17 routed views, 19 API adapters, shell, primitives), the user portal (`forks/portal`, 4 pages, layout, auth middleware), and the backend contracts they depend on (`forks/yunohost/src/nostrhost/api.py`, `portal_api.py`, `native_ops.py`, the core `user.py`/`firewall.py`/`tools.py` return shapes, and the Caddy route table).
**Method:** full read of the admin and portal source, cross-checked line by line against the backend route table, tool registry and core return shapes; `vue-tsc` and ESLint runs on the admin app (both pass, one unused-var warning); design-record docs (`ADMIN-FEATURE-MATRIX`, `NATIVE-ADMIN-API`, `ROLE-AND-APP-ACCESS-DESIGN`, `MAIL-RETIREMENT`, `ALPHA-PLAN`) used as the statement of what the system expects the UI to do.

---

## 1. Executive summary

The admin console is structurally sound (typed adapters, route-derived nav, session-based sign-in, plan-then-apply for app lifecycle) but it was built screen-by-screen without a shared operation, notification, or layout layer, and several screens were never run against the real backend. The most important problems:

1. **Silent failure on every signed write.** The backend returns HTTP 200 with `ok:false` when the policy chain rejects, fails, or parks an operation for approval. Nine of the ten write screens ignore that and show a green "submitted" notice. Users will believe a firewall port is closed, a backup deleted, or a user created when nothing happened.
2. **Two screens are broken outright** against the current backend: Groups & permissions (response shape mismatch, shows one bogus group called `groups`) and the portal's account/password forms (POST to a route the portal API does not serve; the portal's error handler then replaces the whole app with a fatal error page).
3. **Navigation dead ends and wrong links**: the sidebar "Portal" link points at the retired `/yunohost/sso/` path; a signed-in non-admin lands on an "Access denied" page with no way to sign out; the logo links to Package authoring instead of Overview.
4. **Network chatter**: the API client probes `/package/session` before every call, every view calls `sync()` (another probe) on load and on every action, and the router re-probes on every navigation. Opening AI management fires roughly 30 HTTP requests to render.
5. **One MCP scope name is wrong** (`system.read` in the UI, `server.read` in the backend), so the recommended "Read-only" preset grants a scope that does not exist.
6. **Missing functionality the backend already provides**: operation history/audit, live progress (SSE endpoint exists, never consumed), service logs and restart history, certificate status/renewal, host status (load, hostname), legacy-app removal, `change_url`, typed settings schemas. All exist as CLI tools; most lack an HTTP route, and none have a screen.
7. **Design debt**: 17 flat sidebar entries with no grouping, four different page widths, dark-only theme with no toggle (portal has light/dark/auto), boilerplate header + three alerts copy-pasted into every view, `danger` buttons used to confirm benign actions, 10–11 px labels, a hard-coded "State reconciled" status light, and inconsistent product naming across five surfaces.

The plan below fixes correctness first (Phase 0, a few days), then builds the shared layer that every screen needs (Phase 1), reworks each screen on top of it (Phase 2), adds the missing capabilities with their backend routes (Phase 3), and closes with tests, i18n, accessibility and docs (Phase 4).

---

## 2. Findings

Severity: **S1** breaks a user task or misleads about system state · **S2** wrong or degraded behaviour · **S3** usability/consistency · **S4** polish/code health.

### 2.1 Correctness bugs

| ID | Sev | Where | Finding | Evidence |
|---|---|---|---|---|
| C1 | S1 | All write screens except Applications and Diagnosis | `run_signed_chain` returns `{ok:false, state, reason, pending_approval?}` with HTTP 200 on rejection, failure, or pending approval. Domains, Backups, Firewall, Users, Groups, Settings, Power, Updates, credentials and free-hostname flows read only `request_id` and show a success notice. | `forks/yunohost/src/nostr_operations.py:1391-1404`; e.g. `BackupsView.vue:111`, `FirewallView.vue:107`, `PowerView.vue:34`. Only `nativeDiagnosis.ts:runLifecycle` checks `ok`; the app lifecycle routes map it to HTTP 409 server-side. |
| C2 | S1 | Groups & permissions | `user_group_list()` returns `{"groups": {...}}`; `getGroups()` returns it unwrapped and the view iterates `Object.keys()` → a single group named `groups` with no members; the "Grant access to…" select offers only `groups`. | `forks/yunohost/src/user.py` (`return {"groups": groups}`), `nativeGroupsPermissions.ts:31`, `GroupsView.vue:56,843`. |
| C3 | S1 | Portal › Edit | `UserInfoForm` and `UserPasswordForm` POST `/update`; `portal_api.py` registers no such route. `useApi` treats any non-400/401 error as fatal → the whole portal is replaced by the error page. | `forks/portal/components/UserInfoForm.vue:39`, `UserPasswordForm.vue:50`, `forks/yunohost/src/nostrhost/portal_api.py:56-67`, `forks/portal/composables/api.ts:811`. |
| C4 | S1 | Sidebar | "Portal" link is `/yunohost/sso/`; Caddy serves the portal at `/nostrhost/sso/` and answers the old path with the plain-text root responder. `doc/UI-REDESIGN.md` documents the wrong path too. | `AppSidebar.vue:32`, `forks/yunohost/conf/caddy/caddy_domain.conf:44`. |
| C5 | S1 | Connect gate | A signed-in non-admin sees "Access denied" with no sign-out, no "switch account", no link back to the portal. The only sign-out control lives in `AppShell`, which the bare layout does not render. | `ConnectGateView.vue`, `router/index.ts:35-41`. |
| C6 | S2 | API client, router, every view | `request()` calls `sessionProbe()` before every request; every view calls `sync()` (another `/package/session` fetch) in `load()` and again in every action; `router.beforeEach` calls `refreshSession()` on every navigation although its comment says the result is reused. Domains load = 5 API calls + 6 probes; AI management ≈ 12 API + 12 probes + 5 syncs. | `client.ts:15-18`, `useSigner.ts:83-101`, `router/index.ts:19`. |
| C7 | S2 | `/package/session` (backend, UI-facing) | Picks the first enabled identity of the session user; the authorizer accepts any identity that is an admin. A user whose second linked key is the admin key is shown "Access denied" while the API would authorise them. | `api.py:305-333` vs `api.py:_session_admin_pubkey`. |
| C8 | S2 | AI management › MCP access | `SCOPE_TOOLS` uses `system.read`; the backend constant is `server.read`. The recommended Read-only preset therefore grants a non-existent scope and `system.status` stays unreachable. Custom checkbox list has the same bug. | `AiManagementView.vue:69-80`, `forks/yunohost/src/nostr_operations.py:75`. |
| C9 | S2 | Router | Branch 1 stores an absolute URL in `query.redirect`; branch 3 returns that string to `vue-router`, which treats it as an in-app path (`#/https://host/...`). Triggers when an already-signed-in user reaches `/connect?redirect=…` (back button, bookmark). | `router/index.ts:29-45`. |
| C10 | S2 | AI management › Local model | `downloadModel` is a synchronous POST for multi-GB artefacts: no progress, and Caddy/Bottle timeouts will surface as a generic failure while the download continues server-side. | `AiManagementView.vue:352-367`. |
| C11 | S2 | Diagnosis | `load()` awaits `getIgnoreFilters()` and discards the result (dead round-trip); `runNow()` does not refresh the ignored state; no progress or timeout handling for a forced full run (can exceed a minute). | `DiagnosisView.vue:339,348-360`. |
| C12 | S2 | Users | Create form demands "Mail domain" and a password even though mail is retired and sign-in is Nostr-only (`MAIL-RETIREMENT.md`, `LDAP-RETIREMENT.md`); no domain picker although `/package/domain/list` exists; `admin` flag supported by the API but not exposed; no client-side password-length check (backend requires ≥ 8, error only after round-trip). | `UserManagementView.vue:97-138,265-357`, `native_ops.py:495`. |
| C13 | S2 | Domains | The credential field requires the operator to type `secret:dns/<provider>/<name>` by hand even though `getCredentials()` is loaded on the same screen; `removeDomain` never offers `force` and the "apps still use this domain" rejection is swallowed by C1; `domain_list` returns `main` but the type drops it, so the primary domain is never marked in the list. | `DomainsView.vue:480-491,188-208`, `nativeDomains.ts:61`. |
| C14 | S2 | Applications | The plan-review panel renders at the very bottom of the page, below the two-column grid; after "Review install" nothing scrolls or moves focus, so on a populated list the reviewer sees no change. Apps with `installed-unlisted` status (legacy installs) have zero actions although `/package/app/remove` exists. No deep link to a selected app. | `AppManagementView.vue:778-830,679-685`. |
| C15 | S3 | Settings | Editor type is inferred from the current value (null → text) and `settings.list?full=true`, which carries type/choices/help, is never used; long values render inside an uppercase 10 px badge; no validation; "Reset all to defaults" sits in the card title one click from a confirm. | `SettingsView.vue:1188-1210,1369`. |
| C16 | S3 | Updates | Migrations card copy says the subsystem is disabled, but the "major platform upgrade" alert tells the user to review migrations; refresh buttons do not reload the migrations list. | `UpdatesView.vue:729-732,875`. |
| C17 | S3 | Services | "Start" shown for running services, "Stop/Restart" for dead ones; one pending action disables every button on the page; expanded row says logs are unavailable although `logs.read` and `service.history` tools exist. | `ServiceControlView.vue:240-262,211-215`. |
| C18 | S3 | Backups | Apps/system selection is comma-separated free text with no picker (installed apps are one call away); no archive contents/info view; restore has no scope selection; sort assumes `created_at` is a string. | `BackupsView.vue:1057-1081,997-1001`. |
| C19 | S3 | Identities | Username is free text (users list exists); the link form is a second, divergent copy of `IdentityFields`; disabled identities cannot be re-enabled; no marker for the current session's key, admins, or the operator; unsorted, unsearchable. | `IdentitiesView.vue:682-727`. |
| C20 | S3 | Sidebar footer | "State reconciled" green dot and "native control plane" badge are hard-coded; they never reflect health, pending operations, or drift. | `AppSidebar.vue:113-130`. |
| C21 | S3 | Every view | `signerAvailable` is `true` after the first probe, so the "You are not signed in" danger alert is unreachable; the info alert is unreachable because the router already redirected. Both are duplicated in all 17 views. | `useSigner.ts:19-21`, every view's template head. |
| C22 | S3 | API client | Errors lose HTTP status and the backend `code`; 401 does not trigger re-login; no timeout/abort; no idempotency key on writes (required by the feature matrix); NIP-07 fallback signs with whatever key the extension holds, which the backend then rejects as "not a linked identity". | `client.ts`. |
| C23 | S3 | Portal › Login | `error.value = e?.data` may be an object → renders `[object Object]`; several strings hard-coded in English on an otherwise localised page ("Or connect a remote signer", "Use passkey", "Private cloud hub"). | `forks/portal/pages/login.vue:312,479-497`. |
| C24 | S3 | Portal › Edit | "Change password — for accounts that still use password sign-in" contradicts the Nostr-only login and hits the missing `/update` route (C3). | `forks/portal/pages/edit.vue:1519-1538`. |
| C25 | S4 | AI management › Data sharing | `DEFAULT_DATASET_REPO` pre-fills a personal Hugging Face repo as the upload target; the Local model card hard-codes the claim that every candidate fails the safety gate instead of deriving it from `deployment_eligible`. | `AiManagementView.vue:456,1082-1087`. |
| C26 | S4 | Repo hygiene | `LoginView.vue`, `service/ServiceInfo.vue` and `i18n/locales/en.json` (607 lines) are dead; no vue-i18n is installed; `lint:js` and `tsconfig` carry an explicit allow-list of files because of them; `README.md` still says the console is served at `/admin/` and proxies `/api/v1`. | `forks/admin/app/package.json`, `tsconfig.json`, `README.md`. |
| C27 | S4 | Tests | The admin app has no unit, contract or end-to-end tests; C2 and C8 are exactly the class of defect a one-line adapter contract test catches. | `forks/admin/app` |

### 2.2 Missing functionality the underlying system expects

Cross-referenced against the tool registry (`native_ops.py`), `api.py`, and the design record.

| Capability | Backend today | UI today | Gap |
|---|---|---|---|
| Operation history / audit trail | `audit.list`, `audit.get` tools; every write returns `request_id`; `/package/events/<id>` SSE stream | Request IDs printed in a one-line notice, never linkable; SSE never consumed | No route for audit; no screen; no progress. Feature matrix calls this a must ("durable operation ID, reconnectable progress, history/detail view"). |
| Pending approvals | `pending_approval: true` result state | Shown as success | No approvals inbox; operator cannot see or act on parked operations. |
| Logs | `logs.read`, `logs.web`, `service.history` (read-only, allowlisted) | "Log viewing isn't available" | No route, no screen. |
| Host status | `system.status` (versions, platform, hostname, load) | Overview shows API health + versions only | No route; Overview cannot show load/hostname; no aggregate of diagnosis/updates/services. |
| Certificates | `domain.cert.info`, `domain.cert.install` | none | No route, no UI; Caddy config says public domains need the cert-install flow. |
| Legacy app management | `/package/app/remove`, `app.change_url`, `app.config.read/set` | none for unlisted apps | Installed-unlisted apps are inert in the UI. |
| Typed global settings | `settings.list?full=true` (type, choices, help) | inferred editors | Wrong editors, no help text. |
| Users without mail | `user.create` still requires domain+password (core) | form mirrors it | Needs the backend account model from `LDAP-RETIREMENT`/`MAIL-RETIREMENT`; until then the form should at least pick the domain and hide mail fields. |
| Capability-derived navigation and denied states | Admin-only gate | flat nav, all-or-nothing | `ROLE-AND-APP-ACCESS-DESIGN §UI`: nav derived from capabilities, read-only pages when write capability is missing, access-denied state on direct URLs. |
| Package authoring | JSON schema in `schema/package.schema.json`; manifests are `package.toml` | plain textarea labelled `package.json` | No schema hints, no TOML, no draft persistence, no example loader (`NATIVE-ADMIN-API` follow-ups). |
| Catalogue install path | Applications already merges catalogue | separate read-only Catalogue screen | Duplicate surface; no "Install" hand-off from a catalogue card to Applications. |
| Theme preference | portal supports light/dark/auto | admin dark-only, `data-bs-theme` never set | No toggle, no `prefers-color-scheme`, portal and admin diverge. |
| Localisation | portal is fully i18n'd | admin hard-coded English | No vue-i18n; strings inline. |

### 2.3 Usability

- **Feedback model.** One `notice` and one `error` string per page, overwritten by the next action, never auto-dismissed, and placed at the top of the page far from the control that triggered them. Long pages (Domains, AI) leave the user staring at a button that appears to do nothing.
- **Confirmation model.** Inline "Confirm?" rows are used for everything from creating a group to shutting down the host. Three problems: the confirm button is `danger` red even for benign actions (create group, create backup, open port, register domain), so red stops meaning "destructive"; destructive actions (shutdown, delete user with purge, reset all settings, delete backup) get the same weight as benign ones; and the confirm row shifts layout, pushing the Cancel button under the cursor.
- **Discoverability of consequences.** "Apply DNS", "Reload firewall", "Restore backup" and "Run migration" state the risk in a sentence but never show *what* will change. The app lifecycle screen already has the right pattern (server-derived plan → review → approve); DNS has `dns.plan` and the domain inspect already carries the pending changes, yet "Apply DNS" does not show them at the point of confirmation.
- **Selection by typing.** Users (Identities), domains (Users), credential refs (Domains), app IDs (Backups), migration IDs — all typed by hand when the list is available on the same or a neighbouring screen.
- **Form defaults.** Domain "Wildcard" defaults on; "IPv6" defaults on even when the host reports no IPv6; user "Mail domain" is blank with no default to the primary domain.
- **Empty and loading states.** Plain "Loading…" / "No X yet." text; no skeletons, no icon, no next step ("Add a domain to get started").
- **Refresh buttons everywhere.** Every card has a manual Refresh; nothing auto-refreshes after a write resolves or when the tab regains focus.
- **Session identity.** The header shows a truncated hex pubkey or username but never which account is an admin/operator, and "Sign out" is a small outline button labelled "Sign in" for non-admins.
- **Mobile.** Two-column layouts collapse acceptably, but confirm rows with three buttons wrap awkwardly; the 10 px badge action buttons (`remove`, `×`, `revoke`, `confirm`) in Groups are far below the 24 px minimum target.

### 2.4 Layout and arrangement

- **Navigation.** 17 flat items in an order that follows commit history rather than tasks (Packages before Catalogue, AI in the middle, Power before Settings). Proposed grouping:
  - Overview
  - **Apps** — Applications · Catalogue · Package authoring
  - **People & access** — Users · Identities · Groups & permissions
  - **Network** — Domains & DNS · Certificates (new) · Firewall
  - **System** — Services · Logs (new) · Updates · Backups · Diagnosis · Settings · Power
  - **Operations** — History & approvals (new)
  - **AI** — Agent · MCP access · Models · Data sharing (sub-routes)
- **Page frame.** Content widths vary: `max-w-4xl` (most), `max-w-5xl` (Users), `max-w-6xl` (Catalogue), full width (Applications). Header markup differs between Applications and the rest (different eyebrow text, different `h1` classes). Standardise on one `PageHeader` (eyebrow = section group, `h1`, lead, actions slot) and two widths: reading (`4xl`) and workspace (full, for master–detail screens).
- **Header bar.** 80 px tall, holds only a tagline ("Self-Hosted Application Hub") and the identity chip. Use it for the current page title/breadcrumb on mobile, a global search or command palette later, and an identity menu (account, role, theme, sign out).
- **Master–detail screens.** Applications gets it right (list left, detail right). Domains stacks five cards and inserts the selected-domain card between the list and unrelated cards; Users/Identities/Backups/Services are long single lists with inline expanders. Move Domains, Users, Services and Backups to the same list/detail arrangement, with the detail pane hosting actions and the plan/confirm panel so it never falls off-screen.
- **Plan/confirm placement.** Render the review panel inside the detail pane (or a right-side sheet on narrow screens), scroll it into view and move focus to its heading.
- **Cards inside card titles.** `CardTitle` currently contains buttons and confirm rows. Give `CardHeader` an `actions` slot; keep titles as text.
- **AI management.** 1,510 lines and five unrelated cards on one scroll. Split into sub-routes/tabs under `/ai`; each tab loads only its own data.
- **Overview.** Turn it into a real dashboard: status strip (health, load, hostname, uptime), attention tiles (diagnosis errors/warnings, pending updates, failed services, pending approvals), recent operations, then versions and identities collapsed.

### 2.5 Styling

- **Theme.** Only the dark palette is ever active (`data-bs-theme` is never set; `:root` defaults dark). Add a three-state preference (system/light/dark) in the identity menu, honour `prefers-color-scheme`, persist in `localStorage`, and rename the attribute from the Bootstrap-era `data-bs-theme` to `data-theme`. Share one token file with the portal (both already use the same hex values; the portal expresses them as RGB triplets).
- **Type scale.** Many `tw:text-[10px]`/`[11px]` labels and all badges are 10 px uppercase mono — fine for a status chip, wrong for data values (settings values, scopes, usernames in Groups). Minimum 12 px for anything a user reads; add a non-uppercase `chip` variant for data.
- **Colour semantics.** `danger` is used for confirmation of benign actions and for the "Turn off agent" toggle. Reserve red for destructive/irreversible; use `primary` for confirm of additive actions; add a `warning` button variant for disruptive-but-reversible (restart, reload).
- **Control sizing.** Inputs are 40 px; selects in Groups are `h-8 text-xs`; badge buttons are 10 px. Adopt two control sizes (`md` 40 px, `sm` 32 px) and never smaller for interactive elements.
- **Surface hierarchy.** Every block is a bordered rounded card, including nested list rows inside cards inside cards. Flatten: rows inside a card use dividers, not borders+radius; reserve the bordered surface for the card itself and the plan-review panel.
- **Brand consistency.** Five names in use: "NostrHost System Console" (title), "System Console" (sidebar), "Self-Hosted Application Hub" (header), "NostrHost Service Portal" and "Private cloud hub" (portal). Pick "NostrHost Console" and "NostrHost Portal"; drop taglines. Sidebar uses the `nostrhost-mark.svg`; portal uses a generic shield icon — use the mark in both.
- **Buttons in sidebar footer.** Replace the static status block with a live health indicator fed by `/package/healthz` + pending-operations count, or remove it.
- **Loading/empty.** Add a `Skeleton` primitive and an `EmptyState` (icon, sentence, primary action).
- **Focus and motion.** Focus rings are present and consistent (good). Add `prefers-reduced-motion` guards to the sidebar transition.

### 2.6 Accessibility

- Auto-submit `Switch` has no accessible name (`aria-labelledby` missing).
- Selects for "Add member…"/"Grant access to…" have no `<label>`; placeholder option is the only label.
- 10 px text buttons inside badges (Groups) fail target-size and contrast for muted text on muted surface.
- Status communicated by colour only in several badges (add text or icon — mostly present, verify Services and Diagnosis).
- Plan panel and confirm rows appear without focus management or `aria-live`.
- `aria-current="true"` on app rows should be `aria-selected` within a `listbox`, or use `aria-pressed`.

---

## 3. Rectification plan

### Phase 0 — Correctness hotfixes (1–2 days, no design changes)

| # | Task | Files | Done when |
|---|---|---|---|
| 0.1 | Add `assertLifecycleOk(result)` in `client.ts` (or a `lifecycle()` wrapper) that throws a typed `OperationError` with `state`, `reason`, `request_id`, `pending_approval`; route every write adapter through it. Views distinguish *pending approval* (info) from *rejected/failed* (error). | `api/client.ts`, all `native*.ts` write functions | A rejected `firewall.open` shows the rejection reason; a `pending_approval` shows an "awaiting approval" notice with the request ID. |
| 0.2 | Unwrap `{groups}` in `getGroups()`; add a contract type test. | `nativeGroupsPermissions.ts` | Groups list shows real groups and members. |
| 0.3 | Fix `SCOPE_TOOLS` key `system.read` → `server.read`; generate the scope list from a shared constant or fetch it. | `AiManagementView.vue` | Read-only preset grants `server.read`. |
| 0.4 | Sidebar Portal link → `/nostrhost/sso/`; logo → Overview; fix `doc/UI-REDESIGN.md` and `README.md` paths. | `AppSidebar.vue`, docs | Link opens the portal. |
| 0.5 | Connect gate denied state: show signed-in account, "Sign out", "Open portal". | `ConnectGateView.vue`, `useSigner.ts` | Non-admin can leave the dead end. |
| 0.6 | Session caching: probe once per navigation with a 30 s TTL; `request()` uses the cached state and only tries NIP-07 on a 401 with no session; drop the per-action `sync()` calls (keep one on route enter). | `client.ts`, `useSigner.ts`, `router/index.ts`, views | Domains load issues 5 requests, not 11. |
| 0.7 | Router redirect: store `to.fullPath` (relative) and let the gate build the absolute URL. | `router/index.ts`, `ConnectGateView.vue` | Back-button to `/connect` while signed in lands on the intended page. |
| 0.8 | Backend: `/package/session` checks *any* enabled identity against the admin set (mirror `_session_admin_pubkey`). | `api.py` | Multi-key admins are not denied. |
| 0.9 | Portal: add `POST /update` (fullname only) to `portal_api.py` **or** remove `UserPasswordForm` and make `UserInfoForm` target an existing route; make `useApi` non-fatal for 404. | `portal_api.py`, `forks/portal` | Editing full name works; no fatal page. |
| 0.10 | Remove the dead `getIgnoreFilters()` call; refresh ignore state after a forced run. | `DiagnosisView.vue` | — |
| 0.11 | Coerce portal login errors to strings. | `login.vue` | No `[object Object]`. |

### Phase 1 — Shared platform (1–2 weeks)

1. **API layer.** `ApiError {status, code, message}`; 401 → re-login flow; `AbortController` timeouts; `Idempotency-Key` header on writes (backend accepts and dedupes); generated client from an OpenAPI document (`NATIVE-ADMIN-API` follow-up) or, minimally, zod/valibot schemas per adapter with contract tests.
2. **Operations composable.** `useOperation(request_id)` subscribing to `/package/events/<id>` with reconnect, exposing `state`, `progress`, `result`; an `OperationToast` that tracks in-flight operations globally (persisted in `sessionStorage` so a reload does not lose them).
3. **Feedback.** Replace per-page `notice/error` strings with a toast/notification store (`useNotifications`), inline field errors for forms, and an `aria-live` region.
4. **Confirmation.** `ConfirmDialog` (modal, focus-trapped) with three tiers: *soft* (primary button, one click), *disruptive* (warning button, states impact), *destructive* (red, requires typing the resource name for shutdown/purge/reset-all/delete backup). Retire the inline confirm rows.
5. **Layout primitives.** `PageHeader`, `PageLayout` (`reading | workspace`), `MasterDetail`, `DataTable` (sortable, sticky header, responsive stack), `KeyValueList`, `EmptyState`, `Skeleton`, `CardHeader` actions slot, `Chip` badge variant, `Field` (label + control + help + error).
6. **Navigation.** Grouped sidebar from `meta.nav.group`; collapsible groups; active group expanded; `Operations` badge count of pending approvals.
7. **Theme.** `data-theme` three-state with system default; toggle in identity menu; shared tokens with the portal; `prefers-reduced-motion`.
8. **Identity menu.** Avatar/npub, username, role (operator/admin), theme, "Open portal", "Sign out".
9. **Auth gate.** Move the "not signed in" handling entirely to the router + gate; delete the duplicated alerts from all views.

### Phase 2 — Screen rectification (2–3 weeks, on top of Phase 1)

| Screen | Changes |
|---|---|
| Overview | Dashboard composition: status strip (needs `system.status` route, Phase 3), attention tiles linking to Diagnosis/Updates/Services/Operations, recent operations, versions and identities collapsed. |
| Applications | Move plan panel into detail pane with focus; list shows installed/catalogue versions as columns; status filter as segmented control; route param for selected app; actions for unlisted apps (remove via `/package/app/remove`, change URL when route exists); show post-apply health result. |
| Catalogue | Either fold into Applications (recommended: an "Available" tab) or keep as a browse surface with an "Install" button that deep-links to `/apps?id=`. |
| Package authoring | Code editor with JSON/TOML toggle, schema-driven validation messages, example manifests, autosave draft in `localStorage`, plan diff on re-plan. |
| Users | Domain select defaulting to primary; hide mail fields until mail is optional in the backend; admin checkbox; quota; client-side password rules; identity column showing all linked keys; detail pane with edit/delete/link; guard self-delete. |
| Identities | Reuse `IdentityFields`; username select; sort/search; mark current session key, operator, admins; enable/re-link for disabled identities. |
| Groups & permissions | Table per group with member chips at ≥ 24 px targets; permission matrix (groups × permissions) instead of per-permission lists; protected permissions marked. |
| Domains | Master–detail; primary domain badge; credential select; "Apply DNS" confirmation shows the pending change list; verify results rendered per record; certificate status tab (Phase 3). |
| Firewall | Table with port, protocol, comment, UPnP; warn before closing 22/80/443; move "skip UPnP" into the reload dialog. |
| Services | Status-aware actions (Start only when not running, etc.); per-row busy state; detail pane with description, boot state, last change, and log/history tab (Phase 3). |
| Updates | Fix contradictory migration copy; show package list collapsed by default with counts; apply runs via `useOperation` with live progress; refresh reloads migrations. |
| Backups | App/system multi-select pickers; archive detail (info endpoint needed, Phase 3); restore scope selection; destructive-tier confirms. |
| Diagnosis | Category tabs or accordion with per-category counts; "last run" timestamp; ignored items in a collapsed section; forced run with progress. |
| Settings | Use `full=true`: grouped by prefix, typed editors from schema, help text, dirty-state save per field, reset-all as destructive tier. |
| Power | Destructive-tier confirm; after reboot poll `/package/healthz` and show "back online". |
| AI management | Split into sub-routes (Agent, MCP access, Models, Mode, Data sharing); model download via operation with progress; derive safety-gate copy from data; remove personal default repo (leave placeholder text only). |
| Portal | Localise remaining strings; remove the password section; unify header brand with the console; render a proper 4xx page instead of fatal error for API 404. |

### Phase 3 — Missing functionality (backend + UI, 2–3 weeks)

| Feature | Backend route(s) to add | UI |
|---|---|---|
| Operations history & approvals | `GET /package/operations` (audit.list), `GET /package/operations/<id>` (audit.get), `POST /package/operations/<id>/approve|reject` (wrap `approve_operation`) | `/operations` list with state filter, detail with event timeline (SSE), approve/reject for `pending_approval`. Sidebar badge. |
| Logs | `GET /package/logs/read`, `/package/logs/web`, `/package/service/history` | `/logs` screen (journal picker, time range, search) + Services detail tab. |
| Host status | `GET /package/system/status` | Overview status strip. |
| Certificates | `GET /package/domain/<d>/cert`, `POST /package/domain/cert/install` (lifecycle) | Certificates tab in Domains: issuer, expiry, renew. |
| Legacy app ops | expose `app.change_url`, `app.config.read/set` | Actions for unlisted apps. |
| Backup info | `GET /package/backup/<name>` (backup_info) | Archive detail pane. |
| Users without mail | account model per `LDAP-RETIREMENT` | Simplified create form. |
| Capability-aware UI | session response returns capabilities | nav/route/write-control gating per `ROLE-AND-APP-ACCESS-DESIGN §UI`. |

### Phase 4 — Quality, i18n, accessibility, docs (1 week)

- Vitest: adapter contract tests (response unwrapping, lifecycle handling), `useSigner`/router guard tests, component tests for `ConfirmDialog` tiers.
- Playwright smoke against the VM testbed: sign-in, each screen loads without console errors, one write per screen resolves to a visible terminal state.
- vue-i18n with the portal's locale pipeline; extract all strings; delete the dead `en.json`, `LoginView.vue`, `ServiceInfo.vue`; drop the file allow-lists from `tsconfig.json` and `lint:js`.
- Accessibility pass: labels on all controls, target sizes, focus management for dialogs and panels, `aria-live` for notifications, colour-independent status.
- Docs: update `ADMIN-FEATURE-MATRIX.md` (currently describes a 3-screen console), `NATIVE-ADMIN-API.md` (missing ~90 routes and the session path), `UI-REDESIGN.md`, `forks/admin/README.md`.

---

## 4. Suggested order and effort

| Phase | Effort | Blocking dependencies |
|---|---|---|
| 0 Hotfixes | 1–2 days | none |
| 1 Platform | 1–2 weeks | 0.1, 0.6 |
| 2 Screens | 2–3 weeks | 1 |
| 3 Missing features | 2–3 weeks (backend + UI in parallel) | 1 for UI; backend routes independent |
| 4 Quality | 1 week | 2 |

Phase 0 should ship as its own release: it removes false-success reporting on every write, which is the single largest trust risk in the current console.
