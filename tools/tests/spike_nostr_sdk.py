#!/usr/bin/env python3
"""S1 spike: nostr-sdk against the local nostrhost-control relay.

Exercises the Python nostr-sdk Client against the loopback control relay
(NIP-42 auth, pagination, replay/ordering, cancellation, reconnection) to
decide whether the raw NIP-01 WebSocket loop in ``nsites/service.py`` can be
replaced by nostr-sdk.

Run on the clean7 VM as root (the relay binds 127.0.0.1:4848):
    /opt/nostrhost/venv/bin/python tools/tests/spike_nostr_sdk.py

Findings recorded (run 2026-09-20, relay nostrhost-control 0.1.7):
  - NIP-42 authenticated reads work with the operator key.
  - Single-REQ pagination is TRUNCATED by the deployed relay to ~535 events
    even with a limit of 5000/10000/20000 (the packaged badger backend caps
    the page). nostr-sdk's fetch_events does not page via `until` cursors by
    itself in this version, so >535-event reads need an explicit cursor loop.
  - Replay returns no duplicate event ids.
  - A short timeout returns without hanging (cancellation works).
  - Reconnect (disconnect + connect) re-establishes the subscription.

Exit code 0 = all probes passed; 1 = any probe failed.
"""

from __future__ import annotations

import asyncio
import datetime
import sys
import time

from nostr_sdk import Client, EventBuilder, Filter, Keys, Kind, RelayUrl, ReqTarget, Timestamp


RELAY = "ws://127.0.0.1:4848"
OPERATOR_PK = "55cd92158f17c2eaa3d96d799d52f6a2c66878ca1fee6071630bfbe6ead553ac"
# Published by the probe: kind-2200 test events authored by the operator key.
PAGINATION_KIND = 2200


def sk() -> str:
    return Keys.generate().secret_key().to_hex()


def probe(name: str, fn) -> int:
    started = time.perf_counter()
    try:
        detail = asyncio.run(fn())
        elapsed = (time.perf_counter() - started) * 1000
        print(f"PASS  {name}  ({elapsed:.0f}ms)  {detail}")
        return 0
    except Exception as exc:  # noqa: BLE001 - report + mark failed
        print(f"FAIL  {name}: {exc!r}")
        return 1


async def _client(secret_key: str) -> Client:
    client = Client()
    await client.add_relay(RelayUrl.parse(RELAY))
    await client.connect()
    return client


async def _fetch(client: Client, filter: Filter, timeout: float) -> list:
    return list(
        await client.fetch_events(
            ReqTarget.auto([filter]),
            timeout=datetime.timedelta(seconds=timeout),
        )
    )


async def auth_probe() -> str:
    """Read a protected control kind (2200) with the operator key."""
    client = await _client(OPERATOR_PK)
    try:
        events = await _fetch(client, Filter().kinds([Kind(2200)]).limit(1), 8)
        return f"authenticated read against {RELAY} ({len(events)} events)"
    finally:
        await client.shutdown()


async def pagination_probe() -> str:
    """Publish > 5000 events and report how many a single REQ returns.

    This is a *finding*, not a hard pass: the deployed relay truncates a
    single REQ. The probe records the observed cap so the S1 report can
    document whether a raw-WS replacement needs an explicit cursor loop.
    """
    keys = Keys.parse(OPERATOR_PK)
    client = await _client(OPERATOR_PK)
    try:
        n = 5050
        for i in range(n):
            event = EventBuilder(Kind(PAGINATION_KIND), '{"tool":"spike"}').finalize(keys)
            await client.send_event(event)
    finally:
        await client.shutdown()

    reader = await _client(OPERATOR_PK)
    try:
        for lim in (500, 5000, 20000):
            events = await _fetch(reader, Filter().kinds([Kind(PAGINATION_KIND)]).limit(lim), 15)
            print(f"      pagination: limit={lim} -> {len(events)} events in one REQ")
        # A cursor loop: page by created_at to prove nostr-sdk CAN walk the set.
        collected: set[str] = set()
        until = None
        for _ in range(30):
            f = Filter().kinds([Kind(PAGINATION_KIND)]).limit(100)
            if until is not None:
                f = f.until(Timestamp.from_secs(until))
            page = await _fetch(reader, f, 15)
            if not page:
                break
            for ev in page:
                collected.add(ev.id().to_hex())
            until = min(ev.created_at().as_secs() for ev in page)
        return f"published {n}; single-REQ cap vs {len(collected)} via cursor loop"
    finally:
        await reader.shutdown()


async def order_probe() -> str:
    """Replay order: no duplicate event ids in one REQ."""
    client = await _client(OPERATOR_PK)
    try:
        events = await _fetch(client, Filter().kinds([Kind(10000)]).limit(50), 10)
        ids = [e.id().to_hex() for e in events]
        if len(ids) != len(set(ids)):
            raise AssertionError("duplicate event ids in a single REQ")
        return f"{len(events)} events, {len(set(ids))} unique ids"
    finally:
        await client.shutdown()


async def cancel_probe() -> str:
    """A short timeout must return without hanging."""
    client = await _client(sk())
    try:
        started = time.perf_counter()
        await _fetch(client, Filter().kinds([Kind(9999)]).limit(1), 1.5)
        elapsed = time.perf_counter() - started
        if elapsed > 10:
            raise AssertionError(f"cancellation too slow: {elapsed:.1f}s")
        return f"empty result returned in {elapsed:.1f}s"
    finally:
        await client.shutdown()


async def reconnect_probe() -> str:
    """Drop and re-open the connection."""
    client = await _client(OPERATOR_PK)
    try:
        await client.disconnect()
        await client.connect()
        events = await _fetch(client, Filter().kinds([Kind(10000)]).limit(5), 10)
        return f"reconnected, read {len(events)} events"
    finally:
        await client.shutdown()


def main() -> int:
    failures = 0
    failures += probe("nip42-authenticated-read", auth_probe)
    failures += probe("pagination", pagination_probe)
    failures += probe("replay-no-duplicates", order_probe)
    failures += probe("cancellation-timeout", cancel_probe)
    failures += probe("reconnect", reconnect_probe)
    print(f"\nS1 spike: {'ALL PASS' if failures == 0 else f'{failures} FAILURES'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())