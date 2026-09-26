---
tags:
  - '#plan'
  - '#env-parity'
date: '2026-09-26'
tier: L3
related:
  - '[[2026-09-26-env-parity-adr]]'
  - '[[2026-09-26-env-parity-research]]'
  - '[[2026-09-23-typesafe-search-adr]]'
  - '[[2026-07-14-install-parity-adr]]'
modified: '2026-09-26'
body_schema: body-v2
body_hash: 'sha256:007a51787be87b46e91590123875a9ac104a3cd6c7c0b2ea7f082baada562c2e'
---

# `env-parity` plan

Make every vaultspec package resolve settings, env files and credentials in one order and expose one install surface, owned by vaultspec-core and imported rather than mirrored.

## Description

Approved 2026-09-26. The user approved `2026-09-26-env-parity-adr` and this plan in session ("approve!"), in reply to a request that named both and the a2a operating-model change gated by `W03.P09.S40`. Pushing branches, opening pull requests and cutting releases stay separate outward-facing actions confirmed when reached.

This plan executes `2026-09-26-env-parity-adr`, grounded by `2026-09-26-env-parity-research`. The ADR governs every Wave:

- **W01** gives vaultspec-core the public contract:

  - the resolution order and the chain fallback;
  - one value vocabulary and reject-on-invalid;
  - the per-package workspace `.env` credential gate;
  - root, log-level and unattended resolution;
  - the install envelope.

  Core's own CLI and MCP server are brought onto it in the same Wave.

- **W02** deletes vaultspec-rag's mirrors of that contract and imports it. vaultspec-core stays a floor-only runtime dependency, as it already is.

- **W03** does the same for vaultspec-a2a, and pins the dashboard's core calls to their target.

- **W04** aligns the site-authored guides.

`2026-09-23-typesafe-search-adr` and `2026-07-14-install-parity-adr` constrain W01 and W02: the credential boundary holds unchanged, and a rag parity wave is gated on a core release.

Two of the record rewordings the user asked for on 2026-09-26 were made before approval, under that direct instruction: `W01.P03.S13` in this vault and `W02.P08.S36` in the vaultspec-rag vault. They are logged when execution begins.

## Steps

## Wave `W01` - vaultspec-core public contract and core conformance

Give vaultspec-core a public, importable implementation of the one resolution order, the chain fallback from package-scoped to framework variables, the single value vocabulary, reject-on-invalid, the gated workspace .env credential reader opened per package, workspace-root, log-level and unattended resolution, and the shared install envelope; bring core's own CLI and MCP server onto it; correct core's example file, docs and records; and pin the public surface with a contract test. Grounded by the env-parity ADR. This wave ships in a vaultspec-core release that gates waves W02 and W03.

### Phase `W01.P01` - shared vocabulary, registries and the gated credential reader

Add the public, standard-library-only value vocabulary, open core's registry accessors to package registries with a framework fallback, open the workspace .env gate per package, and move core's own call sites and loaded fields onto one vocabulary and reject-on-invalid.

- [x] `W01.P01.S01` - Add a standard-library-only public vocabulary module: the true and false word tables, a parser that treats blank as unset, and the one rejection message naming variable, value and expected shape; `src/vaultspec_core/env_values.py`.
- [x] `W01.P01.S02` - Let a package declare its own registry of ConfigVariable entries, add a framework_fallback field that chains a package-scoped entry to a shared VAULTSPEC\_ entry, and make env_value and child_environment accept any registered package entry; `src/vaultspec_core/config/config.py`.
- [x] `W01.P01.S03` - Add a package parameter to resolve_credential so the workspace .env opens on that package's resolved install mode, keeping the interpreter-inside-workspace test and the one-variable read; `src/vaultspec_core/config/credential.py`.
- [x] `W01.P01.S04` - Move the per-site switch readings onto the shared vocabulary, turning VAULTSPEC_NON_INTERACTIVE and VAULTSPEC_NO_HINTS into booleans and keeping the stdio watchdog fail-safe; `src/vaultspec_core/cli/rendering_hints.py`.
- [x] `W01.P01.S05` - Reject invalid loaded-field values, reporting every problem together, instead of logging and using the default; `src/vaultspec_core/config/config.py`.
- [x] `W01.P01.S06` - Test the vocabulary, the chain fallback, blank-as-unset, collective rejection and the per-package credential gate against real files in temporary workspaces; `src/vaultspec_core/config/tests/test_resolution.py`.

### Phase `W01.P02` - core CLI and MCP server conformance

Route core's own entry points through the public resolution functions: workspace root, log level, editor ladder, unattended detection, legacy upgrade inference and the install envelope, all importable by other packages.

