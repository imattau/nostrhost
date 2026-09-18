# NostrHost

NostrHost helps you run websites and online services on a computer you control.
It provides a web dashboard for installing apps, managing who can use them,
checking that the server is healthy, and making backups.

Instead of creating another administrator password, you sign in with a Nostr
key. If you already use Nostr, you can use the same identity with a safe signer.
If you do not use Nostr yet, the [beginner's guide](docs/guide/getting-started.md)
explains what you need.

## Is it ready for everyday use?

Not yet. NostrHost is **pre-alpha software**. Important parts work, but setup,
upgrades, and recovery are still being tested. Use it on a spare computer or a
test virtual machine. Do not use it as the only home for important data.

The optional AI assistant is also experimental. No local AI model has yet
passed the project's safety and quality checks, so the assistant should remain
in its read-only Observe mode. NostrHost does not automatically download an AI
model or send your server data to an AI provider.

## What NostrHost can do

- Host web apps on your own domain.
- Let people sign in using Nostr identities.
- Control who can use each app.
- Manage domains, web addresses, services, and software updates.
- Make encrypted backups and restore them after a problem.
- Check the server and explain problems through a web dashboard.
- Keep a signed history of important administrative actions.
- Send private Nostr notifications to administrators.
- Connect approved external assistants through MCP.
- Run an optional local assistant with tightly limited access.

## What you need

- A spare computer or virtual server using Debian 12 on an amd64 processor.
- A domain name that points to that computer.
- A Nostr identity for the first owner.
- Somewhere else to keep backups and recovery information.

Installing a server still requires comfort with a terminal. After setup, most
day-to-day work can be done in the web dashboard.

## Start here

1. [Learn what NostrHost is](docs/guide/README.md).
2. [Install a test server](docs/guide/getting-started.md).
3. [Install and use apps](docs/guide/apps.md).
4. [Understand identities and access](docs/guide/identity-and-access.md).
5. [Set up backups](docs/guide/backups-and-recovery.md).
6. [Look after the server](docs/guide/server-care.md).
7. [Learn about the optional AI assistant](docs/guide/ai-assistant.md).

The [documentation home](docs/README.md) also links to information for server
operators, developers, and people building integrations.
