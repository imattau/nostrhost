# Application management implementation plan

## Outcome

Use one application catalogue for discovery and inventory. A trusted catalogue
entry is joined with locally installed state by stable app ID, while installed
apps missing from the current catalogue remain visible as unmanaged/legacy
entries. Filters cover all, installed, not installed, version differences, and
installed-only apps.

Native app configuration uses package-declared typed settings and managed
configuration resources. The new management UI is native-only: no legacy
config-panel adapter or package-migration workflow is planned.

## Delivery order

1. **Backend inventory contract.** Add a typed read model that joins trusted
   catalogue entries and installed apps, preserves provenance and installation
   metadata, and reports catalog-only and installed-only apps. Add stable tests
   for each intersection case.
2. **Native settings contract.** Extend setting definitions with UI metadata
   and type/choice validation; expose the installed schema/current values;
   render declared config templates with effective settings; reject secret
   values from the generic settings interface.
3. **Settings change plan.** Accept proposed values only for declared keys,
   validate types and constraints, produce a deterministic plan and semantic
   diff, and keep the existing package install/reconcile policy boundary. Do
   not execute an arbitrary browser-supplied operation list.
4. **Operation lifecycle.** Submit accepted setting changes through the signed
   request/approval/execution path, persist the updated manifest only after the
   dependent config/service operations succeed, and return an operation ID.
   Preserve user overrides across app upgrades when
   the new manifest retains compatible fields.
5. **UI last.** Build one catalogue/inventory view with status filters, source
   and version information, and per-app details. Show native settings as typed
   forms; review a semantic diff and risk before submit; show operation results
   and request IDs. Label any installed legacy/unlisted app as such and
   avoid presenting native controls as if they could manage its configuration.
6. **Docs and verification.** Update the API and feature matrix to match the
   shipped contract. Run focused Python tests, admin type-check/build, and the
   relevant packaging checks.

## Safety and compatibility rules

- Catalogue trust and local installation state are separate facts. Never
  treat an installed app as trusted just because it is installed.
- Preserve installed-only apps in the Installed view even when their publisher
  or catalogue entry disappears.
- Generic settings are non-secret. Credentials use the dedicated secret
  resources and must be redacted from plans, diffs, and operation events.
- Re-rendered files, service reloads, and health checks are explicit plan
  operations. A setting write must not silently run shell scripts.
- Do not port the YunoHost config-panel scripting API. Native settings and
  config resources are the sole app configuration contract.
- A preview is not authority to apply. Writes require the established signed
  operation and approval policy, and state history must identify the operation
  that caused the change.

## Implemented in this change

- Added the joined inventory endpoint and UI filters; catalogue and local
  installation remain separate facts, including installed-only entries.
- Added native setting metadata, validated update plans, rendered
  `template_content` with the reserved settings context, and an ordered
  service restart where managed config is present.
- Added digest-bound install, upgrade, remove, and settings apply endpoints;
  each derives its plan on the server and submits it through
  `run_signed_chain`.
- Preserved compatible user setting values during catalogue upgrades and
  discarded values whose type or enum choice no longer matches.
- Added the application catalogue and per-app settings UI after the API and
  resource-engine work. Legacy YunoHost config panels were not ported.
- In-page live progress is not included: the API returns the operation request
  ID and result, while the existing event stream remains available to
  authenticated API clients.
