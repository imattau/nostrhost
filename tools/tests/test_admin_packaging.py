"""Keep admin asset packaging, build output, and Caddy routing aligned."""

from __future__ import annotations

import json
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

    assert route == "/nostrhost/admin/"
    assert asset_root in caddy
    assert '"/usr/share/nostrhost/admin", "admin", "/nostrhost/admin"' in caddy
    assert "env.VITE_BASE_URL || '/nostrhost/admin/'" in vite
    assert not (ROOT / "forks/admin/debian/control").exists()


def test_shipped_admin_routes_are_native_only() -> None:
    routes = (ROOT / "forks/admin/app/src/router/routes.ts").read_text(encoding="utf-8")
    api = (ROOT / "forks/yunohost/src/nostrhost/api.py").read_text(encoding="utf-8")
    caddy = (ROOT / "forks/yunohost/src/nostrhost/caddy_admin.py").read_text(encoding="utf-8")

    assert "native-packages" in routes
    assert "/yunohost/api" not in routes
    assert '@app.post("/package/plan")' in api
    assert "@app.get(\"/yunohost/api\")" not in api
    native_client = (ROOT / "forks/admin/app/src/api/nativePackages.ts").read_text(encoding="utf-8")
    assert "'/package/plan'" in native_client
    assert '"/package/*"' in caddy


def test_admin_source_and_dependencies_match_native_slice() -> None:
    app = ROOT / "forks/admin/app"
    package = json.loads((app / "package.json").read_text(encoding="utf-8"))
    dependencies = set(package["dependencies"])

    assert not dependencies.intersection(
        {
            "@vueuse/core",
            "@vuelidate/core",
            "bootstrap",
            "bootstrap-vue-next",
            "date-fns",
            "fork-awesome",
            "reka-ui",
            "simple-evaluate",
            "uuid",
            "vue-i18n",
            "vue-showdown",
        }
    )
    assert not (app / "src/api/api.ts").exists()
    assert not (app / "src/views/app/AppCatalog.vue").exists()
    assert not (app / "src/views/user/UserList.vue").exists()
