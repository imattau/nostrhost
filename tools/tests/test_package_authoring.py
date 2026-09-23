"""Contract tests for the human/AI native package authoring CLI."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "forks/yunohost/bin/nostrhost-package"
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "forks/yunohost/src")}

# The fork's pinned npack submodule binary; skip tests that shell out to npack
# when it has not been built (cargo build in forks/npack).
NPACK = ROOT / "forks/npack/target/release/npack"
NEEDS_NPACK = pytest.mark.skipif(
    not NPACK.is_file(), reason="npack binary not built (cargo build --release in forks/npack)"
)

PUBLISHER = "3bf0c63fcb93463407af97a5e5ee64fa883d107ef9e558472c4eb9aaaefa459d"


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


@NEEDS_NPACK
def test_build_npk_produces_a_verified_content_addressed_archive(tmp_path: Path) -> None:
    app_dir = tmp_path / "myapp"
    (app_dir / "var/www/myapp").mkdir(parents=True)
    (app_dir / "var/www/myapp/index.html").write_text("<h1>ok</h1>\n", encoding="utf-8")
    package_file = app_dir / "package.toml"
    package_file.write_text(
        '[app]\nid = "myapp"\nversion = "0.1.0"\n\n'
        '[directories.install]\npath = "/var/www/myapp"\nmode = 0o755\n',
        encoding="utf-8",
    )

    artifact = tmp_path / "myapp-0.1.0.npk"
    env = {**ENV, "NPACK_BIN": str(NPACK)}
    result = subprocess.run(
        [str(CLI), "build-npk", str(package_file), "--payload", str(app_dir), "--output", str(artifact), "--publisher", PUBLISHER],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    body = json.loads(result.stdout)
    assert body["name"] == "myapp"
    assert body["version"] == "0.1.0"
    assert body["publisher"] == PUBLISHER
    assert len(body["sha256"]) == 64
    assert artifact.is_file()

    verified = subprocess.run(
        [str(NPACK), "verify", str(artifact)], text=True, capture_output=True, check=False
    )
    assert verified.returncode == 0, verified.stderr
    assert "myapp 0.1.0" in verified.stdout


@NEEDS_NPACK
def test_build_npk_embeds_the_canonical_native_manifest(tmp_path: Path) -> None:
    import tarfile
    import tempfile

    app_dir = tmp_path / "myapp"
    (app_dir / "var/www/myapp").mkdir(parents=True)
    (app_dir / "var/www/myapp/index.html").write_text("<h1>ok</h1>\n", encoding="utf-8")
    package_file = app_dir / "package.toml"
    package_file.write_text(
        '[app]\nid = "myapp"\nversion = "0.1.0"\n\n'
        '[config.index]\ndestination = "/var/www/myapp/index.html"\n'
        'content = "managed"\n',
        encoding="utf-8",
    )

    artifact = tmp_path / "myapp-0.1.0.npk"
    env = {**ENV, "NPACK_BIN": str(NPACK)}
    result = subprocess.run(
        [str(CLI), "build-npk", str(package_file), "--payload", str(app_dir), "--output", str(artifact), "--publisher", PUBLISHER],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["embedded_manifest"] == ".npack/nostrhost/manifest.json"

    raw = artifact.read_bytes()
    assert raw[:4] == b"\x28\xb5\x2f\xfd", "expected a zstd-compressed .npk (deterministic tar.zst)"

    with tempfile.TemporaryDirectory() as scratch:
        decompressed = Path(scratch) / "archive.tar"
        subprocess.run(
            ["zstd", "-d", "-o", str(decompressed), str(artifact)], check=True, capture_output=True
        )
        with tarfile.open(decompressed) as archive:
            member = ".npack/nostrhost/manifest.json"
            assert member in archive.getnames(), archive.getnames()
            embedded = json.loads(archive.extractfile(member).read().decode("utf-8"))  # type: ignore[union-attr]
    assert embedded["app"] == {"id": "myapp", "version": "0.1.0"}
    assert embedded["config"]["index"]["destination"] == "/var/www/myapp/index.html"


@NEEDS_NPACK
def test_build_npk_signs_repo_and_commit_into_the_release(tmp_path: Path) -> None:
    """--repo/--commit land in npack's own signed .npack/manifest.json (not
    just the embedded nostrhost manifest) - nostrhost-catalog's npack-release
    ingestion (ParseFromNpackRelease) reads them from there."""
    import tarfile
    import tempfile

    package_file = tmp_path / "package.toml"
    package_file.write_text('[app]\nid = "myapp"\nversion = "0.1.0"\n', encoding="utf-8")

    artifact = tmp_path / "myapp-0.1.0.npk"
    env = {**ENV, "NPACK_BIN": str(NPACK)}
    commit = "c" * 40
    # npack's own release signing requires repo to be a NIP-34 kind:30617
    # address ("30617:<pubkey>:<identifier>"), not a plain URL - it rejects
    # any other format (validate_repo_reference in sign_release_event).
    repo = f"30617:{PUBLISHER}:myapp"
    result = subprocess.run(
        [
            str(CLI), "build-npk", str(package_file), "--output", str(artifact),
            "--publisher", PUBLISHER, "--repo", repo,
            "--commit", commit,
        ],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    with tempfile.TemporaryDirectory() as scratch:
        decompressed = Path(scratch) / "archive.tar"
        subprocess.run(
            ["zstd", "-d", "-o", str(decompressed), str(artifact)], check=True, capture_output=True
        )
        with tarfile.open(decompressed) as archive:
            npack_manifest = json.loads(archive.extractfile(".npack/manifest.json").read().decode("utf-8"))  # type: ignore[union-attr]
    assert npack_manifest["repo"] == repo
    assert npack_manifest["commit"] == commit


@NEEDS_NPACK
def test_build_npk_rejects_non_semver_versions(tmp_path: Path) -> None:
    package_file = tmp_path / "package.toml"
    package_file.write_text('[app]\nid = "myapp"\nversion = "0.1"\n', encoding="utf-8")
    env = {**ENV, "NPACK_BIN": str(NPACK)}
    result = subprocess.run(
        [str(CLI), "build-npk", str(package_file), "--publisher", PUBLISHER],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    body = json.loads(result.stdout)
    assert body["valid"] is False
    assert "SemVer" in body["error"]
