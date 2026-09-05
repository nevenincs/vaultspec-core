---
tags:
  - '#research'
  - '#managed-block-declaration'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:f6b63afb7dbc869748f9505857fd2a83d8c10c25533204e7eced755f1665149e'
related: []
---

# `managed-block-declaration` research: `Where a managed-block opt-out belongs, and what records it`

GH issue 420 reports that declining the vaultspec-managed `.gitignore` block is recorded in `.vaultspec/providers.json`, a per-machine file that is itself an entry in the block whose deletion it records. The decision cannot survive a clone. The question this research grounds is not only where the flag should live but what a workspace is actually saying when a managed block goes missing, since the same absence currently means four different things across four managed subjects.

The evidence favours moving the record into the committed declaration `.vaultspec/workspace.json`, where the pre-commit opt-out already lives for reasons the codebase states in its own words. What the ADR must settle is whether an explicit verb becomes the gesture that writes it, whether inference survives alongside, and whether the per-subject contract table below is ratified as it stands or normalised.

## Findings

### R1 - The current record is invisible to everyone but the machine that wrote it

`gitignore_opted_out` is a field of `ManifestData` (`src/vaultspec_core/core/manifest.py`), serialised to `.vaultspec/providers.json`. That path is listed in the managed block itself (`src/vaultspec_core/core/gitignore.py:189`), so it is never committed.

The failing sequence is three steps. Teammate A deletes the block and syncs; `_reconcile_gitignore_opt_out` records the opt-out in A's manifest. Teammate B clones and installs; `install_run` sets `gitignore_opted_out = False` unconditionally (`src/vaultspec_core/core/provision.py:784`) and writes the block back. B commits, A pulls, and A's declined block is in A's tree again.

The reversal introduced in the `install-degraded-robustness` work makes this reachable rather than theoretical: before it, the flag did not exist and an absent block was simply never repaired.

### R2 - The codebase has already answered this question, in writing, for the identical shape

`hooks.pre_commit` lives in `.vaultspec/workspace.json`, which is committed. The reasoning is stated in the module rather than inferred: `src/vaultspec_core/core/workspace_mode.py:4-17` says the declaration is the source of truth every contributor and a fresh clone read, while the manifest only echoes it. `src/vaultspec_core/core/precommit.py:449-454` applies it, and the resolver encodes the precedence explicitly at `src/vaultspec_core/core/resolver.py:129-136`: a committed opt-out outranks the per-machine manifest flag.

The dependency direction is not new for the ignore module either. `get_recommended_entries` already reads the declaration (`src/vaultspec_core/core/gitignore.py:230`) to decide whether `/.pre-commit-config.yaml` belongs in the block.

### R3 - `.gitattributes` has the stronger case and the weaker implementation

The default entries are `* text=auto eol=lf` and two batch-file exemptions (`src/vaultspec_core/core/gitattributes.py:23-27`). That is checkout-normalisation policy binding every clone, so a per-machine opt-out is incoherent on its face: one contributor cannot decline line-ending normalisation for a file everyone shares.

Its implementation is also a phase behind. There is no `gitattributes_opted_out` field, so `gitattributes_managed = False` still conflates declined with never-established; `_finalize_upgrade_manifest` never calls `ensure_gitattributes_block` at all (`src/vaultspec_core/core/provision.py:393-435`); and the collector catches `OSError` without `UnicodeDecodeError` (`src/vaultspec_core/core/diagnosis/collectors_config.py:294-298`). Filed as GH issue 410.

### R4 - Four contracts for an absent managed subject coexist, three of them deliberate

| Subject                   | Absent on `sync` | Absent on `install --upgrade` | Opt-out store              |
| ------------------------- | ---------------- | ----------------------------- | -------------------------- |
| `.mcp.json`               | recreated        | recreated                     | none; `--skip mcp` only    |
| `.pre-commit-config.yaml` | stands down      | re-enrolled unless declared   | committed declaration      |
| `.gitattributes`          | stands down      | never reconciled              | manifest, no opt-out field |
| `.gitignore`              | stands down      | reconciled unless opted out   | manifest                   |

`.mcp.json` is a fully derived, team-shared artefact whose absence carries no information, so recreating it is right and no opt-out is needed. `.pre-commit-config.yaml` absence is a policy statement, because a tree-wide hook that rewrites the working tree to the staged state is unsafe where several workers share a checkout. The two git blocks are ambiguous precisely because they live inside files the operator also authors, which is the condition a declaration exists to disambiguate.

