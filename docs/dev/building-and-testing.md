# Building and testing

NostrHost is an umbrella repository. It contains documentation, packaging,
schemas, integration tests, and a set of Git submodules. Each submodule is a
separate Git repository with its own build and test commands.

This page explains how to get a complete checkout, work safely inside a
submodule, test each component, and verify the top-level repository.

## What you need

Install the tools required by the component you are changing:

- Git with submodule support;
- Python 3.11 or newer and `uv` for Python components;
- the Go version named in each component's `go.mod` file;
- Node.js and Yarn 1 for the Portal and Admin interfaces; and
- Debian packaging tools only when building `.deb` packages.

VM and installer testing needs additional virtualisation and ISO-building
tools. Do not install every tool if you are changing only one component.

## Get a complete checkout

Clone the umbrella repository and all submodules together:

```bash
git clone --recurse-submodules <repository-url>
cd nostrhost
```

If you already cloned without submodules, initialise them afterwards:

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

Check what is present:

```bash
git submodule status --recursive
```

The first character on each line is meaningful:

- a space means the submodule is at the commit recorded by the parent;
- `-` means it has not been initialised;
- `+` means it is checked out at a different commit; and
- `U` means it has an unresolved merge conflict.

A submodule normally opens at a detached commit. That is expected for a pinned
checkout. Create or switch to a component branch before making commits.

## Decide where a change belongs

| Area | Repository |
|---|---|
| Native CLI, API, operations, providers, package engine | `forks/yunohost` |
| User Portal | `forks/portal` |
| Admin dashboard | `forks/admin` |
| Installer image tooling | `forks/installer` |
| Identity and login library | `libs/nostrhost-auth` |
| Roles, scopes, approvals, and redaction | `libs/nostrhost-policy` |
| App catalogue | `libs/nostrhost-catalog` |
| Local relay and notification daemon | `libs/nostrhost-control` |
| Resident AI assistant | `libs/nostrhost-agent` |
| Native MCP adapter | `libs/nostrhost-mcp` |
| Compatibility MCP bridge | `libs/yunohost-mcp` |
| Nsite gateway | `libs/nostrhost-nsite` |
| Package graph, integration, schemas, testbeds, docs | top-level repository |

Run tests from the component directory unless a command below explicitly says
to run from the repository root.

## Work inside a submodule

Before editing, inspect the component and switch to the correct branch:

```bash
git -C libs/nostrhost-auth status -sb
git -C libs/nostrhost-auth switch main
```

Use the branch named in `.gitmodules` or the component's contribution rules.
Do not invent a shared branch name, and do not force a branch switch over local
work.

After making a change:

1. Run that component's focused tests.
2. Run its complete test and build checks.
3. Commit and publish the component commit.
4. Return to the top-level repository.
5. Review the changed submodule pointer with `git diff --submodule=log`.
6. Run the relevant integration and package checks.
7. Commit the new pointer in the top-level repository.

For example:

```bash
git -C libs/nostrhost-auth status -sb
git -C libs/nostrhost-auth diff --check
git diff --submodule=log
git status --short
```

The parent repository stores only the component commit ID. Other contributors
cannot use a pointer to a component commit that has not been pushed to its own
repository.

Do not run `git submodule update` while a submodule contains uncommitted work;
it may move the checkout away from the commit you were editing. Commit, stash,
or otherwise protect that work first.

## Python library tests

The identity and policy libraries use `uv` and pytest:

```bash
cd libs/nostrhost-auth
uv sync --all-groups
uv run pytest -q
```

```bash
cd libs/nostrhost-policy
uv sync --all-groups
uv run pytest -q
```

The two MCP components use the same workflow:

```bash
cd libs/nostrhost-mcp
uv sync --all-groups
uv run pytest -q
```

```bash
cd libs/yunohost-mcp
uv sync --all-groups
uv run pytest -q
```

The compatibility MCP repository is deliberately conservative. Avoid adding
new platform behaviour there; test compatibility fixes against both its fake
fixtures and a real test host when the change touches server calls.

## Core server tests

The core fork depends on the local identity and policy libraries. From
`forks/yunohost`, run the NostrHost-specific suite with those source trees on
`PYTHONPATH`:

```bash
PYTHONPATH=src:../../libs/nostrhost-policy/src:../../libs/nostrhost-auth/src \
  python -m pytest -c /dev/null tests_nostr/ -q
```

Install the dependencies declared in `pyproject.toml` before running the
suite. The CI workflow uses Python 3.12 and editable installs of the two local
libraries.

Run static checks for core changes:

```bash
ruff check src bin doc maintenance
ruff format --check --diff src bin doc maintenance tests tests_nostr
mypy src
```

The legacy `tests/` suite exercises behaviour inherited from YunoHost and may
expect Debian packages, root privileges, or host services. Run it in the
supported Debian test environment rather than weakening tests or swallowing a
failure on a normal workstation:

```bash
python -m pytest tests -q
```

Changes to operations, permissions, providers, backup, web routing, or service
management also need integration or VM testing; the Python suite alone does
not prove that system changes work.

## Go component tests

The catalogue, control plane, agent, and nsite gateway use standard Go
commands. Each component's `go.mod` records the required toolchain.

```bash
cd libs/nostrhost-catalog
go test ./...
go build ./...
```

```bash
cd libs/nostrhost-control
go test ./...
go build -buildvcs=false ./cmd/nostrhost-control
```

```bash
cd libs/nostrhost-agent
go test ./...
go build ./cmd/nostrhost-agent
go build ./cmd/nostrhost-agent-export
go build ./cmd/nostrhost-agent-model
```

