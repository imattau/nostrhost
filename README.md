# nostrhost

A Nostr-native self-hosting platform. YunoHost's mature server-management
engine remains underneath as a compatibility/migration source, but the platform
is increasingly native: Nostr identity/authority as the control plane, a
declarative package/resource engine, Caddy + automatic TLS, CrowdSec security,
ngit/NIP-34 state with Restic data linkage, and a componentised APT
distribution.

The core architectural idea is a **local Nostr relay as the control-plane bus**:
identity, policy, approval, execution, catalogue and audit state flow as signed
events. The design is primitive-first — standard Nostr
(NIP-42/44/51/65/66/77/78/86/89/98) is used wherever possible and custom kinds
are reserved for genuine NostrHost semantics. See `docs/CONTROL-PLANE.md`,
`docs/NIP-MAPPING.md` and `docs/STATELAYER.md` (ngit / NIP-34 configuration-state
+ Restic data linkage).

The platform is at the "make it a product" transition: architecture and major
components exist; the work is integration, dependency cleanup, native
bootstrap and proving the full install/upgrade/recovery path. See
`docs/ALPHA-PLAN.md` for the current execution plan and `docs/ROADMAP.md` for
the full provenance. `docs/BASELINE.md` records the current derivative
baseline and pins.
The separate agent runtime, APT package, Hugging Face model artifacts,
evaluation Space, and opt-in community data loop are planned in
`docs/AGENT-DISTRIBUTION-PLAN.md`.

## Layout

```
nostrhost/
├── forks/            # git submodules: component forks
│   ├── yunohost/     #   imattau/nostrhost-yunohost  (core engine; derivative
│   │                 #   branch `nostrhost`, ships as `nostrhost-core`)
│   ├── portal/       #   imattau/nostrhost-portal    (Nuxt/Vue/TS portal)
│   └── admin/        #   imattau/nostrhost-admin     (Vue/Vite/TS admin)
├── libs/             # git submodules: reusable component libraries
│   ├── nostrhost-auth/     #   identity/challenge/verify/npub/mappings/NIP-05
│   ├── nostrhost-policy/   #   roles/scopes/NIP-98/delegation/approvals/audit
│   ├── nostrhost-catalog/  #   catalogue schema/relay/attestation/trust
│   ├── nostrhost-control/  #   control plane: local relay + event model
│   └── nostrhost-agent/    #   policy-bound local administrator
├── packages/         # native package.toml examples / test apps (resource engine)
├── packaging/        # APT release BOM, scripts, compatibility matrix
├── baseline/
│   └── pins.yml      # authoritative component → fork → pinned ref mapping
├── scripts/          # pin/verify helpers
└── docs/             # roadmap, control plane, state layer, resource engine,
                      # Caddy/CrowdSec migrations, testbed, alpha plan
```

## Platform state

| Area | Status |
|---|---|
| Nostr identity / auth | Native libraries; NIP-07/46/passkey direction |
| Policy / delegation / approvals | Native policy layer |
| Control plane | Local Nostr relay + signed event model |
| App lifecycle | Declarative `package.toml` resource engine (install proof in progress) |
| Catalogue / trust | Native catalogue component |
| Web / TLS | Caddy replacing nginx/SSOwat (SSOwat retired) |
| Security | CrowdSec + nftables (fail2ban retired) |
| Notifications | Nostr notification service (NIP-17/59) |
| State | ngit / NIP-34 semantic configuration state |
| Backup / recovery | Restic linkage + state orchestration |
| Debian packaging | Componentised APT repository (GitHub Pages) |
| Core rename | `yunohost` → `nostrhost-core` (transitional package retained) |
| Moulinette removal | Native `python3-nostrhost` replaces it (dependency dropped) |

The `nostrhost-core` package Provides/Replaces/Conflicts the historical
`yunohost` name; a transitional empty `yunohost` package depends on it so old
references keep resolving.

## Distribution

- `packaging/packages.yml` is the APT release BOM; `packaging/scripts/*`
  build and publish the repo to GitHub Pages
  (`deb [signed-by=…] https://imattau.github.io/nostrhost/debian/ bookworm main`).
- The core engine (`nostrhost-core`) and the native framework/CLI/API
  (`python3-nostrhost`) come from the fork's own `debian/` tree.
- `nostrhost` (meta) → `nostrhost-core-system` → `nostrhost-core` +
  `nostrhost-control` + `nostrhost-catalog` + `nostrhost-caddy` +
  `nostrhost-security-config` + `python3-nostrhost{-auth,-policy}` +
  `nostrhost-runtime` (private venv with bundled wheels).
- Some Python runtime deps (`nostr-sdk`, `pydantic>=2`) are not in Debian
  bookworm (pydantic only ships v1 there).
  They are bundled into `nostrhost-runtime` as pinned manylinux cp311 wheels
  and installed offline into `/opt/nostrhost/venv` (created with
  `--system-site-packages` so the dist-packages debs stay visible); daemons
  run on the venv interpreter — no manual `pip` on the target.

## Umbrella ownership

This repository owns architecture, integration tests, dependency/version pins,
release tooling, packaging metadata, and derivative documentation. The core
fork under `forks/yunohost` is a derivative on its `nostrhost` branch; the
`portal`/`admin` forks are pinned to upstream refs. Pins are recorded in
`baseline/pins.yml`.
