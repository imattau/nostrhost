# Roles and app access implementation plan

**Status:** proposed engineering plan  
**Design:** [Roles and application access design](ROLE-AND-APP-ACCESS-DESIGN.md)  
**Scope:** NostrHost portal/native API authorization, app permissions, app ownership, settings, and role migration

## Outcome

Deliver a default-deny authorization path shared by the native API and UI.
Visitors cannot access NostrHost internals. Authenticated members can read the
trusted catalogue and only their own app/request data. App access, app
administration, and host administration remain distinct. Member self-service
install/remove ships only for packages and instances whose resource plans can
be constrained to an owner boundary; shared packages stay manager/admin
operated.

This plan is staged so member reads and permission-based portal access can ship
before personal app instances. It does not make ordinary users system
operators merely to give them app access.

## Current baseline

- `forks/yunohost/src/nostrhost/api.py` has 28 Bottle routes. Its auth plugin
  exempts health and session probes, then requires a configured admin for
  every other endpoint. The `session` response reports `admin: bool`.
- `forks/admin/app/src/router/index.ts` redirects signed-out users and denies
  signed-in non-admins. `routes.ts` and `AppSidebar.vue` expose the same
  navigation to every admitted admin.
- `libs/nostrhost-policy` already defines scopes and roles, but the native API
  is not wired to that capability model. Its `readonly` is a trusted
  operations role, not a member role; its role bundles are hierarchical and
  `package-developer` inherits `app-admin`.
- Native app management currently joins catalogue entries to one installation
  per app ID. It serves non-secret typed settings from the installed manifest,
  renders settings into host config files, and explicitly restarts a declared
  service. Generated credentials are mode-0600 and can be passed through
  systemd `LoadCredential`; there is no owner-scoped app settings or
  user-supplied secret rotation API.
- NIP-51 permission projection exists for app/domain membership, but it is
  additive with current permission data and does not provide app-instance
  ownership. The current projection's authoritative cutover is separate work.
- YunoHost's app permission model separates app route grants from portal tile
  display and supports named app sub-permissions. NostrHost can reuse those
  semantics while keeping account/group state Nostr-native and excluding
  visitors from the control plane.

## Authorization contract to implement

Use one server-side decision interface for every API route and operation:

```text
principal = resolve authenticated key -> active NostrHost account
decision = authorize(principal, capability, resource, action)
allow only when identity is active, capability is granted,
and resource ownership/assignment is valid
```

Represent decisions using stable capability names and typed resource
constraints; do not have endpoint code branch on role names. Role bundles are
only grant-management conveniences. Resolve account-level grants from the
authoritative identity/grant projection on every request or from a cache with
a defined revocation/version invalidation mechanism. Fail closed if that
projection is malformed or unavailable.

Each operation must declare:

- required read/write capability;
- target resource type and identifier, when applicable;
- whether access is self/account scoped, assigned-app scoped, or host wide;
- confirmation/owner approval requirements;
- audit fields safe to retain (never secret values).

The capability list and resource ownership rules must have a single source of
truth. The API must not maintain an independent, looser copy of the MCP/policy
scope table.

## Route authorization matrix

Finalize this matrix during Phase 0 and keep it beside the route registry.
The entries below are the intended starting policy.

| Route family | Visitor | Member | App manager | Operator/admin/owner |
| --- | --- | --- | --- | --- |
| Health and login/session probe | Minimal liveness or own auth state only | Own auth state and effective capabilities | Same | Same; owner/admin markers only for self |
| Trusted catalogue | Denied | Read trusted declarations and install eligibility | Read | Read |
| Installed app inventory | Denied | Own personal instances only | Assigned shared apps | Host-wide per granted capability |
| App settings read | Denied | Own instance and fields marked member-readable | Assigned app; manager-readable fields | Host-wide per capability |
| App settings plan/apply | Denied | Own instance; only member-editable fields | Assigned app; manager-editable fields | Host-wide per capability and policy |
| Install/upgrade/remove | Denied | Personal eligible instance only after Phase 4; otherwise request endpoint | Assigned shared apps only if granted | Host-wide per capability and policy |
| App permission list/update | Denied | Own grants/preferences only | Assigned apps | Host-wide access administration per capability |
| Service/system status | Denied | Denied | Only app-scoped health needed for assigned apps | Bounded reads per capability |
| Service/system writes | Denied | Denied | Only explicitly app-scoped actions, if introduced | Per capability, plan, and policy |
| Identity and capability management | Denied | Own linked identity/profile only | Denied | Administrator/owner; elevated grants owner-gated |
| Operation detail/event stream | Denied | Own request/result only | Assigned app requests | Host-wide audit requires explicit capability and policy |

