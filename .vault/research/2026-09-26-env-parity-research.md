---
tags:
  - '#research'
  - '#env-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:12159fdd18d613ba7edac7679fcd2b08bb8014218c9b12e2a2b04540475168bf'
related:
  - "[[2026-02-16-environment-variable-adr]]"
  - "[[2026-09-23-typesafe-search-adr]]"
  - "[[2026-07-14-install-parity-adr]]"
---

# `env-parity` research: `environment resolution, env files and install surfaces across the vaultspec packages`

The question: do vaultspec-core, vaultspec-rag and the other vaultspec packages read the same environment variables and env files, resolve them in the same order, and expose the same install, upgrade and uninstall surfaces? They do not. The packages apply two different trust models to one workspace `.env` file. They use five boolean vocabularies and two policies for invalid values. They give different names to the same framework concepts, and some documented variables are never read. The shared install flags differ in validation, output shape, exit codes and unattended detection. Most of the drift sits where vaultspec-rag mirrors vaultspec-core behaviour instead of importing it. Rag already takes core as a runtime dependency with a floor and no ceiling.

Evidence was read at vaultspec-core `89455a12` (its `src/` is identical to `origin/main` `fb56eab1`) and vaultspec-rag `d978f7ec` (`origin/main` `ee062f42` plus an unmerged client-role change to the install torch flow). vaultspec-a2a and vaultspec-dashboard were read at their main worktrees. Core paths below are under `src/vaultspec_core/`, rag paths under `src/vaultspec_rag/`, unless a repository is named.

## Findings

### Env files: two trust models on one workspace

**Core reads one named credential, under a gate.**

- `config/credential.py:164-176` reads the process environment first. It falls back to `<root>/.env` only when both hold:
  - the running interpreter lives inside the workspace (`config/credential.py:95-109`);
  - the resolved install mode is dependency or dev (`config/credential.py:112-133`).
- From that file it reads the one variable its registry entry names (`config/dotenv.py:64-89`). No other dotenv reader exists in core.
- The gate calls `resolve_install_mode(root)`, which runs the full chain (`core/workspace_mode.py:1042-1052`). A mode *detected* from `pyproject.toml` therefore opens the file, not only a declared one. The mode is core's own package entry: there is no parameter for another package.

**Rag loads every variable from whichever `.env` it finds above its own installed files.**

- `cli/_core.py:37-39` calls `load_dotenv()` with no path at import. In `python-dotenv@1.2.3`, `find_dotenv()` starts from the calling file's directory (`vaultspec_rag/cli/`), not the working directory. It walks up to the filesystem root with `override=False` (`dotenv/main.py:361-381,392`). The only exceptions are a REPL, a debugger, a tracer or a frozen app, which use the working directory.
- The effect depends on the install route:
  - a workspace `.venv` (dependency or dev mode) loads the workspace `.env`, whole;
  - a source checkout loads the checkout's `.env`;
  - a uv tool environment loads the first `.env` above the tool directory, which may be one in the user's home directory.
- The effect was confirmed empirically from a foreign working directory.
- Only the CLI imports `cli._core`:
  - the stdio MCP server (`server/_main.py:199-263`) loads nothing;
  - the resident daemon, spawned by `server start` (`cli/_process.py:463-573`), inherits whatever the CLI loaded.
- `python-dotenv>=1.0.0` is a runtime dependency (rag `pyproject.toml`) with no other use.

**vaultspec-a2a loads its project-root `.env` unconditionally.**

- It uses pydantic-settings with the order init, process environment, `<project root>/.env`, then file secrets (a2a `src/.../settings_base.py:207-229`).
- There is no install-mode or interpreter gate.
- The project root comes from `VAULTSPEC_A2A_PROJECT_ROOT`, the nearest `.vaultspec` or `.vault`, `.git`, then the working directory (`settings_base.py:51,147-155`). This is a workspace a2a operates on, so it carries the exposure core's gate was built to close.

**vaultspec-dashboard reads no env file.** Its Rust engine runs the core CLI as a subprocess with the inherited environment and `current_dir` (dashboard `engine/crates/ingest-core/src/runner.rs:226-230`).

**Two example files point at a file nothing reads.** Core's `.env.example:5` and the dashboard's `.env.example` both say to copy to `.env.local`. Rag's `.env.example` says to copy to `.env`.

