# Operation catalogue

The operation catalogue is the common contract behind Admin, CLI, HTTP API,
MCP, and the resident agent. Each operation declares:

- a unique name;
- an input schema and result schema;
- one or more required scopes;
- whether approval is required;
- risk and reversibility metadata; and
- a server-side handler.

This prevents interfaces from inventing their own privileged code paths.

## Main operation families

| Family | Examples |
|---|---|
| System | status, configuration regeneration, migrations, upgrade |
| Services | list, status, start, stop, restart, logs |
| Apps | list, install, upgrade, configure, change URL, remove |
| Packages | validate/plan native resources, reconcile an approved plan |
| Backups | create, list, inspect, restore, delete |
| Domains and DNS | add, remove, configure, reconcile records |
| Users and access | users, groups, permissions, identities, capabilities |
| Security | firewall inspection and changes, audit reads |
| Health | diagnosis, update checks, network and resource information |
| Catalogue | discover, publish, attest, trust, and verify packages |
| State | compare, reconcile, replicate, and assist rollback |
| Integrations | notifications, signers, MCP endpoint, resident agent |

The exact catalogue is generated from the running version. Use CLI help or the
exported operation catalogue for automation rather than relying on this
summary.

## Read and write behaviour

Read-only operations normally execute without approval when the caller has the
required scope. Writes enter the signed request chain. Risk, caller role,
delegation, and policy determine whether owner or administrator approval is
needed.

Handlers validate all arguments and reject unknown fields. Results are also
validated before publication. Sensitive fields are marked so clients can avoid
logging or exposing them.

## Following an operation

The initial request event ID is the operation ID. Clients subscribe to events
that reference it. CLI users can inspect or follow the chain with:

```bash
nostrhost op status <request-id>
nostrhost op follow <request-id>
```

Consumers should handle requested, approved, rejected, executing, progress,
succeeded, and failed states. A timeout means the result is not yet known; it
does not mean the operation failed.

## Adding an operation

Define typed input and output, scope, risk, reversibility, approval behaviour,
and verification before exposing a handler. Add tests for schema rejection,
policy denial, approval, execution, result validation, audit linkage, and safe
failure. Then let interfaces consume the catalogue instead of hand-writing a
duplicate definition.
