#!/usr/bin/env python3
"""Minimal NIP-01 relay used as the Phase 0 spike's local manifest source.

Seeds events from one or more directories (files that are either bare NIP-01
events or corpus records with an ``event`` key) and then behaves like a plain
public relay: EVENT publish, REQ replay + live delivery, CLOSE, EOSE. Filter
matching covers ``kinds``, ``authors``, ``ids`` and ``#tag`` which is what the
upstream gateway's resolver and BUD-03 lookups use.

Not a production relay: single process, in-memory, no auth, no persistence.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import websockets


class FakeRelay:
    def __init__(self, seed_dirs: list[Path]):
        self.events: dict[str, dict] = {}
        # subid -> (queue, filters)
        self.subs: dict[str, tuple[asyncio.Queue, list[dict]]] = {}
        for d in seed_dirs:
            for f in sorted(d.glob("*.json")):
                try:
                    data = json.loads(f.read_text())
                except (ValueError, OSError):
                    continue
                event = (
                    data.get("event")
                    if isinstance(data, dict) and "event" in data
                    else data
                )
                if (
                    isinstance(event, dict)
                    and event.get("id")
                    and isinstance(event.get("tags"), list)
                ):
                    self.events[event["id"]] = event
        self.seed_count = len(self.events)

    @staticmethod
    def _matches(event: dict, filt: dict) -> bool:
        if "kinds" in filt and filt["kinds"] and event.get("kind") not in filt["kinds"]:
            return False
        if (
            "authors" in filt
            and filt["authors"]
            and event.get("pubkey") not in filt["authors"]
        ):
            return False
        if "ids" in filt and filt["ids"] and event.get("id") not in filt["ids"]:
            return False
        for key, values in filt.items():
            if not (key.startswith("#") and isinstance(values, list)):
                continue
            tag = key[1:]
            got = {
                t[1]
                for t in event.get("tags", [])
                if isinstance(t, list) and len(t) > 1 and t[0] == tag
            }
            if not values or not (got & set(values)):
                return False
        return True

    async def _send_replay(self, ws, subid: str, filters: list[dict]) -> None:
        matched = [
            e for e in self.events.values() if any(self._matches(e, f) for f in filters)
        ]
        for event in sorted(matched, key=lambda e: e.get("created_at", 0)):
            await ws.send(json.dumps(["EVENT", subid, event]))
        await ws.send(json.dumps(["EOSE", subid]))

    async def handler(self, ws) -> None:
        my_subs: set[str] = set()
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(msg, list) or not msg:
                    continue
                op = msg[0]
                if op == "EVENT" and len(msg) >= 2 and isinstance(msg[1], dict):
                    event = msg[1]
                    self.events[event["id"]] = event
                    await ws.send(json.dumps(["OK", event["id"], True, ""]))
                    for subid, (queue, filters) in list(self.subs.items()):
                        if any(self._matches(event, f) for f in filters):
                            try:
                                await queue.put(event)
                            except Exception:
                                pass
                elif op == "REQ" and len(msg) >= 2:
                    subid = msg[1]
                    filters = [f for f in msg[2:] if isinstance(f, dict)]
                    queue: asyncio.Queue = asyncio.Queue()
                    self.subs[subid] = (queue, filters)
                    my_subs.add(subid)
                    await self._send_replay(ws, subid, filters)
                elif op == "CLOSE" and len(msg) >= 2:
                    self.subs.pop(msg[1], None)
                    my_subs.discard(msg[1])
        finally:
            for subid in my_subs:
                self.subs.pop(subid, None)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7777)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--seed", action="append", default=[])
    args = ap.parse_args()

    relay = FakeRelay([Path(d) for d in args.seed])
    print(
        f"[fake-relay] seeded {relay.seed_count} events from {args.seed or '(none)'}",
        flush=True,
    )
    async with websockets.serve(relay.handler, args.host, args.port):
        print(f"[fake-relay] listening on ws://{args.host}:{args.port}", flush=True)
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