Never let a route parameter such as `app_id`, `instance_id`, `request_id`, or
`username` decide authorization by itself. Resolve the referenced object and
check the caller's relationship to it before returning data or creating a
plan. Recheck at apply time to close the gap between planning and execution.

## Work packages and sequencing

### WP0 — Freeze the policy vocabulary and compatibility map

**Deliverables**

- A reviewed endpoint/operation policy matrix covering all 28 current API
  routes, plus CLI/control-plane operations exposed to agents.
- A capability vocabulary split into member, app access/management, operator,
  administrator, owner approval, and package publication capabilities.
- A migration table from current configured admins and `identity.toml` role
  bundles to new grants. Preserve existing admin access as an explicit
  migration grant; never silently upgrade a member to admin.
- Decisions on whether members are invitation-only, whether all trusted
  catalogue entries are member-visible, and how a Nostr pubkey maps to an
  account when there are multiple keys.

**Likely files**

- `libs/nostrhost-policy/src/nostrhost_policy/policy/scopes.py`
- `libs/nostrhost-policy/src/nostrhost_policy/policy/roles.py`
- `libs/nostrhost-policy/src/nostrhost_policy/auth/identity.py`
- `forks/yunohost/src/nostrhost/api.py`
- this plan and `ROLE-AND-APP-ACCESS-DESIGN.md`

**Exit gate**

No endpoint remains implicitly classified as “admin because the whole API is
admin-only.” Every exposed data/write operation has an explicit decision and
resource scope.

### WP1 — Introduce the shared authorization service

**Deliverables**

- A request principal carrying verified signer, linked account, active/revoked
  state, platform grants, and relevant app/resource grants.
- An injectable `authorize(capability, resource, action)` service used by the
  native API and reusable by the operation executor.
- API auth middleware that authenticates first, then applies route-specific
  authorization. Keep only minimal liveness and login/session bootstrap
  endpoints public.
- An authenticated session/capabilities response for the UI. It returns only
  the caller's effective capabilities and account summary; it does not expose
  the system-wide identity/role directory.
- Explicit response cache headers for authorization-sensitive reads. Current
  frontend requests already use `cache: 'no-store'`; server responses must
  match.

**Likely files**

- `forks/yunohost/src/nostrhost/api.py` and a new API authorization module
- `libs/nostrhost-policy/src/nostrhost_policy/auth/identity.py`
- API constructors/packaging that supply the identity and grant stores
- `forks/yunohost/tests_nostr/test_api.py`

**Exit gate**

Tests prove the new auth service can admit one non-admin member to a permitted
read while denying the same request to a visitor and denying unrelated writes.
Existing configured admins retain their current access via the documented
migration grant.

### WP2 — Add an explicit route policy registry and safe rollout mode

**Deliverables**

- Route definitions declare policy metadata rather than inheriting blanket
  admin access. Add startup validation that every non-public route has a
  policy entry.
- Include SSE/event stream authorization: a member can subscribe only to a
  request they submitted; app managers only to assigned app operations;
  privileged audit access is separately granted.
- Feature-flag the new evaluator for staged rollout. In audit-only mode,
  calculate/log would-deny/would-allow decisions without widening access. Do
  not log request bodies, setting values, tokens, or secrets.
- Add bounded denial reasons suitable for UI without disclosing whether
  another user's app or request exists (avoid ID enumeration).

**Exit gate**

Route coverage test fails if an endpoint is added without policy metadata.
Visitor probes for every internal route return denied regardless of guessed
IDs.

