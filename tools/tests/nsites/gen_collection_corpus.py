#!/usr/bin/env python3
"""Deterministic generator for the curated-nsite collection corpus (kind 30004).

Writes signed NIP-01 events plus expected verdicts into ``collection-corpus/``
relative to this file. Requires ``nostr-sdk`` for signing. Re-running
regenerates the corpus with the same event ids (the id is computed over the
unsigned fields); Schnorr signatures may differ run to run but verification is
what matters, not byte equality.

Run: uv run --with nostr-sdk python tools/tests/nsites/gen_collection_corpus.py
     (or: python tools/tests/nsites/gen_collection_corpus.py with nostr-sdk)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nostr_sdk import EventBuilder, Keys, Kind, Tag, Timestamp  # noqa: E402

import collection_spec as spec  # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parent / "collection-corpus"

# Deterministic test identity (matches the NIP-5A corpus test key).
TEST_SK = "3f4f6b8d" * 8
TEST_PUBKEY = Keys.parse(TEST_SK).public_key().to_hex()

# A separate identity that plays the "host / operator" key role.
HOST_SK = "deadbeef" * 8
HOST_PUBKEY = Keys.parse(HOST_SK).public_key().to_hex()

# A third-party pubkey for live-site entry coordinates.
SITE_PUBKEY = "266815e0c9210dfa324c6cba3573b14bee49da4209a9456f9484e5106cd408a5"

# A 64-hex event id used as a pinned snapshot reference.
SNAP_EVENT_ID = "5c8ed07b8c33b5d1e2d1c1dcec4d1d1a1e1f1a1b1c1d1e1f2021222324252627"

FIXED_CREATED_AT = 1750000100


def sign(
    sk: str,
    kind: int,
    tags: list[list[str]],
    content: str = "",
    created_at: int = FIXED_CREATED_AT,
) -> dict:
    keys = Keys.parse(sk)
    event = (
        EventBuilder(Kind(kind), content)
        .tags([Tag.parse(t) for t in tags])
        .custom_created_at(Timestamp.from_secs(created_at))
        .finalize(keys)
    )
    return json.loads(event.as_json())


def emit(name: str, event: dict, expect: dict, description: str = "") -> None:
    payload = {
        "name": name,
        "description": description,
        "event": event,
        "expect": expect,
    }
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    (CORPUS_DIR / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n")


def build() -> None:
    base = [
        ["d", "indie-web"],
        ["title", "Small independent sites"],
        ["description", "Personal sites and experiments worth wandering through."],
        ["image", "https://cdn.example/indie-web-cover.webp"],
        ["t", "nsite"],
    ]

    # --- valid: mixed live + pinned --------------------------------------
    valid_tags = list(base)
    valid_tags += [
        ["a", f"15128:{SITE_PUBKEY}:", "wss://relay.example"],
        ["a", f"35128:{SITE_PUBKEY}:blog"],
        ["e", SNAP_EVENT_ID, "wss://relay.example"],
    ]
    emit(
        "valid-mixed",
        sign(TEST_SK, spec.COLLECTION_KIND, valid_tags),
        {
            "valid": True,
            "d": "indie-web",
            "coordinate": spec.coordinate(spec.COLLECTION_KIND, TEST_PUBKEY, "indie-web"),
            "title": "Small independent sites",
            "entries": 3,
        },
        "Kind 30004 collection with t=nsite, a live-root/a live-named/e pinned entries.",
    )

    # --- valid: minimal (no image, no relay hints) ------------------------
    emit(
        "valid-minimal",
        sign(
            TEST_SK,
            spec.COLLECTION_KIND,
            [["d", "tools"], ["title", "Nostr tools"], ["t", "nsite"], ["a", f"15128:{SITE_PUBKEY}:"]],
        ),
        {"valid": True, "d": "tools", "coordinate": spec.coordinate(spec.COLLECTION_KIND, TEST_PUBKEY, "tools")},
        "Minimal collection: d, title, t=nsite, one live root entry, no image or hints.",
    )

    # --- invalid: wrong kind ----------------------------------------------
    emit(
        "invalid-wrong-kind",
        sign(TEST_SK, 30023, [["d", "x"], ["title", "Article"], ["t", "nsite"]]),
        {"valid": False, "errors": ["bad_kind"]},
        "Kind is not 30004.",
    )

    # --- invalid: bad d ---------------------------------------------------
    emit(
        "invalid-bad-d",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "has space"], ["title", "t"], ["t", "nsite"]]),
        {"valid": False, "errors": ["bad_d"]},
        "d tag violates ^[a-zA-Z0-9_-]{1,64}$.",
    )

    # --- invalid: missing d -----------------------------------------------
    emit(
        "invalid-missing-d",
        sign(TEST_SK, spec.COLLECTION_KIND, [["title", "t"], ["t", "nsite"]]),
        {"valid": False, "errors": ["missing_d"]},
        "No d tag.",
    )

    # --- invalid: missing t marker ----------------------------------------
    emit(
        "invalid-missing-t",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["a", f"15128:{SITE_PUBKEY}:"]]),
        {"valid": False, "errors": ["missing_t"]},
        "No t=nsite marker; this is not an nsite collection.",
    )

    # --- invalid: oversize title ------------------------------------------
    emit(
        "invalid-bad-title",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t" * 121], ["t", "nsite"]]),
        {"valid": False, "errors": ["bad_title"]},
        "Title exceeds the 120-character bound.",
    )

    # --- invalid: oversize description ------------------------------------
    emit(
        "invalid-bad-description",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["description", "d" * 501], ["t", "nsite"]]),
        {"valid": False, "errors": ["bad_description"]},
        "Description exceeds the 500-character bound.",
    )

    # --- invalid: multiple images -----------------------------------------
    emit(
        "invalid-multiple-image",
        sign(
            TEST_SK,
            spec.COLLECTION_KIND,
            [
                ["d", "x"],
                ["title", "t"],
                ["t", "nsite"],
                ["image", "https://cdn.example/a.webp"],
                ["image", "https://cdn.example/b.webp"],
            ],
        ),
        {"valid": False, "errors": ["multiple_image"]},
        "More than one image tag.",
    )

    # --- invalid: non-https image -----------------------------------------
    emit(
        "invalid-bad-image",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["t", "nsite"], ["image", "http://cdn.example/a.webp"]]),
        {"valid": False, "errors": ["bad_image"]},
        "image is not an https URL.",
    )

    # --- invalid: malformed a coordinate ----------------------------------
    emit(
        "invalid-bad-a",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["t", "nsite"], ["a", "15128:not-hex:"]]),
        {"valid": False, "errors": ["bad_a_shape"]},
        "a tag coordinate has a non-hex pubkey.",
    )

    # --- invalid: malformed e reference -----------------------------------
    emit(
        "invalid-bad-e",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["t", "nsite"], ["e", "not-hex"]]),
        {"valid": False, "errors": ["bad_e_shape"]},
        "e tag reference is not a 64-hex event id.",
    )

    # --- invalid: bad relay hint ------------------------------------------
    emit(
        "invalid-bad-relay",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["t", "nsite"], ["a", f"15128:{SITE_PUBKEY}:", "http://relay.example"]]),
        {"valid": False, "errors": ["bad_relay"]},
        "Relay hint is not a ws/wss URL.",
    )

    # --- invalid: duplicate entry ------------------------------------------
    emit(
        "invalid-duplicate-entry",
        sign(
            TEST_SK,
            spec.COLLECTION_KIND,
            [
                ["d", "x"],
                ["title", "t"],
                ["t", "nsite"],
                ["a", f"15128:{SITE_PUBKEY}:"],
                ["a", f"15128:{SITE_PUBKEY}:"],
            ],
        ),
        {"valid": False, "errors": ["duplicate_entry"]},
        "Same live-site coordinate twice.",
    )

    # --- invalid: oversize entry count -------------------------------------
    many = [["a", f"15128:{SITE_PUBKEY}:"] for _ in range(6)]
    many[1][1] = f"35128:{SITE_PUBKEY}:d{0}"  # distinct refs so only the count trips
    many[2][1] = f"15128:{'a' * 64}:"
    many[3][1] = f"35128:{'a' * 64}:d1"
    many[4][1] = f"15128:{'b' * 64}:"
    many[5][1] = f"35128:{'b' * 64}:d2"
    emit(
        "invalid-oversize-entry-count",
        sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["t", "nsite"], *many]),
        {"valid": False, "errors": ["oversize_entry_count"], "max_entries": 5},
        "More entries than the validator's max_entries (5 in this fixture).",
    )

    # --- invalid: bad signature --------------------------------------------
    bad_sig = sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["t", "nsite"]])
    bad_sig["sig"] = ("0" if bad_sig["sig"][0] != "0" else "1") + bad_sig["sig"][1:]
    emit(
        "invalid-bad-signature",
        bad_sig,
        {"valid": False, "errors": ["bad_signature"]},
        "Signature does not verify against the event fields.",
    )

    # --- invalid: bad id ---------------------------------------------------
    bad_id = sign(TEST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["t", "nsite"]])
    bad_id["content"] = "tampered-after-signing"
    emit(
        "invalid-bad-id",
        bad_id,
        {"valid": False, "errors": ["bad_id"]},
        "Event id no longer matches the (tampered) serialized fields.",
    )

    # --- invalid: forbidden signer -----------------------------------------
    emit(
        "invalid-forbidden-signer",
        sign(HOST_SK, spec.COLLECTION_KIND, [["d", "x"], ["title", "t"], ["t", "nsite"]]),
        {"valid": False, "errors": ["forbidden_signer"]},
        "Collection signed by a pubkey the validator treats as a host key.",
    )


if __name__ == "__main__":
    build()
    print(f"wrote {len(list(CORPUS_DIR.glob('*.json')))} collection corpus files to {CORPUS_DIR}")