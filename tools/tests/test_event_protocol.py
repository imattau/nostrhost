"""Contract tests for the WP1 event-protocol corpus and the Python reference."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "event_protocol", ROOT / "tools" / "event_protocol.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ep = _load_module()


def test_verdict_corpus_is_wellformed() -> None:
    fixtures = ep.load_fixtures(ROOT / "authority/event-protocol/fixtures/verdicts.json")
    assert len(fixtures) >= 30
    ids = [f["id"] for f in fixtures]
    assert len(ids) == len(set(ids)), "duplicate fixture ids"
    for fixture in fixtures:
        assert "event" in fixture
        assert "expect" in fixture
        assert fixture["expect"]["accept"] in (True, False)
        if not fixture["expect"]["accept"]:
            assert fixture["expect"]["code"], f"{fixture['id']} lacks a reason code"


def test_fold_corpus_is_wellformed() -> None:
    fixtures = ep.load_fixtures(ROOT / "authority/event-protocol/fixtures/folds.json")
    assert fixtures
    for fixture in fixtures:
        assert fixture["events"], fixture["id"]
        assert "expect" in fixture


def test_python_reference_matches_corpus() -> None:
    problems = (
        ep._verdict_mismatches(ep.run_verdicts(ROOT))
        + ep._fold_mismatches(ep.run_folds(ROOT))
    )
    assert problems == []


def test_schemas_validate_accepted_content() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    checked = 0
    for fixture in ep.load_fixtures(
        ROOT / "authority/event-protocol/fixtures/verdicts.json"
    ):
        if not fixture["expect"]["accept"]:
            continue
        kind = int(fixture["event"]["kind"])
        schema_path = next(
            iter(sorted((ROOT / "authority/event-protocol/schemas").glob(f"{kind}-*.schema.json"))),
            None,
        )
        if schema_path is None:
            continue
        raw = fixture["event"].get("content") or ""
        if raw == "":
            continue
        body = json.loads(raw)
        if not isinstance(body, dict):
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(body)
        checked += 1
    assert checked > 0, "no accepted fixtures exercised a content schema"


def test_every_kind_has_a_schema() -> None:
    schemas = {p.stem.split("-")[0] for p in (ROOT / "authority/event-protocol/schemas").glob("*.schema.json")}
    assert {"31100", "31101", "31102", "27236", "27237"} <= schemas


def _load_matrix() -> dict:
    import tomllib

    with (ROOT / "authority/authority-matrix.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_matrix_schema_references_exist() -> None:
    matrix = _load_matrix()
    assert matrix["version"] >= 2
    for row in matrix["kind"]:
        schema = row["schema"]
        if schema.startswith("pending:"):
            continue
        assert (ROOT / schema).exists(), f"kind {row['kind']}: missing schema {schema}"


def test_matrix_covers_required_custom_kinds() -> None:
    kinds = {str(row["kind"]) for row in _load_matrix()["kind"]}
    for required in ("31100", "31101", "31102", "27236", "27237"):
        assert required in kinds, f"matrix is missing kind {required}"


def test_matrix_fixtures_cover_go_validated_kinds() -> None:
    matrix_kinds = {str(row["kind"]) for row in _load_matrix()["kind"]}
    fixtures = ep.load_fixtures(ROOT / "authority/event-protocol/fixtures/verdicts.json")
    go_kinds = {str(f["event"]["kind"]) for f in fixtures if "go" in f["validators"]}
    assert go_kinds <= matrix_kinds, f"matrix missing kinds: {go_kinds - matrix_kinds}"


def test_go_testdata_mirror_is_identical() -> None:
    """The Go module bundles a mirror of the canonical corpus for standalone
    builds; it must stay byte-identical or the CI conformance checks diverge."""
    canonical = ROOT / "authority/event-protocol/fixtures"
    mirror = ROOT / "libs/nostrhost-control/internal/eventprotocol/testdata"
    for name in ("verdicts.json", "folds.json"):
        assert (mirror / name).read_bytes() == (canonical / name).read_bytes(), (
            f"Go testdata mirror of {name} has drifted from authority/event-protocol/fixtures"
        )


def test_rejections_carry_stable_codes() -> None:
    results = ep.run_verdicts(ROOT)
    for item in results:
        if not item["accept"]:
            assert item["code"], item["id"]


def test_fold_revision_prefers_protocol_over_time() -> None:
    events = [
        {
            "id": "a",
            "kind": 31100,
            "created_at": 100,
            "tags": [["d", "a" * 64]],
            "content": '{"type":"agent","scopes":["x"],"revision":2}',
        },
        {
            "id": "b",
            "kind": 31100,
            "created_at": 999,
            "tags": [["d", "a" * 64]],
            "content": '{"type":"agent","scopes":["y"],"revision":1}',
        },
    ]
    result = ep.fold(31100, events)
    assert result.revision == 2
    assert result.fact["scopes"] == ["x"]


def test_legacy_documents_do_not_conflict() -> None:
    events = [
        {
            "id": "a",
            "kind": 31100,
            "created_at": 100,
            "tags": [["d", "a" * 64]],
            "content": '{"type":"agent","scopes":["x"]}',
        },
        {
            "id": "b",
            "kind": 31100,
            "created_at": 200,
            "tags": [["d", "a" * 64]],
            "content": '{"type":"agent","scopes":["y"]}',
        },
    ]
    assert ep.fold(31100, events).conflicts == 0
