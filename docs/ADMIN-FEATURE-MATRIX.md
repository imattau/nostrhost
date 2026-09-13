# Native Admin Feature Matrix

**Status:** first-release scope decision, based on the current checkout
**Target:** Debian 12; native NostrHost UI and API only

The former route inventory in `forks/admin/app/src/router/routes.ts` informed
this review. The shipped route table now contains only the native
package-authoring view. Native capability references are from
`forks/yunohost/src/nostrhost/api.py`,
the CLI `ToolSpec` registry, the package engine, and the portal identity
routes. A capability listed as “core/CLI” is not yet available to the browser
through `/api/v1`.

| Current UI area | Current native capability in this checkout | First native admin decision | Delivery state |
| --- | --- | --- | --- |
| Login and post-install | Portal has Nostr login/link routes; native identity bootstrap is a CLI operation. The legacy admin login sent username/password to `/yunohost/api/`. | Use a signer connection for the admin SPA. Keep first-run server bootstrap outside the package screen; do not port the password flow. | Legacy login/post-install screens are no longer routed or shipped. NIP-07 signing, linked-admin confirmation, and current identity display are implemented; recovery remains. |
| Home | The former home linked to YunoHost-specific user, domain, app, update, diagnosis, and backup screens. Native v1 exposes system status, identity, catalogue, and version reads. | Add a native overview with health, identity, operation, and catalogue summaries. | Deferred; v1 read endpoints exist but no overview UI yet. |
| Users and groups | Native operation registry has user list/create/update/delete and permission tools; no complete admin `/api/v1` identity/user surface. | Implement user administration only after a Nostr identity-to-system-user authorization model is specified. Do not carry password or LDAP UI assumptions forward. | Deferred pending auth and API contract. |
| Domains and DNS | Native domain list/inspect/add/remove, DNS plan/apply/verify, credential, and certificate operations exist in the CLI/control plane. | Build typed domain and DNS screens after API methods expose dry-run plans, provider status, and approval outcomes. | Deferred; no YunoHost form/API adapter. |
| Applications and catalogue | Native catalogue list/get/publish and app lifecycle operations exist in the operation registry. Package declarations are validated into typed resource plans; installed native manifests are retained locally. | Join trusted catalogue provenance with local installation state; keep unlisted installed apps visible and route install/upgrade/remove/settings changes through digest-bound policy plans. | Implemented: combined inventory endpoint and UI filters; install/upgrade/remove plan and apply routes; native typed settings read/plan/apply. Legacy config-panel scripting is not part of the new UI contract. |
| Package authoring | Python package library, Typer CLI, schema, diagnostics, and deterministic plan are present. | Keep authoring separate from installed-app management; editing and inspection remain read-only. | Implemented: NIP-07 signing, JSON manifest editor, validation through planning, and read-only plan review. |
| Services | Native service status/control/restart tools exist; event streaming is implemented for operation progress. | Expose allowlisted service health and operation-linked restart controls only after approval and result contracts are explicit. | Deferred; API/UI contract not implemented. |
| Updates and migrations | Native operation registry has update check/refresh and migration inspection/run tools. | Separate read-only available updates from privileged apply/migration review; show co-signature and recovery needs before submission. | Deferred; operations currently exist below the browser API. |
| Diagnosis, logs, firewall, power, settings, and webadmin tools | Some native read/write tools exist in the operation registry, but not all current screens have an exact typed equivalent. Power and webadmin include host actions with significant risk. | Review each tool against policy, bounded output, and a corresponding plan. Exclude legacy-only screens and do not recreate a generic command console. | Deferred pending feature-level API review. |
| Backups and restore | Native backup create/list/restore tools exist in the operation registry. | Expose archive inventory and backup verification first; gate restore/delete through explicit plan, backup selection, approval, and operation result. | Deferred; browser endpoints not yet implemented. |
| Operation history and progress | Native API exposes a versioned event stream; operation requests, approval, execution, and state events are handled by the control plane. | Every submitted mutation must have an idempotency key and a durable operation ID; provide reconnectable progress and a history/detail view. | Event infrastructure and v1 SSE endpoint exist; submit/status endpoints and UI remain. |

## First native release slice

1. NIP-07 signer connection with no browser key persistence.
2. Package schema discovery, local manifest editing, validation diagnostics,
   and a deterministic resource plan.
3. System identity/health and trusted catalogue provenance as the next
   read-only surfaces.
4. Policy-authorized operation submission, approval, progress, verification,
   and history after those contracts are published.

The current implementation intentionally ends before any package apply
button. Validation and planning are signed, read-only requests. The native API
must not expose arbitrary commands or accept the browser's proposed operation
objects as authority.
