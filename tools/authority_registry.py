#!/usr/bin/env python3
"""Authority register: scan persistent NostrHost paths, validate the registry.

This is the WP0 deliverable of docs/RELAY-STATE-MIGRATION-PLAN.md. It is a
report/guard tool with no host-side effects:

- ``scan``     discover persistent-path literals in the source tree;
- ``validate`` check authority/registry.toml against its contract;
- ``check``    fail when a discovered path is unregistered, a registered path
               no longer exists, or an authority rule is violated.

The registry is the checked-in, machine-readable statement of exactly one
authority per persistent control-plane fact.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - CI uses 3.11+
    import tomli as tomllib  # type: ignore[no-redef]

CLASSES = {
    "event",
    "repository",
    "secret",
    "bootstrap",
    "projection",
    "transactional",
    "external",
}
SENSITIVITIES = {"secret", "private", "public"}

# Roots owned by NostrHost whose literals are treated as persistent state.
PATH_ROOTS = (
    "/etc/nostrhost-agent",
    "/etc/nostrhost",
    "/var/lib/nostrhost",
    "/var/cache/nostrhost",
    "/run/nostrhost",
)
_ROOT_RE = re.compile(
    r"(?:/etc/nostrhost(?:-agent)?|/var/(?:lib|cache)/nostrhost|/run/nostrhost)"
)
# A quoted string containing a root; capture the whole literal body.
_LITERAL_RE = re.compile(r"""["'`]([^"'`\n]*?(?:/etc/nostrhost(?:-agent)?|/var/(?:lib|cache)/nostrhost|/run/nostrhost)[^"'`\n]*)["'`]""")

SCAN_DIRS = (
    "forks/yunohost/src",
    "forks/yunohost/bin",
    "forks/yunohost/hooks",
    "forks/yunohost/debian",
    "libs/nostrhost-auth/src",
    "libs/nostrhost-policy/src",
    "libs/nostrhost-mcp/src",
    "libs/nostrhost-agent",
    "libs/nostrhost-catalog/internal",
    "libs/nostrhost-catalog/cmd",
    "libs/nostrhost-control/internal",
    "libs/nostrhost-control/cmd",
)
SCAN_SUFFIXES = {".py", ".go", ".sh", ".toml", ".json", ".service", ".conf", ".env"}
SCAN_EXCLUDES = (
    "__pycache__",
    ".venv",
    "node_modules",
    ".git",
    "/tests/",
    "/testdata/",
    "test_",
    "_test.go",
    ".example",
)


@dataclass
class State:
    id: str
    path: str
    cls: str
    owner: str
    sensitivity: str
    target_authority: str
    retention: str
    recovery: str
    readers: list[str] = field(default_factory=list)
    writers: list[str] = field(default_factory=list)
    direct_writes: list[str] = field(default_factory=list)
    notes: str = ""


def _norm_literal(literal: str) -> str:
    """Reduce a literal to the stable path prefix it denotes."""
    text = literal.strip()
    # Stop at obvious dynamic/format placeholders.
    for marker in ("{", "<", "$", "%", " ", "\\", ","):
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    # Drop trailing filename punctuation.
    text = text.rstrip(").,;:'\"")
    # Collapse duplicate slashes and a trailing slash (except root itself).
    parts = [p for p in text.split("/") if p not in ("", ".")]
    if not parts:
        return text
    return "/" + "/".join(parts)


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in SCAN_DIRS:
        base = root / rel
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                continue
            # Match exclusions against the path relative to the scanned root so
            # an enclosing directory name (e.g. a pytest tmp dir) cannot hide
            # real source files.
            rel = "/" + path.relative_to(root).as_posix()
            if any(token in rel for token in SCAN_EXCLUDES):
                continue
            files.append(path)
    return files


def discover(root: Path) -> dict[str, list[str]]:
    """Map normalized persistent path -> sorted list of source files."""
    found: dict[str, set[str]] = {}
    for path in _iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for match in _LITERAL_RE.finditer(text):
            norm = _norm_literal(match.group(1))
            if _ROOT_RE.match(norm):
                found.setdefault(norm, set()).add(rel)
    return {key: sorted(value) for key, value in sorted(found.items())}


def load_registry(root: Path) -> tuple[dict, list[State]]:
    path = root / "authority" / "registry.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    states: list[State] = []
    for raw in data.get("state", []):
        states.append(
            State(
                id=raw.get("id", ""),
                path=raw.get("path", ""),
                cls=raw.get("class", ""),
                owner=raw.get("owner", ""),
                sensitivity=raw.get("sensitivity", ""),
                target_authority=raw.get("target_authority", ""),
                retention=raw.get("retention", ""),
                recovery=raw.get("recovery", ""),
                readers=list(raw.get("readers", [])),
                writers=list(raw.get("writers", [])),
                direct_writes=list(raw.get("direct_writes", [])),
                notes=raw.get("notes", ""),
            )
        )
    return data, states


def _repo_artifact_errors(root: Path, state: State) -> list[str]:
    errors: list[str] = []
    candidates = [state.owner, *state.readers, *state.writers, *state.direct_writes]
    for candidate in candidates:
        if not candidate or "/" not in candidate:
            continue
        if candidate.startswith("/"):
            continue
        if not (root / candidate).exists():
            errors.append(f"{state.id}: artifact does not exist: {candidate}")
    return errors


def validate_registry(states: list[State], root: Path | None = None) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for state in states:
        where = state.id or "<missing id>"
        if not state.id:
            errors.append("entry missing 'id'")
        elif state.id in seen:
            errors.append(f"duplicate id: {state.id}")
        seen.add(state.id)
        if not state.path:
            errors.append(f"{where}: missing 'path'")
        if state.cls not in CLASSES:
            errors.append(f"{where}: invalid class '{state.cls}'")
        if state.sensitivity not in SENSITIVITIES:
            errors.append(f"{where}: invalid sensitivity '{state.sensitivity}'")
        if not state.owner:
            errors.append(f"{where}: missing 'owner'")
        if not state.target_authority:
            errors.append(f"{where}: missing 'target_authority'")
        if not state.retention:
            errors.append(f"{where}: missing 'retention'")
        if not state.recovery:
            errors.append(f"{where}: missing 'recovery'")
        if state.sensitivity == "secret" and state.target_authority.startswith("events:"):
            errors.append(
                f"{where}: secret material must not have event authority "
                f"({state.target_authority})"
            )
        if root is not None:
            errors.extend(_repo_artifact_errors(root, state))
    return errors


def _covered(discovered: str, states: list[State]) -> bool:
    for state in states:
        reg = state.path
        if not reg:
            continue
        if reg == discovered:
            return True
        if reg.endswith("/**"):
            prefix = reg[:-3].rstrip("/")
            if discovered == prefix or discovered.startswith(prefix + "/"):
                return True
        elif fnmatch.fnmatch(discovered, reg):
            return True
    return False


REPO_PREFIXES = ("forks/", "libs/", "tools/", "schema/", "authority/", "packaging/", "docs/", "scripts/")


def _is_repo_path(value: str) -> bool:
    return value.startswith(REPO_PREFIXES)


def _registered_exists(reg_path: str, discovered: dict[str, list[str]]) -> bool:
    if reg_path.endswith("/**"):
        prefix = reg_path[:-3].rstrip("/")
        return any(d == prefix or d.startswith(prefix + "/") for d in discovered)
    if reg_path in discovered:
        return True
    return any(fnmatch.fnmatch(d, reg_path) for d in discovered)


def check(root: Path) -> list[str]:
    errors: list[str] = []
    _, states = load_registry(root)
    errors.extend(validate_registry(states, root))
    disk = discover(root)
    for path in disk:
        if not _covered(path, states):
            examples = ", ".join(disk[path][:3])
            errors.append(f"unregistered persistent path: {path} (e.g. {examples})")
    for state in states:
        if not _is_repo_path(state.path):
            # Absolute paths exist only on a live host; logical coordinates
            # (relay:, in-memory:) are not filesystem paths.
            continue
        if not _registered_exists(state.path, disk):
            errors.append(f"{state.id}: registered path not found in source: {state.path}")
    return errors


def _jsonschema_errors(root: Path, data: dict) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ModuleNotFoundError:
        return []
    schema_path = root / "schema" / "authority-registry.schema.json"
    if not schema_path.exists():
        return [f"schema file missing: {schema_path}"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"schema: {'/'.join(str(p) for p in err.path)}: {err.message}"
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    ]


def _cmd_scan(root: Path, as_json: bool) -> int:
    disk = discover(root)
    if as_json:
        print(json.dumps(disk, indent=2, sort_keys=True))
    else:
        for path, files in disk.items():
            print(f"{path}\t({len(files)} file(s))")
        print(f"\n{len(disk)} distinct persistent path(s)")
    return 0


def _cmd_validate(root: Path) -> int:
    data, states = load_registry(root)
    errors = validate_registry(states, root) + _jsonschema_errors(root, data)
    for err in errors:
        print(f"ERROR: {err}", file=sys.stderr)
    print(f"validated {len(states)} entr{'y' if len(states) == 1 else 'ies'}: {'OK' if not errors else 'FAIL'}")
    return 1 if errors else 0


def _cmd_check(root: Path) -> int:
    errors = check(root)
    if not errors:
        _, states = load_registry(root)
        print(f"authority register OK ({len(states)} entries)")
        return 0
    for err in errors:
        print(f"ERROR: {err}", file=sys.stderr)
    print(f"authority register FAILED ({len(errors)} problem(s))", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("scan", "validate", "check"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="machine-readable output for scan")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "scan":
        return _cmd_scan(root, args.json)
    if args.command == "validate":
        return _cmd_validate(root)
    return _cmd_check(root)


if __name__ == "__main__":
    raise SystemExit(main())