- [x] `W01.P02.S07` - Add a public workspace-root resolver ranking the invocation, then VAULTSPEC_TARGET_DIR, then discovery, and use it from the CLI and the MCP server; `src/vaultspec_core/cli/_target.py`.
- [x] `W01.P02.S08` - Add -v/--verbose to the root callback and honour VAULTSPEC_LOG_LEVEL when neither --debug nor --verbose is given, rejecting an unknown level name; `src/vaultspec_core/cli/root_app.py`.
- [x] `W01.P02.S09` - Resolve every editor use through one ladder, flag then VAULTSPEC_EDITOR then the committed config key then VISUAL then EDITOR then vi, and declare vi as the registry default; `src/vaultspec_core/core/local_config.py`.
- [x] `W01.P02.S10` - Expose unattended detection publicly outside the CLI package: CI or VAULTSPEC_NON_INTERACTIVE, a non-TTY standard input or output, or --json; `src/vaultspec_core/config/session.py`.
- [x] `W01.P02.S11` - Expose legacy upgrade-time mode inference as one public function taking a package name, so rag stops keeping its own variant; `src/vaultspec_core/core/install_mode.py`.
- [x] `W01.P02.S12` - Expose the install and uninstall envelope and hint rendering for reuse by other packages, and document the shared exit codes 0, 1 and 2; `src/vaultspec_core/cli/rendering_outcomes.py`.

### Phase `W01.P03` - core records, examples, documentation and the contract test

Correct the example file and documentation to the contract, record the reconciliation of core's records that contradicted the code, pin the public surface other packages import, and run the full gate before release.

- [x] `W01.P03.S13` - Amend the core records that contradict the code: environment-variable, typesafe-search, workspace-path-decoupling, cli-spec-edit-safety, install-mode and install-parity; `.vault/adr/2026-02-16-environment-variable-adr.md`.
- [x] `W01.P03.S14` - State the resolution order and the workspace .env credential rule in the example file, and stop pointing at .env.local; `.env.example`.
- [ ] `W01.P03.S15` - Document the resolution order, the framework variables and the chain fallback in the CLI guide and the bundled reference, including every registry entry; `docs/CLI.md`.
- [ ] `W01.P03.S16` - Add a contract test pinning the public names and signatures other packages import for resolution, credentials, unattended detection and the install envelope; `src/vaultspec_core/tests/test_public_resolution_api.py`.
- [ ] `W01.P03.S17` - Run core's full gate and cut the release that gates W02 and W03; `src/vaultspec_core`.

## Wave `W02` - vaultspec-rag conformance by import

Delete rag's mirrors of the shared contract and import them from the released core: drop the package-relative load_dotenv and python-dotenv, resolve rag's credentials through core's gate with package vaultspec-rag and hand them to the daemon it spawns, chain VAULTSPEC_RAG_ROOT, VAULTSPEC_RAG_LOG_LEVEL and VAULTSPEC_RAG_STDIO_WATCHDOG to the framework names in every process kind, and align the shared install and uninstall flags, envelope, exit codes and unattended detection. Grounded by the env-parity ADR. Executes only after W01 is released and rag's floor names that release, and after the unmerged client-role install branch lands, since both touch the install torch flow.

### Phase `W02.P04` - release gate

Block the wave on a released vaultspec-core that carries W01, raise rag's floor to it with no ceiling, and rebase onto the landed client-role install change.

- [ ] `W02.P04.S18` - Block on the vaultspec-core release carrying W01, then raise rag's vaultspec-core floor to it with no ceiling and refresh the lock; `pyproject.toml`.

### Phase `W02.P05` - env file, credentials and value vocabulary

Remove the package-relative dotenv load and its dependency, declare rag's variables as a core package registry with credentials and framework fallbacks, resolve credentials through core's gate and pass them to the daemon, and interpret every value with core's vocabulary.

- [x] `W02.P05.S19` - Remove the import-time load_dotenv call and drop python-dotenv from the runtime dependencies; `src/vaultspec_rag/cli/_core.py`.
- [ ] `W02.P05.S20` - Declare rag's variables as a core package registry: the classifier key and HF_TOKEN as workspace-.env-eligible credentials, and ROOT, LOG_LEVEL and STDIO_WATCHDOG chained to the framework names; `src/vaultspec_rag/config/_types.py`.
- [ ] `W02.P05.S21` - Resolve rag's credentials in the CLI through core's gate with package vaultspec-rag and hand them to the daemon it spawns through the child environment; `src/vaultspec_rag/cli/_process.py`.
- [ ] `W02.P05.S22` - Read the classifier key through the registry accessor rather than a bare environment lookup; `src/vaultspec_rag/search/_typesafe_transport.py`.
- [ ] `W02.P05.S23` - Replace the mirrored boolean table with core's vocabulary, treat a blank boolean as unset, and make the preprocess kill switch a boolean; `src/vaultspec_rag/_env_values.py`.
- [x] `W02.P05.S24` - Drop the base-config rung that never matches a rag key from the settings chain; `src/vaultspec_rag/config/_settings.py`.
- [ ] `W02.P05.S25` - Declare the stray production reads (uv cache and tool dirs, the MPS fallback, the junction and preprocess markers, the memory probe literal) as registry members; `src/vaultspec_rag/config/_types.py`.

