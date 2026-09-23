#!/usr/bin/env python3
"""VM e2e: install opencode-web_nh via a locally-built .npk artifact and
verify the portal tile - the npack-path counterpart to
opencode_install_e2e.py (which loads package.toml straight off disk,
bypassing both the catalogue and npack).

Builds a .npk from the same on-disk package.toml with `nostrhost-package
build-npk` (no network needed - [source.app]'s own URL+SHA-256 fetch still
runs unchanged at apply time; npack only signs/transports the manifest
declaration, not the payload bytes), stages it locally with
nostrhost.npk.stage_local() (no relay - there is no Nostr signature to check
for an artifact that was never published), then drives the identical
resource plan and portal-tile assertions as opencode_install_e2e.py to prove
the npk-sourced plan produces the same result as the catalogue-sourced one.

Requires the `npack` binary on PATH or $NPACK_BIN (see
docs/dev/native-app-packages.md).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

PKG_FILE = Path("/tmp/opencode-web_nh/package.toml")
APP = "opencode-web_nh"
PUBLISHER = "3bf0c63fcb93463407af97a5e5ee64fa883d107ef9e558472c4eb9aaaefa459d"
PORTAL_FILE = Path(f"/etc/nostrhost/portal/nostrhost.test.json")


def main() -> None:
    from yunohost.nostr_identity import _init_headless_yunohost

    _init_headless_yunohost()

    import tomllib

    from nostrhost.native_providers import NativeOperationExecutor, native_providers
    from nostrhost.npk import load_embedded_manifest, stage_local
    from nostrhost.package_authoring import build_npk_artifact
    from nostrhost.package_engine import PackageManifest, plan_package, validate_package

    with PKG_FILE.open("rb") as stream:
        package_data = tomllib.load(stream)

    with tempfile.TemporaryDirectory(prefix="opencode-npk-e2e-") as workdir:
        artifact = Path(workdir) / "opencode-web_nh.npk"
        # [app].version carries a YunoHost-style `~nh1` suffix, not valid
        # SemVer (npack requires it) - override just the release version,
        # same as the build comment at the top of package.toml documents.
        build_npk_artifact(
            package_data,
            payload_dir=None,
            output=artifact,
            publisher=PUBLISHER,
            version="1.18.30",
        )
        staged = stage_local(artifact, store=Path(workdir) / "store")

    embedded = load_embedded_manifest(staged["payload_root"])
    package = validate_package(PackageManifest.parse_obj(embedded))
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

    print("\nE2E OPENCODE NPK INSTALL PORTAL TILE OK")


if __name__ == "__main__":
    main()