### Resolution chains as implemented

**Core, loaded fields.**

- Order is override, then `VAULTSPEC_*`, then default (`config/config.py:197-228`).
- An invalid value is logged at ERROR with secrets redacted, and the default is used (`config/config.py:321-403`).
- Three loaded fields have no reader: `antigravity_dir`, `io_buffer_size` and `terminal_output_limit`.

**Core, call-time reads.** Every read goes through `env_value()` with a registry entry, and the registry is total (`config/config.py:810-851`, guarded by `config/tests/test_environment.py`). Each call site applies its own vocabulary (next section).

**Core, editor.** Two defaults exist:

- The edit verbs resolve `--editor`, then `.vaultspec/config.toml`, then `VAULTSPEC_EDITOR`, then `VISUAL`, then `EDITOR`, then `vi` (`core/local_config.py:215-257`). The committed project file ranks above the operator's own variable.
- Interactive creation uses `get_config().editor`, whose default is `zed -w` (`config/config.py:166,509`).

**Rag, settings.** `_raw_rag_setting` resolves in this order (`config/_settings.py:905-953`):

1. CLI overrides, of which only `--data-dir`, `--storage-dir`, `--status-dir` and `--log-file` exist (`cli/_app.py:509-519`).
2. A core base-config attribute of the same name. None exists, so this rung never returns a value.
3. The `VAULTSPEC_RAG_*` variable.
4. The persisted `local-only.json` marker, for `local_only` only (`config/_paths.py:76-101`).
5. The default.

Construction resolves every bounded and boolean key and rejects all invalid values together (`config/_settings.py:959-1012`).

Exceptions to that order:

- `VAULTSPEC_RAG_PREPROCESS=off` beats every source (`config/_settings.py:1059-1061`).
- `--port` resolves through Click `envvar=` (`cli/_service_start.py:207-212`).
- `server start` flags are written into the daemon environment over exported values (`cli/_process.py:358-371`).
- The marker's directory is read from the environment only, so `--status-dir` does not move it (`config/_paths.py:42`).

**Mode.** Both packages resolve `--mode`, then the package's `.vaultspec/workspace.json` entry, then `pyproject.toml` detection, then `tool`, through core (`core/workspace_mode.py:995-1052`; rag `commands/_mode.py:63-88`). The legacy upgrade inference, used when no declaration exists yet, differs:

- core returns dependency only for a `uv run`-shaped hook (`core/install_mode.py:175-179`);
- rag returns the detected dependency or dev mode whenever its MCP entry is present, and its docstring describes a shape check the code does not make (`commands/_mode.py:104-149`).

### Value interpretation

**Booleans.** There are five vocabularies.

- Rag has one table: `1/true/yes/on` and `0/false/no/off`, case-folded and stripped (`_env_values.py:25-59`).
  - Blank reads as false.
  - An unknown word is rejected, except where a reader deliberately fails safe:
    - the stdio watchdog warns and stays armed (`server/_stdio_lifetime.py:97-110`);
    - the offline switches read as online (`config/_types.py:286-289`).
- Rag's ad-hoc readers:
  - `VAULTSPEC_RAG_PREPROCESS` honours only `off` (`config/_settings.py:1059`);
  - `PYTORCH_ENABLE_MPS_FALLBACK` only `1` (`_gpu.py:77`).
- Core applies four per-site rules:
  - `VAULTSPEC_JSON_PRETTY` is off for blank, `0`, `false`, `no` or `off`, and on otherwise (`cli/json_output.py:52,64-65`);
  - `VAULTSPEC_NO_HINTS` needs exactly `1` (`cli/rendering_hints.py:97`);
  - `VAULTSPEC_STDIO_WATCHDOG` is off for `0`, `false`, `off` or `no` (`mcp_server/watchdog.py:53`);
  - `VAULTSPEC_NON_INTERACTIVE` and `CI` count on presence, blank included (`cli/_trigger_trust.py:171`).
- Core's `_parse_bool` accepts `1/true/yes`, not `on`. It is wired only to bool-typed entries, and there are none (`config/config.py:248-259`).

**Blank values.**

- Rag:
  - blank is unset for string settings (`config/_settings.py:928-937`);
  - blank is false for booleans;
  - blank is a parse error for numbers;
  - blank comes back as `""` for the four settings whose default is `None`.
