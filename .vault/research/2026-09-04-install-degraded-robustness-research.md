---
tags:
  - '#research'
  - '#install-degraded-robustness'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:8b3551d3bd64201669f40c2b2949d609c595835915b1495b0ab7edc2c20cc3e1'
related: []
---

# `install-degraded-robustness` research: `Install and provisioning robustness on degraded workspaces`

GH issue 399 reports that `vaultspec-core install` writes its managed ignore block only into a `.gitignore` that already exists, and does nothing when the file is absent. The report reproduces on `main`. The question this research grounds is not "should the file be created" but "what is the provisioning layer's contract when a managed subject is missing, and how many places currently answer that question differently".

Four defects share one shape: managed state is derived from, and gated on, a snapshot of the workspace taken before the install mutates it. They compound. Fixing only the creation gate would leave a fresh install's block one entry short of what a second run produces, because the entry set is computed from files the install has not written yet. The evidence favours a single contract - the managed block is derived from policy and reconciled to it on every run, never from a transient disk reading - with the ADR to settle whether an absent subject is created, refused loudly, or reported.

## Findings

### R1 - `ensure_gitignore_block` no-ops on an absent file; its sibling creates one

`ensure_gitignore_block()` returns `False` before taking any lock when `.gitignore` does not exist (`src/vaultspec_core/core/gitignore.py:359`). The caller cannot distinguish that from "already correct": both are `False`.

`ensure_gitattributes_block()` in `src/vaultspec_core/core/gitattributes.py:72` faces the identical condition and creates the file, and its docstring names the divergence explicitly ("Unlike `ensure_gitignore_block`, this function creates the file"). The asymmetry is documented but not justified anywhere in the corpus.

Reproduced on `fix/399-gitignore` at commit `3e268c1c`: `ensure_gitignore_block(fresh_dir, ['.vaultspec/'])` returns `False` and writes nothing; the same call against a directory holding a zero-byte `.gitignore` returns `True` and writes the full block. A zero-byte file is the whole difference.

End to end: `vaultspec-core install claude --target <fresh git repo>` completes, prints the sharing-policy statement that runtime by-products "stay local", exits `0`, and leaves `.mcp.json.lock` and `.pre-commit-config.yaml.lock` in the working tree with nothing ignoring them.

### R2 - the entry set is a disk snapshot, so block completeness depends on call ordering

`get_recommended_entries()` (`src/vaultspec_core/core/gitignore.py:170`) enumerates advisory-lock sentinels through `managed_lock_paths()`, which filters `_lock_subjects()` down to subjects where `subject.is_file()` is true at call time (`src/vaultspec_core/core/gitignore.py:115`). A sibling derivation, `managed_lock_candidates()` (`src/vaultspec_core/core/gitignore.py:89`), already returns the full ownership surface regardless of whether the subject exists, and its docstring states that reason for existing.

Measured against a provisioned workspace: with `.gitignore`, `.mcp.json` and `.pre-commit-config.yaml` all present, both derivations return the same three sentinels. Deleting `.mcp.json` drops `/.mcp.json.lock` from `get_recommended_entries()` while `managed_lock_candidates()` is unchanged.

`provision.py:755` computes `recommended` and `provision.py:756` passes it to `ensure_gitignore_block`, which then creates `.gitignore.lock` as a side effect of `advisory_lock`. On a workspace with no `.gitignore`, `/.gitignore.lock` is therefore absent from the very block being written and only appears on a later run. This is the mechanism behind the second symptom the issue flags but does not assert - a block that "stops short until the run is repeated". It is the same root cause as R1, not a separate bug, and it becomes reachable the moment R1 is fixed.

### R3 - `--upgrade` never reconciles the block unless `--force` is passed

`_finalize_upgrade_manifest()` calls `ensure_gitignore_block` only inside `if force:` (`src/vaultspec_core/core/provision.py:407`). A workspace installed without a `.gitignore`, that later gains one, stays unprotected across every subsequent `install --upgrade`.

