---
tags:
  - '#adr'
  - '#cli-spec-gitignore'
date: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-spec-gitignore-research]]'
---

# `cli-spec-gitignore` adr: `Reverse default gitignore policy: spec layer is team-shared` | (**status:** `accepted`)

## Problem Statement

The CLI's default `install` operation writes a managed `.gitignore`
block that hides the layer where authored project rules, skills,
agents, and the synthesised system prompt live (`.vaultspec/`,
`.claude/`, `CLAUDE.md`, `.mcp.json`). A teammate cloning a
vaultspec-managed project inherits its history (`.vault/`) but not
its authored policy. The framework is a paper-trail tool whose
authoritative-policy layer is hidden from teammates by default.

The user identified this as a critical bug. Round 1 finding S5 is
the original observation; the round-3a Bridge Gap analysis
documents its compounding effect on codification.

## Considerations

- Some content under `.vaultspec/` and `.claude/` is legitimately
  per-machine runtime by-product: snapshot directories, lock files,
  provider session caches. A reversed default must remain granular
  enough to keep that excluded.
- The managed block in `.gitignore` is delimited by sentinel
  comments. The install operation already rewrites that block on
  re-run. A migration can rewrite the block in place during the
  next upgrade without manual editing.
- Pre-existing installs will have the old block written into their
  `.gitignore`. The migration must distinguish a user who has
  customised the block from a user running stock.
- Changing the default reframes how the framework communicates its
  own purpose. The install summary's wording becomes load-bearing.
- The reversal must coordinate with the memory-lifecycle ADR
  (codification verb), because authored rules are exactly what
  codification produces. Hiding the destination from git defeats
  the producer.

## Constraints

- Touching `.gitignore` is sensitive territory. Other tools
  (linters, CI, IDE integrations) may have written their own blocks.
  The managed delimiters protect this rewrite; the reversal must
  continue to do so.
- The framework's `--dev` flag (round 1 finding [03]) gates writes
  inside the source repository itself. The reversal must not
  re-include the source-repo's own snapshot directories.
- Existing user-authored rules already on disk in
  `.vaultspec/rules/` of installed projects must be inferred as
  intended-for-sharing; the migration should not delete or rename
  anything, only adjust the gitignore policy.

## Implementation

**Policy split.** Replace the current opaque managed block with two
explicit policies:

- **Shared by default** (commit to git): authored content under
  `.vaultspec/rules/`, `.vaultspec/skills/`, `.vaultspec/agents/`,
  `.vaultspec/system/`, plus `CLAUDE.md` and `.mcp.json` (the
  synthesised system prompt and the MCP server config). Provider
  authored directories under `.claude/rules/`, `.claude/skills/`,
  `.claude/agents/` follow the same shared default.
- **Runtime, gitignored**: `.vaultspec/_snapshots/`,
  `.vaultspec/*.lock`, `.claude/sessions/` (if present),
  `.vault/.obsidian/`, `.vault/.trash/`, `.vault/data/`,
  `.vault/logs/` (unchanged), and any provider-specific session
  cache directory.

**Migration.** Land a versioned migration that rewrites the managed
gitignore block on next `install --upgrade`. Detection logic:

- If the managed block matches the prior stock content exactly,
  rewrite it to the new stock content.
- If the managed block has been edited by the user (does not match
  prior stock), do not rewrite. Print a one-line notice that the
  default policy has changed and the operator should reconcile
  manually.
- The migration is idempotent. Re-running after the rewrite is a
  no-op.

**Install summary language.** After `install` and `install --upgrade` both, print a one-line policy statement under a section
heading "Sharing policy". Example wording:

> `.vaultspec/` (rules, skills, agents, system) and `CLAUDE.md`
> are committed to git so teammates inherit your project policy.
> Runtime by-products (`.vaultspec/_snapshots/`, lock files) stay
> local.

The summary is shown unconditionally on install. On upgrade it is
shown only when the migration above rewrites the block.

**Companion language updates.**

- Framework manual section on "what gets shared with teammates"
  is rewritten to state the new default plainly.
- Builtin rule files that reference `.vaultspec/` as
  framework-local state are updated to describe it as
  project-shared state.
- Agent personas (the synthesised `CLAUDE.md` content) are updated
  to assume that an authored rule will reach teammates on next
  push, so codification is meaningful work and not per-machine
  fiddling.

## Rationale

The audit's round-3a Bridge Gap finding identified codification as
the missing pipeline step. The round-1 S5 finding identified the
gitignore default as the policy-level disincentive against
codification. The two findings are not separate bugs; one is the
cause of the other's irrelevance.

Reversing the default makes authored project policy a first-class
artifact teammates inherit. It is the precondition for the
memory-lifecycle ADR's codify verb to do useful work. Without this
reversal, an agent that promotes a finding into a rule will write
the rule into git-invisible territory.

Granular discrimination (shared vs. runtime) is the choice over
blanket reversal because some content under these directories
genuinely should not be checked in. The managed-block migration
mechanism is the existing infrastructure that makes the change
deliverable without manual operator intervention.

## Consequences

Gains. Teammates inherit project policy on clone. Codification
becomes meaningful. The upgrade verb's authored-content
preservation guarantee becomes visible. The framework's stated
purpose and its install behaviour align.

Difficulties. Migrating existing installs is the work. The
detection logic for user-edited blocks must be conservative; false
positives that overwrite operator-customised blocks would be a
trust-destroying regression. The migration ships as opt-in (runs
on next upgrade) and announces itself in the success line, not
silently.

Pitfalls. Provider directories under `.claude/` may contain
credentials or environment-specific paths in authored agent
prompts; a careless reversal would commit secrets to git. The
shared-by-default policy applies only to the `rules/`, `skills/`,
`agents/`, and `system/` subdirectories of each provider, not the
provider directory wholesale. The migration must enforce this
subdirectory-level granularity.

Pathways. With this ADR landed and the memory-lifecycle ADR
landed, the codify verb has a destination that propagates. The
codify verb without this ADR is theatre; this ADR without the
codify verb fixes an obstacle to a journey nobody takes. The two
ADRs ship as a pair, not independently.