- Core treats a blank credential as unset (`config/credential.py:164`), and a blank presence flag as set.

**Invalid values.**

- Core logs and uses the default.
- Rag refuses to construct its configuration.
- Rag's lenient consumers bend its own rule:
  - an unknown log level logs a warning and uses WARNING (`logging_config.py:820-833`);
  - client timeouts warn and use the default (`serviceclient/_transport.py:405-430`);
  - the Qdrant ready timeout silently uses its default (`qdrant_runtime/_supervise.py:262-282`);
  - unknown noise domains are dropped (`config/_settings.py:537-549`).
- No ADR records either repository's policy.

### Shared concepts under different names, some never read

| Concept | vaultspec-core | vaultspec-rag | Others |
| --- | --- | --- | --- |
| Workspace root | `VAULTSPEC_TARGET_DIR` is honoured only by the standalone MCP server (`mcp_server/app.py:237`). The CLI resolves `--target`, then git or cwd discovery, and never reads the variable (`cli/_target.py:117-152`), although `docs/CLI.md:40-41` and `.env.example:22` say it does. | `--target`, then `VAULTSPEC_RAG_ROOT`, then discovery (`cli/_app.py:534-554`). MCP: the tool's `project_root`, then `VAULTSPEC_RAG_ROOT`, then cwd (`mcp/_roots.py:34-79`). `VAULTSPEC_TARGET_DIR` is not read. | a2a sets both variables on the MCP processes it launches (a2a `providers/_harness_mcp_registry.py:276,312`). The dashboard documents `VAULTSPEC_TARGET_DIR` and reads nothing. |
| Log level | `VAULTSPEC_LOG_LEVEL` is honoured only when no level is passed (`logging_config.py:74-89`). The CLI always passes one (`cli/root_app.py:80-81`), so only the MCP server reads it. An unknown name silently becomes INFO. There is no `--verbose` or `--quiet`. | `VAULTSPEC_RAG_LOG_LEVEL` is read by the CLI when neither `-v` nor `-d` is given (`cli/_app.py:504`). The daemon hard-codes INFO (`server/_main.py:140`), and the stdio MCP server configures nothing. | — |
| Stdio watchdog | `VAULTSPEC_STDIO_WATCHDOG` | `VAULTSPEC_RAG_STDIO_WATCHDOG` | — |
| Hints | `--no-hints` or `VAULTSPEC_NO_HINTS=1`, also suppressed inside git hooks (`cli/rendering_hints.py:80-99`) | None | — |
| JSON indent | `VAULTSPEC_JSON_PRETTY` | Rich pretty-prints always | — |
| Unattended | `CI`, `VAULTSPEC_NON_INTERACTIVE`, non-TTY stdin or stdout, or `--json` (`cli/_trigger_trust.py:36-39,162-176`) | `sys.stdin.isatty()` only (`cli/_install.py:373`). `CI` and `VAULTSPEC_NON_INTERACTIVE` are ignored, and under `--json` with a TTY it still prompts. | — |

### Session environment propagation

- **No MCP entry carries an `env` block.** Core renders none (`core/mcps_mode.py:112-160`), though `core/mcps_native.py:26-98` would pass one through. An MCP server therefore sees exactly the host session's environment.
- **Rag's child processes differ in what they inherit.**
  - The daemon inherits the spawning CLI's full environment, minus `VAULTSPEC_RAG_ROOT`, plus flag translations (`cli/_process.py:358-371`).
  - The Qdrant and preprocess children get allow-lists (`qdrant_runtime/_supervise.py:286-313`, `indexer/_hook_sandbox.py:38-73`).
  - Indexing spawn workers inherit.
- **Core's trigger children** get `VAULTSPEC_TARGET_DIR` and `cwd=target` through `child_environment()` (`triggers/engine.py:406-425`).

### Credentials

- **Core** enrols hosted search only through `VAULTSPEC_CORE_TYPESAFE_API_KEY` (`config/config.py:518-533`). `2026-09-23-typesafe-search-adr` forbids the generic `TYPESAFE_API_KEY` and rag's variable from enrolling core.
- **Rag's hosted-classifier key** is read from `os.environ` on every request, in the daemon (`search/_typesafe_transport.py:71,106`). It reaches the daemon from a `.env` only through the CLI's package-relative load.
- **`HF_TOKEN`** is never read by rag. `huggingface_hub` reads it, and rag names it only in a remediation message (`embeddings.py:423`) and an install warning (`commands/_install.py:1347-1363`).
- **Scope.** The daemon is host-scoped and serves up to 16 roots (`config/_settings.py:305`), so any credential it holds applies to every root it serves.

