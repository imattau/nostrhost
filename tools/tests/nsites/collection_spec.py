"""Pure helpers for the curated-nsite collection corpus (kind 30004).

Dependency-free (stdlib only) so the corpus sanity test can run in the
``apt.yml`` tools/tests CI job without ``nostr-sdk``. The fork's
``yunohost.nsites.collections`` re-implements this API independently; the
corpus and the fork tests force the two to agree. See ``NSITES-CURATED-LISTS.md``
for the wire profile.
"""

from __future__ import annotations

import hashlib
import re

# Stable reason codes shared with the collection validator.
COLLECTION_ERROR_CODES = frozenset(
    {
        "not_json",
        "bad_kind",
        "bad_id",
        "bad_signature",
        "forbidden_signer",
        "missing_d",
        "bad_d",
        "missing_t",
        "bad_title",
        "bad_description",
        "multiple_image",
        "bad_image",
        "bad_entry_shape",
        "bad_a_shape",
        "bad_e_shape",
        "bad_relay",
        "duplicate_entry",
        "oversize_entry_count",
    }
)

COLLECTION_KIND = 30004
MAX_ENTRIES = 100
MAX_D = 64

_D_RULE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_COORD = re.compile(r"^(15128|35128):([0-9a-f]{64}):([a-zA-Z0-9_-]*)$")
_COLLECTION_COORD = re.compile(r"^30004:([0-9a-f]{64}):([a-zA-Z0-9_-]*)$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def is_valid_d(d: str) -> bool:
    return bool(_D_RULE.fullmatch(d))


def is_valid_coordinate(value: str) -> bool:
    return bool(_COLLECTION_COORD.fullmatch(value))


def is_valid_site_coordinate(value: str) -> bool:
    return bool(_COORD.fullmatch(value))


def is_sha256_hex(value: str) -> bool:
    return bool(_SHA256.fullmatch(value))


def coordinate(kind: int, pubkey: str, d: str = "") -> str:
    return f"{kind}:{pubkey}:{d}"


def entry_refs(event: dict) -> list[list[str]]:
    """Ordered entry tags (a/e) of one collection event, as full tag arrays."""
    out: list[list[str]] = []
    for t in event.get("tags") or []:
        if len(t) >= 1 and t[0] in ("a", "e"):
            out.append(t)
    return out


def collection_plan_digest(
    *,
    pubkey: str,
    d: str,
    title: str,
    description: str,
    image: str,
    entries: list[list[str]],
    relays: list[str],
) -> str:
    import json

    values = [pubkey, d, title, description, image, entries, sorted(set(relays))]
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode("utf-8")).hexdigest()