"""Tests for the nostrhost-protocol drift guard."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_guard():
    spec = importlib.util.spec_from_file_location(
        "protocol_drift_guard", ROOT / "tools" / "protocol_drift_guard.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def test_manifest_is_wellformed():
    problems = guard._check_manifest()
    assert problems == [], problems


def test_no_literal_kinds_outside_library():
    problems = guard._check_literal_kind_definitions()
    assert problems == [], problems


def test_no_copied_fixtures_outside_mirrors():
    problems = guard._check_copied_fixtures()
    assert problems == [], problems


def test_literal_definition_is_detected(tmp_path):
    source = tmp_path / "probe.py"
    source.write_text('KIND_SYSTEM_EVENT = 2210\n')
    problems = guard._check_literal_kind_definitions_in([source])
    assert problems == [f"{source}:1: literal kind 2210 (KIND_SYSTEM_EVENT) defined outside nostrhost-protocol (import the constant)"]