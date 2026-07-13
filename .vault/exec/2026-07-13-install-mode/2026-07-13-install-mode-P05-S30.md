---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S30'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Update the framework overview to document the mode axis alongside the existing provisioning concepts

## Scope

- `docs/framework.md`

## Description

- Add a Choose an install mode paragraph to the Operate day to day section,
  placed after Share so the mode axis sits with the provisioning and sharing
  concepts.
- Describe the uvx tool-mode default, the uv-run dependency mode auto-selected
  from a pyproject listing, the install --mode override, the committed shared
  declaration, and the install --upgrade inference.
- Reflow docs/framework.md through mdformat --wrap 88.

## Outcome

The framework manual now documents the mode axis alongside the existing
customize, share, maintain, and MCP provisioning concepts, in the same
bold-led register as its siblings. Usage-focused prose, spaced hyphens, no dev
metadata.

## Notes

None.
