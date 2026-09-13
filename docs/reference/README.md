# Reference

API and integration reference for building on top of NostrHost, or for
understanding its wire formats precisely. If you want a narrative
explanation instead of a lookup table, see the [architecture
overview](../dev/architecture-overview.md).

> **Status.** The underlying schemas and event kinds are still being
> finalised in Phase 2 of the roadmap — see
> [`../NIP-MAPPING.md`](../NIP-MAPPING.md) §4 for what's locked versus still
> marked "to verify". Treat kind numbers on these pages as current, not
> frozen.

## Pages

| Page | Covers |
|---|---|
| [Control-plane event reference](control-plane-events.md) | The operation request/approval/execution kind chain (2200–2205), notice kinds, kind-range discipline, and the standard NIPs used instead of custom kinds |
| [MCP integration](mcp-integration.md) | Using `yunohost-mcp-connect` and the native `nostrhost-mcp` adapter from an MCP client (Claude Desktop, Codex, etc.), and why MCP is an interface rather than an authority boundary |

## Use the source directly (no separate reference page planned)

These are already the primary, authoritative reference — a summary page
would only go stale:

| Topic | Source |
|---|---|
| Every NostrHost requirement mapped to a standard Nostr NIP | [`../NIP-MAPPING.md`](../NIP-MAPPING.md) |
| The `package.toml`/`package.json` resource vocabulary, field-by-field | [`../../schema/package.schema.json`](../../schema/package.schema.json), [`../RESOURCE-ENGINE.md`](../RESOURCE-ENGINE.md) |
| Every `.deb` NostrHost ships, its contents and dependency graph | [`../../packaging/README.md`](../../packaging/README.md) |

## Planned pages

| Page | Will cover |
|---|---|
| CLI reference *(TODO)* | Every `nostrhost` subcommand — generate from the CLI's own `--help` once stable |

## Related reading

- [`dev/`](../dev/README.md) for how these pieces fit together.
- [`admin/`](../admin/README.md) for operating a server day to day rather
  than integrating with it.
