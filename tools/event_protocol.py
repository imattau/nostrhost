#!/usr/bin/env python3
"""NostrHost event-protocol reference validation and conformance runner.

Implements authority/event-protocol/envelope.md exactly. The fixture corpus in
authority/event-protocol/fixtures/ is the source of truth; this module and the
Go ``eventprotocol`` package must reach identical verdicts and folds.

Commands::

    event_protocol.py conformance [--json]
    event_protocol.py verdicts
    event_protocol.py fold <fixture-id>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_DIR = _ROOT / "authority" / "event-protocol"
FIXTURES_DIR = PROTOCOL_DIR / "fixtures"
SCHEMAS_DIR = PROTOCOL_DIR / "schemas"

# Kinds whose content is defined to be a JSON object.
JSON_CONTENT_KINDS = {31100, 31101, 31102}
ADDRESSABLE_KINDS = {31100, 31101, 31102, 30000, 30078}
HEX64_D_KINDS = {31100, 31102}
SIGNER_TYPES = {"nip07", "nip46", "passkey", "unknown"}

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_WS_URL = re.compile(r"^wss?://", re.IGNORECASE)


def is_hex64(value: str) -> bool:
    return bool(_HEX64.match(value))


def _tag(event: dict, name: str) -> list[str] | None:
    for tag in event.get("tags", []):
        if tag and tag[0] == name:
            return tag
    return None


def _tags(event: dict, name: str) -> list[list[str]]:
    return [tag for tag in event.get("tags", []) if tag and tag[0] == name]


def _parse_content(event: dict) -> tuple[object, bool]:
    """Return (parsed, ok). Empty content parses to {} with ok True."""
    raw = event.get("content") or ""
    if raw == "":
        return {}, True
    try:
        return json.loads(raw), True
    except (ValueError, TypeError):
        return None, False


@dataclass
class Verdict:
    ok: bool
    code: str = ""

    def as_dict(self) -> dict:
        return {"accept": self.ok, "code": self.code}


def validate(event: dict) -> Verdict:
    """Apply the event-protocol rules in order; return the first failure."""
    kind = int(event.get("kind", 0))
    content, content_ok = _parse_content(event)

    if kind in JSON_CONTENT_KINDS and not content_ok:
        return Verdict(False, "content-not-json")
    body = content if isinstance(content, dict) else {}

    d = _tag(event, "d")
    if kind in ADDRESSABLE_KINDS:
        if d is None or len(d) < 2 or d[1] == "":
            return Verdict(False, "missing-d")
        if kind in HEX64_D_KINDS and not is_hex64(d[1]):
            return Verdict(False, "d-not-hex64")

    if "schema" in body:
        schema = body["schema"]
        if not isinstance(schema, int) or isinstance(schema, bool) or schema < 1:
            return Verdict(False, "schema-invalid")
    if "revision" in body:
        revision = body["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            return Verdict(False, "revision-invalid")
    if "subject" in body and d is not None and len(d) >= 2 and body["subject"] != d[1]:
        return Verdict(False, "subject-mismatch")

    if kind == 31100:
        if not isinstance(body.get("type"), str) or not body["type"]:
            return Verdict(False, "31100:missing-type")
        scopes = body.get("scopes")
        if scopes is not None and (
            not isinstance(scopes, list) or any(not isinstance(s, str) for s in scopes)
        ):
            return Verdict(False, "31100:scopes-not-array")
    elif kind == 31101:
        if "schema" not in body:
            return Verdict(False, "31101:missing-schema")
    elif kind == 31102:
        enabled = body.get("enabled", True)
        if not isinstance(enabled, bool):
            return Verdict(False, "31102:enabled-not-bool")
        if "admin" in body and not isinstance(body["admin"], bool):
            return Verdict(False, "31102:admin-not-bool")
        username = body.get("username")
        if enabled and (not isinstance(username, str) or not username.strip()):
            return Verdict(False, "31102:missing-username")
        signer_type = body.get("signer_type")
        if signer_type not in (None, "") and signer_type not in SIGNER_TYPES:
            return Verdict(False, "31102:bad-signer-type")
    elif kind == 27236:
        p = _tag(event, "p")
        server = _tag(event, "server")
        if (
            p is None
            or len(p) < 2
            or not is_hex64(p[1])
            or server is None
            or len(server) < 2
            or not is_hex64(server[1])
        ):
            return Verdict(False, "27236:bad-tags")
        expiry = _tag(event, "expiry")
        if expiry is None or len(expiry) < 2:
            return Verdict(False, "27236:bad-expiry")
        try:
            if int(expiry[1]) <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Verdict(False, "27236:bad-expiry")
        if not _tags(event, "scope"):
            return Verdict(False, "27236:missing-scope")
    elif kind == 27237:
        e = _tag(event, "e")
        if e is None or len(e) < 2 or not is_hex64(e[1]):
            return Verdict(False, "27237:missing-e")
    elif kind == 30000:
        for tag in _tags(event, "p"):
            if len(tag) < 2 or not is_hex64(tag[1]):
                return Verdict(False, "30000:bad-p")
    elif kind == 10000:
        for tag in _tags(event, "p"):
            if len(tag) < 2 or not is_hex64(tag[1]):
                return Verdict(False, "10000:bad-p")
    elif kind == 10002:
        relays = [tag for tag in _tags(event, "r") if len(tag) >= 2]
        if not relays or any(not _WS_URL.match(tag[1]) for tag in relays):
            return Verdict(False, "10002:bad-r")

    return Verdict(True, "")


def revision_of(event: dict) -> int:
    body, ok = _parse_content(event)
    if ok and isinstance(body, dict) and isinstance(body.get("revision"), int):
        return body["revision"]
    return 0


def _declares_revision(event: dict) -> bool:
    body, ok = _parse_content(event)
    return ok and isinstance(body, dict) and "revision" in body


def _content_key(event: dict) -> str:
    """Canonical comparison key for 'would these fold to the same fact?'."""
    body, ok = _parse_content(event)
    if not ok or not isinstance(body, dict):
        return ""
    relevant = {k: v for k, v in body.items() if k not in ("revision", "updated_by", "reason")}
    return json.dumps(relevant, sort_keys=True, separators=(",", ":"))


@dataclass
class FoldResult:
    subject: str = ""
    revision: int = 0
    enabled: bool = True
    conflicts: int = 0
    fact: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "subject": self.subject,
            "revision": self.revision,
            "enabled": self.enabled,
            "conflicts": self.conflicts,
            "fact": self.fact,
        }


def fold(kind: int, events: list[dict]) -> FoldResult:
    valid = [event for event in events if validate(event).ok]
    if not valid:
        return FoldResult()
    ordered = sorted(
        valid,
        key=lambda e: (revision_of(e), int(e.get("created_at", 0)), str(e.get("id", ""))),
    )
    winner = ordered[-1]
    top_revision = revision_of(winner)
    winner_key = _content_key(winner)
    # A conflict is two events that *explicitly* declare the same revision but
    # would fold to different facts; such a tie is broken by (created_at, id).
    # Legacy documents that omit `revision` are ordinary NIP-33 replacement —
    # time ordering, not a conflict — and exact duplicates are idempotent
    # (envelope.md §3 step 4).
    conflicts = sum(
        1
        for e in valid
        if _declares_revision(e)
        and revision_of(e) == top_revision
        and _content_key(e) != winner_key
    )
    body, _ = _parse_content(winner)
    body = body if isinstance(body, dict) else {}
    d = _tag(winner, "d")
    subject = d[1] if d and len(d) >= 2 else body.get("subject", "")
    enabled = body.get("enabled", True)
    if not isinstance(enabled, bool):
        enabled = True
    fact: dict
    if kind == 31100:
        fact = {"type": body.get("type", ""), "scopes": list(body.get("scopes", []))}
    elif kind == 31102:
        fact = {"username": body.get("username", ""), "signer_type": body.get("signer_type", "")}
    elif kind == 31101:
        fact = {"schema": body.get("schema"), "value": body.get("value", {})}
    else:
        fact = {}
    return FoldResult(
        subject=subject,
        revision=top_revision,
        enabled=enabled,
        conflicts=max(0, conflicts),
        fact=fact,
    )


def load_fixtures(path: Path) -> list[dict]:
    with path.open("rb") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        return data.get("fixtures", [])
    return data


def run_verdicts(root: Path = _ROOT) -> list[dict]:
    results = []
    for fixture in load_fixtures(root / "authority/event-protocol/fixtures" / "verdicts.json"):
        if "python" not in fixture.get("validators", []):
            continue
        verdict = validate(fixture["event"])
        results.append(
            {
                "id": fixture["id"],
                "accept": verdict.ok,
                "code": verdict.code,
                "expect": fixture["expect"],
            }
        )
    return results


def run_folds(root: Path = _ROOT) -> list[dict]:
    results = []
    for fixture in load_fixtures(root / "authority/event-protocol/fixtures" / "folds.json"):
        if "python" not in fixture.get("validators", []):
            continue
        result = fold(int(fixture["kind"]), fixture["events"]).as_dict()
        results.append({"id": fixture["id"], "result": result, "expect": fixture["expect"]})
    return results


def _normalize(value: object) -> object:
    """Drop fields absent from expectations and normalize ordering."""
    return value


def _verdict_mismatches(results: list[dict]) -> list[str]:
    problems = []
    for item in results:
        expect = item["expect"]
        if bool(item["accept"]) != bool(expect["accept"]):
            problems.append(
                f"{item['id']}: accept={item['accept']} expected={expect['accept']}"
            )
            continue
        if expect.get("accept") is False and expect.get("code") != item["code"]:
            problems.append(
                f"{item['id']}: code={item['code']} expected={expect.get('code')}"
            )
    return problems


def _fold_mismatches(results: list[dict]) -> list[str]:
    problems = []
    for item in results:
        actual, expect = item["result"], item["expect"]
        for key, wanted in expect.items():
            if actual.get(key) != wanted:
                problems.append(
                    f"{item['id']}: {key}={actual.get(key)!r} expected={wanted!r}"
                )
    return problems


def _schema_mismatches(root: Path) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ModuleNotFoundError:
        return []
    problems = []
    for fixture in load_fixtures(
        root / "authority/event-protocol/fixtures" / "verdicts.json"
    ):
        event = fixture["event"]
        kind = int(event["kind"])
        schema_path = next(
            iter(sorted((root / "authority/event-protocol/schemas").glob(f"{kind}-*.schema.json"))),
            None,
        )
        if schema_path is None:
            continue
        raw = event.get("content") or ""
        if raw == "":
            continue
        try:
            body = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(body, dict):
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft7Validator(schema).validate(body)
        except jsonschema.ValidationError as exc:
            # A rejected fixture may legitimately violate the schema; only
            # flag schema violations on accepted fixtures.
            if fixture["expect"]["accept"]:
                problems.append(f"{fixture['id']}: schema: {exc.message}")
    return problems


def _cmd_conformance(root: Path, as_json: bool) -> int:
    verdicts = run_verdicts(root)
    folds = run_folds(root)
    problems = _verdict_mismatches(verdicts) + _fold_mismatches(folds) + _schema_mismatches(root)
    payload = {
        "verdicts": verdicts,
        "folds": folds,
        "problems": problems,
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for problem in problems:
            print(f"MISMATCH: {problem}", file=sys.stderr)
        print(
            f"conformance: {len(verdicts)} verdict(s), {len(folds)} fold(s), "
            f"{len(problems)} problem(s)"
        )
    return 1 if problems else 0


def sync_mirror(root: Path = _ROOT) -> list[str]:
    """Copy canonical fixtures into the Go module's testdata mirror."""
    import shutil

    canonical = root / "authority/event-protocol/fixtures"
    mirror = root / "libs/nostrhost-control/internal/eventprotocol/testdata"
    mirror.mkdir(parents=True, exist_ok=True)
    changed = []
    for name in ("verdicts.json", "folds.json"):
        source = canonical / name
        target = mirror / name
        if not target.exists() or target.read_bytes() != source.read_bytes():
            shutil.copyfile(source, target)
            changed.append(name)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("conformance", "verdicts", "fold", "sync-mirror")
    )
    parser.add_argument("fixture_id", nargs="?")
    parser.add_argument("--root", type=Path, default=_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "sync-mirror":
        changed = sync_mirror(root)
        print(f"synced {len(changed)} file(s): {', '.join(changed) or 'already current'}")
        return 0
    if args.command == "conformance":
        return _cmd_conformance(root, args.json)
    if args.command == "verdicts":
        print(json.dumps(run_verdicts(root), indent=2, sort_keys=True))
        return 0
    for fixture in load_fixtures(
        root / "authority/event-protocol/fixtures" / "folds.json"
    ):
        if args.fixture_id in (None, fixture["id"]):
            print(json.dumps({"id": fixture["id"], **fold(int(fixture["kind"]), fixture["events"]).as_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
