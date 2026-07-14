---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S25'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Update the framework overview's install-mode description to name the three-mode model

## Scope

- `docs/framework.md`

## Description

- Open the operate/customize section's "Choose an install mode" paragraph with the
  three-mode framing ("mode-aware, with three modes") instead of the implicit two.
- Add a dev-mode sentence: vaultspec-core placed in the default `dev` dependency group
  renders exactly like dependency mode but does not ship in built distributions, so
  choosing it records the non-leaking placement as a distinct declared state.
- Extend the mode-pinning sentence to all three flag tokens.
- Add the per-package `workspace.json` axis in one clause: the mode is committed per
  package, so a project running vaultspec-core beside a companion package can declare
  each in its own mode; keep the existing upgrade-inference tail.
- Reflow with `mdformat --wrap 88`.

## Outcome

The framework manual's install-mode paragraph now names all three modes and the
per-package declaration in the same single-paragraph operator-guidance register the
section already used, without adding development metadata or a new heading. The dev-mode
nuance is stated as a bookkeeping/declared-state distinction rather than a fourth render
path, matching the ADR's D1 framing and the parallel edits in the README and MCP docs.

## Notes

No incidents.
