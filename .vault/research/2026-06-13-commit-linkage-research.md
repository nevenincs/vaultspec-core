---
tags:
  - '#research'
  - '#commit-linkage'
date: '2026-06-13'
modified: '2026-06-13'
related: []
---

# `commit-linkage` research: `opt-in commit-linkage trailer convention`

GitHub issue #159 proposes an opt-in convention for carrying vaultspec identifiers in
git commit metadata - a trailer such as `Vaultspec-Step: W01.P02.S06` or
`Vaultspec-Feature: <tag>` - that tooling can emit and validate for teams that adopt it.
Tooling that correlates commits to vault records must otherwise do so heuristically
(shared paths, time windows, same-day co-activity) and grade each correlation by
confidence; an explicit identifier in the commit resolves that correlation
deterministically. The hard design constraint is that this is enrichment, never a
prerequisite: absence lowers a downstream tool's confidence but breaks nothing. This
research grounds the identifier formats, the gap in git tooling, and the two available
deployment paths against the live code.

## Findings

### No commit-message handling exists today

`pyproject.toml` declares no git library; git interaction is subprocess-only and limited.
`src/vaultspec_core/core/commands.py` shells out to `git ls-files` and `git rm --cached`
at install time. `src/vaultspec_core/config/workspace.py` walks for `.git` (file or dir,
including linked-worktree pointers) to discover the repo root but never reads history.
`src/vaultspec_core/core/gitignore.py` and `gitattributes.py` manage marked blocks in
those files. There is no commit-message reading, no trailer parsing, and no commit-to-doc
correlation anywhere in `src/`; the one near-miss is a human-readable
`git commit -m "..."` hint string emitted after `vault check all`. All of the trailer
emit and validate logic would therefore be new code.

### The identifier formats a trailer would carry

Plan container identifiers are defined in `src/vaultspec_core/plan/identifiers.py` by the
pattern `^[SPW]\d{2,}[a-z]?$` (Steps take no suffix; Phases and Waves may carry a single
lowercase suffix letter from stable insertion). `src/vaultspec_core/plan/display_path.py`
composes the dot-joined display path, tier-dependent: `S06` at L1, `P02.S06` at L2, and
`W01.P02.S06` at L3 and L4. A `Vaultspec-Step:` trailer carries that display path; its
validation regex is `^(?:W\d{2,}\.)?(?:P\d{2,}[a-z]?\.)?S\d{2,}$`, with the phase-only
form `^(?:W\d{2,}\.)?P\d{2,}[a-z]?$`.

### The feature-tag format, and a missing shared validator

The feature tag is validated inline as `^[a-z0-9][a-z0-9-]*$` (kebab-case) in both
`src/vaultspec_core/cli/vault_cmd.py` and `src/vaultspec_core/mcp_server/vault_tools.py`;
the stored frontmatter form carries a leading `#`. A `Vaultspec-Feature:` trailer carries
the tag with the `#` optional, validated as `^#?[a-z0-9][a-z0-9-]*$`. No shared
feature-tag validator exists yet - the regex is duplicated inline - so a trailer module
would either reuse a newly extracted helper or carry its own copy.

### Two hook systems exist; neither speaks git commit-msg

There are two distinct, deliberately separate hook systems. The vaultspec lifecycle hook
engine (`src/vaultspec_core/hooks/engine.py`, CRUD in `src/vaultspec_core/core/hooks.py`,
CLI under `spec hooks` in `src/vaultspec_core/cli/spec_cmd.py`) fires on a frozen set of
three events - `vault.document.created`, `config.synced`, `audit.completed` - none of
them a git event, so it cannot host a commit-msg hook without inventing a new event and a
`.git/hooks/` writer. The developer toolchain hook system is `.pre-commit-config.yaml`
(run via `prek`, already a dev dependency), whose hooks are `repo: local` entries calling
`uv run ...`; one existing hook (`block-manual-changelog`) already reads git state with
`git diff --cached`. There is no `commit-msg`-stage hook today.

### Where the convention and verbs would live

The trailer format and its parse/format/validate helpers would live in a new
`src/vaultspec_core/plan/trailer.py`, mirroring the `display_path.py` and
`identifiers.py` siblings. The CLI verbs (validate a commit message file, emit a trailer
for a given step or feature) would attach under the existing `vault plan` Typer app in
`src/vaultspec_core/cli/plan_cmd.py`, following the established `add_typer` sub-group
pattern. For optional automated validation, the lowest-friction deployment is a new
`.pre-commit-config.yaml` entry with `stages: [commit-msg]` calling a
`vault plan trailer validate` verb, which a prior repo ADR
(`2026-03-22-clci-release-adr`) already floated; a heavier alternative writes a script
directly into `.git/hooks/commit-msg`. Either way the hook must be advisory: a missing or
malformed trailer is reported, never fatal, to honor the enrichment-not-prerequisite
constraint.
