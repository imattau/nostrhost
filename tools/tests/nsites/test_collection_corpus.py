#!/usr/bin/env python3
"""Structural sanity gate for the curated-nsite collection corpus.

Runs in the parent-repo ``apt.yml`` ``tools/tests`` CI job, which has no
``nostr-sdk``; signature/id verification is exercised by the fork's
``tests_nostr/test_nsites_collections.py`` instead. This test keeps the corpus
self-consistent: schema, reason-code membership and coordinate/ref grammar.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collection_spec as spec  # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parent / "collection-corpus"
NIP01_FIELDS = {"id", "pubkey", "created_at", "kind", "tags", "content", "sig"}


def _corpus_files() -> list[Path]:
    if not CORPUS_DIR.is_dir():
        return []
    return sorted(CORPUS_DIR.glob("*.json"))


pytestmark = pytest.mark.skipif(
    not CORPUS_DIR.is_dir(),
    reason="collection corpus not present",
)


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
        assert code in spec.COLLECTION_ERROR_CODES, f"unknown reason code {code!r}"


def test_event_is_well_formed(corpus_case: dict):
    ev = corpus_case["event"]
    assert isinstance(ev, dict)
    assert NIP01_FIELDS <= set(ev)
    assert isinstance(ev["kind"], int)
    assert isinstance(ev["tags"], list)
    assert isinstance(ev["content"], str)
    assert len(ev["id"]) == 64 and len(ev["pubkey"]) == 64 and len(ev["sig"]) == 128


def test_invalid_cases_declare_errors(corpus_case: dict):
    expect = corpus_case["expect"]
    if not expect["valid"]:
        assert expect.get("errors"), "invalid case must declare expected errors"


def test_valid_cases_are_30004_with_t_marker(corpus_case: dict):
    expect = corpus_case["expect"]
    ev = corpus_case["event"]
    if expect["valid"]:
        assert ev["kind"] == spec.COLLECTION_KIND
        tags = {t[0]: t[1] for t in ev["tags"] if len(t) >= 2}
        assert tags.get("d") == expect["d"]
        assert "nsite" in [t[1] for t in ev["tags"] if t and t[0] == "t"]
        if "coordinate" in expect:
            assert expect["coordinate"] == spec.coordinate(
                spec.COLLECTION_KIND, ev["pubkey"], expect["d"]
            )


def test_entry_grammar(corpus_case: dict):
    if not corpus_case["expect"]["valid"]:
        return  # invalid cases intentionally carry malformed refs
    ev = corpus_case["event"]
    for t in spec.entry_refs(ev):
        assert t[0] in ("a", "e")
        if t[0] == "a":
            assert spec.is_valid_site_coordinate(t[1])
        else:
            assert spec.is_sha256_hex(t[1])
        if len(t) > 2:
            assert t[2].startswith(("wss://", "ws://"))