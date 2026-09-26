---
tags:
  - '#adr'
  - '#env-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:aa8da25ceb7f3c74ad5865bd4cb3249834ab6a569d18872d7d3d4184013f52a6'
related:
  - "[[2026-09-26-env-parity-research]]"
  - "[[2026-02-16-environment-variable-adr]]"
  - "[[2026-09-23-typesafe-search-adr]]"
  - "[[2026-07-14-install-parity-adr]]"
  - "[[2026-07-13-install-mode-adr]]"
  - "[[2026-05-17-cli-spec-edit-safety-adr]]"
  - "[[2026-02-19-workspace-path-decoupling-adr]]"
---

# `env-parity` adr: `one resolution order, one env-file rule and one install surface, owned by core and imported by every package` | (**status:** `proposed`)

## Problem Statement

The vaultspec packages resolve the same concepts in different ways, and both vaults record rules the code does not follow (`2026-09-26-env-parity-research`). The differences are:

- vaultspec-core and vaultspec-rag apply two different trust models to one workspace `.env`, and a2a applies a third.
- The packages use five boolean vocabularies and two invalid-value policies.
- The same framework concept appears under different variable names, some of which no process reads.
- The shared install flags differ in validation, output, exit codes and unattended detection.

The user directed on 2026-09-26 that:

- both packages install, provision and accept the same flags;
- they read the same framework environment file and resolve the session environment identically;
- one resolution and override order be established and implemented in every project;
- the records that disagree with the code be reworded until code and records agree.

The user also proposed that packages import vaultspec-core's modules as a real, floor-only runtime dependency instead of reimplementing them.

## Considerations

- vaultspec-rag already depends on vaultspec-core at runtime with a floor and no ceiling, and imports it from 21 modules. The drift sits in what rag mirrors (`2026-09-26-env-parity-research`, reuse by import).
- Core's reusable pieces are private or closed to other packages' variables, and `vaultspec_core.config` is too heavy for rag's spawn workers (same research, reuse by import).
- `2026-09-23-typesafe-search-adr` fixed core's credential boundary. Repository content may supply a key but never a setting, and only to a process running from the workspace's own interpreter. No finding weakens that reasoning.
- The rag daemon is host-scoped and serves many roots, so a credential it holds applies to every root it serves (same research, credentials).
- `2026-07-14-install-parity-adr` set the precedent: core owns shared mechanism, rag calls it with its package name, and rag's parity wave is gated on a core release.
- `2026-05-17-cli-spec-edit-safety-adr` removed the hard-coded `zed` editor. Its trust tiers for the editor rungs stand.

## Considered options

**Where the contract lives.**

- **Each package keeps its own implementation, held together by parity tests.** Rejected: that is today's arrangement, and it drifted in every dimension the research measured.
- **A new shared package that both depend on.** Rejected: it adds a third release train for a surface core already owns and rag already imports.
- **Core owns the contract as a public API; every Python package imports it, and each takes core as a real runtime dependency with a floor and no ceiling.** Chosen.

**The workspace `.env`.**

- **Load every variable, as rag's CLI does today.** Rejected: a cloned repository could configure a globally installed tool, and which file is found depends on where the package is installed.
- **Session environment only, no `.env`.** Rejected: it breaks the development-dependency workflow `2026-09-23-typesafe-search-adr` chose to support.
- **Core's gated single-credential reader, extended to every package.** Chosen.

**Invalid values.**

- **Log the error and use the default, core's current policy.** Rejected: a mistyped value silently does nothing.
- **Refuse and report every problem together, rag's current policy.** Chosen, with one fail-safe exception for protective switches.

**The editor chain.**

- **Keep the committed project file above the operator's variable.** Rejected: the shared file would outrank a per-operator setting.
- **The package's own variable above the committed file, and generic conventions below it, as git ranks `GIT_EDITOR` over `core.editor` over `VISUAL` and `EDITOR`.** Chosen.

## Constraints

