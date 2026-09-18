# Contributing

Contributions from people and AI-assisted workflows are welcome. You can help
with code, tests, documentation, design, packaging, translations, bug reports,
or careful review.

NostrHost is split across several repositories. The most important first step
is putting a change in the component that owns it.

## Before you start

For a small, self-contained fix, you can open a pull request directly. For a
change that affects public behaviour, several components, security boundaries,
package formats, or stored data, begin with an issue or short design discussion
in the relevant repository. Early discussion helps avoid implementing the
right idea at the wrong layer.

Read:

1. [Architecture overview](architecture-overview.md) to understand the
   boundaries.
2. [Building and testing](building-and-testing.md) for checkout and test
   commands.
3. The README in the component you intend to change.

## AI-assisted contributions are welcome

You may use an AI coding assistant for exploration, implementation,
refactoring, tests, documentation, or review. AI assistance is not a reason to
reject a contribution, and you do not need to apologise for using it.

The contributor remains responsible for the result. Before submitting
AI-assisted work:

- read and understand every changed line;
- remove invented APIs, commands, files, and assumptions;
- run the same tests expected for a hand-written change;
- check error paths, permissions, data loss, and recovery behaviour;
- make sure generated prose describes the code that actually exists;
- preserve copyright and licence obligations;
- remove prompts, scratch files, model output, and unrelated rewrites; and
- never give an assistant private keys, credentials, production logs, user
  data, recovery files, or other secrets.

If AI produced a substantial part of the change, mention that briefly in the
pull request and explain how you reviewed and tested it. Prompt transcripts and
chat logs are not required. Reviewers care about provenance when it affects
licensing, and about the evidence that the final change is understood and
correct.

Do not submit a large, unreviewed AI-generated patch and ask maintainers to
discover what it does. A smaller change with a clear explanation and reliable
tests is much easier to accept.

## Choose the correct repository

### Use the umbrella repository for

- product and cross-component documentation;
- Git submodule pointers and baseline records;
- Debian package definitions and compatibility rules;
- the native app schema and example packages;
- release and repository scripts;
- integration and VM testbeds; and
- changes that coordinate several already-implemented components.

The umbrella repository should not become a second home for component code.

### Use a fork under `forks/` for

| Component | Change belongs here when it affects… |
|---|---|
| `forks/yunohost` | Core server behaviour, CLI, API, operations, providers, users, apps, domains, backup, or diagnosis |
| `forks/portal` | End-user sign-in, account pages, app launcher, or Portal experience |
| `forks/admin` | Administrator dashboard, forms, operation views, or Admin experience |
| `forks/installer` | ISO creation or unattended Debian installation |

These repositories began as upstream YunoHost components. A generally useful
bug fix that is not specific to NostrHost should be suitable for upstream when
possible. NostrHost identity, policy, event, resource-engine, and interface
changes normally belong on the NostrHost derivative branch.

### Use a library under `libs/` for

| Component | Responsibility |
|---|---|
| `nostrhost-auth` | Nostr identities, signature checks, challenges, and identity lookup |
| `nostrhost-policy` | Roles, capabilities, delegation, approval, audit, and redaction |
| `nostrhost-catalog` | App declarations, publishers, trust, attestations, and catalogue projection |
| `nostrhost-control` | Local relay, event validation, relay policy, and notification daemon |
| `nostrhost-agent` | Resident assistant, model boundary, cycle engine, verification, and agent audit |
| `nostrhost-mcp` | Native MCP transport and generated tool exposure |
| `nostrhost-nsite` | Nsite resolution, verification, caching, and gateway serving |
| `yunohost-mcp` | Compatibility bridge for the older YunoHost-facing MCP surface |

`libs/yunohost-mcp` is a compatibility reference. Do not add new NostrHost
platform logic there. Add native operations to the core registry and expose
them through `nostrhost-mcp` instead.

## Changes that cross repositories

Split a cross-component feature along ownership boundaries. For example, a new
administrative action may need:

1. an operation and schema in `forks/yunohost`;
2. policy support in `libs/nostrhost-policy`;
3. a generated agent-catalogue update in `libs/nostrhost-agent`;
4. an Admin interface change in `forks/admin`; and
5. updated submodule pins, package versions, compatibility metadata, and docs
   in the umbrella repository.

Open component pull requests first. Link them to each other and state the order
in which they should merge. The umbrella pull request should pin published
component commits; it should not point to commits that exist only on a local
machine.

Keep compatibility while the pull requests are landing when practical. If an
interface must change incompatibly, update the compatibility rules and explain
the safe upgrade order.

## Branch conventions

The parent checkout pins a commit, so a submodule often starts in detached
`HEAD` state. Before committing, switch to the component's maintained branch or
create a feature branch from it.

The recorded component branches are:

| Component | Maintained branch |
|---|---|
| Core fork | `nostrhost` |
| Portal and Admin forks | `dev` |
| Installer | `main` |
| Native libraries | `main` |
| Compatibility MCP library | `master` |

Check `.gitmodules`, `baseline/pins.yml`, and the component repository before
branching because branch policy can change.

