---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S21'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Document the --mode dev flag, the DEV-renders-as-DEPENDENCY nuance, and the v2 per-package workspace.json shape in the MCP and install documentation

## Scope

- `docs/MCP.md`

## Description

- Broaden the Install modes section's opening framing from two launch shapes to three
  modes selecting between them, keeping the two rendered shapes (uvx for tool, uv run
  for dependency) intact.
- Extend the mode-pinning sentence to list all three flag tokens, `--mode tool`,
  `--mode dependency`, and `--mode dev`.
- Add a dev-mode paragraph: it renders identically to dependency mode through the same
  `uv run` shape because `uv run` resolves the default dev group like a project
  dependency, and the only difference is that dependency mode leaks into built
  distributions while dev mode does not, so choosing dev records the non-leaking
  placement for the doctor and a fresh clone.
- Add a paragraph on the committed per-package `workspace.json`: each provisioned
  package is keyed to its own mode and version floor, so a workspace provisioning both
  vaultspec-core and a companion package can declare each in a different mode without
  one overwriting the other.
- Reflow the section with `mdformat --wrap 88`.

## Outcome

The MCP setup documentation now names all three provisioning modes, states the
DEV-renders-as-DEPENDENCY nuance in the register the surrounding prose already uses
(rendering-identical, differs only in distribution leak and declared bookkeeping), and
describes the v2 per-package declaration shape without exposing any development
metadata. The two rendered launch shapes and their Windows-lock rationale are unchanged;
the edits are additive within the existing section. No em dashes were introduced (spaced
hyphens throughout), and the section stays inside the doc's existing narrative flow
rather than becoming a catalog.

## Notes

No incidents. The dev-mode description is deliberately framed as a bookkeeping and
doctor-labeling distinction, matching the ADR's D1 wording, so a reader does not mistake
it for a third rendered launch command.
