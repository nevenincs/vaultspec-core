---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S22'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Update the provisioning-mode section to describe the three-mode model and per-package declaration

## Scope

- `README.md`

## Description

- Extend the getting-started install-mode paragraph's two-mode sentence to a third
  clause for dev mode, describing it as placement in the default `dev` dependency group
  that renders like dependency mode but does not ship in built distributions.
- Widen the mode-pinning sentence from two flag tokens to all three (`--mode tool`,
  `--mode dependency`, `--mode dev`).
- Add one sentence naming the committed per-package `workspace.json`, so a workspace
  running vaultspec-core alongside a companion package can declare each in its own mode.
- Preserve the existing upgrade-inference closing sentence and the paragraph's sentence
  rhythm.
- Reflow with `mdformat --wrap 88`.

## Outcome

The README getting-started section now presents the full three-mode model in the same
single-paragraph cadence it already used for two, adds the per-package declaration in
one sentence, and keeps the upgrade-inference note intact. The edit is additive prose
within the existing paragraph, with no development metadata and spaced hyphens only.

## Notes

No incidents.
