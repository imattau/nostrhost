# nostrhost

A Nostr-native YunoHost derivative: YunoHost's mature server-management engine
(applications, domains, nginx, certificates, backups, services, firewall,
diagnosis, Debian packaging, user/group compatibility) with Nostr as the
primary control-plane technology for identity, authentication, delegated
authority, agent access, approvals, catalogue discovery, publisher trust,
software attestations, and remote administration.

The core architectural idea is a **local Nostr relay as the control-plane
bus**: identity, policy, approval, execution, catalogue and audit state flow
as signed events, projected into YunoHost by small resolvers. The design is
primitive-first — standard Nostr (NIP-42/44/51/65/66/77/78/86/89/98) is used
wherever possible and custom kinds are reserved for genuine NostrHost
semantics. See `docs/CONTROL-PLANE.md` and `docs/NIP-MAPPING.md`.

See `docs/BASELINE.md` for the current stage and `docs/ROADMAP.md` provenance.

## Layout

```
nostrhost/
├── forks/            # git submodules: source-identical YunoHost component forks
│   ├── yunohost/     #   imattau/nostrhost-yunohost  (core, python)
│   ├── portal/       #   imattau/nostrhost-portal    (Nuxt/Vue/TS portal)
│   ├── admin/        #   imattau/nostrhost-admin     (Vue/Vite/TS admin)
│   └── ssowat/       #   imattau/nostrhost-ssowat    (NGINX auth)
├── libs/             # git submodules: reusable component libraries (Stage 2)
│   ├── nostrhost-auth/     #   identity/challenge/verify/npub/mappings/NIP-05
│   ├── nostrhost-policy/   #   roles/scopes/NIP-98/delegation/approvals/audit
│   └── nostrhost-catalog/  #   catalogue schema/relay/attestation/trust
├── baseline/
│   └── pins.yml      # authoritative component → fork → pinned ref mapping
├── scripts/
│   ├── pin-forks.sh  # sync forks to a pin recorded in pins.yml
│   └── verify-clean.sh # assert forks == upstream pins (source-identical)
├── docs/             # baseline, control plane, NIP mapping, extraction,
│                     # VM testbed, roadmap
└── .github/workflows/baseline.yml, libraries.yml
```

## Umbrella ownership

This repository owns architecture, integration tests, dependency/version pins,
release tooling, packaging metadata, and derivative documentation. The forks
under `forks/` are source-identical to upstream at the pinned stable refs and
must not deviate until the derivative intentionally changes behaviour.
