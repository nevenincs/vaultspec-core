---
tags:
  - '#audit'
  - '#diagnosis-surface-parity'
date: '2026-06-28'
modified: '2026-06-28'
related:
  - "[[2026-03-27-cli-ambiguous-states-resolver-adr]]"
  - "[[2026-02-24-vault-doctor-suite-adr]]"
---

# `diagnosis-surface-parity` audit: `diagnosis surface parity: install/sync/doctor drift`

## Scope

Triggered by a concrete contradiction: `spec doctor` reports the provider copy of
`vaultspec-rag.builtin.md` as clean while `sync` reports the same file as needing an
update, and `spec doctor` reports `builtins error deleted` plus `antigravity mixed` on a
freshly reinstalled workspace. The audit covers the three CLI surfaces that each decide,
independently, whether a provider artifact is in sync with its source - `install`,
`sync`, and `spec doctor` (the `core/diagnosis` collectors) - plus the snapshot
lifecycle in `core/revert.py` and the template resolver in `vaultcore/hydration.py`. The
governing decision is the ambiguous-states resolver ADR, which already specified the
intended design; the finding is that the implementation drifted from it.

The audit is a worked instance of a broader concern: where the same decision is made by
more than one body of code, the copies drift. The codebase-wide sweep for that pattern is
tracked separately in the sibling plan.

## Findings

### content-integrity-name-only | critical | doctor compares filenames, sync compares content, so they contradict

`collect_content_integrity` in `src/vaultspec_core/core/diagnosis/collectors.py` decides
a provider rule file is clean when its basename is present in both the source directory
(`.vaultspec/rules`) and the destination provider directory, and stale only when the
basename is absent from the source. It never reads or compares file content. `sync`
routes every file through `apply_file_sync` in `src/vaultspec_core/core/sync.py`, which
compares the full rendered text byte-for-byte and reports `[UPDATE]` on any difference.
Because both read the same source directory but apply different comparison semantics,
they disagree whenever content drifts without the filename changing - exactly the
`vaultspec-rag.builtin.md` case. This directly violates the ambiguous-states resolver
ADR, which specified that content integrity reuse the sync infrastructure and SHA-256
compare the expected transformed output against the actual destination file. The ADR even
defined a `DIVERGED` content signal for "file differs from expected content"; the shipped
collector never emits it, so `DIVERGED` is a dead state and content drift is structurally
invisible to the doctor.

### orphan-snapshots-never-pruned | high | builtin_version reports DELETED forever after a builtin is removed from source

`snapshot_builtins` in `src/vaultspec_core/core/revert.py` copies every live
`.builtin.md` under `.vaultspec/` into `.vaultspec/_snapshots/` at install time but never
removes a snapshot whose source builtin has since been deleted. `list_modified_builtins`
walks the snapshot tree and reports any snapshot with no live counterpart as `missing`,
which `collect_builtin_version_state` maps to `BuiltinVersionSignal.DELETED`. After the
codify phase was removed from the firmware, the six promoted codify-era rules survive only
as orphan snapshots, so the doctor reports `builtins error deleted` permanently with no
in-workspace remedy. No surface owns orphan-snapshot pruning - not install, not sync, not
uninstall.

### mcp-config-foreign-to-doctor | medium | install writes a provider file its own doctor flags as foreign

`mcp_sync` writes `mcp_config.json` (and a `.lock` sibling) into provider directories
such as `.agents/`. `collect_provider_dir_state` classifies any provider-directory child
that is not a known managed path and not in `_HOST_NATIVE_FILES` as foreign, returning
`MIXED`. `mcp_config.json` and `*.lock` are absent from `_HOST_NATIVE_FILES`, so the
diagnosis flags a directory that the framework itself populated. The writer
(`core/mcps.py`) and the checker (`core/diagnosis/collectors.py`) hold two unsynchronised
notions of what files legitimately live in a provider directory.

### install-dry-run-granularity | medium | install --dry-run previews provider artifacts at directory granularity while sync previews per file

`install --dry-run` renders provider targets through `_scaffold_provider`, which emits one
entry per provider directory (for example `claude (rules) = .claude/rules`), because the
install scaffold creates directories and defers file seeding. `sync --dry-run` renders
through `apply_file_sync`, which emits one entry per file. The two previews of overlapping
work therefore disagree in resolution, and the install preview understates blast radius:
an operator reading it cannot see which individual files will be added or updated.

### action-classification-redeclared | medium | codex agents and MCP sync re-implement the add/update decision instead of using apply_file_sync

`apply_file_sync` is documented as "the single place the add/update/unchanged decision is
made," yet `_sync_codex_agents` recomputes `[UPDATE]`/`[ADD]` inline and `mcp_sync` uses
its own JSON-merge-and-write loop with no per-file content comparison at all. These are
two more copies of the sync decision that can drift from the canonical one, the same class
of defect as the doctor's name-only check.

### template-resolver-version-skew | low | a stale global binary silently shadows the editable source and fails template lookup

`vault add audit` failed with "No template found for type 'audit'" when invoked as the
bare `vaultspec-core` on `PATH` (a stale 0.1.34 global install) while the editable source
is 0.1.35. This is environment skew rather than a source defect, but it is the same
failure mode at the tooling layer: two resolvable copies of the program, the older one
shadowing the newer, producing a result that contradicts the source of truth. The
canonical invocation in this workspace is `uv run --no-sync vaultspec-core`.

## Recommendations

- Restore `collect_content_integrity` to the ambiguous-states resolver ADR: compute the
  expected rendered content through the shared sync renderer and compare it (hash or
  bytes) against the destination, emitting `DIVERGED` on content mismatch. The doctor and
  `sync` must answer "is this file in sync" through one comparator, not two.

- Give orphan-snapshot pruning a single owner so `builtin_version` can return to a clean
  state after a builtin is retired, and so the snapshot tree tracks the live builtin set.

- Centralise the "what may legitimately live in a provider directory" registry so the MCP
  writer and the doctor's foreign-file detector read from one list; add `mcp_config.json`
  and its lock sibling.

- Unify the dry-run preview so `install` and `sync` describe provider work at the same
  per-file granularity.

- Fold the redeclared add/update classifications (codex agents, MCP sync) back onto
  `apply_file_sync`, or extract one shared decision helper, so the canonical comparator is
  the only one.

- Treat each of the above as an instance of one root pattern - the same decision made by
  divergent code - and run the codebase-wide drift and centralisation sweep tracked in the
  sibling plan to find the rest before they surface as contradictions.