Run the agent's deterministic interruption and safety scenarios after changing
its cycle, policy, execution, journal, or recovery behaviour:

```bash
go test ./agent -run '^TestFaultEvaluation$' -v
```

Run the nsite suite against the shared conformance corpus:

```bash
cd libs/nostrhost-nsite
NSITES_CORPUS=../../tools/tests/nsites/corpus go test ./...
go build -buildvcs=false ./cmd/nostrhost-nsite
```

The relative corpus path above is correct when the component is checked out as
this repository's submodule. A standalone clone can set `NSITES_CORPUS` to an
absolute path instead.

## Portal checks

The Portal has lint, branding, and production-build checks. It does not
currently define a general unit-test script.

```bash
cd forks/portal
yarn install --frozen-lockfile
yarn lint
yarn test:branding
yarn build
```

For login, passkey, and app-launch changes, also run the browser testbed
described in [`testbed/e2e/README.md`](../../testbed/e2e/README.md).

## Admin checks

The Admin app lives one level below its submodule root:

```bash
cd forks/admin/app
yarn install --frozen-lockfile
yarn lint
yarn type-check
yarn test
yarn build
```

Run a focused Vitest file while developing, then run the complete commands
above before updating the parent pointer.

## Installer checks

The installer submodule is an ISO-building tool rather than an ordinary app
test suite. At minimum, check its Python entry point and help output in an
isolated environment:

```bash
cd forks/installer
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python udib.py --help
```

A meaningful installer change must also build an ISO and boot it in a VM. Test
both the attended error path and the unattended installation path. Never use a
physical machine containing data you care about.

## Top-level tests and package checks

Run repository-level Python contract tests from the root:

```bash
python -m pytest tools/tests -q
```

Validate the Debian package graph after changing package names, dependencies,
compatibility rules, or meta-packages:

```bash
packaging/scripts/verify-dependencies
```

The check confirms that internal dependencies resolve, the graph has no cycle,
the server meta-packages contain the expected components, the resident agent
remains optional, and compatibility declarations agree.

When the core operation catalogue changes, verify that the resident agent's
generated catalogue snapshot is current:

```bash
python libs/nostrhost-agent/scripts/generate_operation_registry.py \
  --fork-src forks/yunohost/src \
  --output libs/nostrhost-agent/agent/catalog_generated.go \
  --check
```

If this check reports a stale file, regenerate it without `--check`, review the
Go diff, then run the core and agent suites. Do not hand-edit the generated
catalogue.

## What `scripts/verify-clean.sh` checks

`scripts/verify-clean.sh` verifies the four upstream-derived components under
`forks/`: core, Portal, Admin, and installer. It checks that:

- each submodule exists;
- tracked files have no unstaged changes;
- its `HEAD` matches the `pin_commit` in `baseline/pins.yml`; and
- components marked source-identical have not diverged from the named upstream
  tag.

Derivative components are allowed to differ from upstream, but they must still
be at the exact recorded derivative commit.

Run the normal check from the repository root:

```bash
scripts/verify-clean.sh
```

Release and baseline validation should use strict mode:

```bash
scripts/verify-clean.sh --strict
```

Strict mode also fails if a source-identical upstream tag has moved away from
the recorded commit. Checking a remote tag may need network access.

The script does **not** test code, build packages, or inspect library submodules
under `libs/`. Its current dirty-tree check uses `git diff`, so staged and
untracked files require a separate `git status --short` check. It intentionally
fails when a checked fork has unstaged tracked changes. During development, run
it after the fork change is committed and the top-level pin has been updated.

## Understand a `verify-clean` failure

| Message | Meaning | Safe response |
|---|---|---|
| `missing submodule checkout` | The component was not initialised | Run `git submodule update --init` after protecting local work |
| `working tree has uncommitted changes` | A tracked file inside the fork has an unstaged change | Review and commit or stash it; also use `git status --short` to find staged or untracked files |
| `HEAD ... != pinned ...` | The checkout and `baseline/pins.yml` disagree | Confirm the intended component commit, then update the pin through the normal pin workflow |
| `committed changes beyond the tag` | A source-identical fork diverged | Investigate the unexpected commit; do not rewrite the pin to hide it |
| `recorded pin differs from current tag` | The remote tag no longer resolves to the recorded commit | Investigate upstream provenance before changing anything |

Do not fix a failure with `git reset --hard` or by editing `pins.yml` until you
understand whether the local commit or recorded pin is authoritative.

## Choose the right test depth

| Change | Minimum evidence |
|---|---|
| Documentation only | Link check and `git diff --check` |
| One Python or Go library | Focused test plus full component suite |
| Portal or Admin UI | Lint, type checks where available, tests, production build |
| Operation schema or policy | Core, policy, agent catalogue, and affected interface tests |
| Package dependency | Dependency verifier and affected package build |
| Service unit, permissions, networking, Caddy, or CrowdSec | Package install and VM test |
| Backup, restore, update, or first-run setup | End-to-end VM test including failure and recovery |
| Installer | Build an ISO and boot it in a disposable VM |

Use a VM when correctness depends on systemd, Debian packaging, root-owned
files, firewall behaviour, network ports, or a clean-machine transition.

## Before committing the parent repository

From the root, review:

```bash
git status --short
git diff --check
git diff --submodule=log
```

Confirm that:

- every changed component commit is published;
- tests appropriate to each change passed;
- generated catalogues and schemas are current;
- package metadata is updated when required;
- no private keys, credentials, VM disks, build output, or user data were
  added; and
- the top-level submodule pointer is intentional.