### WP3 — Ship member read surfaces and dynamic page access

**Deliverables**

- Members can fetch the trusted catalogue and eligible metadata after signing
  in. Visitors cannot.
- Add account-scoped “My applications” and “My requests” API projections.
  Initially the app list can be empty for accounts without personal instances;
  never substitute the whole host inventory.
- Session capabilities drive router guards and sidebar links. Hide pages the
  account cannot read; direct URL navigation routes to an access-denied view.
  Readable pages with no write grant stay visible but omit write controls.
- Reset in-memory user/account data on logout, expiry, or account switch.
- Keep API authorization authoritative; UI capability data is presentation
  only.

**Likely files**

- `forks/admin/app/src/composables/useSigner.ts`
- `forks/admin/app/src/router/index.ts` and `routes.ts`
- `forks/admin/app/src/components/layouts/AppSidebar.vue`
- `forks/admin/app/src/components/layouts/AppShell.vue`
- `forks/admin/app/src/api/nativeSystem.ts` plus typed account/capability APIs
- `forks/yunohost/src/nostrhost/api.py`

**Exit gate**

As a member, catalogue pages load and system/admin pages are absent and
blocked on direct navigation. As a visitor, no app shell or internal API data
is available. As an admin, current console pages remain accessible.

### WP4 — Complete account/group and app-permission authorization

**Deliverables**

- Define account lifecycle, group membership, invitation/self-registration,
  key linking/revocation, and recovery. Identity authentication stays Nostr
  native; do not reintroduce LDAP as an authorization store.
- Complete the NIP-51 permission projection cutover or establish an equivalent
  authoritative Nostr-signed grant source. Today the projection merges
  additively with LDAP-derived membership; document and test the cutover before
  treating it as the sole authority.
- Add per-app named permissions and optional sub-permissions, account/group
  grants, explicit public grants, and protected permissions. Do not give
  visitors platform roles or catalogue access.
- Enforce app permissions at the reverse-proxy/app access boundary, not only
  when producing portal tiles. Tile visibility is derived presentation.
- Add app-manager assignment scoped to app IDs and separately audit permission
  changes.

**Likely files**

- `forks/yunohost/src/nostrhost/nip51_permissions.py`
- `forks/yunohost/src/nostrhost/permissions.py` and identity projection
- `forks/yunohost/src/permission.py` migration/cutover points
- portal permission projection and auth middleware
- `forks/yunohost/tests_nostr/test_nip51_permissions.py`
- `forks/yunohost/tests_nostr/test_user_permission_projection.py`

**Exit gate**

An account's app grant permits only app use; it cannot read host configuration,
install/remove the app, administer another app, or access admin routes. Public
app access is opt-in for a named permission and prohibited for protected
permissions.

### WP5 — Add durable install requests for shared apps

**Deliverables**

- Member request endpoint stores requester account, trusted package coordinate
  and digest, requested domain/options, timestamps, status, reviewer, decision,
  and resulting operation ID. It stores no secret values.
- Admin/app-manager queue supports approve/reject with reason and server-built
  plan review. Approval is bound to the request digest; stale catalogue or
  resource state requires a fresh plan and review.
- Existing direct shared install/upgrade/remove stays restricted to
  app-manager/admin capabilities. App access grants remain a separate action.
- Members see only their own request state and result. Assigned app managers
  see requests relevant to their managed apps; admins see the queue.

**Likely files**

- New durable request model/store under `forks/yunohost/src/nostrhost/`
- API route registration and lifecycle execution path in `api.py`
- admin app management view and a member request view
- operation event/audit projection
- new focused API/store tests

**Exit gate**

A member can request a shared app but cannot apply a package plan directly.
Unauthorized IDs cannot reveal another member's request. Approval, execution,
rejection, and revocation are audited and recoverable after API restart.

### WP6 — Harden app settings access and secret lifecycle

**Deliverables**

- Add setting metadata for read visibility, editable principal (member,
  instance owner, assigned app manager, admin), sensitivity, validation, and
  apply mode (hot reload, restart, maintenance). Missing metadata defaults to
  manager/admin-only.
