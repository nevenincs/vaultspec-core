---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` `P05` summary

Phase P05 (persona contracts) closed all twenty-two Steps S27-S48, implementing ADR
decisions D3, D9, D10, and D11: the three read-only personas now return findings to
the dispatching orchestrator instead of carrying unfulfillable persistence mandates,
the `mode:` field has a single documented definition, the executor trio is coherent
(tier-appropriate low mission, universal code-review gate, one STANDARD middle-tier
name, complete routing, parallel Documentation sections), ADR authorship belongs to
the adr-researcher, and the curate skill and docs-curator persona describe one
delegate-model contract with a persisted audit report.

- Modified: `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-project-coordinator.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-high-executor.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-researcher.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-writer.md`,
  `src/vaultspec_core/builtins/system/03-vaultspec.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`, and (S40 incident
  fix) `src/vaultspec_core/builtins/rules/vaultspec-archive-discipline.builtin.md`,
  `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`
- Created: twenty-two Step Records `...-P05-S27.md` through `...-P05-S48.md` in this
  folder

## Description

S27-S29 (D3): the code-reviewer, adr-researcher, and reference-auditor persistence
sections were reworded to the return-findings contract - each persona stays
`mode: read-only`, returns its complete report/findings as the final message, and the
dispatching orchestrator persists via `vaultspec-core vault add` scaffold plus
body-prose edit. Template pointers and canonical artifact destinations were kept as
descriptive knowledge; the Frontmatter & Tagging Mandates became orchestrator-owned
schema descriptions.

S30-S31 (D3): the system fragment's Agents section now defines the `mode:` field once
(declared file-mutation intent via the harness Write/Edit tools; read-only personas
return findings; the declaration is intent, not a sandbox - Bash can technically
write), and the project-coordinator notes its Bash-only `gh`/`git` mutation path as
the deliberate reason a read-write persona carries no Write/Edit.

S32-S33 (D9): the low executor's verbatim high-tier mission became a tier-appropriate
mission (simplicity, pattern-following, minimal blast radius, escalate over
improvise), and it gained the mandatory Critical Requirement code-review section the
other two executors carry.

S34 (D9, gate): the code-binding check returned **UNBOUND** - the persona frontmatter
`tier:` value is dropped unread by every agent renderer in `core/agents.py` and never
parsed or asserted as an enum in any test (tier literals in tests are arbitrary
inputs, including the non-enum value "X" accepted by passthrough). No Python
follow-up needs logging in P09.S126 for the tier enum.

S35-S40 (D9): the six `tier: MEDIUM` personas (standard-executor plus its description
wording, codifier, docs-curator, reference-auditor, project-coordinator, researcher)
moved to `tier: STANDARD`. The full test suite ran after the last move: first run
surfaced one failure in the CLI language-contract test (nine backticked bare CLI
snippets missing the `vaultspec-core` prefix - two from S27/S28, three from P02, four
from P04, none tier-related); all nine were prefixed and the suite finished green at
2035 passed, 0 failed.

S41-S44 (D9): the writer's agent-assignment list gained the low executor for
straightforward, pattern-following Steps, and the executor trio's Documentation
sections were made parallel - all three now carry the Template
(`templates/exec-step.md`), Linking, and Content sub-bullets, with the low executor's
dangling fragments cleaned into the shared form.

S45-S46 (D10): the adr-researcher's "context enhancer ... focus solely on gathering"
restriction became a twofold research-and-formalize mandate matching its own
description, and the vaultspec-adr skill now names `vaultspec-adr-researcher` as the
drafting persona, with the writer's mandate noted as plan-only.

S47-S48 (D11): the curate skill states the curator's Audit -> Delegate -> Verify
operating mode (CLI fix paths first, persona delegation for the rest, no in-place
edits), and the docs-curator persona gained the Audit Report Persistence section the
skill promises - scaffold via `vault add audit --feature docs-curation`, then author
the body directly under its read-write contract.

Each Step landed as one commit carrying the edit, its Step Record, and the CLI-driven
plan-state change; all pre-commit hooks pass on every commit and
`vaultspec-core vault check all` reports green.
