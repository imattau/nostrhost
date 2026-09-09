# nostrhost

A Nostr-native YunoHost derivative: YunoHost's mature server-management engine
(applications, domains, nginx, certificates, backups, services, firewall,
diagnosis, Debian packaging, user/group compatibility) with Nostr as the
primary control-plane technology for identity, authentication, delegated
authority, agent access, approvals, catalogue discovery, publisher trust,
software attestations, and remote administration.

See `docs/BASELINE.md` for the current stage and `docs/ROADMAP.md` provenance.

## Layout

```
nostrhost/
├── forks/            # git submodules: source-identical YunoHost component forks
│   ├── yunohost/     #   imattau/nostrhost-yunohost  (core, python)
│   ├── portal/       #   imattau/nostrhost-portal    (Nuxt/Vue/TS portal)
│   ├── admin/        #   imattau/nostrhost-admin     (Vue/Vite/TS admin)
│   └── ssowat/       #   imattau/nostrhost-ssowat    (NGINX auth)
├── baseline/
│   └── pins.yml      # authoritative component → fork → pinned ref mapping
├── scripts/
│   ├── pin-forks.sh  # sync forks to a pin recorded in pins.yml
│   └── verify-clean.sh # assert forks == upstream pins (source-identical)
├── docs/             # baseline, VM testbed, roadmap notes
└── .github/workflows/baseline.yml
```

## Umbrella ownership

This repository owns architecture, integration tests, dependency/version pins,
release tooling, packaging metadata, and derivative documentation. The forks
under `forks/` are source-identical to upstream at the pinned stable refs and
must not deviate until the derivative intentionally changes behaviour.
