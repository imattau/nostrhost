#!/usr/bin/env python3
"""Build a real site for the Phase 0 spike and seed the local fake relay and
fake blossom.

Creates ``site/`` files, hashes them, signs NIP-5A manifests (root, named,
snapshot, private-hint) with the conformance corpus test key, writes the
manifests into ``seed/`` for the fake relay and the blobs into ``blobs/`` for
the fake blossom. When a fake relay/blossom is already listening it also
publishes over the wire (EVENT + BUD-02 PUT) so the live publish path is
exercised.

Run: python make_site.py [--relay ws://127.0.0.1:7777] [--blossom http://127.0.0.1:8787]
Requires: nostr-sdk (signing) and the parent repo's tools/tests/nsites/spec.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "tools" / "tests" / "nsites"))

from nostr_sdk import EventBuilder, Keys, Kind, Tag, Timestamp  # noqa: E402

import spec  # noqa: E402

TEST_SK = "3f4f6b8d" * 8
PRIVATE_SK = "cafebabe" * 8
# Newer than the corpus events (created_at 1750000000) so the gateway
# deterministically resolves the spike site over the seeded corpus manifests
# for the same pubkey/identifier.
FIXED_CREATED_AT = 1750002000
BLOB_SERVER = "http://127.0.0.1:8787"
RELAY = "ws://127.0.0.1:7777"


def _sign(sk: str, kind: int, tags: list[list[str]]) -> dict:
    event = (
        EventBuilder(Kind(kind), "")
        .tags([Tag.parse(t) for t in tags])
        .custom_created_at(Timestamp.from_secs(FIXED_CREATED_AT))
        .finalize(Keys.parse(sk))
    )
    return json.loads(event.as_json())


def _hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _site_files(base: Path, entries: dict[str, bytes]) -> dict[str, str]:
    """Write files, return {abs_path: sha256}."""
    hashes = {}
    for rel, body in entries.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        hashes[f"/{rel}"] = _hash(body)
    return hashes


def _agg(paths: dict[str, str]) -> str:
    return spec.aggregate_hash([(p, h) for p, h in paths.items()])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--relay", default=None, help="ws:// URL of a live fake relay to publish to"
    )
    ap.add_argument(
        "--blossom",
        default=None,
        help="http:// URL of a live fake blossom to upload to",
    )
    args = ap.parse_args()

    test_keys = Keys.parse(TEST_SK)
    test_pubkey = test_keys.public_key().to_hex()
    npub = test_keys.public_key().to_bech32()
    private_keys = Keys.parse(PRIVATE_SK)
    private_pubkey = private_keys.public_key().to_hex()

    seed = HERE / "seed"
    blobs = HERE / "blobs"
    tamper = HERE / "tamper"
    site = HERE / "site"
    seed.mkdir(parents=True, exist_ok=True)
    blobs.mkdir(parents=True, exist_ok=True)
    tamper.mkdir(parents=True, exist_ok=True)

    # --- real site files -------------------------------------------------
    root_files = _site_files(
        site,
        {
            "index.html": b"<h1>conformance root index</h1>\n<p>hello from the root nsite</p>\n",
            "about.html": b"<h1>conformance about</h1>\n",
            "style.css": b"body { color: #333; }\n",
            "404.html": b"<h1>conformance 404</h1>\n",
        },
    )
    blog_files = _site_files(
        site / "blog",
        {
            "index.html": b"<h1>conformance blog index</h1>\n",
            "post.html": b"<h1>conformance blog post</h1>\n",
        },
    )

    # --- manifests -------------------------------------------------------
    root_tags = [["path", p, h] for p, h in root_files.items()] + [
        ["x", _agg(root_files), "aggregate"],
        ["server", BLOB_SERVER],
        ["title", "Conformance Spike Root"],
        ["description", "Real site used by the Phase 0 spike"],
    ]
    root_event = _sign(TEST_SK, spec.KIND_ROOT, root_tags)

    blog_tags = [
        ["d", "blog"],
        ["path", "/index.html", blog_files["/index.html"]],
        ["path", "/post.html", blog_files["/post.html"]],
        ["x", _agg(blog_files), "aggregate"],
        ["server", BLOB_SERVER],
        ["title", "Conformance Spike Blog"],
    ]
    named_event = _sign(TEST_SK, spec.KIND_NAMED, blog_tags)

    snap_tags = [
        ["a", f"{spec.KIND_NAMED}:{test_pubkey}:blog"],
        ["path", "/index.html", blog_files["/index.html"]],
        ["path", "/post.html", blog_files["/post.html"]],
        ["x", _agg(blog_files), "aggregate"],
        ["title", "Conformance Spike Blog v1"],
    ]
    snap_event = _sign(TEST_SK, spec.KIND_SNAPSHOT, snap_tags)

    # A root site whose only server hint is an unreachable private address;
    # records whether the gateway attempts private-network fetches.
    priv_files = {"index.html": b"<h1>private hint site</h1>\n"}
    priv_tags = [
        ["path", "/index.html", _hash(priv_files["index.html"])],
        ["x", _agg({"/index.html": _hash(priv_files["index.html"])}), "aggregate"],
        ["server", "http://127.0.0.1:9"],
        ["title", "Private Hint Site"],
    ]
    priv_event = _sign(PRIVATE_SK, spec.KIND_ROOT, priv_tags)

    # --- seed relay + blobs ----------------------------------------------
    manifest_events = [root_event, named_event, snap_event, priv_event]
    for ev in manifest_events:
        (seed / f"{ev['id']}.json").write_text(json.dumps(ev) + "\n")

    def store_blob(body: bytes, mime: str) -> None:
        sha = _hash(body)
        (blobs / sha).write_bytes(body)
        (blobs / f"{sha}.type").write_text(mime)

    for rel, body in [
        (
            "/index.html",
            b"<h1>conformance root index</h1>\n<p>hello from the root nsite</p>\n",
        ),
        ("/about.html", b"<h1>conformance about</h1>\n"),
        ("/style.css", b"body { color: #333; }\n"),
        ("/404.html", b"<h1>conformance 404</h1>\n"),
    ]:
        store_blob(body, "text/html" if rel.endswith(".html") else "text/css")
    # blog index is good; blog post is tampered in the fake blossom
    store_blob(b"<h1>conformance blog index</h1>\n", "text/html")
    good_post = b"<h1>conformance blog post</h1>\n"
    store_blob(good_post, "text/html")
    (tamper / _hash(good_post)).write_bytes(b"<h1>tampered</h1>")

    # --- live publish ----------------------------------------------------
    if args.relay:
        import websockets
        import asyncio

        async def publish() -> None:
            async with websockets.connect(args.relay) as ws:
                for ev in manifest_events:
                    await ws.send(json.dumps(["EVENT", ev]))
                    ok = json.loads(await ws.recv())
                    print(f"[publish] {ev['kind']} {ev['id'][:12]} {ok}", flush=True)

        asyncio.run(publish())
    if args.blossom:
        for rel, body in [
            (
                "/index.html",
                b"<h1>conformance root index</h1>\n<p>hello from the root nsite</p>\n",
            ),
            ("/about.html", b"<h1>conformance about</h1>\n"),
            ("/style.css", b"body { color: #333; }\n"),
            ("/404.html", b"<h1>conformance 404</h1>\n"),
            ("/blog/index.html", b"<h1>conformance blog index</h1>\n"),
        ]:
            try:
                req = urllib.request.Request(
                    args.blossom + "/upload", data=body, method="PUT"
                )
                resp = json.loads(urllib.request.urlopen(req).read())
                print(f"[upload] {rel} -> {resp.get('sha256')}", flush=True)
            except (urllib.error.URLError, OSError) as exc:
                print(f"[upload] {rel} skipped: {exc}", flush=True)

    print("\n=== spike addresses ===")
    print(f"root    https://{npub}.sites.nostrhost.test/")
    print(
        f"named   https://{spec.named_label(test_pubkey, 'blog')}.sites.nostrhost.test/"
    )
    print(
        f"snap    https://{spec.snapshot_label(snap_event['id'])}.sites.nostrhost.test/"
    )
    print(f"private https://{spec.b36_encode_32(private_pubkey)}.sites.nostrhost.test/")
    print(f"root id {root_event['id']}")
    print(f"blog id {named_event['id']}")
    print(f"snap id {snap_event['id']}")
    print(f"priv id {priv_event['id']}")
    print(f"seeded {len(manifest_events)} manifests in {seed}")
    print(f"blobs in {blobs}, tampered blob sha {_hash(good_post)}")


if __name__ == "__main__":
    main()
