---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S29
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`

## Description

- Rewrite the Reference Persistence section: the persona is read-only and does not
  write the `<Reference>` document to disk; it RETURNS the complete findings to the
  dispatching orchestrator, which persists them by scaffolding
  `vault add reference --feature <feature>` and editing the scaffolded body prose (D3)
- Keep the canonical reference destination as a KNOW-the-destination description of
  where the orchestrator persists, preserving the persona's bold-caps imperative style
- Run mdformat --wrap 88 on the edited file

## Outcome

The reference-auditor's declared `mode: read-only` and its body now agree: the persona
returns `<Reference>` findings instead of persisting them, and the persistence path
(scaffold via `vault add reference`, then body-prose edit) lives with the dispatching
orchestrator, completing the D3 rewording across the three read-only personas
(S27 code-reviewer, S28 adr-researcher, S29 reference-auditor).

## Notes

The Reference Snapshot Template's body-text `Related:` line and the retired
safety-auditors mention were deliberately left untouched; those are P06.S56 and
P06.S57 (D8). The `tier: MEDIUM` frontmatter is handled by P05.S38 after the S34
code-binding check.
