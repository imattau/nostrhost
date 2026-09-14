# MCP integration

NostrHost exposes its native operation model to MCP (Model Context
Protocol) clients — Claude Desktop, Codex, or any other stdio MCP client —
without granting the client, or the agent behind it, root authority. Full
design: [`../MCP-TRANSITION.md`](../MCP-TRANSITION.md).

## The architectural rule

> MCP is an interface, not an authority boundary.

`nostrhost-mcp` is a **thin protocol adapter**, not a privileged management
product: it submits signed operation-request events on behalf of the
client, and observes the same response chain any other client (CLI, Admin,
Portal) would. Authority, policy evaluation, approvals, execution and audit
all live in NostrHost itself — the same control plane described in
[`control-plane-events.md`](control-plane-events.md) — not in the MCP layer.

```text
MCP client (Claude Desktop, Codex, …)
        │
        ▼
nostrhost-mcp adapter        (protocol translation only — no authority)
        │  submits a signed kind-2200 operation request
        ▼
NostrHost control-plane relay
        │
        ▼
policy evaluation → approval (if required) → execution → signed result
        │
        ▼
nostrhost-mcp adapter observes 2201/2203/2204/2205 by `#e` and
translates the result back to the MCP client
```

This is the same registry, executor and signed operation chain that the
CLI and the native HTTP API use — there is no separate, duplicated
YunoHost-integration code path for MCP.

## Two ways to connect

### `yunohost-mcp-connect` (client-side bridge, install today)

A standalone, APT-installable bridge for talking to a NostrHost server's
native admin API from an MCP client:

```bash
sudo apt install yunohost-mcp-connect
```

- Bundles its own locked Python wheels and installs them offline into
  `/opt/yunohost-mcp-connect/venv` — no `uvx`, `pip`, or network access
  needed after the package itself is downloaded.
- Configure your MCP client (Claude Desktop, Codex, or another stdio MCP
  client) to run `/usr/bin/yunohost-mcp-connect`.
- Generate a separate signing key per client:
  ```bash
  yunohost-mcp-connect --generate-key PATH
  ```
- Every request it makes to the server is authenticated with **NIP-98**
  (signed `Authorization: Nostr <event>` headers) — no passwords or static
  API keys.

See [`../../packaging/README.md`](../../packaging/README.md) for the full
package details. This is a **client-side** tool: it is not installed by
either NostrHost server meta-package, and it needs the NostrHost APT source
configured on the machine running the MCP client, not the server.

### `nostrhost-mcp` (native adapter, in development)

The longer-term native adapter, replacing the frozen `yunohost-mcp`
reference implementation feature-for-feature but backed entirely by
NostrHost's own operation registry, policy engine and signed event chain.
See [`../MCP-TRANSITION.md`](../MCP-TRANSITION.md) for the phase plan
(Phases 0–8: registry hardening → skeleton → native identity/capabilities →
signed mutations/streaming → approval flow → Resource Engine integration →
client integrations → multi-host projection → retiring the duplicated
reference logic).

## What's preserved from the reference implementation

`yunohost-mcp` (held as a frozen reference under `libs/yunohost-mcp`) keeps
working for stock YunoHost during the migration. Its useful surface —
NIP-98 authentication, agent keys, delegation, owner co-signatures, audit,
the MCP protocol itself, package-development tools, [diagnostics
tools](mcp-diagnosis-tools.md) — is preserved; only the *implementation*
moves onto NostrHost's native registry, policy and control plane rather
than duplicating that logic in the MCP layer itself.

## Approval flow for privileged operations

An operation a policy marks as requiring approval doesn't execute just
because an MCP client requested it. It sits at `REQUESTED` in the state
machine until an authorised signer (typically the owner, via a NIP-46
signature) approves it — the same approval mechanism used regardless of
which interface (Portal, Admin, CLI, MCP) originated the request. See
[`control-plane-events.md`](control-plane-events.md) and
[`../admin/security-model.md`](../admin/security-model.md) for the
authorization model this sits on top of.

## Related reading

- [`control-plane-events.md`](control-plane-events.md) — the exact event
  kinds an MCP client's requests and observations flow through.
- [`../dev/README.md`](../dev/README.md) — links to the full
  `MCP-TRANSITION.md` phase plan and status tracking.
