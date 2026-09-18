# NostrHost help

You do not need to understand how NostrHost is built to use it. Start with the
user guide and follow it in order.

## For people using NostrHost

| What do you want to do? | Read this |
|---|---|
| Understand NostrHost | [User guide](guide/README.md) |
| Install a test server | [Getting started](guide/getting-started.md) |
| Install or remove an app | [Apps](guide/apps.md) |
| Add people or change access | [Identity and access](guide/identity-and-access.md) |
| Protect your data | [Backups and recovery](guide/backups-and-recovery.md) |
| Keep the server healthy | [Looking after your server](guide/server-care.md) |
| Understand the AI features | [AI assistant](guide/ai-assistant.md) |
| Fix a common problem | [Troubleshooting](guide/troubleshooting.md) |

## For people looking after a server

The [administrator guide](admin/README.md) covers security, updates,
notifications, network setup, and disaster recovery. It assumes some Linux
server experience, but begins with plain-language explanations.

## Advanced information

These sections are not needed for ordinary use:

- [Developer guide](dev/README.md) — changing NostrHost or creating an app
  package.
- [Contributing](dev/contributing.md) — choosing a repository, preparing a
  change, and opening a pull request.
- [Technical reference](reference/README.md) — details for integrations,
  automated tools, and protocol implementers.

## Words used in these guides

### Owner

The person with final control of the server. Sensitive changes may need the
owner's approval.

### Nostr key

A digital identity made of a public part and a private part. The public part
identifies you. The private part proves that you are you and must remain secret.

### Signer

An app or device that safely holds your private key and signs login requests.

### Portal

The page people use to open their apps and manage their own account.

### Admin

The dashboard used to manage the server.

### App

A service hosted by the server, such as a notes app, website, or file-sharing
tool.

### Operation

An administrative action such as installing an app or restoring a backup.

### MCP

A standard way for an external AI assistant to use approved server tools. It
does not give the assistant unrestricted access.
