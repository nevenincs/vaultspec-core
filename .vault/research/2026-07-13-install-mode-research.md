---
tags:
  - '#research'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
related: []
---

# `install-mode` research: `provisioning as tool versus dependency`

Vaultspec-core is development-harness tooling: it governs a project but is not a
runtime dependency of it, so bundling it into a project's dependency set is the wrong
default design. This research grounds a hardening proposal: make provisioning
explicitly mode-aware (tool versus dependency), persist the chosen mode in workspace
configuration, and default to tool mode - the dev environment operates vaultspec via
the MCP server and has the CLI available as a uv tool, and `vaultspec-core install`
is a provisioning step, not a packaging decision. Two research threads ground this:
an inventory of every place the current provisioning couples the workspace to the
project's own venv, and the tool-mode design space (launch commands, the Windows
exe-lock class, hook entries, version-skew handshakes, ecosystem precedent).

## Findings

### Current coupling surface: dependency mode is baked in, not chosen

Every command path that runs after scaffolding assumes `uv run [--no-sync] vaultspec-core ...` or `uv run python -m vaultspec_core...` resolves inside the
target project's own venv:

- **Scaffolded MCP config.** The builtin definition
  `src/vaultspec_core/builtins/mcps/vaultspec-core.builtin.json` hardcodes
  `{"command": "uv", "args": ["run", "python", "-m", "vaultspec_core.mcp_server.app"]}`.
  The sync pipeline (`core/mcps.py:91` `collect_mcp_servers`, `:358`
  `_apply_mcp_merge`, `:560` `mcp_sync`) copies definitions verbatim - no template
  substitution, no mode branching - into `.mcp.json` and each provider-native config.
- **Pre-commit hooks.** `CANONICAL_ENTRY_PREFIX = "uv run --no-sync vaultspec-core"`
  (`core/commands.py:251`); all four canonical hooks (`core/commands.py:488-508`)
  build their `entry:` from it, `language: system`, resolved by uv from the calling
  repo's own project.
- **Even the drift detector assumes the mode.** `collect_precommit_state`
  (`core/diagnosis/collectors.py:647`) flags `PrecommitSignal.NON_CANONICAL` whenever
  a hook entry deviates from that hardcoded prefix, and the resolver warns "should
  use 'uv run --no-sync vaultspec-core'" (`core/resolver.py:824-836`) - so a
  hand-converted tool-mode workspace would be diagnosed as broken.
- **No pyproject probe.** Install, sync, and doctor never read or write the target's
  `pyproject.toml` and never branch on whether a Python project exists at all. A
  non-Python repo provisions without error, then the hooks and the MCP launch fail
  later at runtime because `uv run` has nothing to resolve `vaultspec_core` from.
  The failure is deferred and opaque rather than surfaced at provision time.

### Persistence: no committed home exists for a shared mode flag

- `.vaultspec/providers.json` (`core/manifest.py:22-58`, `ManifestData`,
  `MANIFEST_VERSION "2.0"`) is per-machine and gitignored - the natural home for
  local install bookkeeping (`installed_at`, `serial`, `provider_state`,
  `vaultspec_version`), and the wrong home for a mode that contributors must share.
- The config system (`config/config.py:78-172`) resolves strictly from explicit
  overrides, then `VAULTSPEC_*` env vars, then dataclass defaults - there is no
  file-backed layer at all, and no committed settings file exists anywhere under
  `.vaultspec/` today (the framework files there are content, not settings).
- Consequence: persisting the mode requires either a new committed settings surface
  under `.vaultspec/`, a new field in the gitignored manifest (per-machine only), or
  both - a shared declaration plus local bookkeeping, mirroring how the ecosystem
  splits committed constraint from local tool state (see precedent below).

### Version-skew machinery that already exists

- `_resolve_version_warning` (`core/resolver.py:846-895`) already compares the
  running package version (`importlib.metadata.version("vaultspec-core")`) against
  `manifest.vaultspec_version` from `providers.json`. It implicitly assumes the CLI
  process and the venv used by hooks and the MCP launch are the same environment -
  exactly the assumption tool mode breaks.
- `BuiltinVersionSignal` (`core/diagnosis/signals.py:48-54`) with the snapshot
  comparators (`core/revert.py:197 list_modified_builtins`) is the existing
  provisioned-versus-live drift detector for `.vaultspec/` content.
- The MCP `status` tool already reports `tool_schema_version` so clients can detect
  a server upgrade - a runtime-reported version, not a persisted provision stamp.
- The resolver (`core/resolver.py`, signal-driven `ResolutionPlan` over
  `WorkspaceDiagnosis`) is the architectural seam where a mode-detection signal
  would plug in alongside the existing manifest, config, and precommit signals.

### Tool-mode launch options for the MCP config

Per the uv docs (docs.astral.sh/uv/concepts/tools/, .../guides/tools/):

- `uvx --from vaultspec-core vaultspec-mcp` - self-contained, cross-platform, runs
  in a cached ephemeral env (fetches on first use, reuses the cache after; a fresh
  resolution only on cache prune, `--refresh`, or an `@latest` pin). The `--from` is
  required because the script name (`vaultspec-mcp`, `pyproject.toml:53`) differs
  from the distribution name.