### Install, upgrade and uninstall surfaces

**Flags that already match.** `-t/--target`, `--upgrade`, `--dry-run`, `--force`, `--skip`, `--mode` and `--json` share a name.

**Flags present in only one package.**

- Core only:
  - the `PROVIDER` positional on install, uninstall and sync (`cli/root_install.py:45-50,332-337`);
  - `--no-hints`.
- Rag only:
  - `-v/--verbose`;
  - `-y/--yes`;
  - the provisioning family: `--torch-config`, `--tool-repair`, `--torch-group`, `--sync`, `--provision`, `--mcp`, `--local-only`, `--skip-torch`, `--skip-models`, `--skip-qdrant` (`cli/_install.py:173-277`);
  - the root data-path options.

**Where the same name behaves differently.**

- **`--skip`.** Core validates it against core, provider names, mcp, hooks and precommit (`core/provider_registry.py:69`). Rag forwards unknown tokens to core's sync inside a try/except, so a typo becomes a warning (`commands/_install.py:592-595,660-683`).
- **`--force`.**
  - Rag's also implies `--yes` for the torch prompt (`commands/_torch_flow.py:68`).
  - Uninstall without it: core errors and exits 1 (`core/uninstall.py:426-429`); rag previews and exits 0 (`commands/_uninstall.py:386-388`).
  - Rag's uninstall accepts `--yes` and ignores it.
- **Data removal.** Core's `--remove-vault` removes `.vault/`; rag's `--remove-data` removes `.vault/data/`.
- **`--upgrade`.** Core re-scaffolds missing directories, runs migrations, re-infers the mode, syncs and migrates the MCP launch shape (`core/provision.py:513-639`). Rag re-seeds with force, re-infers, reconciles the `[mcp]` extra in `pyproject.toml`, and runs torch configuration and provisioning, all idempotent (`commands/_install.py:1094-1270`).
- **Builtins.** Rag does not call core's `seed_builtins`; it mirrors it (`builtins/__init__.py:95-130`). It does call core's `mcp_sync` and `sync_provider`.
- **Output.**
  - Core emits a compact `vaultspec.<verb>.v1` envelope with `status` and `hints` (`cli/rendering_outcomes.py:225-270`).
  - Rag install and uninstall print a raw `report.to_dict()` without `status` (`cli/_install.py:413-418,590-595`). Under `--json` they print errors as plain text.
- **Exit codes.** Core install exits 1 for any failure. Rag exits 2 for TOML, MCP-extra, MCP-sync and tool-repair failures, and for a torch step skipped without a TTY, *after* seeding and sync have been written (`cli/_install.py:406-460`).
- **Doctor.** Rag's `server doctor` reads the mode from `Path.cwd()` and ignores `--target` (`cli/_service_doctor.py:71`).

### Dependencies and extras

- **Rag's declared floor is too low.** Rag declares `vaultspec-core>=0.1.45` with no ceiling, but imports per-package `workspace_mode`, which is newer than that floor. Its lock pins core 0.2.4.
- **Core's dev group** takes vaultspec-rag (locked at 0.4.25) and a CUDA torch pin. The pin is dropped on the unmerged `chore/dependency-audit` branch (`eed7c736`) because nothing in core imports torch.
- **Rag's tool-mode MCP launch spec** is the literal `vaultspec-rag[gpu,mcp]` (rag `builtins/mcps/vaultspec-rag.builtin.json:6`), set by `b2278805`. It is not role-aware: `installed_role` gates only the torch step. A client workspace in tool mode therefore launches through the GPU extra, while dependency and dev modes add only `[mcp]` to the project requirement (`commands/_mcp_extra.py:151-208`).
- **Core** never edits `pyproject.toml`, and its tool spec carries no extra (`core/mcps_mode.py:49-50`).
- **a2a:**
  - declares `rag = ["vaultspec-rag[mcp]>=0.3.8"]`;
  - takes core only in its tooling and freeze groups;
  - runs core as a subprocess;
  - launches core's MCP server as `vaultspec-mcp` (a2a `providers/_harness_mcp_registry.py:296`), a script core renamed to `vaultspec-core-mcp`.

