# Roles and application access design

**Status:** proposed design for review  
**Scope:** NostrHost portal and native administration API, including app catalogue and lifecycle operations

The sequenced engineering work, API policy matrix, affected modules, rollout
gates, and test plan are in the companion
[implementation plan](ROLE-AND-APP-ACCESS-IMPLEMENTATION-PLAN.md).

## Decision

Unauthenticated visitors have no access to NostrHost-internal data or
interfaces. This includes the trusted catalogue, installed-app inventory,
server health, identity data, and operation history. Publicly hosted websites
remain reachable at their own published URLs; they are app traffic, not access
to the NostrHost control plane. If NostrHost later offers a public app
directory, it must be a separately published projection and API, not the
trusted internal catalogue.

Signed-in members may browse the trusted catalogue and manage app instances
they own only when the package and instance satisfy a server-enforced personal
installation contract. Until that contract exists, members may request an
installation and an app manager or administrator must apply it. Installing an
ordinary host app can create system users, directories, services, ports,
domains, permissions, and configuration; a UI-only ownership check would not
make that safe.

## Reference and current state

YunoHost is a useful reference for separating account groups from per-app
permissions. Its permission model has named app permissions (including a main
permission and optional sub-permissions), grants those permissions to users or
groups, and separately controls whether an app is shown as a portal tile. Its
`visitors` group is an explicit opt-in for an app permission, with a
`protected` flag that prevents accidental visitor access. This is a good
pattern for app access: public access is app-specific and explicit. NostrHost
should not copy that visitor exception into its own control plane: visitors
still get no internal NostrHost access.

NostrHost already has some of the building blocks, but they do not yet form
one authorization path:

- `nostrhost-policy` defines global roles and scopes. `readonly` is a trusted
  operations role with broad server, user, domain, firewall, log, and backup
  reads; it is not a normal account role. `app-admin` combines app lifecycle
  authority with broad host administration. `package-developer` currently
  inherits all `app-admin` scopes.
- The native HTTP API still authorizes only configured administrators; its
  source describes capability-scoped API authorization as follow-up work.
  App inventory, catalogue reads, plans, and apply routes are therefore not
  currently available to ordinary members.
- The NIP-51 permission projection models membership in app/domain
  permissions. It does not record ownership of installed app instances.
- Native app inventory currently joins catalogue entries to one local
  installation per app ID. The package plan can create host-level resources,
  so app ID plus a user identity is not yet a safe per-user instance model.

Relevant implementation references: [`roles.py`](../libs/nostrhost-policy/src/nostrhost_policy/policy/roles.py),
[`api.py`](../forks/yunohost/src/nostrhost/api.py),
[`nip51_permissions.py`](../forks/yunohost/src/nostrhost/nip51_permissions.py),
[`permission.py`](../forks/yunohost/src/permission.py), and
[`package_engine.py`](../forks/yunohost/src/nostrhost/package_engine.py).

## Authorization model

Use three separate concepts rather than one escalating role hierarchy:

1. **Authentication principal:** a Nostr pubkey linked to an active NostrHost
   account. Multiple signers may be linked to an account; authorization is
   evaluated for the account and the signing key's enabled/revoked state.
2. **Platform capabilities:** grants for host-wide operations such as viewing
   health, managing identities, administering shared apps, or changing
   firewall/system settings. Grants can be bundled into named platform roles
   for convenience, but policy checks capabilities rather than role strings.
3. **Resource grants:** membership in a particular app permission, or
   ownership/management of a particular app instance. A platform role does not
   implicitly grant access to every app's private content; app membership does
   not grant host administration.

Every API request resolves the principal, active account, platform
capabilities, and any resource grant required by that operation. The server
then applies both the capability check and resource constraint. Missing,
expired, revoked, or ambiguous grants deny access. The browser may use a
capabilities response to tailor the interface, but that response is display
state only; the API repeats authorization on every request.

Use NIP-51 membership lists as a transport/storage primitive where appropriate,
but retain server-authoritative validation and projection. Treat app
permission membership, app-instance ownership, and control-plane role grants
as distinct records with distinct update authority and audit events.

## Proposed roles and visibility

These are user-facing personas backed by capability bundles and resource
grants; they should not become a strictly nested ladder.