- Split per-account app preferences from host-managed package settings.
  Preferences are served by the app under its normal per-user auth; they do
  not rewrite the host package manifest or trigger a service restart.
- Scope settings reads/plans/applies by `instance_id` and field. Recheck
  authorization and current setting digest on apply. For shared apps, member
  writes remain denied unless an individual field is explicitly declared
  member-editable and has a bounded effect.
- Redact values from operation results/audit/error output as appropriate.
  Current settings diffs include old/new non-secret values; sensitive fields
  must use redacted diffs even when they are not credential secrets.
- Add a separate write-only credential endpoint for set/rotate/remove only
  when a package declares a credential reference. Never return the value;
  return configured/version state only. Store through the credential provider,
  bind access to the app/instance service identity, and expose it through
  systemd credentials or an equally constrained runtime mechanism.
- Do not make secrets editable through generic setting values. Do not place
  values in Nostr public events, catalogue manifests, browser storage, or
  diagnostic logs.

**Likely files**

- `forks/yunohost/src/nostrhost/package_engine.py`
- `forks/yunohost/src/nostrhost/app_management.py`
- `forks/yunohost/src/nostrhost/native_providers.py`
- `forks/yunohost/src/nostrhost/api.py`
- `forks/admin/app/src/views/native/AppManagementView.vue`
- `forks/admin/app/src/api/nativePackages.ts`
- `forks/yunohost/tests_nostr/test_app_management.py`
- `forks/yunohost/tests_nostr/test_api.py`
- `forks/yunohost/tests_nostr/test_native_providers.py`

**Exit gate**

Members cannot read or mutate manager-only fields or settings on an app they
do not own. Setting changes are server planned and digest-bound, with restart
effects shown before apply. Secret values cannot be recovered from API
responses, plans, operation events, logs, or audit records.

### WP7 — Introduce personal app instances and self-service lifecycle

This is the last product capability because it depends on resource isolation,
settings scoping, account ownership, and the package planner.

**Deliverables**

- Add an explicit `shared | personal` installation class; old/unknown package
  manifests mean `shared`.
- Introduce `instance_id` distinct from `app_id`, with owner account, manager
  assignments, per-instance settings, state, quota, backup policy, and
  lifecycle status.
- Extend package/resource identity and planners so paths, service accounts,
  units, ports, databases, secrets, domains, and permission names cannot
  collide across instances or escape the instance prefix/allowlist.
- Start with a deliberately small supported resource set. Reject packages
  that request host-wide resources, arbitrary hooks/scripts, global domains,
  unrestricted ports, or unbounded resource consumption.
- Add account deletion/disable, orphaned instance, transfer, export, backup,
  restore, quota exhaustion, failed install rollback, and removal recovery
  behavior before exposing “Install” or “Remove” to members.
- Self-service upgrade is allowed only if the installed instance still matches
  the trusted package, the new manifest remains personal-eligible, and the
  upgrade plan stays inside the same resource boundary.

**Likely files**

- `forks/yunohost/src/nostrhost/package_engine.py`
- `forks/yunohost/src/nostrhost/app_management.py`
- native app inventory persistence/provider and backup integration
- app lifecycle API and operation target schema
- member app management UI and account-deletion flow
- expanded package-engine, provider, API, and VM integration tests

**Exit gate**

An adversarial package cannot write outside its allocated instance resources.
A member can only plan/apply/remove their own eligible instance. Shared app
state remains unchanged by member operations. Failed or revoked operations
leave a recoverable, audited instance state.

### WP8 — Split roles, migrate grants, and remove transitional gates

**Deliverables**

- Replace strict scope inheritance with independent platform capability
  bundles. Package publishing/testing is independent from app-admin and
  server-admin scopes.
- Define administrator and owner duties separately. Only owner-authorized
  policy may grant/revoke host administrator or owner-approval capability.
- Produce a dry-run migration report for current groups, `identity.toml`,
  configured admin keys, and delegations. Require review for any grant that
  gains privilege; preserve admin behavior for existing configured admins
  until explicitly changed.
- Remove the blanket admin gate and audit-only compatibility path only after
  every route, event stream, write, and CLI operation has enforcing tests.
