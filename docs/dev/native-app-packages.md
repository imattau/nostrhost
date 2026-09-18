# Writing a native app package

A native app describes desired resources in a manifest. NostrHost validates
and plans those resources before any change reaches the host.

## Start a package

```bash
nostrhost-package init my-app
nostrhost-package validate my-app/package.json
nostrhost-package plan my-app/package.json --json
nostrhost-package explain my-app/package.json
```

Use `nostrhost-package --help` for the exact options installed on your system.
The canonical schema is `schema/package.schema.json`, and examples live under
`packages/`.

## Declare the whole lifecycle

A complete package should declare, as needed:

- package identity, version, source, and trust metadata;
- Unix users and groups;
- directories, ownership, and modes;
- runtime and database requirements;
- systemd services and health checks;
- Caddy routes and access policy;
- settings and secret references;
- backup and restore coverage; and
- removal behaviour.

Do not embed plaintext secrets or arbitrary install, upgrade, and removal shell
scripts. Add a typed resource and provider when the platform lacks a required
primitive.

## Planning and application

Authoring-time planning validates the TOML manifest, resolves dependencies,
and returns ordered operations. It is read-only. Installation through Admin or
the catalogue creates a server-side plan envelope with a digest and provenance,
then submits that envelope through the normal policy and audit path. The
executor verifies it again before applying resources. Do not edit an approved
plan by hand or treat authoring output as an approval token.

## Package quality checklist

- Validation rejects missing and unexpected fields.
- Replanning produces the same result for the same inputs.
- A second reconciliation is safe and converges.
- Health checks detect a broken service or route.
- Backups include all durable data and restore successfully.
- Upgrade and URL changes preserve data and access.
- Removal deletes only declared package-owned resources.
- Logs contain no secrets.
- Permissions are least-privilege and public access is explicit.

Test install, upgrade, backup, restore, URL change, and removal on a clean VM.