- **Core's credential boundary.** Everything `2026-09-23-typesafe-search-adr` fixed about core's credential holds: the enrolling name, the interpreter-inside-workspace test, reading one variable, and never logging the key. This record only rewords which mode opens the gate. The mode that opens it is the package's resolved mode, declared or detected. The interpreter test is the trust boundary, because both inputs are repository content.
- **No cross-package enrolment.** A credential never enrols another package. Rag's key does not enrol core, core's does not enrol rag, and the generic `TYPESAFE_API_KEY` enrols neither.
- **Release gating.** The public core API ships in a core release before any package imports it. Each importing package raises its floor to that release and sets no ceiling.
- **Spawn workers.** They import the value vocabulary from a core module with no imports beyond the standard library.
- **Trust prompts.** Trust and consent prompts, such as core's trigger and hook consent, are never answered by a flag or variable.
- **Out of scope.**
  - Rag's tool-mode extras per installation role, because the stdio MCP server can host the service in-process. They stay with the in-flight client-role work and `2026-09-01-gpu-less-install-footprint-adr`.
  - Rag's builtin seeding mirror.
  - The dashboard's Rust readers, which cannot import Python and conform through the CLI and variable names.

## Implementation

**Resolution and override order.** One order holds for every setting of every package, in every process kind (CLI, MCP server, daemon, child process). Earlier rungs win.

1. **Invocation**: a CLI flag, an MCP tool argument, or an explicit programmatic override for that call.
2. **Session environment**: the process environment the process was started with.
   - For a setting the framework shares, the package-scoped name `VAULTSPEC_<PKG>_<NAME>` is read first. The framework name `VAULTSPEC_<NAME>` is read next: this is the chain fallback.
   - Credentials never chain.
3. **Workspace `.env`**: credentials only, under the gate below.
4. **Persisted configuration**: the single store that owns the key.
   - The committed stores are `.vaultspec/config.toml` and `.vaultspec/workspace.json`; the host store is rag's local-only marker.
   - A key has exactly one persisted home, so stores never compete.
5. **Derived and external defaults**:
   - `pyproject.toml` mode detection;
   - a third-party convention with a product equivalent, such as `VISUAL` and then `EDITOR`.
6. **The shipped default**, declared once in the owning registry. A daemon whose output is a managed log may declare its own default log level there.

**Framework-shared variables.** Every package reads these, and each package's scoped overrides fall back to them:

| Framework variable | Package-scoped override that falls back to it |
| --- | --- |
| `VAULTSPEC_TARGET_DIR` | rag's `VAULTSPEC_RAG_ROOT` |
| `VAULTSPEC_LOG_LEVEL` | rag's `VAULTSPEC_RAG_LOG_LEVEL` |
| `VAULTSPEC_STDIO_WATCHDOG` | rag's `VAULTSPEC_RAG_STDIO_WATCHDOG` |
| `VAULTSPEC_NON_INTERACTIVE` | — |
| `VAULTSPEC_NO_HINTS` | — |
| `VAULTSPEC_JSON_PRETTY` | — |

- External conventions (`CI`, `NO_COLOR`, `GIT_INDEX_FILE`, and the Hugging Face and uv variables) keep their owners' meanings.
- Core's CLI reads `VAULTSPEC_TARGET_DIR` and `VAULTSPEC_LOG_LEVEL` as its documentation already says. `-v/--verbose` joins `--debug` on every root callback.

**The framework environment file.** It is `<resolved workspace root>/.env`, with the root resolved by rungs 1 and 2.

- It is never found by walking up from the working directory or from the package's install location.
- No variant (`.env.local` and the like) is read.
- Only a secret registry entry marked for the workspace `.env` is read from it, one name at a time.
- The file opens only when both hold:
  - the running interpreter lives inside the workspace;
  - the package's own resolved install mode for that workspace is dependency or dev.

What changes in rag:

- Rag drops its import-time `load_dotenv()` and its `python-dotenv` dependency.
- Rag's hosted-classifier key and `HF_TOKEN` become credentials eligible for the workspace `.env`.
- The CLI resolves them, and hands them to the daemon it spawns through the child environment. The daemon never reads a `.env`.

