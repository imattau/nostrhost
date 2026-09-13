# NostrHost documentation

This is the documentation hub for NostrHost. It is organised by audience.
The many existing files at the top level of `docs/` (`ROADMAP.md`,
`CONTROL-PLANE.md`, `STATELAYER.md`, the `*-PLAN.md` and `*-MIGRATION.md`
files, etc.) remain in place as the **design record** — they capture how
each part of the platform was decided and built, and are the primary
sources this guide set is written from. Treat them as the deep-dive/history
layer; the sections below are the entry points.

> **Status note.** NostrHost is pre-alpha (see `ALPHA-PLAN.md` and the
> "Platform state" table in the top-level `README.md`). Sections below that
> describe end-user flows (installation, first run) describe the *target*
> experience the alpha plan is building towards, and are marked accordingly
> where the underlying capability isn't wired up end-to-end yet.

## Start here

| I want to... | Go to |
|---|---|
| Install NostrHost and log in for the first time | [`guide/`](guide/README.md) — user guide |
| Run and operate a NostrHost server long-term | [`admin/`](admin/README.md) — administrator guide |
| Understand or contribute to the codebase | [`dev/`](dev/README.md) — developer guide |
| Integrate with NostrHost's events, schemas or MCP bridge | [`reference/`](reference/README.md) — reference |

## Documentation map

```text
docs/
├── README.md              # you are here
├── guide/                  # end users / self-hosters
├── admin/                  # sysadmins / operators
├── dev/                    # developers / contributors
├── reference/               # API / integration reference
└── *.md                     # design record: architecture decisions,
                              # migration plans, roadmap, phase reports
```

## Design record index

The most load-bearing design documents, in the order a new contributor
should read them:

1. [`ROADMAP.md`](ROADMAP.md) — full provenance: where NostrHost came from
   (a YunoHost fork) and every stage of the derivative build-out.
2. [`ALPHA-PLAN.md`](ALPHA-PLAN.md) — the current execution plan to the 0.1
   alpha ("make it a product").
3. [`BASELINE.md`](BASELINE.md) — the pinned upstream/fork baseline and the
   rules for changing it.
4. [`CONTROL-PLANE.md`](CONTROL-PLANE.md) — the local Nostr relay as the
   control-plane bus; the architectural core of the whole platform.
5. [`NIP-MAPPING.md`](NIP-MAPPING.md) — which standard Nostr NIPs cover which
   platform requirement, and where genuine custom event kinds remain.
6. [`STATELAYER.md`](STATELAYER.md) — ngit/NIP-34 configuration state plus
   Restic data linkage.
7. [`RESOURCE-ENGINE.md`](RESOURCE-ENGINE.md) — the declarative
   `package.toml` app lifecycle engine.

Everything else in `docs/*.md` is a focused deep-dive (a migration such as
`CADDY-MIGRATION.md` / `CROWDSEC-MIGRATION.md` / `LDAP-RETIREMENT.md`, a
subsystem plan such as `NOTIFICATION-SERVICE.md` / `AGENT-DISTRIBUTION-PLAN.md`,
or a point-in-time inventory/stocktake).

## Contributing to the docs

- New end-user, operator, developer or reference material goes under the
  matching section (`guide/`, `admin/`, `dev/`, `reference/`), not at the
  top level of `docs/`.
- The top-level `docs/*.md` files are the design record: update them when a
  documented decision changes, but don't restructure them to read as a
  tutorial — that's what the sections above are for.
- Keep cross-references relative (`../CONTROL-PLANE.md`, `../ROADMAP.md`) so
  the docs work both on GitHub and if this tree is ever built with a static
  site generator.
