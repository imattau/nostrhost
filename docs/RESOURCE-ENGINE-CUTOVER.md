# Resource Engine Cutover and Plane Integration

The resource engine is now capable of describing and reconciling a native
package, but it is not yet the sole application lifecycle authority. The next
work is therefore a cutover: establish one owner for each concern, connect the
engine to the NostrHost planes, then retire compatibility code only after the
replacement is proven.

## 1. What is redundant, and what is still needed

| Existing surface | Current authority | Target authority | Removal condition |
|---|---|---|---|
| `helpers/helpers.v2.1.d/` and package Bash scripts | Legacy YunoHost packages | Native manifest + bounded providers | All supported packages are native, or explicitly quarantined as legacy |
| `yunohost.app` install/upgrade/remove path | Legacy app lifecycle | Resource-engine lifecycle executor | Native lifecycle tools handle catalog resolution, plan, approval, apply, verify, and rollback |
| YunoHost `manifest.json`/v2 resource vocabulary | Legacy package metadata | `package.toml` | Catalog and installer consume native declarations; migration reports are clean |
| Legacy catalog sources | YunoHost catalog fallback | `nostrhost-catalog` trusted projection | Native catalog has a fresh trusted declaration for every installable native package |
| `nostr_operations.py` local scope/approval vocabulary | Fork-local policy adapter | `nostrhost-policy` evaluator | Policy decisions are made by one shared evaluator and are recorded in operation events |
| Fork-local identity projection/store | Compatibility projection | `nostrhost-auth` identity core + Nostr events | All consumers resolve canonical npubs through one identity API; LDAP remains only a projection |
| `nostr_state.py` local Git state | Local state history | NIP-34/ ngit semantic state | State commits carry repository identity, event linkage, and replication/recovery policy |
| `BackupProvider` registration and `nostr_restic.py` | Split declaration/data handling | State declaration + Restic data plane | A reconciled operation creates/link snapshots according to policy and records the result |
| Portal/SSOwat permission APIs | Compatibility projection | NostrHost permission intent projected to Portal/SSO | Native permission events and projection are authoritative; old calls are adapter-only |
| Admin app lifecycle UI | Legacy API calls | Catalog + operation request UI | UI submits signed/approved native operations and displays structured plans/results |

The helper tree is not removable as a single operation. It remains required
for legacy packages until the package cutover gate is met. It must not be a
dependency of native providers.

## 2. Target authority model

```text
catalogue plane
  trusted package declaration + compatibility + attestation
                 |
                 v
identity plane -> policy plane -> control plane
 npub/actor        risk/approval       signed request chain
                                             |
                                             v
state plane ---- desired manifest + pre/post semantic revisions
                                             |
                                             v
resource engine / executor plane
  inspect -> plan -> policy check -> apply -> verify
        |             |                 |
        v             v                 v
 systemd/host     audit/result       Restic/DB data plane
 projections      events             snapshots and restore
```

Authority is deliberately separated:

- The catalogue decides what package declaration and artifact are trusted.
- Identity decides who is acting and which local account is the compatibility
  projection.
- Policy decides whether a plan may be applied, including resource ownership,
  risk, approval, and restore requirements.
- The control plane transports signed requests, approvals, execution results,
  and audit events; it does not implement resource mutations.
- The resource engine owns package desired state and provider execution.
- systemd, databases, Caddy, and the filesystem remain runtime projections.
- Restic owns application data recovery; semantic state history does not
  replace it.

## 3. Required integration seams

### Catalogue to resource engine

The native catalogue projection should return a verified package coordinate,
manifest, artifact URL, digest, architecture, and signer/attestation. The
installer must pass that declaration to `package.plan`; a URL or legacy app id
alone is insufficient. The plan result, selected architecture variant, and
manifest digest become part of the operation request.

The current `package.plan` response is the first version of this seam: a
schema-versioned envelope containing package id/version, `manifest_sha256`,
the typed operation list, and `plan_sha256`. `package.reconcile` verifies the
plan digest before provider execution. Raw operation lists remain accepted
only as a marked legacy compatibility path. The daemon now loads the shared
`nostrhost-policy` rules and maps native plans to the upgrade/remove policy
tiers; the plan digest is carried into pre/post state snapshots.

### Identity and policy to execution

`package.plan` is read-only. Applying a plan must be an approval-gated
operation whose policy input includes the complete operation list, not merely
the package name. The evaluator must check:

1. actor and delegated authority;
2. package signer/catalogue trust;
3. requested resource ownership and host-policy constraints;
4. risk and reversibility, including database deletion;
5. required pre-change Restic snapshot;
6. provider capability coverage.

The result must contain the policy version and plan digest so replay cannot
silently apply a different plan.

### Control plane to executor

The Go relay remains the event bus. `nostr_operationsd` should become the
single boundary that consumes the approved event and invokes the native
executor. Direct CLI/provider mutation is a recovery/debug path, not a second
authority. Execution results should include operation resource, changed state,
verification result, and redacted error details.

### State and data recovery

Before a data-affecting plan, state recording should create a semantic
pre-change revision and, when policy requires it, a Restic snapshot. After
apply and verification, it creates a post-change revision containing:

```toml
[operation]
event = "<request-event-id>"
plan_sha256 = "<plan-digest>"

[backup]
restic_snapshot = "<snapshot-id>"
required = true

[health]
result = "passed"
```

Restore must be selected from the linked revision/snapshot, not inferred from
an app name. Database dump/restore remains a provider operation and must be
linked to the same operation record.

### Portal/Admin integration

Portal permissions remain a projection of native permission resources until
all applications consume the native permission model. Admin should display
native package plans, risk, affected resources, approval state, and structured
results. Existing app pages can remain as a legacy-package view during the
transition.

## 4. Removal gates

The current repository inventory is recorded in
[`LEGACY-INVENTORY.md`](LEGACY-INVENTORY.md) and can be regenerated with
`python3 tools/legacy_inventory.py`. It is intentionally report-only: deleting
the helper tree before the VM proves both native and compatibility paths would
remove host-hook dependencies and invalidate the legacy test fixture.

Remove or disable a legacy surface only when all of these are true:

- native package plan and reconcile pass in a clean test root;
- the catalogue declaration is trusted and architecture-specific;
- policy evaluates the full plan and records approval;
- the control-plane executor applies and verifies it;
- pre/post state and required data snapshots are linked;
- restore/rollback has an exercised procedure;
- Portal/Admin show the same package and operation state;
- no remaining supported package imports the retired helper surface.

Until then, retain the old path as an explicitly labelled compatibility
adapter and prevent it from becoming an implicit fallback for native packages.

## 5. Implementation order

1. Add a canonical native package-coordinate/plan envelope shared by catalog,
   policy, control, and state.
2. Add a policy-aware executor adapter in `nostr_operationsd`; remove direct
   `native_providers()` construction from request handlers. The policy and
   approval seam is now live; provider construction remains inside the
   executor backend as the next isolation step.
3. Add pre/post state and Restic linkage around native reconciliation. Native
   reconciliation is now classified as data-affecting and carries its plan
   digest; the remaining step is linking the policy-selected Restic snapshot
   into the native plan result.
4. Wire Admin and catalogue installation to native plans while retaining the
   legacy path for non-native packages.
5. Migrate representative packages and publish a native/legacy inventory.
6. Disable legacy lifecycle scripts for native packages, then retire helpers
   and fallback catalog sources by domain.
