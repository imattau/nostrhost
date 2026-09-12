"""Contract tests for the human/AI native package authoring CLI."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "forks/yunohost/bin/nostrhost-package"
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "forks/yunohost/src")}


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args], cwd=ROOT, env=ENV, text=True, capture_output=True, check=False
    )


def test_schema_command_emits_json_schema(tmp_path: Path) -> None:
    output = tmp_path / "package.schema.json"
    result = run_cli("schema", "--output", str(output))
    assert result.returncode == 0, result.stderr
    schema = json.loads(output.read_text(encoding="utf-8"))
    assert schema["$schema"].endswith("draft-07/schema#")
    assert schema["properties"]["app"]
    assert schema["properties"]["source"]
    assert "SHA-256" in schema["properties"]["source"]["description"]


def test_checked_in_schema_matches_cli_output() -> None:
    result = run_cli("schema")
    assert result.returncode == 0, result.stderr
    generated = json.loads(result.stdout)
    checked_in = json.loads((ROOT / "schema/package.schema.json").read_text(encoding="utf-8"))
    assert checked_in == generated


def test_init_validate_plan_and_explain_are_read_only(tmp_path: Path) -> None:
    created = run_cli("init", "ai-example", "--directory", str(tmp_path), "--template", "web")
    assert created.returncode == 0, created.stderr
    package_file = tmp_path / "ai-example/package.toml"
    original = package_file.read_bytes()

    validated = run_cli("validate", str(package_file), "--json")
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["valid"] is True

    planned = run_cli("plan", str(package_file), "--json")
    plan = json.loads(planned.stdout)
    assert planned.returncode == 0, planned.stderr
    assert plan["package"] == {"id": "ai-example", "version": "0.1.0"}
    assert plan["operation_count"] > 1

    human_plan = run_cli("plan", str(package_file))
    assert human_plan.returncode == 0, human_plan.stderr
    assert f"{plan['operation_count']} operations" in human_plan.stdout

    explained = run_cli("explain", str(package_file))
    assert explained.returncode == 0, explained.stderr
    assert "risk" in explained.stdout
    assert package_file.read_bytes() == original


def test_validation_returns_path_scoped_machine_diagnostics(tmp_path: Path) -> None:
    package_file = tmp_path / "package.toml"
    package_file.write_text('[app]\nid = "BadName"\nversion = "1"\n', encoding="utf-8")

    result = run_cli("validate", str(package_file), "--json")
    assert result.returncode == 1
    body = json.loads(result.stdout)
    assert body["valid"] is False
    assert body["diagnostics"]
    assert all({"code", "path", "message"} <= item.keys() for item in body["diagnostics"])


def test_init_refuses_to_overwrite_existing_package(tmp_path: Path) -> None:
    target = tmp_path / "already/package.toml"
    target.parent.mkdir()
    target.write_text("keep me", encoding="utf-8")

    result = run_cli("init", "already", "--directory", str(tmp_path), "--template", "minimal")
    assert result.returncode == 2
    assert target.read_text(encoding="utf-8") == "keep me"
