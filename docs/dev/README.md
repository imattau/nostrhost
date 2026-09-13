# Developer guide

For people reading, building, or contributing to the NostrHost codebase.

NostrHost is spread across the umbrella repository (this one — architecture,
integration, packaging, docs) and a set of git submodules: forks of YunoHost
components under `forks/`, and NostrHost-native libraries under `libs/`.

## Pages

| Page | Covers |
|---|---|
| [Architecture overview](architecture-overview.md) | The repository layout, the control-plane relay, how the submodules fit together, and where to go deeper |
| Building and testing *(TODO)* | Working with submodules, running each component's test suite, `scripts/verify-clean.sh` |
| Contributing *(TODO)* | Branch/pin conventions, where a change belongs (umbrella vs. fork vs. lib), commit/PR expectations |
| Writing a native package *(TODO)* | Authoring a `package.toml` app manifest — see [`../AI-PACKAGE-AUTHORING.md`](../AI-PACKAGE-AUTHORING.md) and [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md) in the meantime |
| Packaging and release *(TODO)* | The APT release pipeline — see [`../../packaging/README.md`](../../packaging/README.md) in the meantime |

Pages marked *(TODO)* aren't written yet.

## Design record, by topic

The developer guide is an entry point; the actual design decisions and
rationale live in the top-level `docs/*.md` design record. Useful jumping-off
points by area:

- **Control plane / events:** [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md),
  [`../NIP-MAPPING.md`](../NIP-MAPPING.md),
  [`../RELAY-SELECTION.md`](../RELAY-SELECTION.md)
- **App lifecycle:** [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md),
  [`../RESOURCE-ENGINE-CUTOVER.md`](../RESOURCE-ENGINE-CUTOVER.md),
  [`../APP-MANAGEMENT-PLAN.md`](../APP-MANAGEMENT-PLAN.md)
- **State and backup:** [`../STATELAYER.md`](../STATELAYER.md)
- **Web/TLS:** [`../CADDY-MIGRATION.md`](../CADDY-MIGRATION.md) and its
  `CADDY-P*-SPIKE.md` phase notes
- **Security:** [`../CROWDSEC-MIGRATION.md`](../CROWDSEC-MIGRATION.md)
- **Identity/auth compatibility:** [`../LDAP-RETIREMENT.md`](../LDAP-RETIREMENT.md),
  [`../MAIL-RETIREMENT.md`](../MAIL-RETIREMENT.md)
- **Admin/Portal UI:** [`../ADMIN-PORT-PLAN.md`](../ADMIN-PORT-PLAN.md),
  [`../ADMIN-FEATURE-MATRIX.md`](../ADMIN-FEATURE-MATRIX.md),
  [`../NATIVE-ADMIN-API.md`](../NATIVE-ADMIN-API.md)
- **Roles/permissions:** [`../ROLE-AND-APP-ACCESS-DESIGN.md`](../ROLE-AND-APP-ACCESS-DESIGN.md),
  [`../ROLE-AND-APP-ACCESS-IMPLEMENTATION-PLAN.md`](../ROLE-AND-APP-ACCESS-IMPLEMENTATION-PLAN.md)
- **MCP / agent integration:** [`../MCP-TRANSITION.md`](../MCP-TRANSITION.md),
  [`../AGENT-DISTRIBUTION-PLAN.md`](../AGENT-DISTRIBUTION-PLAN.md)
- **Full history:** [`../ROADMAP.md`](../ROADMAP.md) records every stage of
  the derivative build-out; [`../EXTRACTION.md`](../EXTRACTION.md) and
  [`../LEGACY-INVENTORY.md`/`../YNH-HELPER-STOCKTAKE.md`](../LEGACY-INVENTORY.md)
  record what was extracted or inventoried along the way.

## Contributing to the docs

- End-user material → [`../guide/`](../guide/README.md).
- Operator/sysadmin material → [`../admin/`](../admin/README.md).
- API/event/schema reference → [`../reference/`](../reference/README.md).
- A new architectural decision or migration → a new top-level `docs/*.md`
  file (the design record), linked from this page's topic list above.
- Keep prose in guide/admin/dev pages task-oriented; keep the "why" in the
  design record and link to it rather than duplicating it.