### R5 - Inference cannot safely write a committed file

Today the gesture is deletion and `_reconcile_gitignore_opt_out` infers the decision on the next sync. If the record moves to `workspace.json`, that same inference becomes a sync writing a committed, commit-affecting file on the strength of a guess about intent. The `upgrade-convergence` ADR rejects exactly this: silent mutation of host configuration erodes the trust the ownership sidecar exists to protect.

A deleted block is also a plausible merge-resolution accident, which is an argument for the gesture being explicit rather than inferred.

### R6 - The interval between gesture and record is real and currently mute

Measured on a provisioned workspace: delete the block, and `doctor` reports `gitignore warn unmanaged` with exit `1`; run `sync`, and the opt-out is recorded and the row drops to `info no_entries`. The warning row carries no hint text (`src/vaultspec_core/cli/spec_cmd_doctor.py:298-315`), and the reconciler that clears it now logs but does not surface anything at the console. A reader who has deliberately declined the block sees a warning and is told nothing about how to settle it.

### R7 - A verb already exists to copy

`spec precommit disable|enable` writes `hooks.pre_commit` into the declaration; `_set_precommit_policy` (`src/vaultspec_core/cli/spec_cmd_hooks.py:423-477`) is the whole shape, including its idempotence and its exit-zero-when-already-there contract. A `spec gitignore disable|enable` twin is a small amount of new surface built entirely from existing parts.

### R8 - The record this supersedes predates the file it should move into

`2026-03-27-cli-ambiguous-states-gitignore-adr` chose the manifest and also stated that install must not create `.gitignore`. The second half was reversed by the `install-degraded-robustness` ADR, which contradicts it without recording a supersession. `workspace.json` did not exist when the 2026-03-27 record was written, so its choice of store was made from a smaller option space than the one available now.

`_write_document` writes the declaration whole (`src/vaultspec_core/core/workspace_mode.py:589-597`), so a new key has to be threaded the way `hooks` is rather than merged in. The 2.0 reader ignores unknown top-level keys (`src/vaultspec_core/core/workspace_mode.py:51-53`), which suggests an older reader meeting a newer declaration degrades quietly rather than failing; this was not tested against a real older release.

### Option space for the ADR

- **Move the record to the declaration, keep inference as an announced echo.** Deletion still stands the per-machine flag down and says so; only the verb writes the committed key. Two stores coexist, read with the precedence the resolver already applies to pre-commit.
- **Move the record and make the verb the only gesture.** Cleanest single source of truth, but it breaks the documented deletion gesture (`docs/framework.md:21-25`) and the 2026-03-27 contract.
- **Leave the record in the manifest and document the limitation.** Cheapest, and wrong for the reason in R1.

### Not investigated

Whether a companion package writing `workspace.json` through an older release round-trips an unknown key or drops it. Non-git workspaces. Whether `.mcp.json` should gain an opt-out at all, which R4 suggests it should not but which was not pursued.

## Sources

- `src/vaultspec_core/core/gitignore.py:189` - `providers.json` is inside the managed block
- `src/vaultspec_core/core/gitignore.py:230` - the ignore module already reads the declaration
- `src/vaultspec_core/core/provision.py:784` - a fresh install clears the opt-out unconditionally
- `src/vaultspec_core/core/provision.py:393-435` - the upgrade path never reconciles `.gitattributes`
- `src/vaultspec_core/core/workspace_mode.py:4-17` - declaration versus manifest, in the module's own words
- `src/vaultspec_core/core/workspace_mode.py:51-53` - unknown top-level keys are ignored
- `src/vaultspec_core/core/workspace_mode.py:589-597` - whole-document write contract
- `src/vaultspec_core/core/precommit.py:449-454` - the committed opt-out applied
- `src/vaultspec_core/core/resolver.py:129-136` - committed outranks per-machine
- `src/vaultspec_core/core/gitattributes.py:23-27` - the default entries are clone-wide policy
- `src/vaultspec_core/core/diagnosis/collectors_config.py:294-298` - the gitattributes collector's narrow net
- `src/vaultspec_core/cli/spec_cmd_hooks.py:423-477` - `_set_precommit_policy`, the verb to copy
- `src/vaultspec_core/cli/spec_cmd_doctor.py:298-315` - the gitignore row carries no hint
- https://github.com/nevenincs/vaultspec-core/issues/420 - the filed report
- https://github.com/nevenincs/vaultspec-core/issues/410 - the `.gitattributes` lag
- Measurements taken against `main` at `e5bdebea`