| Persona | Internal NostrHost visibility | Authority |
| --- | --- | --- |
| **Visitor** | None. No console, trusted catalogue, inventory, health, identity, or operation data. | Public app URLs only where the app owner explicitly grants public access. No control-plane API except the minimum public login/challenge flow. |
| **Member** | Own profile/account, trusted catalogue, own app instances, own requests and operation results. | Request installs for packages not eligible for self-service. Manage eligible owned instances only. No server-wide inventory or admin diagnostics. |
| **App manager** | Shared-app inventory and the access settings for apps assigned to them. | Manage assigned shared apps and their per-app user/group permissions. No unrelated server settings or identity administration. |
| **Operator** | Bounded server/service health, relevant logs, backup status, and operation status. | Allowlisted operational actions such as service restart and backup creation. No identity grants, shared-app ownership transfer, or system-wide security policy changes. |
| **Administrator** | Host inventory, users/identities, domains, apps, backups, audit, and system status. | Routine host administration, app lifecycle, access management, and configuration. High-impact actions remain policy-gated. |
| **Server owner** | Full control-plane policy and approval view. | Grant/revoke administrator and operator authority, configure recovery, and co-sign designated high-impact operations. This is a distinct trust responsibility, not just another label for administrator. |
| **Package publisher** | Package authoring, package test results, and publication provenance. | Test and publish trusted catalogue entries. This capability is additive and does not grant app-admin, user, backup, firewall, or system authority. |

The existing `readonly`, `operator`, and `app-admin` bundles can inform the
operator/admin capability mapping. Split package publishing out of
`package-developer` so it no longer inherits app-admin. Keep the owner approval
identity separate from the requester; retain explicit co-signature for
high-impact operations.

## App access and ownership

Keep **catalogue trust**, **installation state**, **app access**, and
**installation ownership** as separate facts:

- A catalogue entry means a publisher has declared a package and the node
  trusts its provenance. It does not mean a member may install it.
- An installed app means resources exist on the host. It does not mean the
  current caller owns or may administer it.
- An app permission means an account may use a particular app route or feature.
  It does not allow that account to change the installation.
- An app-instance ownership grant identifies who may administer a personal
  instance. It does not imply that the app's web content is private; web access
  remains governed by the app's own permissions.

Extend the package contract with an explicit installation class, defaulting to
`shared`:

- **Shared:** one host-managed installation. Install, upgrade, configure, and
  remove are available only to app managers/admins. Members may be granted
  app permissions independently.
- **Personal:** explicitly opted-in packages may create a per-account instance
  with a generated instance ID, owner account, resource limits, and a
  constrained plan. The package must declare supported per-instance resources
  and cannot claim unrestricted host resources. Only that owner (or an
  assigned app manager/admin) may configure, upgrade, export, or remove it.

The inventory key should become `instance_id`; retain `app_id` as the stable
catalogue/package identity. Personal instances must use isolated resource
names, storage, service identities, and domain/path allocation. The planner
must reject any personal package operation that escapes its declared
instance boundary. A package that cannot satisfy these constraints remains
shared-only.

For personal app removal, show the exact instance and data-retention effect,
require explicit confirmation, and offer a documented recovery/backup window
where feasible. Never let a member remove a shared install merely because they
can access that app.

## Catalogue, portal, and app permissions

Model app access like YunoHost's useful separation of permission from tile:

- App packages declare named permissions such as `main` and optional
  sub-permissions. Each permission defines its app route/feature and whether
  public access is allowed.
- The app access manager grants a permission to named accounts or groups. A
  public grant is explicit, visible in the review, and forbidden for
  `protected` permissions.
- Portal tiles are derived from permissions granted to the signed-in account
  and the app's presentation metadata. Hiding a tile never substitutes for
  request-time authorization.
- The internal catalogue is visible to authenticated members and trusted
  operators/admins. It shows provenance and eligibility; install actions are
  independently checked by the server.
- Installed-app inventory is filtered by resource grant: members see their
  personal instances, app managers see assigned shared apps, and operators or
  administrators see host-wide inventory according to their capabilities.
- Installed-but-unlisted apps remain visible to authorized managers/admins as
  unmanaged entries. Do not expose their existence or metadata to ordinary
  members unless they own the instance or have app access.

Do not port YunoHost's LDAP storage assumptions. Its permission semantics are
the reference; NostrHost's account/group source remains Nostr-native, with a
validated local projection for request-time authorization.

