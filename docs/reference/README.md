# Reference

API and integration reference for building on top of NostrHost, or for
understanding its wire formats precisely. If you want a narrative
explanation instead of a lookup table, see the [architecture
overview](../dev/architecture-overview.md).

> **Status.** These pages are scaffolded but not yet written in full. The
> underlying schemas and event kinds are still being finalised in Phase 2
> of the roadmap — see [`../NIP-MAPPING.md`](../NIP-MAPPING.md) §4 for what's
> locked versus still marked "to verify". Each row links to the
> authoritative source in the meantime.

## Planned pages

| Page | Will cover | Written from |
|---|---|---|
| NIP mapping *(TODO — use source directly)* | Every NostrHost requirement mapped to a standard Nostr NIP, and the small remaining set of custom event kinds | [`../NIP-MAPPING.md`](../NIP-MAPPING.md) |
| Control-plane event reference *(TODO)* | The operation request/approval/execution event shapes, kind-range discipline, retention policy | [`../CONTROL-PLANE.md`](../CONTROL-PLANE.md) |
| Package manifest schema *(TODO — use source directly)* | The `package.toml`/`package.json` resource vocabulary field-by-field | [`../../schema/package.schema.json`](../../schema/package.schema.json), [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md) |
| APT package reference *(TODO — use source directly)* | Every `.deb` NostrHost ships, its contents and dependency graph | [`../../packaging/README.md`](../../packaging/README.md) |
| MCP integration *(TODO)* | Using `yunohost-mcp-connect` and the native `nostrhost-mcp` adapter from an MCP client (Claude Desktop, Codex, etc.) | [`../MCP-TRANSITION.md`](../MCP-TRANSITION.md), [`../../packaging/README.md`](../../packaging/README.md) |
| CLI reference *(TODO)* | Every `nostrhost` subcommand | — (generate from the CLI's own `--help` once stable) |

## Related reading

- [`dev/`](../dev/README.md) for how these pieces fit together.
- [`admin/`](../admin/README.md) for operating a server day to day rather
  than integrating with it.
