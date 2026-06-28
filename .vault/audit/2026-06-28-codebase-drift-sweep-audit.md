---
tags:
  - '#audit'
  - '#codebase-drift-sweep'
date: '2026-06-28'
modified: '2026-06-28'
related:
  - "[[2026-06-28-codebase-drift-sweep-plan]]"
  - "[[2026-06-28-diagnosis-surface-parity-audit]]"
---

# `codebase-drift-sweep` audit: `codebase drift sweep: findings and dispositions`

## Scope

A codebase-wide sweep for the root pattern the diagnosis-surface-parity audit exposed -
the same decision made by divergent bodies of code, which drift into contradiction. Five
parallel RAG-led, rg-confirmed discovery passes covered the plan's five phases: decision
logic duplication, source-of-truth registry duplication, lifecycle ownership gaps,
preview-versus-apply parity, and version/tooling shadowing. This document records every
confirmed finding and its disposition (fixed now, deferred, different-by-design, or
guarded). The discovery agents were instructed to be exhaustive; the triage judgment -
which flagged items are genuine duplications worth collapsing versus legitimately distinct
operations - is the substance here.

## Findings

### registry-provider-vocabulary | medium | provider sets and the provider-to-tool map were hand-listed in three places

`VALID_PROVIDERS`, `SYNC_PROVIDERS`, and `_PROVIDER_TO_TOOLS` in
`src/vaultspec_core/core/commands.py` each independently enumerated the provider names, and
`src/vaultspec_core/cli/spec_cmd.py` re-derived the provider-to-tool mapping with a fourth
hand-written if/elif chain. Adding a provider meant editing four sites; missing one would
silently desync install, sync, and the doctor's provider filter. FIXED:
`_PROVIDER_TO_TOOLS` now derives its per-tool entries from the `Tool` enum, `VALID_PROVIDERS`
and `SYNC_PROVIDERS` derive from that map, and the CLI filter reads the same map. One source
of truth; a registry-consistency test guards the derivation.

### lifecycle-mcp-config-unowned | medium | the provider-native MCP config was not claimed by artifact collection

`_collect_provider_artifacts` in `src/vaultspec_core/core/gitignore.py` claimed each
provider's directory and config file but not its `mcp_config_file` (e.g. Antigravity's
`.agents/mcp_config.json`), which `mcp_sync` writes. It survived only because that file
happens to sit under a directory removed wholesale on uninstall - fragile for any future
provider whose MCP config lives elsewhere. FIXED: the collector now appends
`cfg.mcp_config_file`, so per-provider uninstall and gitignore reconciliation own it
explicitly. This also closes the writer/checker split the diagnosis-surface-parity audit
flagged.

### decision-logic-mostly-distinct | low | the flagged sync-decision duplications are legitimately different operations, not the canonical-comparator violation

The P01 sweep flagged `_sync_codex_agents` (`core/agents.py`), `_sync_managed_md` /
`_sync_managed_toml` (`core/config_gen.py`), `_apply_mcp_merge` (`core/mcps.py`),
`_sync_supporting_files` (`core/sync.py`), and the provider-hooks dual-file writer as
re-implementing the add/update decision. On inspection these are not the bug the
diagnosis-surface-parity audit was about. Each performs an operation `apply_file_sync` does
not: managed-block upsert that preserves user content outside the block (config_gen, codex),
per-entry JSON merge with ownership tracking (mcp), byte-copy of supporting assets with no
per-file action reporting (supporting files), and coordinated native+sidecar writes
(provider hooks). Their only overlap with the canonical comparator is a small
compare-and-write tail; folding it would require signature changes and action-label
normalisation for low correctness payoff. The one genuine canonical-comparator violation -
the doctor's name-only content check - was already fixed in the diagnosis-surface-parity
work. DISPOSITION: different-by-design; left as-is. If a shared compare-and-write tail
helper is later extracted, it should normalise the `[UPDT]`/`[SKIP]` labels config_gen
emits to the canonical `[UPDATE]`/`[UNCHANGED]` vocabulary.

### lifecycle-mcp-prune-conservative | low | stale managed MCP entries are pruned only under --force

`_apply_mcp_merge` prunes managed entries whose source file was removed only when
`prune=True` (wired to `--force`), so retiring a builtin MCP definition leaves its
`_vaultspecManaged` entry in `.mcp.json` until a forced sync. Unlike the snapshot prune
(now unconditional), this is a deliberate conservative default on a file that can carry
user-authored entries. DISPOSITION: deferred - changing the default to prune managed-only
orphans is a policy decision worth its own ADR, not folded into this sweep.

### parity-clean | low | every destructive verb's dry-run faithfully matches its apply

The P04 sweep checked every `--dry-run` verb (install, upgrade, sync, uninstall, vault
feature archive/unarchive/rename, plan mutators, vault add, link add/remove, rule promote,
mcp sync) and found no preview/apply parity defects: no verb writes during dry-run, item
sets and granularity match, and no apply-only branch is skipped in preview. The install
directory-versus-file granularity defect was already fixed in the diagnosis-surface-parity
work. The only nit: `rule promote` always reports "created" even when `--force` overwrites
an existing rule - a cosmetic status-label inaccuracy, not a parity defect. DISPOSITION:
class is clean; the rule-promote label nit is noted, not fixed here.

### shadowing-guarded-or-environmental | low | the shadowing surfaces are already guarded or are environment issues

The P05 sweep found the deployed-copy-versus-source surfaces mostly guarded: the generated
CLI reference is gated by `spec reference generate --check` plus a byte-fidelity test; the
builtins mirror has `check_outdated` drift detection; the template legacy-filename fallback
is a scheduled-for-removal grace path with a runtime warning. Two residual items: templates
participate in `check_outdated` but not the `.builtin.md` snapshot/revert mechanism (an
asymmetry, not a live bug), and a stale global `vaultspec-core` binary on `PATH` can shadow
the editable source - an environment issue, not source-fixable, whose remedy is the
canonical `uv run --no-sync vaultspec-core` invocation. DISPOSITION: guarded / doc-only; no
code change warranted.

## Recommendations

- Keep the provider vocabulary single-sourced: any new provider is added to the `Tool` enum
  and flows to `_PROVIDER_TO_TOOLS`, `VALID_PROVIDERS`, `SYNC_PROVIDERS`, and the CLI filter
  automatically; the consistency test fails loudly if a fourth copy reappears.

- If the conservative managed-MCP prune default is revisited, do it through an ADR that
  weighs orphan accumulation against the risk to user-authored `.mcp.json` entries.

- Treat the decision-logic finding as the campaign's main lesson: "the same decision in two
  places" is only a defect when the surrounding operation is the same. The doctor was; the
  upsert/merge/dual-file writers are not. Future sweeps should triage on operation identity,
  not surface similarity.
