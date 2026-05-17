---
tags:
  - '#research'
  - '#cli-spec-gitignore'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
---

# `cli-spec-gitignore` research: `Default gitignore policy demotes the spec layer`

Synthesis note for the gitignore-policy finding. Captures the audit
evidence behind the sibling ADR that proposes reversing the default.

## Findings

### Install writes a gitignore block that buries the spec layer

On first `vaultspec-core install` against a fresh repository, the
CLI appends a managed block to the consumer's `.gitignore` that
excludes `.claude/`, `.vaultspec/`, `.mcp.json`, and `CLAUDE.md`
from version control. `.vault/` is largely spared (only its
runtime subdirectories are excluded: `.obsidian/`, `.trash/`,
`data/`, `logs/`).

Joan documented this in round 1 finding S5. The directory pair
`.vault/` and `.vaultspec/` differs by a single suffix; the install
operation puts one under version control and the other under
gitignore. No install output explains the split.

### The policy collides with the framework's stated purpose

The framework's elevator pitch is durable, shareable, agent-readable
project memory. `.vaultspec/` is where authored rules, skills,
agents, and system prompts live — the layer that mandates "how this
project is supposed to work". A teammate cloning the repository
inherits everything under `.vault/` but nothing under `.vaultspec/`.
What gets shared is the project's history; what gets gitignored is
the project's authoritative policy.

`CLAUDE.md`, the agent-readable system prompt that synthesises the
framework manual plus project-specific rules, follows the same
pattern: it is gitignored by default. The artifact most likely to
shape future agent behaviour is the artifact least likely to
propagate.

### The policy amplifies the codification gap

Round 3a Bridge Gap finding documents that agents do not reach the
`spec` subtree organically — the pipeline does not push them
toward it. The gitignore default is the second compounding factor.
An agent that did reach for `spec rules add` would discover that
the rules it just authored are local to its machine. The framework
explicitly signals "this is ephemeral". The incentive structure
discourages the very operation the framework was built to support.

The two findings compound: the bridge is missing, and the
destination is gitignored. Either one alone would suppress
codification; together they make it a dead-letter route.

### Why the current default may have been chosen

Two plausible reasons for the existing policy:

- `.claude/` and `.mcp.json` historically have contained
  agent-tool runtime state (open files, ephemeral preferences) that
  legitimately should not be checked in.
- `.vaultspec/_snapshots/` and `*.lock` files inside `.vaultspec/`
  are runtime by-products that should not be checked in either.

The fix is to discriminate. Runtime by-products stay gitignored
(`.vaultspec/_snapshots/`, `.vaultspec/*.lock`, `.claude/sessions/`,
provider-specific runtime). Authored content does not.

### Adjacent consequence: provider sync becomes meaningful

Joan round 3a confirmed that `install --upgrade` preserves authored
content correctly under the hood. The mechanism for keeping
project-specific rules across upgrades exists. What does not exist
is the visibility: the success line does not say "we preserved
your authored rules", and the policy that hides them from version
control compounds the invisibility.

Reversing the default exposes both: agents see authored content in
git diffs, teammates inherit it on clone, and the upgrade verb's
preservation guarantee becomes visible work rather than hidden
work.

## Constraints identified

- Existing installs have an `.gitignore` block already written
  against them. A change to the default must either migrate
  existing repositories or limit its scope to new installs.
- The managed-block delimiter sentinels let the install operation
  rewrite its own block. The reversal can ship as a migration that
  rewrites the block in place during the next upgrade run.
- Some provider directories legitimately need runtime exclusions
  (snapshots, locks). The reversed default must be granular, not a
  blanket "commit everything".

## Recommendation

Reverse the default for authored content under `.vaultspec/`,
`.claude/` (rules/skills/agents/system slices only), and
`CLAUDE.md`. Keep runtime by-products gitignored. Update the
install summary's language to state the policy plainly. Land a
migration that rewrites the managed gitignore block on next
upgrade. Full design in the sibling ADR.
