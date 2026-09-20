#!/usr/bin/env python3
"""NostrHost event-protocol reference validation and conformance runner.

Thin wrapper over the ``nostrhost-protocol`` library (formerly the reference
implementation of authority/event-protocol/envelope.md). The authoritative spec
and conformance corpus now live in ``libs/nostrhost-protocol/spec``; this
tool exists to keep the umbrella's authority CI check wired the same way.

Commands::

    event_protocol.py conformance [--json]
    event_protocol.py verdicts
    event_protocol.py fold <fixture-id>
    event_protocol.py sync-mirror
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from nostrhost_protocol.conformance import conformance, load_folds, load_verdicts
from nostrhost_protocol.fold import fold
from nostrhost_protocol.schemas import fixtures_dir, spec_root

_ROOT = Path(__file__).resolve().parents[1]


def run_verdicts() -> list[dict]:
    return conformance("python")["verdicts"]


def run_folds() -> list[dict]:
    return conformance("python")["folds"]


def sync_mirror() -> list[str]:
    """Copy canonical fixtures into the Go module's testdata mirror."""
    canonical = fixtures_dir()
    mirror = _ROOT / "libs/nostrhost-protocol/go/testdata"
    mirror.mkdir(parents=True, exist_ok=True)
    changed = []
    for name in ("verdicts.json", "folds.json"):
        source = canonical / name
        target = mirror / name
        if not target.exists() or target.read_bytes() != source.read_bytes():
            shutil.copyfile(source, target)
            changed.append(name)
    # The Python binding bundles a mirror too.
    py_mirror = _ROOT / "libs/nostrhost-protocol/python/src/nostrhost_protocol/spec/fixtures"
    py_mirror.mkdir(parents=True, exist_ok=True)
    for name in ("verdicts.json", "folds.json"):
        source = canonical / name
        target = py_mirror / name
        if not target.exists() or target.read_bytes() != source.read_bytes():
            shutil.copyfile(source, target)
            changed.append(f"python/{name}")
    return changed


def _cmd_conformance(as_json: bool) -> int:
    result = conformance("python")
    verdicts, folds, problems = result["verdicts"], result["folds"], result["problems"]
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for problem in problems:
            print(f"MISMATCH: {problem}", file=sys.stderr)
        print(
            f"conformance: {len(verdicts)} verdict(s), {len(folds)} fold(s), "
            f"{len(problems)} problem(s)"
        )
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("conformance", "verdicts", "fold", "sync-mirror")
    )
    parser.add_argument("fixture_id", nargs="?")
    parser.add_argument("--root", type=Path, default=_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "sync-mirror":
        changed = sync_mirror()
        print(f"synced {len(changed)} file(s): {', '.join(changed) or 'already current'}")
        return 0
    if args.command == "conformance":
        return _cmd_conformance(args.json)
    if args.command == "verdicts":
        print(json.dumps(run_verdicts(), indent=2, sort_keys=True))
        return 0
    for fixture in load_folds():
        if args.fixture_id in (None, fixture["id"]):
            print(
                json.dumps(
                    {"id": fixture["id"], **fold(int(fixture["kind"]), fixture["events"]).as_dict()},
                    indent=2,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())