- Update `ADMIN-FEATURE-MATRIX.md`, this plan, role docs, API docs, and operator
  recovery instructions to match shipped behavior.

**Exit gate**

Grant migration is explainable and reversible. No ordinary member or package
publisher gains host-wide authority. Owner recovery remains possible if all
delegated administrators are revoked.

## Cross-cutting test and rollout requirements

### Authorization tests

- Table-driven API tests for visitor, member, app manager, operator,
  administrator, owner, and package publisher over every route family.
- Object-level authorization tests for guessed `app_id`, `instance_id`,
  `request_id`, username, and sub-permission IDs; use non-enumerating denial
  responses where another object's existence would leak.
- Plan/apply TOCTOU tests: revoke a grant, change ownership, change package
  digest, or alter settings between planning and applying; apply must reject.
- Revocation tests covering portal session plus NIP-98 signer, linked keys,
  pending operations, and active event streams.
- Property/negative tests proving a member grant never implies a platform
  capability and an app permission never implies lifecycle authority.

### Package and settings tests

- Personal-plan allowlist tests for every resource provider, including paths,
  users, systemd units, ports, database, DNS/domain, permissions, secrets,
  backup, and removal reversal.
- Settings tests for default manager-only behavior, field-specific access,
  invalid types/ranges/choices, hidden fields, stale digest, restart effects,
  and per-user preferences that do not mutate host state.
- Secret canary tests: submit a unique fake secret, then assert the canary is
  absent from HTTP responses, diffs, stored manifests, audit/events, logs,
  operation results, and frontend state. Verify only authorized service
  processes can consume the credential.

### UI checks

- Route matrix tests: inaccessible pages absent from sidebar and denied on
  direct navigation; readable/no-write pages remain read-only.
- Account-switch/logout tests clear catalogue inventory, settings, and
  operation data from shared client state.
- Frontend type-check and production build for each API shape/UI migration.

### Rollout sequence

1. Ship policy vocabulary and reporting with no authorization expansion.
2. Enable new middleware in audit-only mode and reconcile mismatches.
3. Enable explicit admin grants; verify recovery and admin workflows.
4. Enable member catalogue and filtered read surfaces.
5. Enable app permission management and request/approval workflow.
6. Enable member settings only for approved fields/instances.
7. Enable personal install lifecycle for a small package allowlist.
8. Remove legacy gates only after logs and tests show complete policy coverage.

At every stage, provide a local recovery path that can restore the last known
owner/admin grant without depending on the web UI or the identity being
repaired.

## Decisions required before implementation starts

1. What is the account source of truth: existing YunoHost usernames mapped to
   Nostr keys, or a new NostrHost account record independent of usernames?
2. Is member registration invitation-only, admin-created, or open?
3. Do signed-in members see every trusted catalogue package or only the
   request/self-install eligible subset?
4. Which team member can approve shared app requests, and may an app manager
   also approve their own request?
5. Which apps and resource types are initial candidates for personal
   instances? If none are ready, ship the request workflow first.
6. Who owns shared operational settings, and can individual settings keys be
   delegated to members?
7. What backup, restore, retention, quota, account deletion, and instance
   transfer behavior is required before personal self-service?

## Validation commands

Run focused checks as each work package lands, then the broader project suite
before enabling a rollout stage:

- API/auth: `pytest forks/yunohost/tests_nostr/test_api.py`
- app lifecycle/settings: `pytest forks/yunohost/tests_nostr/test_app_management.py forks/yunohost/tests_nostr/test_package_engine.py`
- NIP-51/account permissions: `pytest forks/yunohost/tests_nostr/test_nip51_permissions.py forks/yunohost/tests_nostr/test_user_permission_projection.py`
- policy roles/scopes: run the `nostrhost-policy` test suite using the repo's
  Python workspace environment
- admin UI: from `forks/admin/app`, run `yarn type-check`, `yarn lint`, and
  `yarn build`
- integration: run the relevant VM/E2E suite after API route, auth, or package
  resource changes

Do not treat test coverage as a replacement for an explicit route-policy
registry and migration review.
