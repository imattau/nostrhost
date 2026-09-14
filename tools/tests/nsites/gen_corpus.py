#!/usr/bin/env python3
"""Deterministic generator for the NIP-5A conformance corpus.

Writes signed NIP-01 events plus expected verdicts into ``corpus/*.json``
relative to this file. Requires ``nostr-sdk`` (for signing and the npub
label). Re-running regenerates the corpus with the same event ids (the id is
computed over the unsigned fields); Schnorr signatures may differ run to run
but verification is what matters, not byte equality.

Run: uv run --with nostr-sdk python tools/tests/nsites/gen_corpus.py
     (or: python tools/tests/nsites/gen_corpus.py with nostr-sdk installed)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nostr_sdk import EventBuilder, Keys, Kind, Tag, Timestamp  # noqa: E402

import spec  # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"

# Deterministic test identity (matches the frozen interop test key).
TEST_SK = "3f4f6b8d" * 8
TEST_PUBKEY = Keys.parse(TEST_SK).public_key().to_hex()
TEST_NPUB = Keys.parse(TEST_SK).public_key().to_bech32()

# A separate identity that plays the "host / operator" key role.
HOST_SK = "deadbeef" * 8
HOST_PUBKEY = Keys.parse(HOST_SK).public_key().to_hex()

# A third-party pubkey used as the origin of copied sites (from the NIP-5A
# examples, so references in the spec text match the corpus).
ORIGIN_PUBKEY = "266815e0c9210dfa324c6cba3573b14bee49da4209a9456f9484e5106cd408a5"

FIXED_CREATED_AT = 1750000000

INDEX_H = "186ea5fd14e88fd1ac49351759e7ab906fa94892002b60bf7f5a428f28ca1c99"
ABOUT_H = "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
POST_H = "deadbeef" * 8
FAVICON_H = "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321"


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


def paths(tags: list[list[str]]) -> list[tuple[str, str]]:
    return [(t[1], t[2]) for t in tags if len(t) >= 3 and t[0] == "path"]


def agg(tags: list[list[str]]) -> str:
    return spec.aggregate_hash(paths(tags))


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
    # --- valid: root -----------------------------------------------------
    root_tags = [
        ["path", "/index.html", INDEX_H],
        ["path", "/about.html", ABOUT_H],
        ["x", agg([]), "aggregate"],
        ["server", "https://blossom.example.com"],
        ["title", "Conformance Root Site"],
        ["description", "Valid root nsite for the conformance corpus"],
        ["source", "https://github.com/example/my-nostr-site"],
    ]
    root_tags[2] = ["x", agg(root_tags), "aggregate"]
    root = sign(TEST_SK, spec.KIND_ROOT, root_tags)
    emit(
        "valid-root",
        root,
        {
            "valid": True,
            "site_type": "root",
            "aggregate_hash": agg(root_tags),
            "label": spec.root_label(TEST_NPUB),
            "canonical_url": spec.canonical_site_url(
                spec.root_label(TEST_NPUB), "sites.example.org"
            ),
        },
        "Kind 15128 root site with two paths, aggregate x tag, server hint and metadata.",
    )

    # --- valid: named ----------------------------------------------------
    named_tags = [
        ["d", "blog"],
        ["path", "/index.html", INDEX_H],
        ["path", "/post.html", POST_H],
        ["x", agg([]), "aggregate"],
        ["server", "https://blossom.example.com"],
        ["title", "Conformance Blog"],
        ["description", "Valid named nsite"],
    ]
    named_tags[3] = ["x", agg(named_tags), "aggregate"]
    named = sign(TEST_SK, spec.KIND_NAMED, named_tags)
    emit(
        "valid-named",
        named,
        {
            "valid": True,
            "site_type": "named",
            "d": "blog",
            "aggregate_hash": agg(named_tags),
            "label": spec.named_label(TEST_PUBKEY, "blog"),
        },
        "Kind 35128 named site with a canonical d tag.",
    )

    # --- valid: snapshot -------------------------------------------------
    snap_paths = [["path", "/index.html", INDEX_H], ["path", "/post.html", POST_H]]
    snap_tags = [
        ["a", f"{spec.KIND_NAMED}:{TEST_PUBKEY}:blog"],
        ["path", "/index.html", INDEX_H],
        ["path", "/post.html", POST_H],
        ["x", agg(snap_paths), "aggregate"],
        ["title", "Conformance Blog v1"],
    ]
    snapshot = sign(TEST_SK, spec.KIND_SNAPSHOT, snap_tags)
    emit(
        "valid-snapshot",
        snapshot,
        {
            "valid": True,
            "site_type": "snapshot",
            "aggregate_hash": agg(snap_tags),
            "label": spec.snapshot_label(snapshot["id"]),
        },
        "Kind 5128 snapshot capturing a named site; a and x tags as required.",
    )

    # --- valid: copied ---------------------------------------------------
    copied_tags = [
        ["d", "blog"],
        ["a", f"{spec.KIND_NAMED}:{ORIGIN_PUBKEY}:blog"],
        ["A", f"{spec.KIND_NAMED}:{ORIGIN_PUBKEY}:blog"],
        ["path", "/index.html", INDEX_H],
        ["path", "/post.html", POST_H],
        ["x", agg([]), "aggregate"],
        ["title", "Conformance Copied Blog"],
    ]
    copied_tags[5] = ["x", agg(copied_tags), "aggregate"]
    copied = sign(TEST_SK, spec.KIND_NAMED, copied_tags)
    emit(
        "valid-copied",
        copied,
        {
            "valid": True,
            "site_type": "named",
            "d": "blog",
            "aggregate_hash": agg(copied_tags),
            "label": spec.named_label(TEST_PUBKEY, "blog"),
        },
        "Copied named site with a/A lineage tags.",
    )

    # --- invalid: bad d --------------------------------------------------
    bad_d_tags = [["d", "Blog!"], ["path", "/index.html", INDEX_H]]
    emit(
        "invalid-bad-d",
        sign(TEST_SK, spec.KIND_NAMED, bad_d_tags),
        {"valid": False, "errors": ["bad_d"]},
        "Named site whose d tag violates ^[a-z0-9-]{1,13}$.",
    )

    # --- invalid: d on root ----------------------------------------------
    emit(
        "invalid-d-on-root",
        sign(
            TEST_SK, spec.KIND_ROOT, [["d", "blog"], ["path", "/index.html", INDEX_H]]
        ),
        {"valid": False, "errors": ["d_on_root"]},
        "Kind 15128 root site MUST NOT carry a d tag.",
    )

    # --- invalid: missing d ----------------------------------------------
    emit(
        "invalid-missing-d",
        sign(TEST_SK, spec.KIND_NAMED, [["path", "/index.html", INDEX_H]]),
        {"valid": False, "errors": ["missing_d"]},
        "Kind 35128 named site MUST include a d tag.",
    )

    # --- invalid: duplicate path -----------------------------------------
    emit(
        "invalid-duplicate-path",
        sign(
            TEST_SK,
            spec.KIND_ROOT,
            [["path", "/index.html", INDEX_H], ["path", "/index.html", ABOUT_H]],
        ),
        {"valid": False, "errors": ["duplicate_path"]},
        "Two path tags mapping the same absolute path.",
    )

    # --- invalid: non-hex hash -------------------------------------------
    emit(
        "invalid-non-hex-hash",
        sign(TEST_SK, spec.KIND_ROOT, [["path", "/index.html", "z" * 64]]),
        {"valid": False, "errors": ["bad_hash_hex"]},
        "path tag hash is not lowercase hex.",
    )

    # --- invalid: relative path ------------------------------------------
    emit(
        "invalid-relative-path",
        sign(TEST_SK, spec.KIND_ROOT, [["path", "index.html", INDEX_H]]),
        {"valid": False, "errors": ["relative_path"]},
        "path tag does not begin with a leading slash.",
    )

    # --- invalid: no extension -------------------------------------------
    emit(
        "invalid-no-extension",
        sign(TEST_SK, spec.KIND_ROOT, [["path", "/index", INDEX_H]]),
        {"valid": False, "errors": ["no_extension"]},
        "Absolute path must end with a filename and extension.",
    )

    # --- invalid: dot-dot path -------------------------------------------
    emit(
        "invalid-dotdot-path",
        sign(TEST_SK, spec.KIND_ROOT, [["path", "/../index.html", INDEX_H]]),
        {"valid": False, "errors": ["bad_path_chars"]},
        "path contains a .. segment.",
    )

    # --- invalid: dot-dot substring --------------------------------------
    emit(
        "invalid-dotdot-substring",
        sign(TEST_SK, spec.KIND_ROOT, [["path", "/dir..0/index.html", INDEX_H]]),
        {"valid": False, "errors": ["bad_path_chars"]},
        "path segment contains '..' as a substring (defence in depth).",
    )

    # --- invalid: oversize path count ------------------------------------
    many_tags = [
        [f"/file{i:05d}.html", hashlib.sha256(f"{i}".encode()).hexdigest()]
        for i in range(6)
    ]
    oversize = [["path", p, h] for p, h in many_tags]
    emit(
        "invalid-oversize-path-count",
        sign(TEST_SK, spec.KIND_ROOT, oversize),
        {"valid": False, "errors": ["oversize_path_count"], "max_paths": 5},
        "More path tags than the validator's max_paths (5 in this fixture).",
    )

    # --- invalid: wrong aggregate x --------------------------------------
    wrong_x_tags = [
        ["path", "/index.html", INDEX_H],
        ["path", "/about.html", ABOUT_H],
        ["x", "0" * 64, "aggregate"],
    ]
    emit(
        "invalid-wrong-aggregate",
        sign(TEST_SK, spec.KIND_ROOT, wrong_x_tags),
        {"valid": False, "errors": ["bad_aggregate_x"]},
        "x tag present but does not match the computed aggregate hash.",
    )

    # --- invalid: bad signature ------------------------------------------
    bad_sig = sign(TEST_SK, spec.KIND_ROOT, [["path", "/index.html", INDEX_H]])
    bad_sig["sig"] = ("0" if bad_sig["sig"][0] != "0" else "1") + bad_sig["sig"][1:]
    emit(
        "invalid-bad-signature",
        bad_sig,
        {"valid": False, "errors": ["bad_signature"]},
        "Signature does not verify against the event fields.",
    )

    # --- invalid: bad id -------------------------------------------------
    bad_id = sign(TEST_SK, spec.KIND_ROOT, [["path", "/index.html", INDEX_H]])
    bad_id["content"] = "tampered-after-signing"
    emit(
        "invalid-bad-id",
        bad_id,
        {"valid": False, "errors": ["bad_id"]},
        "Event id no longer matches the (tampered) serialized fields.",
    )

    # --- invalid: forbidden signer ---------------------------------------
    emit(
        "invalid-forbidden-signer",
        sign(HOST_SK, spec.KIND_ROOT, [["path", "/index.html", INDEX_H]]),
        {"valid": False, "errors": ["forbidden_signer"]},
        "Manifest signed by a pubkey the validator treats as a host key.",
    )

    # --- invalid: snapshot without a tag ---------------------------------
    snap_no_a = [
        ["path", "/index.html", INDEX_H],
        ["x", agg([["path", "/index.html", INDEX_H]]), "aggregate"],
    ]
    emit(
        "invalid-snapshot-missing-a",
        sign(TEST_SK, spec.KIND_SNAPSHOT, snap_no_a),
        {"valid": False, "errors": ["missing_a"]},
        "Kind 5128 snapshot MUST include exactly one a tag.",
    )

    # --- invalid: snapshot without x -------------------------------------
    snap_no_x = [
        ["a", f"{spec.KIND_NAMED}:{TEST_PUBKEY}:blog"],
        ["path", "/index.html", INDEX_H],
    ]
    emit(
        "invalid-snapshot-missing-x",
        sign(TEST_SK, spec.KIND_SNAPSHOT, snap_no_x),
        {"valid": False, "errors": ["missing_aggregate_x"]},
        "Kind 5128 snapshot MUST include exactly one x aggregate tag.",
    )

    # --- invalid: no paths -----------------------------------------------
    emit(
        "invalid-no-paths",
        sign(TEST_SK, spec.KIND_ROOT, [["title", "empty"]]),
        {"valid": False, "errors": ["no_paths"]},
        "Manifest MUST include one or more path tags.",
    )


if __name__ == "__main__":
    build()
    print(f"wrote {len(list(CORPUS_DIR.glob('*.json')))} corpus files to {CORPUS_DIR}")
