---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S11'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add a warn-only dependency-leak advisory to resolve() that appends a plan warning when a package's declared mode is DEPENDENCY, never refusing the placement

## Scope

- `src/vaultspec_core/core/resolver.py`

## Description

- Add `_resolve_dependency_leak_advisory` to the resolver: reads vaultspec-core's own entry in the shared per-package declaration and appends a one-line warning when the declared mode is DEPENDENCY, naming the built-distribution leak and pointing at the non-leaking `--mode dev` and `--mode tool` alternatives.
- Wire the advisory into `resolve` after the mode-mismatch rule, gated to the INSTALL, SYNC, and UPGRADE actions so it fires at provision time but not while uninstalling.
- Never refuse and never consult the absent-declaration legacy bridge, so a legacy undeclared workspace is not nagged and dependency mode stays fully supported.
- Update the two pre-existing resolver tests that assert a clean diagnosis yields no warnings to filter the context-derived advisory, via a shared `_signal_warnings` helper that also absorbs the existing version-upgrade nudge.

## Outcome

A workspace declared in dependency mode now gets a low-key, informational reminder on the resolve-time warning channel at install, sync, and upgrade, satisfying the install-parity ADR's D3 warn-only choice: never silent, never a refusal. The advisory is deliberately invisible to `spec doctor`: `resolve` returns the empty plan before any rule runs for the DOCTOR action, so the advisory cannot enter doctor output or shift its exit weighting. That is the intended weighting decision - a dependency-mode workspace (this repository included, by deliberate self-hosting choice) is a fully legitimate configuration, so the leak reminder belongs at provision time as guidance, not as a doctor finding that would turn every such workspace's doctor exit code amber. The advisory reads only vaultspec-core's own map entry, matching the "each surface consults its own entry" discipline the ADR carries over from install-mode, so a companion package in dependency mode will be handled by its own repository's resolver in W02 rather than through a shared branch here. Scoped `ruff` and `ty` clean; the full 45-test resolver suite passes, as do 42 install, install-conditions, sync, and mode-flip flow tests that exercise `resolve` against a real target.

## Notes

Two pre-existing resolver tests (`test_missing_install_proceeds`, `test_clean_content_no_steps`) began failing because they call `resolve` without an explicit target, so the resolver falls back to the real repository context, which is declared in dependency mode and now legitimately emits the advisory. They already filtered the analogous context-derived version-upgrade warning; the fix folds both context advisories into a shared `_signal_warnings` helper so the tests keep asserting the absence of signal-driven warnings, which is what they mean. The third filter site uses the DOCTOR action, which returns before the advisory and needed no change. This is the same green-in-one-commit discipline used elsewhere in the phase: the tests the behavior change directly falsifies are corrected in the same commit rather than left red for the dedicated test Step, which instead adds fresh advisory presence-and-absence coverage in S13.

### Review refinement (ADR D3 moment-of-choice)

P02 code review (supervisor ruling) refined the D3 implementation: the advisory as first built here fired on every install, sync, and upgrade for any workspace with a persisted dependency declaration - this repository included, forever - which is a nag rather than guidance. The corrected semantics fire the advisory only at the moment of choice: when this run newly elects dependency mode by explicit `--mode dependency`, by detection, or by upgrade inference, and never when the mode is merely read back from an existing committed declaration. The implementation threads mode-resolution provenance (`ModeProvenance` on a new `ResolvedMode`, produced by `resolve_install_mode_with_provenance`) and evaluates the advisory in the install and upgrade command path via `newly_establishes_dependency`, where provenance is known, rather than in `resolve()` which only ever sees persisted state. Consequently `_resolve_dependency_leak_advisory` was removed from `resolver.py` entirely, and this repository's `sync --dry-run` and `install --dry-run` now print no advisory while a fresh `install --mode dependency` or a detection-resolved dependency provisioning still warns. The advisory now surfaces through `install_run`'s result and `cmd_install`, not the resolve-time warning channel; doctor remains untouched (it never emitted the advisory before and does not now).
