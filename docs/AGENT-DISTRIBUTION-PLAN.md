# NostrHost agent distribution plan

> **Plan and status are consolidated in `ROADMAP.md` (§ "Agent Distribution
> Plan"). This document is the working detail — decisions, phases and release
> gates.**

## Decision

Keep the agent runtime and model artifacts independently installable. APT will distribute the Go daemon and its service integration. Hugging Face Hub will be the later home for validated model artifacts and public-safe evaluation data; a Hugging Face Space will provide an interactive evaluation demo. NostrHost must run without a Hugging Face account or network connection when the operator supplies a local OpenAI-compatible inference endpoint.

Do not publish or ship the current LoRA adapter. The 36-row synthetic dataset contains only 22 independent episodes, and the adapter scored 3/17 on the frozen regression suite while abstaining on 15 cases. It is rejected. Training outputs, raw VM captures, private traces, and credentials stay out of APT and public Hugging Face repositories.

Treat community contributions as a shared, model-agnostic improvement loop: a reviewed example should improve the benchmark and be eligible for any model's training set, without treating any one model's output as ground truth.

## Current state

- `libs/nostrhost-agent` has the Go resident daemon, strict runtime configuration, a typed operation boundary, audit journal, and local inference endpoint support.
- The APT build tooling already supports Go packages from pinned submodules, but `nostrhost-agent` is not listed in `packaging/packages.yml` and has no shipped systemd unit.
- The component README says operators currently provide service-manager packaging.
- The model is not ready for release. The independent-episode and safety gates in [`../libs/nostrhost-agent/docs/training-regime.md`](../libs/nostrhost-agent/docs/training-regime.md) still apply.
- `nostrhost-agent-model` now probes local Linux resources, reports catalog resource fit, and can fetch immutable, hash-verified GGUFs after explicit operator action. The two catalogued candidates remain evaluation-only; neither passed the planner gate. No model is currently eligible for deployment.
- The test VM used for collection has core `12.1.41.21`; current repo source is `12.1.41.28`. Its upgrade remains unverified until VM access is restored.

## Phase 1 — Make the daemon packageable

Keep this work in `libs/nostrhost-agent` and the umbrella APT release manifest.

1. Add `deploy/nostrhost-agent.service` to the component. Run `/usr/bin/nostrhost-agent` as a dedicated unprivileged `nostrhost-agent` account with no shell or home directory; apply systemd hardening, clean SIGTERM handling, and restart-on-failure. Grant write access only to the agent's audit/state directory. Do not give it broad access to NostrHost's root-owned platform configuration or keys.
2. Make service setup safe on all package transitions. The `.deb` should create the system account and empty `/var/lib/nostrhost-agent` with restrictive ownership/mode, install the unit, and run `systemctl daemon-reload`; it must not enable or start the service. Handle upgrades without replacing operator data. On removal, stop/disable the service and remove the unit, but retain the account and audit/state data so ownership stays stable. On purge only, remove the audit/state directory and then the system account. Keep maintainer scripts idempotent and avoid restarting a service that is not configured.
3. Keep agent provisioning out of APT `postinst`. APT must not generate identities, grant relay capabilities, invent trusted server keys, download models, or enable autonomous operation. Provide an explicit root-only `nostrhost agent init` (or equivalent) after platform `postinstall --new`/`--restore`: validate that NostrHost is initialized, provision a *separate* agent identity, bind the trusted server key and configured control relay, and write an Observe-mode configuration by default. Any capability grant or move to a proposal/write-capable policy must be a separate explicit operator action with bounded scopes. Do not add agent setup to the default bootstrap path until this opt-in flow has passed VM acceptance.
4. Resolve secret delivery without weakening `LoadRuntimeConfig`: its config file must be a regular file with no group/other permissions. Keep the source config root-owned and unreadable to the service account; test a systemd `LoadCredential=` handoff and confirm the daemon can read the credential copy while the service cannot alter its source. If the current single-file config shape prevents safe credential handoff, make the smallest reviewed loader change before packaging. Test this on Debian 12.
5. Add build and package checks: Go tests, binary build, package-content inspection, `systemd-analyze verify`, config/credential permission tests, and install/upgrade/remove/purge tests in a disposable current NostrHost VM. Assert that a fresh install does not create config or enable/start the service, that explicit initialization produces Observe mode, and that removal retains audit/state until purge.

The package should be a separate optional `nostrhost-agent` package at first. Do not add it as a dependency of the default `nostrhost` or `nostrhost-core-system` meta-package until setup and operational support are mature.

## Phase 2 — Add and verify the APT package

1. Extend `packaging/packages.yml` with an optional `nostrhost-agent` Go package sourced from the pinned `libs/nostrhost-agent` submodule. Do not add it to either meta-package. Depend only on the platform interfaces the agent actually uses; avoid introducing a cycle through `nostrhost-control`.
2. Extend `packaging/scripts/build-package` to fail the build if a declared unit is missing, stage the unit, and install reviewed `postinst`, `prerm`, and `postrm` lifecycle scripts (including systemd helper use and purge-only data removal). The binary package should contain only the daemon, service unit, required defaults/documentation, and maintainer scripts. Exclude eval/export/model utilities, training scripts, datasets, adapters, and model weights unless separately justified and reviewed.
3. Add CLI/bootstrap integration in the NostrHost core only after the explicit provisioning contract is implemented: `nostrhost agent init`, `status`, and `disable` (names may change during implementation). `postinstall --new` and `--restore` should report that the optional agent is unconfigured; they must not silently create credentials, grants, enablement, or model downloads. Document the operator path from apt install → explicit init → inspect config/scopes → explicit enable.
4. Verify dependency edges and generated package contents. On the latest NostrHost VM, test a clean install, postinstall-before-and-after agent installation, explicit initialization, service disabled before explicit enable, Observe mode without inference, upgrade with config and audit retained, remove with audit retained, purge behavior, and recovery after failed configuration. Also verify default NostrHost meta-package installs do not pull the agent.
5. Keep the package change on a review branch until the whole APT workflow and VM acceptance pass. The current APT workflow publishes on pushes to `main`, so merging the manifest entry is also a repository publication action.

Acceptance: an operator can install the daemon without downloading model weights, without granting it root, and without it starting before valid configuration is installed. Observe mode can run without an inference server; write-capable modes remain subject to NostrHost's registered-operation, approval, and fresh-verification controls.

### Integration sequence and ownership

| Step | Owner | Deliverable | Gate |
|---|---|---|---|
| A | `nostrhost-agent` component | hardened unit, service-account assumptions, credential loading validated on Debian 12 | daemon tests + unit/config permission tests pass |
| B | umbrella packaging | optional `.deb`, unit staging, idempotent maintainer scripts, package-content check | built `.deb` installs disabled with no operator config |
| C | NostrHost core (`forks/yunohost`) | explicit `nostrhost agent init/status/disable` lifecycle and scoped capability setup; no implicit `postinstall` activation | tests prove identity separation, Observe default, and no accidental grants |
| D | VM acceptance | clean install, initialize, enable, observe, upgrade, remove, purge and recovery checks on current NostrHost | all checks pass from a clean snapshot |
| E | release | publish optional package and operator docs; keep default meta-packages unchanged | review of package contents, security boundary, and APT workflow |

Do not start step C by directly coupling the agent daemon to platform internals. Keep the boundary at explicit config generation and the existing relay/operation protocol. If postinstall integration is later desired, make it an opt-in flag that invokes the same tested provisioning path and leaves service enablement as a distinct operator decision.

## Phase 3 — Publish model artifacts on Hugging Face

Start only after a candidate passes the training-regime gates and has a reproducible end-to-end evaluation through the production planner interface.

1. Create a model repository for the deployment artifact, with a model card recording base model and license, exact base revision, tokenizer/chat format, quantization, supported inference runtime, dataset and evaluation report hashes, and intended/unsupported use.
2. Keep research adapters private during review. Publish an adapter or a merged/quantized GGUF only after review and license checks. Prefer `safetensors` for adapter weights and a documented, hash-verified GGUF for llama.cpp deployment; do not publish Python pickle checkpoints.
3. The agent component now pins catalog downloads to immutable Hub commits and verifies expected size and SHA-256. Its explicit model command compares local resource estimates before downloading, writes under the operator-selected model directory, and never switches the active model. Keep it out of APT post-install; package the optional command only after the release catalog includes a qualified model and install-path permissions are tested.
4. Do not embed a Hugging Face token in a `.deb`, example config, Space source, or model. Private/gated downloads require the operator's own credentials. A local model and inference endpoint remain the default deployment path.
5. If hosted inference is ever supported, make it an explicit operator-selected endpoint and clearly disclose that host observations leave the server. Never route to a hosted service by default.

Acceptance: a documented artifact can be downloaded by an operator at an exact revision, verified locally, selected explicitly, used offline after download, and rolled back by changing the model pin.

## Phase 4 — Build the Hugging Face Space

The requested Space is appropriate once the evaluation harness can emit a versioned, public-safe report. Its defined demo is **NostrHost Agent Lab**: browse synthetic scenario families, inspect expected no-call/proposal decisions, compare base and candidate outputs, and view per-category safety and utility metrics. It must never dispatch NostrHost operations.

1. Use the Hugging Face Spaces workflow in the official [`huggingface-spaces` skill](https://github.com/huggingface/skills/tree/main/skills/huggingface-spaces) and the requested [Space agent instructions](https://huggingface.co/new-space/agents.md) when implementation starts.
2. Begin with only synthetic or explicitly redacted public cases and immutable evaluation reports. Exclude raw signed events, VM identifiers, domains, keys, logs, audit journals, and any production traces.
3. Start with a CPU/static or low-cost demo that renders committed reports. Add live inference only if it materially improves review and the owner approves the compute cost; Spaces may sleep and their default local disk is not persistent.
4. Public visibility is appropriate only for the synthetic evaluation UI and public artifacts. Keep unpublished model candidates and training data private until their promotion and license review is complete.
5. Make every displayed model result traceable to a model revision, dataset hash, prompt version, and evaluation code revision. Treat model output as a proposal for review, never as an executable action.

Acceptance: a visitor can reproduce the published comparison from pinned inputs, see the adapter rejection and its regression behavior, and cannot submit live host data or trigger operations.

## Community contribution loop

Community data should improve the common dataset and evaluation suite for all candidate models. It must not become automatic telemetry or a firehose of server logs.

This should be part of the agent project, but split across a local exporter and an external review pipeline. The agent owns a companion export command because it has the verified cycle record and exact operation schemas. The resident daemon does not upload data, ask for a Hugging Face token, or change training labels. Dataset curation, review, release, and training remain maintainer-controlled processes outside the running agent.

1. Keep raw operation traces, prompts, logs, domains, addresses, identifiers, event IDs, and keys on the contributor's host by default. Contribution is opt-in, separate from normal agent operation, and off by default.
2. Implemented in `nostrhost-agent-export`: it accepts one explicitly selected completed cycle, applies conservative local redaction, and writes a review candidate without transmitting data. It preserves operation schemas and leaves the expected decision unlabeled. The candidate is not dataset-ready: a maintainer workflow still needs to validate privacy, evidence, schema conversion, provenance, licensing, and acceptance.
3. Export a model-neutral episode: trigger/request, observations available at the decision point, registered operation schemas, expected proposal or no-call, concise rationale, evidence-backed outcome/verification, scenario family, and provenance/review status. Do not include chain-of-thought or private free-form reasoning. A model's raw proposal is candidate metadata, not a label.
4. The operator submits the reviewed bundle separately, initially through a documented dataset contribution workflow (for example, a pull request). Accept public contributions first as `submitted` candidates, not trusted training rows. A maintainer or qualified reviewer validates redaction, operation availability, the expected decision, and supporting outcome evidence. Reject poisoned, duplicated, unsafe, or unverifiable samples. Keep reviewer identity and public credit optional.
5. Give every accepted episode a stable pseudonymous source reference and group related paraphrases, machines, incident families, and fault scenarios together. A contributor signature can attest origin and consent, but must not be required to expose a real-world Nostr identity publicly.
6. Maintain a versioned public-safe dataset repository on Hugging Face after review. Keep sensitive/uncertain submissions private and delete them on request according to a documented retention policy. Publish dataset cards with schema, collection policy, license, category balance, redaction limits, known bias, and release hashes.
7. Split by source/incident family before any training. Accepted rows may join a train split only after review; frozen evaluation and adversarial holdouts are never open for direct training submissions. Maintain a separate live community benchmark queue so new contributions do not leak into the current test set.
8. Run every accepted dataset release against every supported base and candidate model with the same prompt/tool schema and decoding settings. Publish per-category safety and utility results. This shared benchmark is the primary way a new contribution benefits all models; derive model-specific fine-tuning formats from the same reviewed source records.
9. Use Nostr for contribution announcements, signed review attestations, and pointers to versioned releases if the community wants that integration. Do not publish raw operational data to relays. Define and review any event kinds and consent semantics before implementing a relay-based submission protocol.

Acceptance: the agent's offline exporter lets an operator inspect and explicitly prepare one sanitized episode without network access; the public dataset contains only accepted, licensed, de-identified records; and each release has a reproducible evaluation report for the same set of models. No host sends data by default, and contribution has no effect on a running agent until a new reviewed dataset/model release is deliberately installed.

## Order and release gates

1. Restore access to `nostrhost-clean6`; upgrade and verify core `12.1.41.28` before using it for package acceptance.
2. Implement the daemon's service/config lifecycle and package it as optional, disabled-by-default APT software.
3. Validate clean-install, upgrade, removal, and Observe-mode behavior on the current NostrHost VM.
4. Continue independent episode collection; do not release a model artifact until the corpus, fresh holdout, regression, safety, and license gates pass.
5. Build the Space around public-safe synthetic data and reproducible reports. Connect it to no live host.
6. Finish the maintainer review and dataset intake path for the implemented offline contribution exporter. Publish accepted examples as model-neutral dataset releases and rerun the common benchmark across supported models.

The APT package and Space can be prepared independently of model training. Model publication remains blocked until there is a candidate worth releasing.
