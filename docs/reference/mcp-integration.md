# MCP integration

NostrHost can expose its operation catalogue to Model Context Protocol clients.
MCP is an interface, not an authority boundary: the server still verifies the
client identity, scopes, policy, approval, and operation schema.

```text
MCP client
    │ tool call
    ▼
NostrHost MCP adapter
    │ signed operation request
    ▼
local control plane → policy → approval → executor → signed result
```

## Native adapter

`nostrhost-mcp` derives tools from the native catalogue and can run over stdio
or a loopback HTTP listener. On a server, keep the listener private and publish
it through the managed Caddy route only when remote access is required.

```bash
nostrhost mcp route mcp.example.org
nostrhost mcp status
```

Public certificates need no custom client trust. For a lab domain using
Caddy's internal certificate authority, export the required CA with
`nostrhost mcp export-ca` and install it only on the intended client.

## Client identity

Give each MCP client a separate Nostr key and only the scopes needed for its
tools. Prefer read-only access first. NIP-98 protects HTTP requests; the signed
operation chain protects the administrative action behind the adapter.

Never reuse the owner key as an unattended MCP credential. Revoke a retired or
compromised client without affecting other users.

## Approval

A tool call that requires approval returns or waits on a request ID. The client
cannot approve its own request unless policy explicitly grants that authority.
An owner or administrator signs the matching approval, after which the client
can follow progress and receive the result.

## Compatibility bridge

`yunohost-mcp-connect` is a client-side bridge for the compatible HTTP surface.
Install it on the machine running the MCP client, generate a unique client key,
and point it at the server. It is not part of the NostrHost server
meta-packages.

## Operational guidance

- Keep the adapter and internal relay off public interfaces.
- Put remote HTTP access behind Caddy and TLS.
- Limit scopes and review audit events by client key.
- Treat tool results, logs, and app data as potentially sensitive.
- Use timeouts as an unknown state, then query the request ID.
- Remove the route, key, and capabilities when decommissioning a client.