## Settings visibility, writes, and delivery to applications

Treat application settings as host-managed configuration, not as portal
content. In the current native package flow, typed non-secret values are
stored with the installed package manifest. The planner supplies them to
package-declared config templates; the resulting files are written on the
host with declared owner, group, and mode, then the plan may restart the app's
service. The app reads its configuration as a local process. Settings are not
supposed to be fetched by the app from the browser, the public catalogue, or a
public Nostr event. A package can expose an app URL through the portal, but
that does not expose its host configuration.

Current implementation details: the native settings endpoint returns declared
non-secret fields and values, and the UI loads them into an editor; the API is
currently administrator-only. Generic setting updates are server-planned and
render config files, with an explicit restart when the package declares a
service and config. Generated credentials are stored as mode-0600 files and
can be passed to a service through systemd `LoadCredential`. The generic
settings path rejects secret fields. There is not yet an owner-scoped settings
API or an app-facing set/rotate flow for user-supplied secrets.

Keep four setting classes distinct:

- **App user preferences:** per-account preferences consumed by the app
  itself. Store them with the app/account preference mechanism and serve them
  only to that signed-in app user. They must not mutate the shared host
  manifest or restart a service.
- **Member-manageable instance settings:** non-secret values for an owned
  personal instance. Return only that instance's declared editable fields and
  values to its owner or an assigned manager.
- **Shared operational settings:** host-level values that can affect every
  user, a service, domain, network binding, or availability. Default these to
  app manager/admin write access. A specific key can be made self-service only
  when its package declaration says so and the server can constrain the
  resulting effects.
- **Secrets/credentials:** never readable after write or generation. Show only
  whether a credential is configured and offer set/rotate/remove operations
  through a separate secret interface. Plans, diffs, logs, operation events,
  and API errors must redact the value. A secret reference may be supplied to
  a service or config renderer, but the value must not be copied into the
  browser-visible manifest or generic settings response.

Each setting definition needs server-validated metadata for visibility,
editable principals, and apply behavior (for example hot reload, app restart,
or admin-only maintenance). Missing metadata defaults to private-to-managers
and admin-managed. The browser may render the declared form, but the API must
validate the caller, app/instance ownership, setting key, type, range/choices,
and write authority on both plan and apply. A user may not widen access by
editing a manifest or submitting a browser-proposed resource plan.

For reads, return schema and current values only to callers authorized for
those exact fields. Use authenticated, non-cacheable responses; clear values
from client state at logout/account switch. For writes, build the plan on the
server, show an appropriately redacted semantic diff and operational effect,
then apply the digest-bound plan through the operation/audit path. Avoid
including values in generic audit summaries; record the actor, instance,
setting keys, outcome, and operation ID. Restart or reload only when the plan
declares it, and show that effect before confirmation.

YunoHost's config panels are a useful reference for exposing typed settings
and showing their impact, but their imperative config scripts should not be
ported as the NostrHost settings execution contract. Keep the native typed
resource planner as the only path from a setting change to host mutation.

## API and UI changes

1. **Authorization contract:** replace the native API's configured-admin-only
   gate with a shared authorization service that resolves the caller and
   checks operation capabilities and resource constraints. Add an authenticated
   session/capabilities response for UI composition. Keep `/healthz` and
   public login/challenge endpoints minimal and non-sensitive.
2. **Endpoint policy map:** specify required capability and resource scope for
   every route. Split public catalogue projections from internal trusted
   catalogue reads if a public directory is later desired. Add owner/app ID
   constraints to inventory, settings, plan, apply, and operation-result
   routes. Apply routes must recheck authorization and plan digest at execution
   time, not only when creating a plan.
3. **Identity and grants:** define account lifecycle and Nostr-key linking,
   group membership, self-service invitation/registration policy, role grant
   and revocation authority, and recovery. Ensure revoking a key/account or
   resource grant takes effect on the next request and pending operation.
