#!/usr/bin/env python3
"""Drift guard for the nostrhost-protocol library (CORE-LIBRARY-EXTRACTION §Test plan).

Rejects newly introduced local event-kind definitions or copied protocol
fixtures outside the compatibility modules. The canonical kind registry and
conformance corpus live in libs/nostrhost-protocol/spec; consumer code must
import kinds from the library rather than redefining them (one-release
compatibility aliases are allowed to *alias* library constants but must not
introduce new numbers).

Checks:

1. No source file outside libs/nostrhost-protocol may define a literal numeric
   constant equal to a control-plane kind (a raw `= 2200`-style definition that
   is not an import of the library constant).
2. No copied protocol fixtures exist outside the library mirrors
   (libs/nostrhost-protocol/{spec,go/testdata,python/src/nostrhost_protocol/spec}).
3. The manifest has no duplicate kinds and every schema reference resolves.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = ROOT / "libs/nostrhost-protocol"

# Source directories scanned for literal kind definitions (not the library
# itself, not vendored/frozen snapshots).
SCAN_DIRS = [
    ROOT / "forks/yunohost/src",
    ROOT / "tools",
    ROOT / "libs/nostrhost-auth/src",
    ROOT / "libs/nostrhost-policy/src",
    ROOT / "libs/nostrhost-mcp/src",
]

# Paths that legitimately carry the kind registry / corpus.
ALLOWED_KIND_DIRS = [LIB_DIR]
ALLOWED_FIXTURE_DIRS = [
    LIB_DIR / "spec" / "fixtures",
    LIB_DIR / "go" / "testdata",
    LIB_DIR / "python" / "src" / "nostrhost_protocol" / "spec" / "fixtures",
]

# Control-plane kinds (mirror of the manifest; keeps the guard standalone).
_CONTROL_PLANE_KINDS = {
    10000, 10002, 10006, 2200, 2201, 2202, 2203, 2204, 2205,
    2210, 2211, 2212, 2213, 2214, 22242, 24243, 27235, 27236, 27237,
    30000, 30078, 30617, 31100, 31101, 31102, 31300,
}


def _manifest_kinds() -> set[int]:
    manifest = LIB_DIR / "spec" / "manifest.json"
    if not manifest.exists():
        return _CONTROL_PLANE_KINDS
    with manifest.open("rb") as handle:
        data = json.load(handle)
    return {int(row["kind"]) for row in data.get("kinds", [])}


def _is_import_line(line: str) -> bool:
    stripped = line.strip()
    return bool(
        re.match(r"^(from|import)\s+nostrhost_protocol", stripped)
        or re.match(r"^(from|import)\s+nostrhost_policy", stripped)
        or "KindSystemEvent as KIND_SYSTEM_EVENT" in stripped
        or "as KIND_" in stripped
        or "as DELEGATION_KIND" in stripped
        or "as NIP98_KIND" in stripped
        or "as OWNER_APPROVAL_KIND" in stripped
        or "as RELAY_LIST_KIND" in stripped
        or "as CHALLENGE_EVENT_KIND" in stripped
        or "as PERMISSION_LIST_KIND" in stripped
    )


def _check_literal_kind_definitions() -> list[str]:
    problems: list[str] = []
    kinds = _manifest_kinds()
    for directory in SCAN_DIRS:
        if not directory.is_dir():
            continue
        files = [path for path in sorted(directory.rglob("*.py"))
                 if "__pycache__" not in path.parts and ".venv" not in path.parts
                 and not path.name.startswith("spike_")]
        problems.extend(_check_literal_kind_definitions_in(files, kinds))
    return problems


def _check_literal_kind_definitions_in(files, kinds: set[int] | None = None) -> list[str]:
    """Check an explicit file list for literal *_KIND = <int> definitions."""
    if kinds is None:
        kinds = _manifest_kinds()
    problems: list[str] = []
    # An assignment to a KIND-named constant, e.g. `KIND_SYSTEM_EVENT = 2210` or
    # `PERMISSION_LIST_KIND = 30000`. Import lines and prose are ignored.
    pattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d{3,5})\s*(#.*)?$")
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for index, line in enumerate(lines, start=1):
            match = pattern.match(line.strip())
            if not match or "KIND" not in match.group(1):
                continue
            value = int(match.group(2))
            if value in kinds:
                problems.append(
                    f"{path}:{index}: literal kind {value} "
                    f"({match.group(1)}) defined outside nostrhost-protocol "
                    f"(import the constant)"
                )
    return problems


def _check_copied_fixtures() -> list[str]:
    problems: list[str] = []
    allowed = [p.resolve() for p in ALLOWED_FIXTURE_DIRS]
    for directory in [ROOT / "libs", ROOT / "tools", ROOT / "forks"]:
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("verdicts.json")):
            if ".venv" in path.parts or ".git" in path.parts:
                continue
            if any(path.resolve().is_relative_to(base) for base in allowed):
                continue
            problems.append(f"copied protocol fixture outside mirrors: {path.relative_to(ROOT)}")
        for path in sorted(directory.rglob("folds.json")):
            if ".venv" in path.parts or ".git" in path.parts:
                continue
            if any(path.resolve().is_relative_to(base) for base in allowed):
                continue
            problems.append(f"copied protocol fixture outside mirrors: {path.relative_to(ROOT)}")
    return problems


def _check_manifest() -> list[str]:
    manifest = LIB_DIR / "spec" / "manifest.json"
    if not manifest.exists():
        return ["libs/nostrhost-protocol/spec/manifest.json missing"]
    with manifest.open("rb") as handle:
        data = json.load(handle)
    kinds: list[dict] = data.get("kinds", [])
    seen: dict[int, int] = {}
    problems: list[str] = []
    for row in kinds:
        kind = int(row["kind"])
        seen[kind] = seen.get(kind, 0) + 1
        schema = row.get("schema")
        if schema and not (LIB_DIR / "spec" / schema).exists():
            problems.append(f"kind {kind}: schema {schema!r} not found")
    for kind, count in seen.items():
        if count > 1:
            problems.append(f"duplicate kind {kind}")
    return problems


def main(argv: list[str] | None = None) -> int:
    problems = (
        _check_literal_kind_definitions()
        + _check_copied_fixtures()
        + _check_manifest()
    )
    for problem in problems:
        print(f"DRIFT: {problem}", file=sys.stderr)
    if "--json" in (argv or []):
        print(json.dumps({"problems": problems}, indent=2))
    print(f"protocol drift guard: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())