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
| `nostrhost-core` | forked YunoHost engine (Stage 1 ships as `yunohost`) | moulinette, libs, caddy, security-config |
| `nostrhost-control` | local khatru control-plane relay | core |
| `nostrhost-notify` | NIP-17/59 notification daemon | control, core |
| `nostrhost-catalog` | catalogue resolver/service | control |
| `python3-nostrhost-auth` | Python auth/identity library | nostr-sdk |
| `python3-nostrhost-policy` | Python authorisation library | bech32, coincurve, pydantic |
| `nostrhost-admin` | built admin SPA assets | core |
| `nostrhost-portal` | built portal SPA assets | core |
| `nostrhost-caddy` | Caddy + `caddy-l4` | — |
| `nostrhost-security-config` | CrowdSec acquisition/scenarios/bouncer config | crowdsec, crowdsec-firewall-bouncer |

`moulinette`, `crowdsec`, `nftables`, `slapd` and normal Python/system
libraries stay ordinary external Debian packages — never repackaged here.

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
       │
       ├──── Recommends: nostrhost-admin
       └──── Recommends: nostrhost-portal

external Debian packages: moulinette · crowdsec · crowdsec-firewall-bouncer
                          · nftables · slapd · Python/system deps
```

## Files

- `packages.yml` — the APT release BOM (package → source repo, kind, deps).
- `compatibility.yml` — version constraints; conservative `>=`, `Breaks` only
  on real protocol/ABI incompatibilities; the Stage 1→2 core-rename plan.
- `scripts/verify-dependencies` — validates the manifest graph (every
  depends resolves, no cycles, meta closure, provides/replaces coherence).
- `scripts/generate-meta-package` — emits the meta `.deb`s.
- `scripts/build-package` — builds one non-meta package from its pinned
  submodule (golang/python/spa/config/caddy kinds). `nostrhost-core` is built
  with `dpkg-buildpackage` in its own debian/ tree by the workflow.
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

# build one package (go/python/spa/config/caddy kinds)
packaging/scripts/build-package --name nostrhost-control -o packaging/build

# assemble an index from built .debs
packaging/scripts/publish-deb --repo packaging/repository \
    packaging/build/*.deb
```