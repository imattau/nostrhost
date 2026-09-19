"""Contract tests for the WP0 authority register and its CI guard."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "authority_registry", ROOT / "tools" / "authority_registry.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ar = _load_module()


def _state(**overrides):
    base = dict(
        id="example",
        path="/etc/nostrhost/example.toml",
        cls="projection",
        owner="forks/yunohost/src/example.py",
        sensitivity="private",
        target_authority="events:1",
        retention="transient",
        recovery="rebuild",
    )
    base.update(overrides)
    return ar.State(**base)


def test_checked_in_registry_validates() -> None:
    data, states = ar.load_registry(ROOT)
    assert states
    assert ar.validate_registry(states, ROOT) == []
    assert data["version"] >= 1


def test_checked_in_registry_matches_json_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (ROOT / "schema" / "authority-registry.schema.json").read_text(encoding="utf-8")
    )
    data, _ = ar.load_registry(ROOT)
    jsonschema.Draft7Validator(schema).validate(data)


def test_check_passes_on_source_tree() -> None:
    assert ar.check(ROOT) == []


def test_scan_discovers_persistent_literals(tmp_path: Path) -> None:
    src = tmp_path / "forks" / "yunohost" / "src"
    src.mkdir(parents=True)
    (src / "mod.py").write_text(
        'DEFAULT = "/etc/nostrhost/example.db"\n'
        'STATE = "/var/lib/nostrhost/state"\n'
        'TMP = "/tmp/ignore-me.db"\n',
        encoding="utf-8",
    )
    found = ar.discover(tmp_path)
    assert "/etc/nostrhost/example.db" in found
    assert "/var/lib/nostrhost/state" in found
    assert all("/tmp/" not in path for path in found)


def test_scan_ignores_tests_and_venv(tmp_path: Path) -> None:
    tests = tmp_path / "libs" / "nostrhost-control" / "internal" / "relay" / "tests"
    tests.mkdir(parents=True)
    (tests / "x_test.go").write_text('var p = "/var/lib/nostrhost/events.db"\n', encoding="utf-8")
    assert ar.discover(tmp_path) == {}


def test_glob_entry_covers_children(tmp_path: Path) -> None:
    states = [_state(id="state", path="/var/lib/nostrhost/state/**")]
    assert ar._covered("/var/lib/nostrhost/state", states)
    assert ar._covered("/var/lib/nostrhost/state/apps", states)
    assert not ar._covered("/var/lib/nostrhost/elsewhere", states)


def test_unregistered_path_fails_check(tmp_path: Path) -> None:
    src = tmp_path / "forks" / "yunohost" / "src"
    src.mkdir(parents=True)
    (src / "mod.py").write_text('P = "/var/lib/nostrhost/new.db"\n', encoding="utf-8")
    auth = tmp_path / "authority"
    auth.mkdir()
    (auth / "registry.toml").write_text(
        'version = 1\n\n[[state]]\n'
        'id = "known"\npath = "/etc/nostrhost/known.toml"\nclass = "projection"\n'
        'owner = "x"\nsensitivity = "private"\ntarget_authority = "events:1"\n'
        'retention = "x"\nrecovery = "x"\n',
        encoding="utf-8",
    )
    errors = ar.check(tmp_path)
    assert any("unregistered persistent path: /var/lib/nostrhost/new.db" in e for e in errors)


def test_secret_authority_must_not_be_event() -> None:
    errors = ar.validate_registry([_state(sensitivity="secret", target_authority="events:31102")])
    assert any("secret material must not have event authority" in e for e in errors)


def test_invalid_class_and_sensitivity_rejected() -> None:
    errors = ar.validate_registry([_state(cls="nonsense")])
    assert any("invalid class" in e for e in errors)
    errors = ar.validate_registry([_state(sensitivity="nonsense")])
    assert any("invalid sensitivity" in e for e in errors)


def test_duplicate_ids_rejected() -> None:
    dup = [_state(id="same"), _state(id="same", path="/etc/nostrhost/other.toml")]
    errors = ar.validate_registry(dup)
    assert any("duplicate id" in e for e in errors)


def test_missing_required_field_rejected() -> None:
    errors = ar.validate_registry([_state(recovery="")])
    assert any("missing 'recovery'" in e for e in errors)


def test_missing_artifact_rejected(tmp_path: Path) -> None:
    entry = _state(owner="forks/yunohost/src/does_not_exist.py")
    errors = ar.validate_registry([entry], tmp_path)
    assert any("artifact does not exist" in e for e in errors)
