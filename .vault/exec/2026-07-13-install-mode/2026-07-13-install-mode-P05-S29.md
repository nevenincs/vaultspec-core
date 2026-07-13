---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S29'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Update the getting-started and MCP touchpoints to describe install mode selection and the tool-mode default

## Scope

- `README.md`

## Description

- Add a getting-started paragraph after the install NOTE describing mode
  selection: the uvx tool-mode default, the uv-run dependency mode auto-selected
  from a pyproject listing, the install --mode override, and the install
  --upgrade inference for existing workspaces.
- Touch up the MCP server section so it notes the .mcp.json launch command
  follows the install mode (uvx in tool mode, uv run in dependency mode).
- Reflow README.md through mdformat --wrap 88.

## Outcome

The README's getting-started and MCP touchpoints now describe the mode axis and
the tool-mode default without restructuring the surrounding sections. Prose stays
usage-focused with spaced hyphens and no dev metadata.

## Notes

None.
