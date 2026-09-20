# NostrHost event protocol — moved

**Status:** Superseded by the `nostrhost-protocol` library
(`libs/nostrhost-protocol/`).

The authoritative specification and conformance corpus moved here:

- **Spec** (envelope rules, JSON Schemas, machine-readable kind manifest,
  verdict/fold fixtures): [`libs/nostrhost-protocol/spec/`](../../libs/nostrhost-protocol/spec/)
- **Python binding**: [`libs/nostrhost-protocol/python/`](../../libs/nostrhost-protocol/python/)
- **Go binding**: [`libs/nostrhost-protocol/go/`](../../libs/nostrhost-protocol/go/)

This directory is retained as a compatibility marker only. The umbrella's
authority checks now run the corpus through the library:

```sh
python tools/event_protocol.py conformance
python tools/event_protocol.py sync-mirror
```

The conformance corpus is the source of truth; CI runs both the Python and Go
bindings against it and they must reach identical verdicts and folds. Editing
the corpus means editing `libs/nostrhost-protocol/spec/fixtures/` and syncing
the binding mirrors.

Historical note: this used to freeze the contract in place (WP1 of
`docs/RELAY-STATE-MIGRATION-PLAN.md`); it is now a reusable cross-language
library following the separate-repository/submodule model.