An operator-owned settings file (a2a's case) is not repository content. It may supply settings only when the invocation or the session environment names it explicitly, and then it ranks as rung 2. It is never discovered.

**Value interpretation.**

- **Booleans.** One vocabulary: `1`, `true`, `yes` and `on` against `0`, `false`, `no` and `off`, case-folded and stripped.
- **Blank.** A blank value is unset for every product-owned variable and falls through to the next rung.
- **Presence flags.** Product-owned presence flags become booleans: `VAULTSPEC_NON_INTERACTIVE`, `VAULTSPEC_NO_HINTS`, and rag's preprocess kill switch.
- **Invalid values.** An invalid product-owned value refuses the process and names the variable, the value and the expected shape. All problems are reported together.
- **Exception.** A protective switch, today only the stdio watchdog, keeps its protective state and warns.

**What core exposes publicly.**

- A standard-library-only vocabulary module.
- Package registries: a package declares its variables with scope, secrecy, `.env` eligibility and framework fallback, and gets `env_value`, `child_environment` and `resolve_credential` for them. `resolve_credential` takes the package's name for its mode gate.
- Workspace-root resolution over rungs 1 and 2.
- Log-level resolution.
- Unattended detection.
- The install envelope and hint rendering.

Rag deletes its mirrors of each and imports them. a2a promotes core from its tooling group to a runtime dependency to do the same. Core adds a contract test that pins the API those packages import.

**The shared install surface.** A flag present in more than one package has the same name, short form, default and meaning. A package-specific flag never reuses a shared name.

- **Shared root options:** `-t/--target`, `-d/--debug`, `-v/--verbose`, `-V/--version`.
- **Shared on install:**
  - `--upgrade`: refresh everything install owns, idempotently, re-inferring the mode through one core function;
  - `--dry-run`;
  - `--force`: overwrite only, never consent;
  - `--skip`: validated, and an unknown value errors with the valid list;
  - `--mode`;
  - `--json`, in the core envelope;
  - `--no-hints`.
- **`-y/--yes`** answers configuration prompts only, and exists only where a package has one.
- **Uninstall without `--force`** errors in every package and points at `--dry-run`.
- **Unattended detection is one rule:**
  - `CI` or `VAULTSPEC_NON_INTERACTIVE`;
  - a non-TTY standard input or output;
  - or `--json`.

  An unattended run never prompts. A configuration step it skips for lack of consent is reported as skipped, naming the flag that enables it.
- **Exit codes** are shared: 0 success, 1 failure, 2 completed with a required step skipped.
- **Package extensions stay:** core's `PROVIDER` argument and `--remove-vault`; rag's provisioning flags, `--remove-data` and data-path options.

**Record reconciliation.** Each record the research lists as contradicting the code is amended in its own vault with a dated note. The amendment points at this record, or corrects the claim to what the code does.

## Rationale

Importing wins because the research located the drift in exactly the pieces rag mirrors, while the pieces it imports (mode resolution, MCP rendering, the vault kernel) agree. The floor-only runtime dependency the user proposed already exists for rag. What was missing is a public core API worth importing, a floor that names it, and a test that keeps it stable without a ceiling. A contract test in core replaces the ceiling: a change that would break an importer fails in core's own gate before release.

The single-credential `.env` gate wins because it is the only option that serves the development-dependency workflow without letting repository content reconfigure a tool. Extending it unchanged, rather than inventing a second rule, is what makes "the same framework environment file" true. Rejecting invalid values wins because silent defaults are the failure `2026-02-16-environment-variable-adr` was written to end, and rag already runs this policy in production. Ranking the package's own variable above the committed file follows the one widely known precedent, git's editor chain, and keeps shared files from overriding an operator.

## Consequences

**Gains.**

- One order, one vocabulary, one `.env` rule and one flag contract.
- Records and documentation that match the code.
- Rag loses a runtime dependency.
- The package-relative `.env` load, which reached a user's home directory from a tool install, is gone.
- Core's documented `VAULTSPEC_TARGET_DIR` and `VAULTSPEC_LOG_LEVEL` start working on the CLI.

**Behaviour changes to announce.**

- Core refuses invalid values it used to ignore.
- Blank rag booleans fall to their defaults instead of off.
- `VAULTSPEC_NON_INTERACTIVE=0` now means interactive.
- `VAULTSPEC_EDITOR` outranks the committed editor key.
- The default editor is `vi` everywhere.
- Rag's `--force` no longer implies consent.
- Rag's uninstall without `--force` errors instead of previewing.
- Rag's install and uninstall `--json` switch to the core envelope.
- Settings a user kept in a workspace `.env` for rag stop applying; only credentials do. This is the intended closing of the boundary.

**Costs.**

- A core release gates the rag and a2a waves.
- Core's public API becomes a compatibility surface with a contract test.
- A daemon holds the credentials of the session that started it, for every root it serves. This matches today's inheritance, and is now stated.
- a2a's settings move out of the workspace `.env` into an explicitly named operator file. That is a change of operating model for a2a, confirmed before its wave executes.

**Pathways.**

- The dashboard can adopt the framework names through the CLI.
- Later packages inherit the contract by importing it.
