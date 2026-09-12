"""Keep admin asset packaging, build output, and Caddy routing aligned."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_admin_route_and_asset_path_match_release_manifest() -> None:
    release = yaml.safe_load((ROOT / "packaging/packages.yml").read_text(encoding="utf-8"))
    admin = next(item for item in release["packages"] if item["name"] == "nostrhost-admin")
    source = admin["source"]
    route = source["base_path"]
    asset_root = source["static_dir"]

    caddy = (ROOT / "forks/yunohost/src/nostrhost/caddy_admin.py").read_text(encoding="utf-8")
    vite = (ROOT / "forks/admin/app/vite.config.ts").read_text(encoding="utf-8")

    assert route == "/admin/"
    assert asset_root in caddy
    assert '"/usr/share/nostrhost/admin", "admin", "/admin"' in caddy
    assert '"path": [f"{path}/*"]' in caddy
    assert "env.VITE_BASE_URL || '/admin/'" in vite
    assert not (ROOT / "forks/admin/debian/control").exists()


def test_shipped_admin_routes_are_native_only() -> None:
    routes = (ROOT / "forks/admin/app/src/router/routes.ts").read_text(encoding="utf-8")
    api = (ROOT / "forks/yunohost/src/nostrhost/api.py").read_text(encoding="utf-8")

    assert "native-packages" in routes
    assert "/yunohost/api" not in routes
    assert "@app.get(\"/api/v1/packages/schema\")" in api
    assert "@app.post(\"/api/v1/packages/validate\")" in api
    assert "@app.post(\"/api/v1/packages/plan\")" in api
    assert "@app.get(\"/yunohost/api\")" not in api
