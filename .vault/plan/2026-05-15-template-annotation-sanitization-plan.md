---
tags:
  - '#plan'
  - '#template-annotation-sanitization'
date: '2026-05-15'
modified: '2026-06-13'
tier: L2
related:
  - '[[2026-05-15-template-annotation-sanitization-research]]'
  - '[[2026-05-15-template-annotation-sanitization-adr]]'
---

# template-annotation-sanitization plan: implementation

Implement explicit sanitation for generated VaultSpec template annotations while
preserving agent-facing guidance at document creation time.

## Proposed Changes

Add a first-class annotations checker and sanitizer. Wire it through the vault
fix suite, explicit vault sanitation command, repair pipeline, canonical
pre-commit hook generation, repository pre-commit config, and local fix recipe.
Clean the source templates so frontmatter guidance uses Markdown comment
directives outside YAML frontmatter.

## Steps

### Phase `P01` - add the annotation sanitizer capability

This Phase adds the domain checker and command surfaces.

- [x] `P01.S01` - add the annotations checker and sanitizer; `src/vaultspec_core/vaultcore/checks/annotations.py`.
- [x] `P01.S02` - include annotations in the shared vault check suite; `src/vaultspec_core/vaultcore/checks/__init__.py`.
- [x] `P01.S03` - expose `vault check annotations --fix` and `vault sanitize annotations`; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P01.S04` - register the sanitizer in canonical pre-commit hooks; `src/vaultspec_core/core/enums.py`.
- [x] `P01.S05` - wire the sanitizer hook command; `src/vaultspec_core/core/commands.py`.

### Phase `P02` - normalize template annotation syntax

This Phase keeps source template guidance but removes YAML comment directives.

- [x] `P02.S06` - move ADR template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/adr.md`.
- [x] `P02.S07` - move audit template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/audit.md`.
- [x] `P02.S08` - move code-review template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/code-review.md`.
- [x] `P02.S09` - move research template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/research.md`.
- [x] `P02.S10` - move reference template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/ref-audit.md`.
- [x] `P02.S11` - move execution step template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/exec-step.md`.
- [x] `P02.S12` - move execution summary template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/exec-summary.md`.
- [x] `P02.S13` - move plan template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/plan.md`.
- [x] `P02.S14` - move index template frontmatter guidance into Markdown comments; `.vaultspec/rules/templates/index.md`.

### Phase `P03` - wire operator automation and documentation

This Phase registers the command in the affected operator surfaces.

- [x] `P03.S15` - add the repository pre-commit sanitizer hook; `.pre-commit-config.yaml`.
- [x] `P03.S16` - add the sanitizer to the local fix recipe; `justfile`.
- [x] `P03.S17` - document the sanitizer in the CLI handbook; `.vaultspec/CLI.md`.
- [x] `P03.S18` - document the sanitizer in the framework manual; `.vaultspec/README.md`.
- [x] `P03.S19` - document the sanitizer in the framework rule summary; `.vaultspec/rules/rules/vaultspec-cli.builtin.md`.
- [x] `P03.S20` - update the framework rule snapshot; `.vaultspec/_snapshots/rules/vaultspec-cli.builtin.md`.

### Phase `P04` - verify behavior

This Phase proves the command preserves creation-time guidance and strips only on
explicit fix paths.

- [x] `P04.S21` - test checker reporting and explicit fixes; `src/vaultspec_core/vaultcore/checks/tests/test_annotations.py`.
- [x] `P04.S22` - test creation preserves annotations until fix; `src/vaultspec_core/tests/cli/test_vault_cli.py`.
- [x] `P04.S23` - test repair and explicit sanitize command wiring; `src/vaultspec_core/tests/cli/test_vault_repair.py`.
- [x] `P04.S24` - test template source frontmatter has no comment directives; `tests/test_template_annotations.py`.
- [x] `P04.S25` - test pre-commit and fix automation registration; `tests/test_automation_contracts.py`.

### Phase `P05` - harden sanitizer operations

This Phase adds non-mutating observability and stricter contracts around the
sanitizer policy.

- [x] `P05.S26` - document and test the sanitizer allowlist and malformed-annotation policy; `src/vaultspec_core/vaultcore/checks/annotations.py`.
- [x] `P05.S27` - expose `vault sanitize annotations --dry-run`; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P05.S28` - report generated annotations and unreadable markdown in `spec doctor` without mutating documents; `src/vaultspec_core/core/diagnosis/`.
- [x] `P05.S29` - harden template source tests against malformed HTML comment syntax and non-data frontmatter; `tests/test_template_annotations.py`.
- [x] `P05.S30` - lock pre-commit sanitizer ordering after fix and before doctor/check surfaces; `tests/test_automation_contracts.py`.
- [x] `P05.S31` - update operator documentation for dry-run and doctor visibility; `.vaultspec/CLI.md`.

## Parallelization

The checker implementation and template syntax cleanup were independent after
the ADR fixed the lifecycle boundary. Command wiring depended on the checker.
Pre-commit and documentation updates depended on the command names. The later
doctor signal stayed independent from the mutating checker by using a read-only
filesystem collector.

## Verification

The implementation is complete when focused annotation tests pass, doctor signal
tests pass, CLI handbook drift tests pass, pre-commit contract tests pass, and
ruff reports no issues in the touched Python surfaces.
