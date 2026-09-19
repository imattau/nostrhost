# NostrHost event protocol

**Status:** WP1 of [`docs/RELAY-STATE-MIGRATION-PLAN.md`](../../docs/RELAY-STATE-MIGRATION-PLAN.md).

This directory freezes the control-plane event contract: the common envelope,
per-kind JSON Schemas, deterministic replacement/conflict/revocation rules, and
a cross-language conformance corpus.

```text
event-protocol/
├── README.md                 this file
├── envelope.md               envelope + revision/conflict/revocation + compatibility rules
├── schemas/                  checked-in JSON Schemas (content objects)
└── fixtures/                 the conformance corpus
    ├── verdicts.json         single event → accept/reject + reason code
    └── folds.json            ordered events → effective fact
```

Two independent implementations consume this corpus:

- Python reference: `tools/event_protocol.py` (`python tools/event_protocol.py conformance`)
- Go reference: `libs/nostrhost-control/internal/eventprotocol` (`go test ./internal/eventprotocol/...`)

The corpus is the source of truth. CI runs both; they must produce identical
`accept`/`reject` verdicts and identical folded facts for every fixture.

The Go module is a standalone repository, so it bundles a byte-identical mirror
of the fixtures under `libs/nostrhost-control/internal/eventprotocol/testdata/`.
After editing the corpus run:

```sh
python tools/event_protocol.py sync-mirror
```

A test fails if the mirror drifts from `authority/event-protocol/fixtures/`.

## Why a corpus and not just schemas

JSON Schema validates a content object but cannot express tag semantics,
authorization, revision ordering, or fold outcomes. The schemas document the
content shape; the fixtures pin the observable verdict and the effective state.
Where the two disagree, the fixtures win and the schema is fixed.

## Which implementation validates which kind

Not every implementation claims every kind — the local relay deliberately treats
standard NIP kinds as opaque while the Python fork consumers project them. Each
fixture declares the `validators` that must reach its expected verdict:

| Validator | Claims |
|---|---|
| `python` | all kinds in this directory |
| `go` | NostrHost custom kinds (`31100`, `31101`, `31102`, `27236`, `27237`) |

For the custom kinds both implementations must agree with the corpus **and**
with each other. `eventprotocol` delegates to the relay's `eventmodel.Validate`
for those kinds, and a test asserts the two Go paths agree.

## Reason codes

Rejections carry a stable code so verdicts are comparable across languages. A
fixture violates exactly one rule, so codes are unambiguous. The code vocabulary
and the rule order are in [envelope.md](envelope.md).

## Editing the corpus

1. Add the fixture to `verdicts.json` or `folds.json`.
2. Run `python tools/event_protocol.py conformance` — it reports mismatches.
3. Run the Go conformance test.
4. If a kind's required fields change, bump its `schema` version and update the
   JSON Schema and `authority/authority-matrix.toml` together.
