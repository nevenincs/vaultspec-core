---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S34
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# run the code-binding check for tier MEDIUM frontmatter consumption in Python loaders and tests before any enum value change (D9)

## Scope

- `src/vaultspec_core`

## Description

- Grep `src/vaultspec_core` Python and `tests/` for consumption of the persona
  frontmatter `tier:` values (MEDIUM, HIGH, LOW): searched `tier`, `MEDIUM`,
  `CapabilityLevel`, agent-frontmatter parsing, and renderer code paths
- Inspect every hit: `core/agents.py` renderers, `core/enums.py` capability model,
  `tests/cli/test_agents_render.py`, `vaultcore/tests/test_core.py`,
  `protocol/tests/conftest.py`, the plan-tier subsystem under `plan/`, and
  `tests/test_template_annotations.py`

## Outcome

**Verdict: UNBOUND.** The persona frontmatter `tier:` value is never parsed, mapped,
or asserted as an enum anywhere in Python loaders or tests. Evidence:

- `core/agents.py`: both registered renderers (`_render_claude_agent`,
  `_render_gemini_agent`) drop the `tier` and `mode` authoring keys without reading
  their values (docstrings state "Drops vaultspec authoring keys"); the Codex renderer
  never touches `tier`; the passthrough renderer emits frontmatter verbatim with no
  value inspection.
- `tests/cli/test_agents_render.py`: tier values appear only as opaque literals
  constructed inside the tests themselves - line 125 uses `"MEDIUM"` solely to assert
  the key is dropped, line 197 uses `"HIGH"` the same way, and lines 204-207 use the
  non-enum value `"X"` and assert it is preserved by passthrough, proving no enum
  validation exists on the value.
- `vaultcore/tests/test_core.py` and `protocol/tests/conftest.py` use `tier: LOW` and
  `tier: HIGH` as arbitrary strings in generic frontmatter-parsing fixtures; no test
  reads `MEDIUM` from a shipped persona file.
- `core/enums.py` `CapabilityLevel.MEDIUM` is a model-selection IntEnum used by the
  protocol providers; nothing converts persona `tier:` strings into it.
- Every other `tier` reference in Python (`plan/frontmatter.py`, `plan/commands/`,
  `cli/plan_cmd.py`, plan checks/tests) is the plan-document Tier (L1..L4), a
  different field; `tests/test_template_annotations.py` lists `tier` as an allowed
  template frontmatter key, again the plan tier.

The MEDIUM-to-STANDARD frontmatter move in S35-S40 is therefore unblocked; no Python
follow-up needs logging in P09.S126 for the tier enum.

## Notes

Check-only Step: no firmware edit; this record plus the plan-state change is the
commit. The full test suite run is deferred to the last enum-move Step (S40) per the
phase guidance.