### Reuse by import versus mirroring

Rag already imports core from 21 production modules. The most frequent imports are `vaultcore`, `core.enums`, `graph`, `config`, `core.types`, `core.manifest` and `core.workspace_mode`. The drift is concentrated in what rag mirrors instead:

- the env-file loader;
- the boolean table;
- the root variable;
- unattended detection;
- log-level resolution;
- builtin seeding;
- the JSON envelope.

**What blocks importing core today.**

- **Core's reusable pieces are private or closed to other packages.**
  - Unattended detection lives in `cli/_trigger_trust.py`.
  - `env_value()` and `resolve_credential()` refuse any variable that is not a core registry entry (`config/config.py:803-807`).
  - The credential gate reads core's own package mode.
- **Import cost.** Measured cold with `python -X importtime` on this workstation:
  - `import vaultspec_core` costs about 0.16 s, almost all of it `importlib.metadata`;
  - `vaultspec_core.config` costs about 0.31 s cumulative;
  - rag's stdlib-only `_env_values` costs about 0.01 s.

  `_env_values.py` is stdlib-only because spawn workers re-import their chain. A shared vocabulary must therefore live in a core module with no package-level imports beyond the stdlib.
- **Floor-only risk.** A floor without a ceiling against a 0.x core means any core minor release can change an imported name. No test in either repository pins the core API that rag uses.

### Records that contradict the code

**Core `2026-02-16-environment-variable-adr`** describes a 33-variable registry that does not exist. The live registry has 26 entries (`config/config.py:693-795`). The record also promises:

- `VS_*` aliases, never shipped;
- WARNING-level logging for invalid values, where the code logs at ERROR;
- `_ENABLED` and `_DISABLED` boolean suffixes, used nowhere;
- a `.env.local` setup, which nothing reads.

It assigns rag knobs bare `VAULTSPEC_*` names, contradicting rag's prefix rule.

**Core `2026-09-23-typesafe-search-adr`** says the workspace *declares* the mode. The code gates on the *resolved* mode, detection included.

**Core `2026-02-19-workspace-path-decoupling-adr`** names `VAULTSPEC_ROOT_DIR`, `VAULTSPEC_CONTENT_DIR` and `VAULTSPEC_VAULT_DIR`. None exists.

**Core `2026-05-17-cli-spec-edit-safety-adr`** omits the `VAULTSPEC_EDITOR` rung and claims `zed` was removed.

**Rag `2026-09-21-typesafe-classifier-adr`** says enrolment reads only the dedicated environment variable, with no key in root-controlled configuration. The CLI's package-relative `load_dotenv()` breaks that boundary.

**Rag `2026-04-04-test-and-paths-adr`** requires every read to flow through the settings wrapper and bans string-literal reads. Several production reads are direct literals or undeclared markers:

- `UV_CACHE_DIR`, `UV_TOOL_DIR` (`cli/_gpu_errors.py:76,81`);
- `PYTORCH_ENABLE_MPS_FALLBACK`;
- `VAULTSPEC_JUNCTION_*` (`commands/_mcp_topology.py:878-881`);
- `VAULTSPEC_PREPROCESS_INVOCATION` (`indexer/_preprocess_schema.py:45`).

**Rag `2026-04-12-vaultspec-rag-install-adr`** (proposed) promises "100% CLI flag alignment" with core, which the surface above does not have.

**Neither vault** records the boolean vocabulary or the invalid-value policy that its code applies.

### Documentation that contradicts the code

- **Core `docs/CLI.md:40-41,3399-3406`** and `.vaultspec/reference/cli.md:1008` say `VAULTSPEC_TARGET_DIR` is equivalent to `--target` on the CLI. The reference's variable table omits five variables.
- **Rag `docs/configuration.md:73-74`** says a project `.env` is not loaded for the classifier key. That holds only when rag is installed outside the project.
- **Rag `docs/configuration.md:179`** says the log level is settable by variable; the daemon ignores it.
- **The documentation site** tells unmanaged MCP clients to set `VAULTSPEC_RAG_ROOT` (site `docs/source/guides/mcp.md:280-296`). It also tells users to authenticate "the account that will run the service" with `HF_TOKEN` (site `docs/source/requirements.md:84-85`). Both depend on how the session environment reaches each process, which no page states.

