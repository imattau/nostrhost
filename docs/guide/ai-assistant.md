# AI assistant

NostrHost includes optional ways to use an AI assistant for server management.
They are experimental and are **not required** to use NostrHost.

## Current status

The local resident assistant is not ready to manage an important server by
itself. The project has tested several small local models, but none has yet
passed the required safety and reliability checks.

For now:

- keep the resident assistant in **Observe** mode;
- do not give it permission to change the server;
- review its findings yourself; and
- do not depend on it for monitoring, backups, or incident recovery.

NostrHost does not automatically download a model or an AI program. It also
does not automatically send your server information to an online AI service.

## Two different AI features

### Resident assistant

This is an optional service running beside NostrHost. In Observe mode, it can
read approved health information and record what it sees. More powerful modes
exist for testing, but they require a separately installed local AI model,
careful permissions, and additional safety checks.

### External assistant through MCP

MCP lets an assistant on another trusted computer use a selected set of
NostrHost tools. The assistant receives its own identity and permissions. It
does not receive the owner's private key or unrestricted server access.

MCP is intended for experienced operators during pre-alpha testing. Setting it
up safely requires server and AI-client configuration.

## Safe Observe-mode setup

Only try this on a test server.

Install the optional service:

```bash
sudo apt install nostrhost-agent
sudo nostrhost agent init
```

The second command creates a separate identity and read-only starting
configuration for the assistant. It does not start the service or grant
permission by itself.

Copy the assistant's public key from the command output. Grant only the
read-only service permission:

```bash
sudo nostrhost capability grant <assistant-public-key> services.read --type agent
```

Then enable it:

```bash
sudo nostrhost agent enable
sudo nostrhost agent status
```

Observe mode does not need an AI model or internet-based AI provider. It is the
only mode recommended by this user guide today.

## What the modes mean

| Mode | What it can do | Recommendation |
|---|---|---|
| Observe | Read approved information and record observations | Suitable for careful testing |
| Assist | Suggest one action for a person to review | Experimental |
| Maintain | Request approved low-risk actions | Do not use on an important server |
| Autonomous | Work with broader independence inside its permissions | Not recommended |

A mode does not create permission by itself. The assistant can use only the
specific permissions granted to its separate identity. Sensitive actions may
still require an owner to approve them.

## Local models

Assist, Maintain, and Autonomous modes need a local program that provides an
OpenAI-compatible connection. NostrHost does not install that program or its
model files.

The available model tool can inspect the computer and show whether an
evaluation model might fit, but a hardware fit is not a safety approval. The
models currently listed by the project are for evaluation only and must not be
treated as approved for server management.

Model installation, configuration files, embeddings, and action-verification
rules are advanced operator tasks. They are described in the
[resident-agent operator guide](../admin/resident-agent.md), not in this
beginner's setup.

## Your data and privacy

The assistant's observations may contain service names, app names, web
addresses, usernames, IP addresses, file paths, or log messages. Treat its
records as private server data.

NostrHost keeps an on-server activity journal for the resident assistant.
Sharing an example with the project is optional. Nothing should be uploaded
without your deliberate action and review. Automatic contribution should stay
off unless you understand exactly what will be shared.

## Stop the assistant

```bash
sudo nostrhost agent disable
```

Disabling stops the service and removes its ability to write to the local
control channel. If you are retiring it permanently, also remove its granted
permissions. Removing the package keeps its configuration and activity journal
unless you explicitly purge them.

## Warning signs

Disable the assistant if it:

- asks for the owner's private key;
- proposes an action unrelated to the evidence;
- repeats changes after a failure;
- treats text from a log or website as an instruction;
- asks for broad administrator access; or
- behaves differently from the selected mode.

Keep the activity journal and operation number when reporting a problem.