- Bare `vaultspec-mcp` on PATH after `uv tool install vaultspec-core` - fastest
  launch, but silently breaks for anyone who has not run the install step, and the
  MCP client will not auto-provision it.
- Version pinning exists in both forms: `uvx --from 'vaultspec-core==X.Y.Z' vaultspec-mcp` per invocation, or `uv tool install vaultspec-core==X.Y.Z`
  persistently (with `uv tool upgrade` honoring install-time constraints).
- There is currently no `vaultspec-core <subcommand>` that starts the server; tool
  mode either uses the `vaultspec-mcp` script or module invocation through
  `uvx --from vaultspec-core python -m vaultspec_core.mcp_server.app`.

### The Windows exe-lock class relocates; it does not disappear

The original problem (commit `18d13bc8`, restated in `docs/MCP.md`): MCP clients
hold the console-script exe open, and on Windows that blocked `uv sync` against
`.venv/Scripts/`; module invocation was the fix because `.py` files are never
locked. In tool mode the executable is a copy (not a symlink) under the uv tool bin
dir (docs.astral.sh/uv/reference/storage/), and the same lock class moves to
`uv tool upgrade vaultspec-core` while a client is connected - confirmed upstream as
astral-sh/uv issue 11930. The mitigation also carries over: ephemeral `uvx`
invocation does not touch a persistently installed copy, and module invocation
avoids exe locks entirely in either mode.

### Hook entries in tool mode

With no project venv to resolve against, `uv run` is the wrong verb for hooks.
Three structurally available options:

- `entry: uvx --from vaultspec-core vaultspec-core ...` with `language: system` -
  self-contained, cache-fast after first run, no PATH assumption.
- Bare `entry: vaultspec-core ...` - assumes a prior `uv tool install` and PATH;
  silently breaks for contributors without it.
- `language: python` with `additional_dependencies: ["vaultspec-core==X.Y.Z"]` -
  the ruff precedent (astral-sh/ruff-pre-commit ships `language: python` hooks so
  pre-commit's own isolated env manages the tool); decouples from both PATH and the
  project venv, and pre-commit owns the version pin.

### Ecosystem precedent

- **Committed constraint, local tool state.** pre-commit commits
  `.pre-commit-config.yaml` with `rev:` pins and an optional
  `minimum_pre_commit_version`, never the tool itself. Terraform commits
  `required_version` constraints and refuses to run when the binary does not
  satisfy them. Cargo declares `rust-version` and refuses on older toolchains.
  The shared pattern: a declarative floor constraint committed to the repo, checked
  at the start of every invocation, hard-refuse with a human-directed remediation -
  none of them auto-upgrade, and none persist a "last provisioned version" stamp
  separately from the constraint.
- **Harness ships wiring, never the tool.** husky commits the hook trigger scripts
  while linters stay in devDependencies; ruff-pre-commit pins a wrapper tag rather
  than installing ruff into the consumer's venv; nx warns explicitly when the global
  shim and the local version diverge.
- vaultspec's nearest in-repo analogue for "warn on drift from what was
  provisioned" is the `BuiltinVersionSignal` snapshot pattern, not the floor
  constraint - the two are complementary: a committed floor constraint gates
  invocation, the provision stamp explains what produced the workspace.

### Migration and detection

- This repository itself is dependency-mode and self-hosting (`pyproject.toml:40, 51-53`; every hook entry uses `uv run --no-sync vaultspec-core`), so dependency
  mode must remain a first-class explicit opt-in, and the canonical-entry doctor
  check must become mode-aware rather than assuming one prefix.
- No mode flag, no detection logic, and no tool-mode workspace example exist
  anywhere in the codebase today.
- Detection inputs available at provision time: absence of any `pyproject.toml`
  (tool mode is forced - nothing can resolve a dependency), presence of
  `vaultspec-core` in the target's dependencies or dev group (evidence of
  deliberate dependency mode), and otherwise the default (tool mode) with
  `--mode dependency` as the explicit override.

## Sources

- Coupling inventory: `core/mcps.py:91,358,503,544,560`, `core/commands.py:251, 488-516,531-561`, `core/manifest.py:22-58,69,131`, `config/config.py:78-172, 329-403`, `core/resolver.py:824-836,846-895`, `core/diagnosis/collectors.py:647-671`,
  `core/diagnosis/signals.py:48-54`, `core/revert.py:76,197`, `core/gitignore.py:44`,
  `src/vaultspec_core/builtins/mcps/vaultspec-core.builtin.json`, `pyproject.toml:40, 51-53`, `docs/MCP.md:21-45`, commit `18d13bc8`.
- uv tool semantics: https://docs.astral.sh/uv/concepts/tools/,
  https://docs.astral.sh/uv/guides/tools/, https://docs.astral.sh/uv/reference/storage/,
  https://docs.astral.sh/uv/guides/integration/pre-commit/,
  https://pydevtools.com/handbook/explanation/when-to-use-uv-run-vs-uvx/.
- Windows tool-exe lock upstream: https://github.com/astral-sh/uv/issues/11930.
- Precedent: https://pre-commit.com/,
  https://github.com/astral-sh/ruff-pre-commit,
  https://developer.hashicorp.com/terraform/language/expressions/version-constraints;
  husky and nx characterizations are from general knowledge, not re-verified.
