#!/usr/bin/env python3
"""Structural sanity gate for the NIP-5A conformance corpus.

Runs in the parent-repo ``apt.yml`` ``tools/tests`` CI job, which has no
``nostr-sdk``; signature/id verification and label decoding are exercised by
the fork's ``tests_nostr/test_nsites_manifest.py`` instead. This test keeps
the corpus self-consistent: schema, aggregate-hash recomputation against the
expected value, and label grammar.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spec  # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
NIP01_FIELDS = {"id", "pubkey", "created_at", "kind", "tags", "content", "sig"}


def _corpus_files() -> list[Path]:
    return sorted(CORPUS_DIR.glob("*.json"))


@pytest.fixture(scope="module", params=_corpus_files(), ids=lambda p: p.stem)
def corpus_case(request: pytest.FixtureRequest):
    case = json.loads(request.param.read_text())
    assert case["name"] == request.param.stem, "corpus filename must match name"
    return case


def test_corpus_file_shape(corpus_case: dict):
    assert set(corpus_case) == {"name", "description", "event", "expect"}
    expect = corpus_case["expect"]
    assert "valid" in expect and isinstance(expect["valid"], bool)
    for code in expect.get("errors", []):
        assert code in spec.ERROR_CODES, f"unknown reason code {code!r}"


def test_event_is_well_formed(corpus_case: dict):
    ev = corpus_case["event"]
    assert isinstance(ev, dict)
    assert NIP01_FIELDS <= set(ev)
    assert isinstance(ev["kind"], int)
    assert isinstance(ev["tags"], list)
    assert isinstance(ev["content"], str)
    assert len(ev["id"]) == 64 and len(ev["pubkey"]) == 64 and len(ev["sig"]) == 128


def test_aggregate_hash_matches_expected(corpus_case: dict):
    expect = corpus_case["expect"]
    if "aggregate_hash" not in expect:
        return
    computed = spec.aggregate_hash(list(spec.iter_paths(corpus_case["event"])))
    assert computed == expect["aggregate_hash"]
    assert spec.is_sha256_hex(computed)


def test_invalid_cases_declare_errors(corpus_case: dict):
    expect = corpus_case["expect"]
    if not expect["valid"]:
        assert expect.get("errors"), "invalid case must declare expected errors"


def test_label_grammar(corpus_case: dict):
    expect = corpus_case["expect"]
    label = expect.get("label")
    if label is None:
        return
    assert len(label) <= 63, "DNS label max length"
    if label.startswith("npub1"):
        assert len(label) == 63
    elif label.startswith("v"):
        assert len(label) == 51 and spec._B36_50.fullmatch(label[1:])
    else:
        assert spec._NAMED_LABEL.fullmatch(label) and not label.endswith("-")


def test_named_snapshot_labels_roundtrip(corpus_case: dict):
    expect = corpus_case["expect"]
    label = expect.get("label")
    site_type = expect.get("site_type")
    if site_type == "named":
        decoded = spec.b36_decode_50(label[:50])
        assert corpus_case["event"]["pubkey"] == decoded
        assert label[50:] == expect["d"]
    elif site_type == "snapshot":
        assert label == spec.snapshot_label(corpus_case["event"]["id"])