Use a short, descriptive feature-branch name. A namespace such as
`fix/login-loop`, `feature/backup-check`, or `<username>/backup-check` is fine
unless the component repository specifies another convention. Do not commit a
feature directly on a shared release or maintained branch unless you are the
maintainer performing that release.

Base the branch on the component's current recorded commit or agreed target
branch. Do not silently update unrelated submodules while creating a feature
branch.

## Pin conventions

The umbrella repository records component versions in two places:

- the Git submodule pointer records the exact commit to check out; and
- `baseline/pins.yml` records the component, branch, upstream baseline, and
  expected commit.

For the four upstream-derived forks, the submodule pointer and `pin_commit`
must agree. Native libraries also have recorded commits in the baseline file,
even though `scripts/verify-clean.sh` currently checks only the forks.

When advancing a component:

1. merge or publish the component commit;
2. check out that exact commit in the submodule;
3. update the matching `pin_commit` and any package version or compatibility
   entry;
4. review `git diff --submodule=log`;
5. run the component tests and top-level checks; and
6. commit the pointer and metadata together in the umbrella repository.

Do not edit a pin simply to silence a verification failure. Confirm that the
new commit is intentional, available remotely, tested, and compatible.

`scripts/pin-forks.sh` changes checkouts to recorded fork pins and stages the
related top-level paths. Protect local work before running it. The `--update`
form is a maintainer operation for deliberate baseline changes, not a routine
way to prepare a contributor branch.

## Commit expectations

A good commit is small enough to understand and complete enough to test.

- Keep one logical change per commit.
- Use a short imperative subject that names the area, such as
  `policy: reject expired delegations`.
- Explain why the change is needed when the reason is not obvious from the
  diff.
- Include tests with the behaviour they protect.
- Keep generated output in the same commit as its source change and state how
  it was generated.
- Separate mechanical formatting or generated-file churn from behavioural
  changes when that improves review.
- Do not combine an unrelated submodule bump, dependency update, or document
  rewrite with a focused fix.
- Do not commit secrets, production data, build output, local environments,
  model weights, VM disks, or editor state.

Preserve useful authorship when incorporating another person's commit. Do not
copy code from a source whose licence is incompatible or unclear.

## Tests expected before a pull request

Run the narrow test while developing and the complete affected component suite
before submission. Then run the relevant top-level checks.

At minimum:

```bash
git diff --check
git status --short
git diff --submodule=log
```

Use [Building and testing](building-and-testing.md) to choose the rest. Changes
to networking, service units, privileges, installation, updates, backup, or
recovery need a Debian VM test. UI changes need lint, type checks where
available, tests, a production build, and screenshots or a short recording.

If you cannot run an expected test, say exactly which test was not run and why.
Do not report a test as passing when it was skipped, mocked beyond the changed
boundary, or allowed to fail.

## Pull request expectations

Open the pull request in the repository containing the implementation. A useful
description answers:

- What problem does this solve?
- Why does the change belong in this component?
- What behaviour changes for users or operators?
- What are the security, privacy, compatibility, and recovery effects?
- How was it tested?
- Which related component or umbrella pull requests are required?

Include, when relevant:

- before-and-after screenshots for UI changes;
- sample input and output for a protocol or schema change;
- migration and rollback instructions for stored state;
- package and upgrade-order information;
- documentation updates; and
- a short note about substantial AI assistance and the human review performed.

Keep the pull request focused. Review your own final diff before requesting
review. Remove debugging code, temporary compatibility hacks, unexplained
generated files, and unrelated formatting.

Respond to review by updating the change or explaining the trade-off. Avoid
resolving a technical concern with a pin change or test deletion. New commits
during review are fine; maintainers can decide whether to squash when merging.

## Security-sensitive changes

Changes involving authentication, key handling, permissions, approvals,
network exposure, secrets, backups, or the resident agent need explicit
negative tests. Show that unauthorised input is rejected and that failure does
not leave partial authority or machine state behind.

Do not put a real secret, exploit against a live server, or private user data in
a public issue or pull request. Use the repository's private security-reporting
channel when available, or contact the maintainers before publishing details.

## Documentation expectations

Update the documentation in the same contribution when behaviour changes.

- User tasks belong in `docs/guide/`.
- Server operations belong in `docs/admin/`.
- Contributor workflows belong in `docs/dev/`.
- Stable machine and integration contracts belong in `docs/reference/`.

Write about current behaviour in direct language. Do not make readers follow
internal work notes to understand the feature. Check every command against the
implemented CLI and verify relative links before submitting.

## Ready-for-review checklist

- The change is in the repository that owns the behaviour.
- The branch starts from the intended maintained branch or pin.
- Component commits are published before the parent pointer is updated.
- Commits are focused and explain non-obvious decisions.
- Relevant unit, component, integration, UI, package, or VM tests pass.
- Failure, permission, privacy, and recovery paths were considered.
- Generated files and schemas are current.
- Documentation and examples match the implementation.
- The diff contains no secrets, production data, or unrelated files.
- AI-assisted code has been understood, reviewed, and tested by the submitter.
- The pull request explains dependencies and any tests that were not run.