Reproduced: install into a fresh repo with no `.gitignore` (no block written, per R1), create an empty `.gitignore`, then `install --upgrade` - the file is still empty. `install --upgrade --force` writes the full eleven-entry block. The recovery path exists but nothing tells the reader it is needed, because of R4.

### R4 - the diagnostic classifies the unprotected state as `info`

`collect_gitignore_state()` returns `GitignoreSignal.NO_FILE` for a missing file, and `vaultspec-core doctor` renders it as `gitignore info no_file` and exits `0`. `PARTIAL` - the R2 shape - is the only degraded signal the collector can emit, and it is reached only when a block already exists (`src/vaultspec_core/core/diagnosis/collectors_config.py:249`).

The comparison the collector performs is itself built on R2: `complete` is computed against `get_recommended_entries(target)`, the same disk snapshot the writer used, so a block that is short because its subject did not exist at write time is also judged complete at read time by the same missing subject. The check cannot observe the defect it exists to catch.

### What this changes about the framing

The issue's own suggested fix - create the file, reuse the `atomic_write_bytes` under `advisory_lock` path - is correct and sufficient for R1. It is not sufficient for the install to be trustworthy on a non-scaffolded workspace: R2 makes the first block short, R3 makes it unrecoverable without a flag the reader has no reason to pass, and R4 keeps all three invisible. The four are worth landing together because each one alone leaves a reader with a workspace that reports success and is not protected.

### Option space for the ADR

Three policies are available for an absent managed subject, and the corpus currently contains all three:

- Create it - what `ensure_gitattributes_block` does today, and what the issue proposes. Cheapest, matches the sibling, and removes the platform-split `touch .gitignore` instruction the marketing docs currently open with. Cost: the install writes a file the workspace never asked for.
- Refuse loudly - keep the current behaviour but raise, so the install fails rather than exiting `0`. Honest, but breaks every workspace that has deliberately no `.gitignore`, and no other managed subject behaves this way.
- Report and continue - write nothing, return a distinguishable third state, and surface it as a `warn` in `doctor` and a hint at the end of install. Preserves the current write behaviour and fixes only the silence.

The evidence favours create-it for `.gitignore` specifically, on the grounds of sibling parity and because the block's whole purpose is to keep per-machine artefacts the install itself just wrote out of the reader's first commit. What the ADR must settle is whether that becomes a general contract for managed subjects or stays a per-subject decision, and whether the boolean return of the `ensure_*` family is replaced by a three-state result so callers can tell "created", "already correct", and "declined" apart.

### Not investigated

Whether `provider_sync.py:214` and the `m_0_1_20_gitignore_reversal` migration have their own ordering exposure was not measured; both call `ensure_gitignore_block` and inherit R1 and R2 by construction, but neither was reproduced. Non-git workspaces (no `.git` directory) were not covered - `untrack_managed_paths` runs unconditionally after the block is written and its behaviour there is unverified.

## Sources

- `src/vaultspec_core/core/gitignore.py:89` - `managed_lock_candidates`, full ownership surface
- `src/vaultspec_core/core/gitignore.py:115` - `managed_lock_paths`, `is_file()` filter
- `src/vaultspec_core/core/gitignore.py:170` - `get_recommended_entries`
- `src/vaultspec_core/core/gitignore.py:359` - `ensure_gitignore_block` absent-file early return
- `src/vaultspec_core/core/gitattributes.py:72` - `ensure_gitattributes_block` creates on absence
- `src/vaultspec_core/core/provision.py:407` - upgrade reconciles the block only under `--force`
- `src/vaultspec_core/core/provision.py:755` - `recommended` computed before the block is written
- `src/vaultspec_core/core/diagnosis/collectors_config.py:249` - `PARTIAL` vs `COMPLETE` comparison
- https://github.com/nevenincs/vaultspec-core/issues/399 - the filed report
- Reproductions run against commit `3e268c1c` on branch `fix/399-gitignore`
