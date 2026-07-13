---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S45
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# transfer ADR authorship to this persona by amending the context-enhancer-only restriction to match its own formalizes-decisions description (D10)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md`

## Description

- Rewrite the Important section's "context enhancer ... focus solely on gathering"
  restriction: the persona is a researcher and decision formalizer whose twofold
  mandate is to gather/synthesize research AND formalize the resulting architectural
  decisions into `<ADR>` content structured on `templates/adr.md` (D10)
- Keep the not-a-developer boundary (no code implementation or implementation
  suggestions) and route both deliverables through the S28 return-to-orchestrator
  persistence contract
- Run mdformat --wrap 88 on the edited file

## Outcome

The persona's body no longer forbids what its own description promises ("formalizes
architectural decisions into an `<ADR>`"): ADR drafting is now owned by the
adr-researcher, with the content returned to the dispatching orchestrator for
persistence, consistent with the read-only mode. The skill-side swap naming this
persona as the ADR drafter is the next Step (S46).

## Notes

The frontmatter description needed no change; it already claimed
formalizes-decisions. The H1 ("`<ADR>` Decision Support") also already matched.
