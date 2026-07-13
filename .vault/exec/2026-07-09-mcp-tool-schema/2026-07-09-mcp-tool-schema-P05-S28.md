---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S28'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Audit and tighten the hot-verb help strings in the CLI reference so the discover payload reads well verbatim, regenerating the inventory between the vaultspec:generated markers (agent: vaultspec-low-executor)

## Scope

- `.vaultspec/reference/cli.md`

## Description

- Audit every hot-verb and long-tail description in the generated command-inventory block of the CLI reference, since each is what the `discover` payload surfaces to an agent verbatim.
- Find one defective description: `vault check markdown` was truncated mid-sentence at "trailing whitespace, blank" because the reference generator captures only the docstring's first physical line and the source docstring wrapped across two lines.
- Fix the defect at its source, not in the generated block: collapse the `check markdown` command docstring in `vault_cmd.py` to a single physical line ("Check and optionally fix markdown hygiene (whitespace, blank runs, newline).") within the line-length budget.
- Regenerate the bundled reference between the `vaultspec:generated` markers with `spec reference generate`, then propagate to the workspace `.vaultspec/reference/cli.md` via `install --upgrade` so the copy the catalog reads carries the fix.
- Confirm the remaining descriptions across the vault, spec, and plan groups read as complete, agent-usable one-liners needing no change.

## Outcome

- Source fix: `src/vaultspec_core/cli/vault_cmd.py` (single-line `check markdown` docstring).
- Regenerated: `src/vaultspec_core/builtins/reference/cli.md` and the propagated `.vaultspec/reference/cli.md`; the catalog now surfaces the full, untruncated description.
- The reference-drift and reference-generated CLI test suites pass, confirming the managed block stays in sync with the live Typer tree.

## Notes

- The generated block was never hand-edited; the only lever was the command docstring the generator reads, exactly as the no-hand-edit rule requires. One truncation was the sole material defect in the surfaced help; the rest of the inventory was already agent-quality.
