# Developer guide

This guide explains where code belongs, how the runtime works, and how to
develop and release changes safely.

## Read in this order

1. [Architecture overview](architecture-overview.md)
2. [Building and testing](building-and-testing.md)
3. [Contributing](contributing.md)
4. [Writing a native app package](native-app-packages.md)
5. [Packaging and releases](packaging-and-releases.md)
6. [Reference](../reference/README.md) for event and integration contracts

## Repository boundaries

The top-level repository owns component pins, integration, Debian packaging,
schemas, testbeds, and product documentation. Most runtime code lives in Git
submodules under `forks/` and `libs/`. Make a code change in the component that
owns it, commit that component, then update the top-level submodule pin and any
compatibility metadata.

Do not mix generated build output, private keys, credentials, VM disks, or
runtime state into source commits.

## Design rules

- All interfaces use the shared operation catalogue and policy path.
- Only the executor changes machine state after validation and approval.
- Prefer a standard Nostr primitive before adding a custom event kind.
- Keep sessions and secrets out of the relay event stream.
- Native apps declare resources; they do not run arbitrary lifecycle scripts.
- Planning and inspection are read-only; application is a separate action.
- Every write needs a clear permission, audit result, and recovery story.
- Preserve compatibility only at explicit boundaries and keep those boundaries
  private where possible.

## Documentation changes

Update the audience-facing page that owns the behaviour. User tasks belong in
`guide/`, operations in `admin/`, development in `dev/`, and stable contracts
in `reference/`. Explain current behaviour directly and avoid making readers
reconstruct it from internal notes or change history.