### Phase `W02.P06` - root, log level, watchdog and unattended detection

Resolve the workspace root, log level and stdio watchdog through the framework chain in the CLI, the stdio MCP server and the daemon, and decide unattended runs with core's detector.

- [ ] `W02.P06.S26` - Resolve the root as invocation, then VAULTSPEC_RAG_ROOT, then VAULTSPEC_TARGET_DIR, then discovery, through core's resolver in the CLI and the MCP roots; `src/vaultspec_rag/cli/_app.py`.
- [ ] `W02.P06.S27` - Apply the log-level chain in the CLI, the stdio MCP server and the daemon, keeping INFO as the daemon's declared default; `src/vaultspec_rag/logging_config.py`.
- [ ] `W02.P06.S28` - Chain the stdio watchdog switch to VAULTSPEC_STDIO_WATCHDOG, keeping its fail-safe reading; `src/vaultspec_rag/server/_stdio_lifetime.py`.
- [ ] `W02.P06.S29` - Decide unattended installs with core's detector, so CI, VAULTSPEC_NON_INTERACTIVE, non-TTY output and --json never prompt; `src/vaultspec_rag/cli/_install.py`.

### Phase `W02.P07` - shared install and uninstall surface

Make every flag rag shares with core carry the same name, short form, default and meaning, emit core's envelope and exit codes, and infer the legacy upgrade mode through core.

- [ ] `W02.P07.S30` - Add --no-hints and VAULTSPEC_NO_HINTS, and emit core's envelope for install and uninstall under --json, errors included; `src/vaultspec_rag/cli/_install.py`.
- [x] `W02.P07.S31` - Validate --skip against rag's component set and fail on an unknown value with the valid list; `src/vaultspec_rag/commands/_install.py`.
- [x] `W02.P07.S32` - Stop --force from implying consent to the torch configuration prompt; consent comes only from --yes; `src/vaultspec_rag/commands/_torch_flow.py`.
- [x] `W02.P07.S33` - Make uninstall without --force an error pointing at --dry-run, and retire the no-op uninstall --yes behind a deprecation warning; `src/vaultspec_rag/commands/_uninstall.py`.
- [ ] `W02.P07.S34` - Infer the legacy upgrade mode through core's public function with package vaultspec-rag and delete rag's variant; `src/vaultspec_rag/commands/_mode.py`.
- [x] `W02.P07.S35` - Make server doctor honour --target and the root chain instead of the working directory; `src/vaultspec_rag/cli/_service_doctor.py`.

### Phase `W02.P08` - rag records, documentation and parity tests

Record the reconciliation of rag's records, correct the example file and guides, prove parity against the released core, and run the full gate.

- [x] `W02.P08.S36` - Amend the rag records that contradict the code: typesafe-classifier, test-and-paths, vaultspec-rag-install, mcp-service-client and index-drift-hardening; `.vault/adr/2026-09-21-typesafe-classifier-adr.md`.
- [ ] `W02.P08.S37` - Correct the example file header and the configuration, installation and CLI guides to the contract, including the resolution order and the .env credential rule; `docs/configuration.md`.
- [ ] `W02.P08.S38` - Add parity tests: rag resolves the framework variables and chain as core does, reads no .env outside the gate, and its shared install flags match core's help surface; `src/vaultspec_rag/tests/test_env_parity.py`.
- [ ] `W02.P08.S39` - Run rag's full gate and cut the release; `src/vaultspec_rag/tests`.

## Wave `W03` - vaultspec-a2a and vaultspec-dashboard conformance

Bring the other two packages onto the contract: a2a imports core's resolver as a runtime dependency, reads only registered credentials from the workspace .env under core's gate and takes settings from an explicitly named operator file, and launches core's MCP server under its current script name; the dashboard passes its target explicitly to the core CLI and stops documenting a variable it never reads. Grounded by the env-parity ADR. Executes after W01 is released and after the user confirms the a2a operating-model change the ADR names.

