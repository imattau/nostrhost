#!/usr/bin/env python3
"""VM e2e: native [settings] app driven through the legacy config panel.

Installs a native package with typed settings + a template-backed config + a
systemd service, then exercises yunohost.app.app_config_get / app_config_set
(the same path app.config.read / app.config.set use) and verifies the value
flows: panel -> show script -> apply script -> settings state -> config
re-render -> service reload.
"""
import json
import shutil
import subprocess
from pathlib import Path

APP = "configdemo"
APPS = Path("/etc/yunohost/apps")
PKG_STATE = Path("/var/lib/nostrhost/state/packages")
SETTINGS_STATE = Path("/var/lib/nostrhost/state/settings")
ROOT = Path("/")
RUN = ROOT / "opt/configdemo/run.sh"

manifest = {
    "app": {"id": APP, "version": "0.1"},
    "settings": {
        "fields": {
            "port": {"type": "integer", "default": 8090, "label": "Listen port"},
            "mode": {"type": "enum", "choices": ["safe", "fast"], "default": "safe"},
        },
        "values": {"port": 8090, "mode": "safe"},
    },
    "service": {"name": APP, "exec": "/opt/configdemo/run.sh", "user": "root"},
    "config": {
        "run": {
            "destination": str(RUN),
            "template_content": "#!/bin/sh\nwhile true; do sleep 30; done\n# settings: port={{ settings.port }} mode={{ settings.mode }}\n",
            "mode": 0o755,
        }
    },
}


def main() -> None:
    # Same headless init the daemons use: sets the YunohostLogger class (so
    # `logger.success()` works in the ConfigPanel machinery) + a headless CLI
    # interface.
    from yunohost.nostr_identity import _init_headless_yunohost

    _init_headless_yunohost()

    # Clean slate.
    shutil.rmtree(APPS / APP, ignore_errors=True)
    RUN.parent.mkdir(parents=True, exist_ok=True)
    RUN.unlink(missing_ok=True)
    (PKG_STATE / f"{APP}-manifest.json").unlink(missing_ok=True)
    (SETTINGS_STATE / f"{APP}-settings.json").unlink(missing_ok=True)
    subprocess.run(["systemctl", "disable", "--now", "configdemo"], capture_output=True)
    unit = ROOT / "etc/systemd/system/configdemo.service"
    unit.unlink(missing_ok=True)

    from nostrhost.native_providers import (
        ConfigFileProvider,
        NativeOperationExecutor,
        NativeSettingsProvider,
        PackageProvider,
        ServiceProvider,
    )
    from nostrhost.package_engine import PackageManifest, plan_package, validate_package

    package = validate_package(PackageManifest.parse_obj(manifest))
    executor = NativeOperationExecutor(
        {
            "package": PackageProvider(state_dir=PKG_STATE, apps_dir=APPS),
            "settings": NativeSettingsProvider(state_dir=SETTINGS_STATE, apps_dir=APPS),
            "config": ConfigFileProvider(root=ROOT),
            "service": ServiceProvider(unit_dir=ROOT / "etc/systemd/system", command=subprocess.run),
        }
    )
    for op in plan_package(package):
        executor.execute(op)

    assert (APPS / APP / "config_panel.toml").is_file(), "panel missing"
    assert (APPS / APP / "scripts" / "config").is_file(), "config script missing"
    assert RUN.is_file()
    print("install: panel + script + run.sh rendered + service started")
    print(RUN.read_text().strip())

    # The engine's service.ensure already wrote + started the real unit.

    from yunohost.app import app_config_get, app_config_set

    full = app_config_get(APP, full=True)
    print("\nGET full:", json.dumps(full, indent=1))
    assert full["panels"][0]["id"] == "main"
    options = {opt["id"]: opt for opt in full["panels"][0]["sections"][0]["options"]}
    assert set(options) == {"port", "mode"}
    assert options["port"]["value"] == 8090
    assert options["mode"]["value"] == "safe"

    classic = app_config_get(APP)
    print("\nGET classic:", json.dumps(classic))
    assert classic["main.main.port"]["value"] == "8090"

    # Single-option set (this is what app.config.set receives).
    before = subprocess.run(["systemctl", "show", "configdemo", "-p", "ActiveEnterTimestamp"], capture_output=True, text=True).stdout
    app_config_set(APP, "main.main.port", "9000")
    after = subprocess.run(["systemctl", "show", "configdemo", "-p", "ActiveEnterTimestamp"], capture_output=True, text=True).stdout

    state = json.loads((SETTINGS_STATE / f"{APP}-settings.json").read_text())
    print("\nsettings state:", json.dumps(state["values"]))
    assert state["values"] == {"port": 9000, "mode": "safe"}

    rendered = RUN.read_text()
    print("\nrun.sh after apply:", rendered.strip())
    assert "port=9000" in rendered
    assert "mode=safe" in rendered

    print("\nservice restarted:", before != after, "|", before.strip(), "->", after.strip())
    assert before != after, "service was not reloaded after config apply"

    # apply a bad value -> per-key validation error, nothing changes.
    from nostrhost.native_config import apply_values

    result = apply_values(APP, {"port": "nope"})
    assert result == {"validation_errors": {"port": "expected an integer"}}
    state = json.loads((SETTINGS_STATE / f"{APP}-settings.json").read_text())
    assert state["values"]["port"] == 9000

    print("\nE2E CONFIG PANEL OK")


if __name__ == "__main__":
    main()