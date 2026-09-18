# Reference

This section describes the stable contracts used by NostrHost interfaces and
integrations. It assumes you already understand the
[architecture](../dev/architecture-overview.md).

## Contents

- [Control-plane events](control-plane-events.md): signed requests,
  approvals, results, definitions, and notices.
- [Operation catalogue](operations.md): the shared tool and policy boundary.
- [Diagnosis engine](diagnosis-engine.md): health checks, cache, and ignored
  findings.
- [MCP integration](mcp-integration.md): connecting an agent or MCP client.
- [MCP diagnosis tools](mcp-diagnosis-tools.md): agent-facing health and
  incident evidence.

## Source contracts

Some contracts are best consumed directly by tools:

- `schema/package.schema.json` validates native app manifests.
- `packaging/packages.yml` defines Debian packages and their sources.
- `packaging/compatibility.yml` defines component version constraints.
- `forks/yunohost/src/nostrhost/native_ops.py` defines operation schemas,
  scopes, risk, reversibility, and handlers.
- `libs/nostrhost-control/internal/eventmodel/` validates custom event kinds.

Generated clients should use exported schemas or catalogues rather than parse
human documentation.