### Not investigated

- a2a's invalid-value behaviour, inferred as pydantic's `ValidationError` and not traced.
- The dashboard's Rust readers beyond listing them.
- Behaviour on macOS and Linux.
- Rich's handling of a blank `NO_COLOR`.
- Why `b2278805` chose `[gpu,mcp]` over `[mcp]` for the tool-mode launch. Its governing record, `2026-09-01-gpu-less-install-footprint-adr`, does not say.

### What the ADR must settle

- One resolution and override order, including where the workspace `.env`, persisted configuration and external conventions rank.
- One `.env` trust rule, and whether package-scoped variables fall back to framework-scoped ones.
- One boolean vocabulary, one blank rule and one invalid-value policy.
- The names shared across packages, and the shared install-surface contract.
- Whether rag, and a2a, import these from a public core API or keep mirroring them. The evidence favours import, given the existing floor-only runtime dependency.

## Sources

**vaultspec-core** (`src/vaultspec_core/`):

- `config/config.py:166,197-228,248-259,321-403,509,518-533,693-795,803-851`
- `config/credential.py:95-176`
- `config/dotenv.py:64-89`
- `core/workspace_mode.py:995-1052`
- `core/install_mode.py:175-179`
- `core/local_config.py:215-257`
- `core/provider_registry.py:69`
- `core/uninstall.py:426-429`
- `core/provision.py:513-639`
- `core/mcps_mode.py:49-50,112-160`
- `core/mcps_native.py:26-98`
- `cli/_target.py:117-152`
- `cli/root_app.py:80-81`
- `cli/root_install.py:45-50,332-337`
- `cli/json_output.py:52,64-65`
- `cli/rendering_hints.py:80-99`
- `cli/_trigger_trust.py:36-39,162-176`
- `cli/rendering_outcomes.py:225-270`
- `logging_config.py:74-89`
- `mcp_server/app.py:237`
- `mcp_server/watchdog.py:53`
- `triggers/engine.py:406-425`
- `.env.example:5,22`
- `docs/CLI.md:40-41,3399-3406`
- `.vaultspec/reference/cli.md:1008`
- commit `eed7c736`

**vaultspec-rag** (`src/vaultspec_rag/`):

- `cli/_core.py:37-39`
- `cli/_app.py:504,509-519,534-554`
- `cli/_install.py:173-277,373,406-460,413-418,590-595`
- `cli/_process.py:358-371,463-573`
- `cli/_service_start.py:207-212`
- `cli/_service_doctor.py:71`
- `cli/_gpu_errors.py:76,81`
- `config/_settings.py:305,537-549,905-1012,1059-1061`
- `config/_paths.py:42,76-101`
- `config/_types.py:286-289`
- `_env_values.py:25-59`
- `_gpu.py:77`
- `logging_config.py:820-833`
- `serviceclient/_transport.py:405-430`
- `qdrant_runtime/_supervise.py:262-313`
- `indexer/_hook_sandbox.py:38-73`
- `indexer/_preprocess_schema.py:45`
- `server/_main.py:140,199-263`
- `server/_stdio_lifetime.py:97-110`
- `mcp/_roots.py:34-79`
- `search/_typesafe_transport.py:71,106`
- `embeddings.py:423`
- `commands/_install.py:592-595,660-683,1094-1270,1347-1363`
- `commands/_uninstall.py:386-388`
- `commands/_mode.py:63-149`
- `commands/_mcp_extra.py:151-208`
- `commands/_mcp_topology.py:878-881`
- `commands/_torch_flow.py:68`
- `builtins/__init__.py:95-130`
- `builtins/mcps/vaultspec-rag.builtin.json:6`
- `docs/configuration.md:73-74,179`
- commit `b2278805`
- `python-dotenv@1.2.3` `dotenv/main.py:361-392`

**vaultspec-a2a**:

- `settings_base.py:51,147-155,207-229`
- `providers/_harness_mcp_registry.py:276,296,312`
- `pyproject.toml:51-54,151,167`

**vaultspec-dashboard**: `engine/crates/ingest-core/src/runner.rs:226-230`.

**Documentation site**:

- `docs/source/guides/mcp.md:280-296`
- `docs/source/requirements.md:84-85`
