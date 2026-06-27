---
tags:
  - '#research'
  - '#rag-pipeline-enrollment'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-06-25-framework-dir-flatten-adr]]'
---

# `rag-pipeline-enrollment` research: `firmware rag-grounding mandate`

The firmware under `src/vaultspec_core/builtins/` is the contract that tells every
agent and coder how to discover, ground, and decide. This research maps where its
information-gathering and grounding mandates live, and how unevenly `vaultspec-rag`
semantic search is enrolled into them, to scope the prose changes that make rag the
first grounding move across the research, decision, reference, and audit phases.

## Findings

### The grounding mandate lives in three layers, and rag thins out downstream

The directive to gather context before acting is present at three altitudes, but rag
coverage drops off exactly where the discovery work actually happens.

- **System prompt (present).** `src/vaultspec_core/builtins/system/03-vaultspec.md`
  carries a "Ground in existing intent" block that already leads with
  `vaultspec-rag search "<intent>" --type vault` then `--type code`. This is the
  cleanest existing prose model and the template the lower layers should mirror.
- **Skills (present).** The three pipeline-entry skills each open with a "Ground ...
  first" required step citing rag: `skills/vaultspec-research/SKILL.md`,
  `skills/vaultspec-adr/SKILL.md`, and `skills/vaultspec-code-research/SKILL.md`.
- **Agent personas (the gap).** The personas that actually perform discovery do not
  mention rag at all. `agents/vaultspec-researcher.md` is a four-line stub with no
  methodology. `agents/vaultspec-adr-researcher.md` is roughly ninety percent
  external research (web, package metadata, GitHub); its "Investigate", "Exploration
  Phase", and "Integration Pass" mandates say a generic "search tools", and the
  "internal project context" half of its stated mission is undeveloped.
  `agents/vaultspec-reference-auditor.md`, `agents/vaultspec-code-reviewer.md`,
  `agents/vaultspec-writer.md`, and `agents/vaultspec-docs-curator.md` all drive
  discovery through `rg` and `fd` with no rag entry point.

### rag is an optional sister tool with a graceful fallback, owned outside core

`vaultspec-rag` is a separate package, not part of core. It ships its own builtin
rule and MCP (`vaultspec_rag/builtins/rules/vaultspec-rag.builtin.md` and
`vaultspec_rag/builtins/mcps/vaultspec-rag.builtin.json`) and installs them into a
workspace through its own `vaultspec-rag install` verb; the dogfood copies tracked
under `.vaultspec/` came from that installer, not from core's seed. Core's source
builtins therefore must not own or duplicate a rag rule. Instead core's firmware
references rag the way the existing skills already do: prefer it, and fall back to
`vaultspec-core vault list` and grep when rag is not installed. This hedged-optional
discipline (assert no infrastructure that may be absent) is the same posture the
firmware-wording-review decision adopted for capability claims.

### rag's distinguishing value is internal semantic discovery

The concept the personas miss is what rag is *for*: it searches our own code and
vault by meaning, not external sources. It is the internal-grounding complement to
the web and package research the adr-researcher already does well, not a replacement
for it. It is most valuable precisely when a new research, feature, or audit needs to
find where and how something is already done without a known identifier, which is the
discovery moment these personas govern. The hybrid index (dense plus sparse plus
cross-encoder rerank) rewards short natural-language queries carrying the concrete
domain nouns, narrowed by `--type`, `--language`, `--path`, and the vault filters.

### A reference-parity defect rides alongside the rag gap

The Phase 1 framework-dir flatten swept Python docstrings but not the builtins `.md`
firmware. Roughly thirty `.vaultspec/rules/...` references remain across rules,
skills, agents, system, and the bundled reference; for example
`agents/vaultspec-adr-researcher.md` points at `.vaultspec/rules/templates/adr.md`,
which now resolves to `.vaultspec/templates/adr.md`. These send agents to files that
no longer exist at those paths. They violate the firmware-reference-parity principle
(every artifact named in firmware prose must resolve to a shipped artifact of exactly
that name), so they are corrected in the same prose pass rather than left as known
breakage in files this work already edits.

### Scope boundaries

- **In scope:** enroll the rag mandate into core's own agent personas, align the
  skills and system prompt to one consistent grounding story, and correct the stale
  `.vaultspec/rules/...` paths.
- **Out of scope:** owning a rag rule inside core's builtins, and any change to the
  `vaultspec-rag` package itself.

### What was not investigated

The downstream execute and project-management skills were not examined in depth; they
sit after the discovery-heavy phases this work targets. The rag command surface is
taken as shipped by rag's own builtin rule rather than re-derived, so every rag verb
cited in the new prose must be cross-checked against that surface during execution to
keep reference parity.
