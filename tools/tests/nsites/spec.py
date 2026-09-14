"""Pure NIP-5A spec helpers shared by the corpus generator and the parent-repo
sanity test.

Kept dependency-free (stdlib only) so the corpus sanity test can run in the
`apt.yml` tools/tests CI job, which does not install `nostr-sdk`. The fork's
`yunohost.nsites.manifest` re-implements this API independently; the conformance
corpus and the fork tests are what force the two implementations to agree.

Pinned revision: `nostr-protocol/nips@5d6b4322` (`5A.md`, 2026-06-16).
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterator

# Stable reason codes referenced by corpus `expect.errors` and returned by the
# validator. Generator and validator must agree on these strings.
ERROR_CODES = frozenset(
    {
        "bad_kind",
        "missing_d",
        "bad_d",
        "d_on_root",
        "no_paths",
        "bad_path_shape",
        "relative_path",
        "no_extension",
        "bad_path_chars",
        "duplicate_path",
        "bad_hash_hex",
        "oversize_path_count",
        "bad_x_shape",
        "missing_aggregate_x",
        "multiple_aggregate_x",
        "bad_aggregate_x",
        "bad_a_shape",
        "bad_A_shape",
        "missing_a",
        "missing_A",
        "multiple_a",
        "multiple_A",
        "forbidden_signer",
        "bad_id",
        "bad_signature",
        "not_json",
    }
)

KIND_ROOT = 15128
KIND_NAMED = 35128
KIND_SNAPSHOT = 5128

BASE36_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
_B36_50 = re.compile(r"^[0-9a-z]{50}$")
_NAMED_LABEL = re.compile(r"^[0-9a-z]{50}[a-z0-9-]{1,13}$")
_D_RULE = re.compile(r"^[a-z0-9-]{1,13}$")
_REF = re.compile(r"^\d+:([0-9a-f]{64}):([a-zA-Z0-9_\-]*)$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def aggregate_hash(paths: list[tuple[str, str]]) -> str:
    """Aggregate hash of a manifest's `path` tags (NIP-5A "Aggregate Hash").

    ``paths`` is a list of ``(path, hash)`` tuples in tag order. Each produces
    a line ``<hash> <path>\\n``; lines are sorted ascending lexicographically,
    concatenated as UTF-8, and SHA-256 hashed.
    """
    lines = [f"{h} {p}\n" for p, h in paths]
    lines.sort()
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def b36_encode_32(bytes32_hex: str) -> str:
    """32-byte value (64 hex chars) to exactly 50 lowercase base36 chars.

    Any 32-byte value is >= 36**49, so 50 digits always fit without padding;
    ``zfill(50)`` is belt-and-braces for values that decode to leading zeros.
    """
    n = int.from_bytes(bytes.fromhex(bytes32_hex), "big")
    if n == 0:
        return "0" * 50
    out = ""
    while n:
        n, rem = divmod(n, 36)
        out = BASE36_ALPHABET[rem] + out
    return out.zfill(50)


def b36_decode_50(label50: str) -> str:
    """Exactly-50-char lowercase base36 back to 64-char hex (32 bytes)."""
    n = 0
    for ch in label50:
        n = n * 36 + BASE36_ALPHABET.index(ch)
    return n.to_bytes(32, "big").hex()


def is_sha256_hex(value: str) -> bool:
    return bool(_SHA256.fullmatch(value))


def is_valid_d(d: str) -> bool:
    return bool(_D_RULE.fullmatch(d)) and not d.endswith("-")


def is_valid_ref(value: str) -> bool:
    return bool(_REF.fullmatch(value))


def _paths_from_tags(tags: list[list[str]]) -> list[tuple[str, str]]:
    return [(t[1], t[2]) for t in tags if len(t) >= 3 and t[0] == "path"]


def root_label(npub: str) -> str:
    return npub


def named_label(pubkey_hex: str, d: str) -> str:
    return b36_encode_32(pubkey_hex) + d


def snapshot_label(event_id_hex: str) -> str:
    return "v" + b36_encode_32(event_id_hex)


def canonical_site_url(label: str, gateway_domain: str) -> str:
    return f"{label}.{gateway_domain}"


def iter_paths(event: dict) -> Iterator[tuple[str, str]]:
    for t in event.get("tags") or []:
        if len(t) >= 3 and t[0] == "path":
            yield t[1], t[2]
