# NostrHost APT packaging

The umbrella repo is the **release BOM**: it owns the package manifest, the
inter-component compatibility matrix and the repository tooling, but it is
**not** a giant binary package. The software ships as independent `.deb`s,
each built from its own component repo (held here as pinned submodules).

## The package model

| APT package | Contents | Depends |
|---|---|---|
| `nostrhost` | meta-package: the complete server | core-system + admin + portal + notify |
| `nostrhost-core-system` | meta-package: minimal headless system | core + control + catalog + caddy + security-config + python libs |
| `nostrhost-core` | NostrHost server-management engine (renamed from `yunohost`, Stage 2) | python3-nostrhost, libs, caddy, security-config |
| `yunohost` | transitional package depending on nostrhost-core (rename shim) | nostrhost-core |
| `python3-nostrhost` | native moulinette replacement: framework primitives + Typer CLI + Bottle/NIP-98 API | yunohost, typer, bottle, auth |
| `nostrhost-control` | local khatru control-plane relay | core |
| `nostrhost-notify` | NIP-17/59 notification daemon | control, core |
| `nostrhost-catalog` | catalogue resolver/service | control |
| `python3-nostrhost-auth` | Python auth/identity library | nostr-sdk |
| `python3-nostrhost-policy` | Python authorisation library | nostr-sdk, pydantic |
| `nostrhost-admin` | built admin SPA assets | core |
| `nostrhost-portal` | built portal SPA assets | core |
| `nostrhost-caddy` | Caddy + `caddy-l4` | — |
| `nostrhost-security-config` | CrowdSec acquisition/scenarios/bouncer config | crowdsec, crowdsec-firewall-bouncer |
| `nostrhost-runtime` | private venv `/opt/nostrhost/venv` + bundled wheels | python3-venv, python3-pip |

`crowdsec`, `nftables`, `slapd` and normal Python/system
libraries stay ordinary external Debian packages — never repackaged here.

Some Python runtime deps are **not in Debian bookworm** (or only in an
incompatible version): `nostr-sdk` (for `python3-nostrhost-auth`), and
`nostr-sdk`, `pydantic>=2` (for `python3-nostrhost-policy`; bookworm
only ships pydantic 1.x). They are bundled into `nostrhost-runtime` as pinned
manylinux cp311 wheels (downloaded at build time from `packaging/runtime/
requirements.txt`) and installed **offline** into a private venv:

- `postinst` creates `/opt/nostrhost/venv` with `--system-site-packages`, so
  the dist-packages debs (`nostrhost`, `nostrhost_auth`, `nostrhost_policy`,
  `yunohost`, typer, bottle, …) stay visible and the wheels layer the
  pip-only deps on top.
- Daemons and units run on `/opt/nostrhost/venv/bin/python`.
- No manual `pip` on the target. When the pins in
  `packaging/runtime/requirements.txt` change, bump the `nostrhost-runtime`
  version in `packages.yml` (apt does not upgrade a same-version rebuild).

Control and notify are two **independently-versioned** binary packages even
though they share the `nostrhost-control` source repo: the release flow tags
them separately (`control/v*`, `notify/v*`).

## The dependency shape

```text
                         nostrhost
                       (meta-package)
                            │
       ┌────────────────────┼─────────────────────────┐
       ▼                    ▼                         ▼
 nostrhost-core      nostrhost-control         nostrhost-caddy
       │                    │
       │              ┌─────┴────────┐
       │              │              │
       ▼              ▼              ▼
       │       nostrhost-catalog  nostrhost-notify
       │
       ├──── python3-nostrhost-auth
       ├──── python3-nostrhost-policy
       ├──── nostrhost-security-config
       ├──── nostrhost-runtime
       │
       ├──── Recommends: nostrhost-admin
       └──── Recommends: nostrhost-portal

external Debian packages: crowdsec · crowdsec-firewall-bouncer
                          · nftables · slapd · Python/system deps
```

## Files

- `packages.yml` — the APT release BOM (package → source repo, kind, deps).
- `compatibility.yml` — version constraints; conservative `>=`, `Breaks` only
  on real protocol/ABI incompatibilities; the completed core rename
  (yunohost → nostrhost-core).
- `runtime/requirements.txt` — pinned Python deps bundled into
  `nostrhost-runtime` (see the package model above).
- `scripts/verify-dependencies` — validates the manifest graph (every
  depends resolves, no cycles, meta closure, provides/replaces coherence).
- `scripts/generate-meta-package` — emits the meta `.deb`s.
- `scripts/build-package` — builds one non-meta package from its pinned
  submodule (golang/python/spa/config/caddy/runtime kinds). For SPAs it also
  installs the frozen JavaScript dependencies and runs the declared build;
  generated output is never assumed to exist. `nostrhost-core` is built with
  `dpkg-buildpackage` in its own debian/ tree by the workflow.
- `scripts/publish-deb` — stages `.deb`s into a pool and regenerates the
  index (`Packages`, `Packages.gz`, `Release`, optional `InRelease`).
- `.github/workflows/apt.yml` — builds everything, verifies the graph,
  assembles the repo and publishes to GitHub Pages under `/debian/`.

## Publishing to GitHub Pages

The workflow commits the assembled repo to GitHub Pages under `debian/`, so
the sources line is:

```text
deb [signed-by=/etc/apt/keyrings/nostrhost.asc] \
    https://imattau.github.io/nostrhost/debian/ bookworm main
```

Set the Pages source to "Deploy from a branch" → `gh-pages` / (root).

**Signing:** add the apt signing key id + armored private key to the
`APT_GPG_KEYID` and `APT_GPG_KEY` repository secrets. Without them the repo is
published unsigned and clients must add `[trusted=yes]`.

## Local workflow

```bash
# validate the manifest
packaging/scripts/verify-dependencies

# build meta-packages
packaging/scripts/generate-meta-package -o packaging/build

# build one package (including the complete SPA build when applicable)
packaging/scripts/build-package --name nostrhost-admin -o packaging/build
packaging/scripts/build-package --name nostrhost-control -o packaging/build

# assemble an index from built .debs
packaging/scripts/publish-deb --repo packaging/repository \
    packaging/build/*.deb
```