4. **UI:** no console navigation for visitors. Members get Catalogue,
   My applications, and My requests. App managers get assigned apps and
   permissions. Operator/admin sections appear only when capabilities allow.
   Direct URLs should show an access-denied state; API denial remains
   authoritative. Display eligibility, ownership, app permission, and
   installation source as separate facts. Settings forms show only fields the
   caller may read or change, distinguish app-user preferences from
   host-managed configuration, never prefill secrets, and disclose restart or
   maintenance effects.

   Apply this rule page by page and action by action: if a user lacks the
   capability to read a page's data, omit that page from navigation and deny
   its route, including a directly entered URL. If the user may read the page
   but lacks a write capability, keep the read-only page available and hide
   its write controls. If only some records are in scope, show only those
   records. The API must enforce the same read/write and record-level checks;
   hiding navigation or controls is not authorization.
5. **Operations:** members may submit a personal-install request before
   self-service eligibility ships. Requests have a durable ID and show
   pending/approved/rejected/running/completed status. Shared-app and
   host-wide changes use the existing server-derived plan, confirmation,
   approval, and audit chain.

## Delivery plan

### Phase 1: policy and API boundary

- Inventory every browser/API route and operation; produce an endpoint-to-
  capability/resource matrix.
- Introduce authenticated principals and account membership into the native
  API while retaining current admin access as a migration grant.
- Add default-deny checks and tests for visitor denial, member isolation, and
  admin/operator paths. Do not expose the internal catalogue or app inventory
  to visitor sessions.
- Remove unconditional sidebar exposure; derive nav from capabilities.

### Phase 2: member catalogue and app permissions

- Expose trusted catalogue metadata to authenticated members.
- Add per-app named permissions, account/group membership management, public
  opt-in rules, `protected` behavior, and portal tile derivation.
- Add an admin/app-manager access screen and member-facing app links. Enforce
  access at the proxy/app boundary, not only in the portal.
- Filter inventory and operation history by app permission and assigned
  management authority.

### Phase 3: ownership-aware install requests

- Add durable install requests, review/approval, requester identity, and
  audit trail. Admins can install shared apps and decide whether to grant
  subsequent app-management authority.
- Make shared vs personal installation eligibility explicit in catalogue
  metadata and server-validated package manifests. Unknown/missing eligibility
  defaults to shared.

### Phase 4: personal instances, if supported packages justify it

- Add `instance_id`, owner account, isolation/resource policy, and an
  instance-aware package planner and inventory.
- Start with a narrow set of packages and supported resource types. Deny
  package plans with host-wide resources outside the personal-install allowlist.
- Enable member install/configure/upgrade/remove only for owned instances; add
  explicit transfer, account-deletion, orphan cleanup, backup, quota, and
  recovery behavior before broad rollout.

### Phase 5: role cleanup and migration

- Split publisher/test scopes from app-admin and replace strict role
  inheritance with composable, documented capability bundles.
- Migrate existing identities/groups to equivalent grants with a report of
  newly gained/lost authority; require owner review for elevated changes.
- Remove compatibility admin-only authorization only after all routes have
  equivalent policy checks and migration tests pass.

## Acceptance criteria

- A visitor cannot read any internal NostrHost API, catalogue, inventory,
  identity, health, settings, or operation data, even with a guessed URL.
- A member sees the trusted catalogue but cannot enumerate other members'
  accounts, app instances, settings, or operation results.
- An app permission grant allows app use only; it does not permit install,
  settings changes, upgrade, or removal.
- A member cannot plan or apply changes to an app/instance they do not own.
- A personal package plan cannot create or mutate resources outside its
  instance boundary; shared-only packages cannot be installed by members.
- Members cannot read or change shared operational settings by default.
  Secret values never appear in settings reads, diffs, audit events, or
  operation results; setting changes reach the app only through host-managed
  rendered configuration or an explicitly declared safe runtime mechanism.
- Revocation blocks subsequent reads/writes and invalidates pending approvals
  for the revoked principal or resource grant.
- Package publishers can publish/test without acquiring app-admin or host
  authority.
- UI visibility and API authorization agree, while API checks remain the
  security boundary. All grants and administrative changes are attributable
  and audited.

## Decisions still needed

- Is member registration open, invitation-only, or admin-created?
- Should members browse the complete trusted catalogue or only packages
  currently eligible for member requests/self-install?
- Which package resource types can be safely supported for personal instances,
  and what quotas/backups apply?
- Who may manage a member's app permissions: the app instance owner, assigned
  app managers, or only host admins?
- What happens to personal instances and app access when an account is
  disabled, deleted, or loses all linked signers?
