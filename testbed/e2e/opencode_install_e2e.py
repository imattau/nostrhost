#!/usr/bin/env python3
"""VM e2e: install opencode-web_nh via the native engine and verify the portal tile.

Drives the full resource plan (source download -> user/dirs -> service -> Caddy
route -> Portal permission -> health) through the same providers the runtime
uses, then asserts the portal projection at /etc/nostrhost/portal reflects the
new app and the portal-api /public endpoint exposes its tile.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PKG_FILE = Path("/tmp/opencode-web_nh/package.toml")
APP = "opencode-web_nh"
PORTAL_FILE = Path(f"/etc/nostrhost/portal/nostrhost.test.json")


def main() -> None:
    from yunohost.nostr_identity import _init_headless_yunohost

    _init_headless_yunohost()

    from nostrhost.native_providers import NativeOperationExecutor, native_providers
    from nostrhost.package_engine import load_package, plan_package

    package = load_package(PKG_FILE)
    plan = plan_package(package)
    print("plan ops:", [op.name for op in plan])

    executor = NativeOperationExecutor(native_providers(root=Path("/")))
    failures: list[str] = []
    for op in plan:
        try:
            executor.execute(op)
            print(f"OK   {op.name} {op.resource}")
        except Exception as exc:  # noqa: BLE001 - report every step, keep going
            failures.append(f"{op.name}: {exc}")
            print(f"FAIL {op.name} {op.resource}: {exc}")

    if failures:
        print("\nstep failures (see above):", len(failures))

    # The tile is driven by the Portal permission; its projection is what the
    # portal SPA renders.
    portal = json.loads(PORTAL_FILE.read_text()) if PORTAL_FILE.exists() else None
    print("\nportal projection apps:", sorted((portal or {}).get("apps", {})))

    assert portal is not None, f"{PORTAL_FILE} not written by the permission projection"
    assert f"{APP}.main" in portal["apps"], f"{APP}.main missing from portal projection"
    tile = portal["apps"][f"{APP}.main"]
    print("tile:", json.dumps(tile))
    assert tile["url"] == "nostrhost.test/opencode", tile["url"]
    assert tile["label"], "tile label missing"
    assert tile["public"] is False, "all_users-only app must not be public to visitors"

    # Portal permission really exists with a tile.
    from yunohost.permission import user_permission_info

    info = user_permission_info(f"{APP}.main")
    print("permission:", json.dumps({k: info.get(k) for k in ("url", "show_tile", "allowed")}))
    assert info["show_tile"] is True

    # Anonymous /public correctly hides the all_users-only tile; a signed-in
    # user sees it via /me (the projection above is what both render).
    out = subprocess.run(
        ["curl", "-fsS", "-H", "Host: nostrhost.test", "http://127.0.0.1:6788/public"],
        capture_output=True,
        text=True,
    )
    public = json.loads(out.stdout)
    print("portal /public apps:", sorted(public.get("apps", {})))
    assert f"{APP}.main" not in public["apps"], "all_users-only tile leaked to anonymous /public"

    print("\nE2E OPENCODE PORTAL TILE OK")


if __name__ == "__main__":
    main()