---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S28'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Update the MCP setup section with mode-aware launch command guidance for both tool mode and dependency mode

## Scope

- `docs/MCP.md`

## Description

- Add an Install modes subsection to the Setup section, placed after the
  module-invocation note and before the workspace-override guidance so the
  existing flow is untouched.
- Present tool mode as the default with its uvx launch block, and name the
  existing uv-run block at the top of the section as the dependency-mode shape.
- Document automatic selection from a pyproject dependency listing and the
  explicit install --mode tool / install --mode dependency override.
- Add the migration note: install --upgrade infers the mode from how a
  pre-mode workspace already runs and records it so the launch command stays
  stable.
- Reflow the whole file through mdformat --wrap 88.

## Outcome

The Setup section now explains both launch shapes, which mode produces which,
and how an existing workspace migrates, in the same register as the surrounding
prose. No dependency-mode reader loses the form they already had, and the
tool-first default is stated plainly. Spaced hyphens throughout; no dev metadata
surfaced.

## Notes

The pre-existing primary Setup block still shows the uv-run (dependency) shape;
rather than restructuring the professionally-written section, the new subsection
names that block as the dependency form and adds the uvx default alongside it, so
the default is clear without reordering the section.
