---
tags:
  - '#exec'
  - '#framework-reword'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:81d670fe58fbc48367c2ac8e5df6826115f64caddf16f24f8af44c59dc532284'
related:
  - "[[2026-09-08-framework-reword-plan]]"
---

# `framework-reword` ledger

## Changes

- `S01` `M` `src/vaultspec_core/builtins/system/03-vaultspec.md`
- `S01` `M` `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`
- `S01` `M` `src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md`
- `S01` `verify:` `vault check all` -> `pass`
- `S02` `M` `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md`
- `S02` `M` `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`
- `S02` `M` `src/vaultspec_core/builtins/agents/vaultspec-high-executor.md`
- `S02` `M` `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`
- `S02` `M` `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`
- `S02` `M` `src/vaultspec_core/builtins/agents/vaultspec-writer.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/references/adr-status-taxonomy.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/references/reconciliation-playbook.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-team/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/templates/adr.md`
- `S02` `M` `src/vaultspec_core/builtins/templates/plan.md`
- `S02` `verify:` `mdformat and pymarkdown` -> `pass`
- `S03` `M` `src/vaultspec_core/cli/rendering_hints.py`
- `S03` `M` `src/vaultspec_core/cli/vault_check_cmd.py`
- `S03` `M` `src/vaultspec_core/core/adr.py`
- `S03` `M` `src/vaultspec_core/plan/checks/frontmatter_check.py`
- `S03` `M` `src/vaultspec_core/plan/frontmatter.py`
- `S03` `M` `src/vaultspec_core/plan/serialiser.py`
- `S03` `M` `src/vaultspec_core/tests/cli/test_check_adr_grounding.py`
- `S03` `M` `src/vaultspec_core/tests/cli/test_vault_adr_supersede.py`
- `S03` `M` `src/vaultspec_core/tests/plan/test_checks.py`
- `S03` `M` `src/vaultspec_core/vaultcore/checks/features.py`
- `S03` `M` `src/vaultspec_core/vaultcore/checks/references.py`
- `S03` `M` `src/vaultspec_core/vaultcore/checks/tests/test_features.py`
- `S03` `M` `src/vaultspec_core/vaultcore/checks/tests/test_newline_preservation.py`
- `S03` `M` `src/vaultspec_core/vaultcore/resolve.py`
- `S03` `M` `src/vaultspec_core/vaultcore/tests/test_fix_writer_concurrency.py`
- `S03` `M` `src/vaultspec_core/vaultcore/tests/test_resolve.py`
- `S03` `verify:` `uv run --no-sync pytest src/vaultspec_core/tests/plan/test_checks.py src/vaultspec_core/tests/cli/test_vault_adr_supersede.py -q` -> `pass`
- `S03` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S03` `M` `docs/CLI.md`
- `S03` `verify:` `uv run --no-sync vaultspec-core spec reference generate --check` -> `pass`

## Notes

- `S03` 43 focused plan-check and supersession scenarios passed; full Ruff and Ty checks passed. Broader integration verification belongs to S04. Independent Astra review's PLAN002 finding was corrected before Step closure.
- `S03` CLI reference outputs commit with their owning help change so the generated-reference gate remains valid at this checkpoint.
