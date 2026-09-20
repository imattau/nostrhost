"""Contract tests for the event-protocol corpus and the nostrhost-protocol library."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SPEC_DIR = ROOT / "libs/nostrhost-protocol/spec"
FIXTURES_DIR = SPEC_DIR / "fixtures"
SCHEMAS_DIR = SPEC_DIR / "schemas"


def _protocol():
    import nostrhost_protocol as p

    return p


ep = _protocol()


def test_verdict_corpus_is_wellformed() -> None:
    fixtures = ep.load_verdicts()
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
    fixtures = ep.load_folds()
    assert fixtures
    for fixture in fixtures:
        assert fixture["events"], fixture["id"]
        assert "expect" in fixture


def test_python_reference_matches_corpus() -> None:
    result = ep.conformance("python")
    assert result["problems"] == [], result["problems"]


def test_schemas_validate_accepted_content() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    checked = 0
    for fixture in ep.load_verdicts():
        if not fixture["expect"]["accept"]:
            continue
        kind = int(fixture["event"]["kind"])
        schema = ep.load_schema(kind)
        if schema is None:
            continue
        raw = fixture["event"].get("content") or ""
        if raw == "":
            continue
        body = json.loads(raw)
        if not isinstance(body, dict):
            continue
        jsonschema.Draft7Validator(schema).validate(body)
        checked += 1
    assert checked > 0, "no accepted fixtures exercised a content schema"


def test_every_kind_has_a_schema() -> None:
    schemas = {p.stem.split("-")[0] for p in SCHEMAS_DIR.glob("*.schema.json")}
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
    fixtures = ep.load_verdicts()
    go_kinds = {str(f["event"]["kind"]) for f in fixtures if "go" in f["validators"]}
    assert go_kinds <= matrix_kinds, f"matrix missing kinds: {go_kinds - matrix_kinds}"


def test_go_testdata_mirror_is_identical() -> None:
    """The Go module bundles a mirror of the canonical corpus for standalone
    builds; it must stay byte-identical or the CI conformance checks diverge."""
    canonical = FIXTURES_DIR
    mirror = ROOT / "libs/nostrhost-protocol/go/testdata"
    for name in ("verdicts.json", "folds.json"):
        assert (mirror / name).read_bytes() == (canonical / name).read_bytes(), (
            f"Go testdata mirror of {name} has drifted from libs/nostrhost-protocol/spec/fixtures"
        )


def test_python_package_data_mirror_is_identical() -> None:
    canonical = FIXTURES_DIR
    mirror = ROOT / "libs/nostrhost-protocol/python/src/nostrhost_protocol/spec/fixtures"
    for name in ("verdicts.json", "folds.json"):
        assert (mirror / name).read_bytes() == (canonical / name).read_bytes(), (
            f"Python package-data mirror of {name} has drifted"
        )


def test_authority_event_protocol_is_compat_readme_only() -> None:
    """The old authority/event-protocol path now holds only a compat README."""
    legacy = ROOT / "authority/event-protocol"
    readme = legacy / "README.md"
    assert readme.exists()
    assert "nostrhost-protocol" in readme.read_text()
    for leftover in ("fixtures", "schemas"):
        assert not (legacy / leftover).exists(), f"stale {leftover} at authority/event-protocol"


def test_rejections_carry_stable_codes() -> None:
    result = ep.conformance("python")
    for item in result["verdicts"]:
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
    result = ep.fold_events(31100, events)
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
    assert ep.fold_events(31100, events).conflicts == 0


def test_manifest_is_machine_readable() -> None:
    manifest = json.loads(Path(ep.manifest_path()).read_text())
    assert manifest["schema"] == 1
    kinds = [row["kind"] for row in manifest["kinds"]]
    assert len(kinds) == len(set(kinds)), "duplicate kinds in manifest"
    for row in manifest["kinds"]:
        assert row["name"], row
        assert row["category"], row
        assert isinstance(row["rejection_codes"], list), row