### Phase `W03.P09` - vaultspec-a2a conformance

Gate on the user's confirmation of the a2a operating-model change, then take core as a runtime dependency, read only registered credentials from the workspace .env under core's gate, take settings from an explicitly named operator file, and fix the stale MCP script name.

- [x] `W03.P09.S40` - Block on the user's confirmation that a2a settings move from the workspace .env to an explicitly named operator file; `src/vaultspec_a2a/control/settings_base.py`.
- [ ] `W03.P09.S41` - Promote vaultspec-core from the tooling group to a runtime dependency with a floor on the W01 release and no ceiling; `pyproject.toml`.
- [ ] `W03.P09.S42` - Read only registered credentials from the workspace .env through core's gate, and load settings from an operator file named by the invocation or session environment; `src/vaultspec_a2a/control/settings_base.py`.
- [x] `W03.P09.S43` - Launch core's MCP server as vaultspec-core-mcp instead of the retired vaultspec-mcp script name; `src/vaultspec_a2a/providers/_harness_mcp_registry.py`.

### Phase `W03.P10` - vaultspec-dashboard conformance

Keep the dashboard's core CLI calls pinned to the worktree it inspects now that the CLI honours VAULTSPEC_TARGET_DIR, and correct its example file.

- [x] `W03.P10.S44` - Pass --target explicitly on every core CLI invocation so an exported VAULTSPEC_TARGET_DIR cannot redirect the worktree being inspected; `engine/crates/ingest-core/src/runner.rs`.
- [x] `W03.P10.S45` - Correct the example file: no .env.local, and name the variables the dashboard actually reads; `.env.example`.

## Wave `W04` - documentation site alignment

Align the site-authored installation, requirements and MCP guides with the released contract: the resolution order, the workspace .env credential rule, the framework variable names an unmanaged MCP client should set, and where HF_TOKEN must be present for the service. Grounded by the env-parity ADR. Executes after W02 ships, against the released packages.

### Phase `W04.P11` - site-authored guides

Rewrite the site-authored pages that describe settings, credentials and MCP launch environments against the released packages.

- [ ] `W04.P11.S46` - Add the resolution order, the framework variables and the workspace .env credential rule to the installation guide; `docs/source/core/installation.md`.
- [ ] `W04.P11.S47` - Point the unmanaged MCP client example at the framework root variable and state what the session environment must carry; `docs/source/guides/mcp.md`.
- [ ] `W04.P11.S48` - State where HF_TOKEN must be present for the service and that a workspace .env supplies it only under the gate; `docs/source/requirements.md`.

## Parallelization

**W01 must be released before anything that imports it.**

- W01 lands first, and its closing Step cuts the vaultspec-core release.
- Within W01:
  - `W01.P01` precedes `W01.P02`, whose resolvers build on the registry and vocabulary.
  - `W01.P03`'s documentation Steps can run alongside `W01.P02`.
  - The contract test and the gate close the Wave.

**W02 and W03 both wait on that release and then run in parallel.** They touch different repositories.

- W02 also waits on the unmerged vaultspec-rag client-role install branch, because both change the install torch flow.
- `W02.P05` precedes `W02.P06` and `W02.P07`, which may then run in parallel.
- `W03.P09` waits on its confirmation Step. `W03.P10` does not, and can start as soon as W01 is released.

**W04 runs last**, against released packages.

## Verification

**Behaviour.**

- The same process environment gives the same answer in both packages. That covers:

  - the root, from `VAULTSPEC_TARGET_DIR` alone and with `VAULTSPEC_RAG_ROOT` set;
  - the log level;
  - the watchdog;
  - unattended detection.

  Tests in each repository run against the released core.

- No rag process reads any `.env` outside core's gate. A test places `.env` files above the install location and in the working directory, and shows that neither is loaded.

- A workspace `.env` supplies a credential only when the running interpreter lives inside the workspace and the package's resolved mode is dependency or dev. It never supplies a setting.

- An invalid product-owned value refuses to start the process and names the variable. The watchdog is the one exception.

- `python-dotenv` is absent from rag's runtime dependencies. Rag's floor names the W01 release and carries no ceiling.

**Surfaces.**

- Every flag the install and uninstall verbs share carries the same name, short form, default and meaning. The `--help` comparison test passes.
- `--json` output uses core's envelope in both packages, and the exit codes follow the shared 0, 1, 2 table.

**Records and gates.**

- Every record listed in `2026-09-26-env-parity-research` as contradicting the code carries a reconciling amendment.
- `vaultspec-core vault check all` passes in both vaults.
- Each repository's full gate passes, and a cohesive review of the whole plan signs off.
