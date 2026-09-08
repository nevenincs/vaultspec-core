# `just init` — worktree initialization

`just init` makes the current worktree usable from a bare checkout. It is the
single command any tool — a person, a git hook, an agent, the worktree
provisioner — calls after creating a worktree. It takes no arguments, asks no
questions, and is always safe to run again.

The recipes:

| Recipe             | What it does                                                  |
| ------------------ | ------------------------------------------------------------- |
| `just init`        | Everything, in dependency order.                              |
| `just init-python` | The Python environment and its locked dependencies.           |
| `just init-node`   | The pinned Node dependency graph.                             |
| `just init-tools`  | Framework enrollment, git hooks, and host-tool diagnosis.     |
| `just init-check`  | Reports whether the worktree is initialized. Mutates nothing. |

## The contract

**Idempotent, and cheap when there is nothing to do.** A phase is skipped when
a digest over its declared inputs — lockfiles, version pins, manifests, and
this package's own source — matches the one recorded in `.venv/.init-stamp.json`
*and* every artifact the phase promised is still present. Both halves matter:
the digest catches a changed lockfile, the artifact check catches a `.venv`
somebody deleted. A no-op run does not invoke `uv`, `npm`, or anything else.

**Fail-fast, and complete in what it reports.** Unlike the fleet's `-all`
aggregates, which run every step because they chain independent inspectors,
`init`'s phases are a dependency chain building one artifact — `init-tools`
runs executables out of the environment `init-python` created. So it stops at
the first failing phase, and records the phases it did not attempt as `skipped`
with the upstream cause named. A non-zero `init` names exactly one cause.

**Machine-readable.** Every run writes `.venv/init-report.json` (or
`.init-report.json` when the environment does not exist yet — the path is
always printed). `VAULTSPEC_INIT_JSON=1`, or `--json`, additionally streams
NDJSON events on stdout while human prose stays on stderr. Exit codes come from
`dev/exit_codes.py` and are identical fleet-wide:

| Code | Meaning                                                                  |
| ---- | ------------------------------------------------------------------------ |
| `0`  | Initialized, or already initialized.                                     |
| `2`  | A required host tool is absent. The report names it and where to get it. |
| `3`  | `init-check` only: the worktree is not initialized, or is stale.         |
| `4`  | A bootstrap step ran and failed.                                         |
| `5`  | Drift: a lockfile no longer matches its project metadata.                |
| `6`  | The environment is held open by another process. Close it and re-run.    |

Code `6` is the one worth knowing by sight. On Windows an editor, an MCP
server, or another agent's session holding a console-script `.exe` under
`.venv/Scripts` makes a dependency install fail in a way that looks like a
build error and is not one. The remedy is to close the process, never to debug
the repository.

**Multiplatform without shell branching.** Each recipe body is a single
command. There are no `[windows]`/`[unix]` recipe pairs and no shell logic,
which is what lets one implementation serve `cmd.exe`, `pwsh` and `sh` alike.

**It provisions the worktree, not the workstation.** `uv`, `just`, `node`,
`rustup` and `mise` are the operator's responsibility; `init` probes for them,
reports the complete list of what is missing with installation URLs, and exits
`2`. It never installs system packages — a bootstrap that does cannot be run on
a machine you do not administer, or in a sandbox.

**Network-heavy optional provisioning is out of scope.** Playwright browser
downloads, RAG model and Qdrant provisioning, and `cargo install` of dev gates
stay behind their own named recipes. `init` restores what the lockfiles pin.

## Layout

Every file here except `plan.py` is byte-identical in `vaultspec-core`,
`vaultspec-rag`, `vaultspec-dashboard`, `vaultspec-a2a` and `cadrumo`.

| File          | Role                                                           |
| ------------- | -------------------------------------------------------------- |
| `contract.py` | Phases, steps, results, the event stream, the report schema.   |
| `process.py`  | Running a step, and classifying its failure into an exit code. |
| `probe.py`    | Host-tool discovery and version comparison.                    |
| `stamp.py`    | Input digests and the idempotence stamp.                       |
| `plan.py`     | **This repository's** phases. The only file that differs.      |

The package imports only the standard library and `dev.exit_codes`. It must
never import `dev.toolchain`, `dev.runner`, or anything reached through
`uv run --no-sync python -m dev`: it runs *before* the virtual environment
exists, on an ephemeral interpreter, which is the whole reason it is separate
from the rest of the harness.

## Adding a step

Edit `plan.py` and nothing else. Add a `Step` to the right phase, and — this is
the part that is easy to forget — add whatever file decides that step's outcome
to that phase's `inputs`, and whatever the step produces to its `artifacts`.
A step whose input is not declared will be skipped after that input changes; a
step whose artifact is not declared will be skipped after somebody deletes it.
