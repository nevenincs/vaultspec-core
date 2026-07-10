---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S15'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Edit the emitted header prose at the reference generator source to add the Q5 dual-role paragraph naming the CLI-fallback lookup and MCP-gateway verb-existence roles, leaving the marker-block emission untouched

## Scope

- `src/vaultspec_core/cli/reference_gen.py`

## Description

- Added the Q5 dual-role paragraph to the header prose of the bundled machine-facing CLI reference, naming its two roles: the CLI-fallback command lookup for agents and sessions without the vaultspec MCP server, and the authoritative verb-existence source the MCP discover and invoke gateway parses.
- Placed the paragraph above the generated command-inventory marker block, in the hand-written prose zone, leaving the marker block emission untouched.
- Worded the paragraph capability-first with no em dashes and no availability conditional.

## Outcome

The reference now states its dual role in one concise paragraph. The generated command-inventory marker block is byte-unchanged; the git diff is a pure prose insertion above the markers.

## Notes

Architectural finding: the plan Step scopes `src/vaultspec_core/cli/reference_gen.py` on the ADR premise that the header prose is emitted by the generator. In reality the generator preserves all prose outside the markers verbatim and only rewrites the marker block; the header prose has no Python emission point. Its true source is the committed reference document itself, which the generator round-trips through mdformat on regenerate. The Q5 intent (an edit that survives regeneration while the marker block stays byte-stable and the drift test stays green) is therefore satisfied by editing the committed prose directly, which is what was done. `reference_gen.py` needed no change and was left untouched to honor the constraint that the marker-block emission is not modified; forcing a generated header region would have restructured the markers and broken byte-stability. `ty` and `ruff` on `reference_gen.py` are clean.
