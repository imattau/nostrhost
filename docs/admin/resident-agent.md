# Resident AI assistant

The resident assistant is an optional service that watches selected parts of a
NostrHost server. It has its own identity and permissions. It does not become
an administrator simply because it is installed.

This page is for operators testing the assistant. Most users should read the
simpler [AI assistant guide](../guide/ai-assistant.md).

## Important: current status

No local model in the NostrHost model list has passed the project's deployment
tests. The listed models are evaluation candidates, not approved management
models.

Keep the assistant in **Observe** mode unless you are carrying out controlled
development or safety testing on a disposable server. NostrHost does not ship
an AI model, download one automatically, or install an inference server.

## How the safety boundary works

The assistant has:

- a separate Nostr identity;
- a private configuration file;
- an explicit list of things it may read or request;
- an operating mode that limits how it can respond;
- a local activity journal; and
- the same approval checks used by human-facing tools.

The AI model can suggest only registered NostrHost operations. It cannot run a
shell command, change its own permissions, turn off auditing, or directly edit
the server. NostrHost checks every request again before doing anything.

## Set up Observe mode

Install the optional package:

```bash
sudo apt install nostrhost-agent
```

Create the assistant identity and safe starting configuration:

```bash
sudo nostrhost agent init
```

The command prints the assistant's public key. Review it and grant only the
read-only permission shown by the command:

```bash
sudo nostrhost capability grant <assistant-public-key> services.read --type agent
```

Enable the service and check it:

```bash
sudo nostrhost agent enable
sudo nostrhost agent status
```

Enabling the service lets this identity communicate with the local control
service. It does not add new management permissions.

## What Observe mode does

The starting configuration checks service and nsite status immediately, then
every six hours. It also listens for recent server warnings. Free-form warning
text is not passed to a model; the assistant reduces it to a known event type
and an optional checked target.

Observe mode does not require an AI model. It records approved observations in
the private journal at:

```text
/var/lib/nostrhost-agent/audit.jsonl
```

The root-owned configuration is:

```text
/etc/nostrhost-agent/config.json
```

The service refuses configuration files that are links, readable by other
users, too large, malformed, or contain unknown settings.

## Check a changed configuration

Before restarting after a manual change, run:

```bash
sudo nostrhost-agent --check-config \
  --config /etc/nostrhost-agent/config.json
```

The file must remain owned by root with mode `0600`.

## Operating modes

| Mode | Behaviour |
|---|---|
| Observe | Collect approved information only |
| Assist | Ask a model for one suggestion, which a person reviews |
| Maintain | Allow specifically approved, low-risk requests |
| Autonomous | Allow broader repeated work inside explicit limits |

Changing the mode does not grant a permission. Both the configuration and the
server-side grant must allow an operation. High-risk operations can still need
an owner signature.

## Models and inference

Non-Observe modes need an OpenAI-compatible inference server running on the
same machine. The assistant refuses remote inference addresses, so server
observations are not silently sent to an internet service.

Check whether the machine could physically fit the listed evaluation models:

```bash
sudo nostrhost-agent-model profile \
  --models-dir /var/lib/nostrhost-agent/models

sudo nostrhost-agent-model recommend \
  --models-dir /var/lib/nostrhost-agent/models
```

A result saying a model fits in memory is not approval to use it. Current
catalogue entries are unsuitable for deployment. Downloads require an explicit
evaluation-only option and do not activate a model or start an inference
server.

The model catalogue also contains a pinned, checked llama.cpp runtime for
controlled evaluation. Downloading it verifies and unpacks the archive, but
does not create or start a service. An operator must separately run it on a
loopback address and configure the assistant's local `inference` connection.

Do not use these evaluation downloads on a production server.

## Verification before allowing changes

Maintain and Autonomous modes require a fresh-read verification rule for every
operation that can change the server. A rule tells the assistant how to check
the result using a separate read-only operation. For example, a service restart
must be followed by a fresh service-status check.

If the result cannot be checked, the assistant must treat it as unverified. Do
not grant a write permission until its check has been tested on a disposable
machine.

## Scheduling and warning triggers

The configuration controls how often checks run, whether one runs at startup,
whether warnings trigger a check, how far back startup looks for events, and
how long to wait for results. Only one proposal is handled in a cycle. The next
cycle begins with fresh information.

## Knowledge and embeddings

An operator can provide a private local knowledge file. The assistant searches
it for relevant guidance and records document hashes in the journal. It should
contain trusted operational information only.

Optional embeddings can improve matching through a second local
OpenAI-compatible endpoint. If it fails, the assistant falls back to ordinary
word matching. Embeddings are not needed for Observe mode.

## Activity journal and privacy

The journal records each trigger, observation, available operation, proposal,
policy decision, result, and verification outcome. Common secret-shaped values
and fields marked as sensitive are removed before storage, but automatic
redaction is never perfect.

Protect the journal as private server information. Keep the relevant cycle and
operation identifiers after unexpected behaviour.

## Sharing examples with the project

Sharing assistant cycles is optional and off by default. A review candidate may
still contain private details after automatic redaction. Review and edit or
discard it before sharing.

Automatic contribution sends every completed cycle without per-cycle review.
Leave it disabled unless you understand the destination, access token, privacy
risk, and review process. A model's decision is not automatically correct
training data.

## Stop or remove the assistant

```bash
sudo nostrhost agent disable
```

This stops the service and removes its local relay-writing access. Revoke its
capability grants if it is being retired. Removing the package keeps its
configuration and journal; purging removes package-owned state.

## Before testing a mode that can act

- Use a disposable VM with current backups.
- Use a separate assistant identity.
- Grant one narrowly defined operation at a time.
- Add and test a fresh-read verification rule.
- Confirm owner approval still works.
- Test restraint when the server is healthy or evidence is unclear.
- Test recovery after interruption and failed inference.
- Review the journal for secrets and unexplained actions.
- Disable the assistant when the test ends.
