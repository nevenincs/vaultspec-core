---
tags:
  - '#exec'
  - '#framework-reword'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:32738ead8e0b40e83c5f111e2e564eb83d915a9c64ea0750cd08bb69521acb21'
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
- `S04` `M` `.vaultspec/agents/vaultspec-adr-researcher.md`
- `S04` `M` `.vaultspec/agents/vaultspec-code-reviewer.md`
- `S04` `M` `.vaultspec/agents/vaultspec-docs-curator.md`
- `S04` `M` `.vaultspec/agents/vaultspec-high-executor.md`
- `S04` `M` `.vaultspec/agents/vaultspec-low-executor.md`
- `S04` `M` `.vaultspec/agents/vaultspec-project-coordinator.md`
- `S04` `M` `.vaultspec/agents/vaultspec-reference-auditor.md`
- `S04` `M` `.vaultspec/agents/vaultspec-researcher.md`
- `S04` `M` `.vaultspec/agents/vaultspec-standard-executor.md`
- `S04` `M` `.vaultspec/agents/vaultspec-writer.md`
- `S04` `M` `.vaultspec/reference/cli.md`
- `S04` `M` `.vaultspec/reference/vault-schema.md`
- `S04` `M` `.vaultspec/rules/vaultspec-discovery.builtin.md`
- `S04` `M` `.vaultspec/rules/vaultspec.builtin.md`
- `S04` `M` `.vaultspec/skills/vaultspec-adr/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-code-research/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-code-review/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-curate/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-curate/references/adr-status-taxonomy.md`
- `S04` `M` `.vaultspec/skills/vaultspec-curate/references/reconciliation-playbook.md`
- `S04` `M` `.vaultspec/skills/vaultspec-documentation/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-execute/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-projectmanager/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-research/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-team/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-write/SKILL.md`
- `S04` `M` `.vaultspec/system/03-vaultspec.md`
- `S04` `M` `.vaultspec/templates/adr.md`
- `S04` `M` `.vaultspec/templates/plan.md`
- `S04` `M` `docs/correctness.md`
- `S04` `M` `docs/framework.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-high-executor.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-project-coordinator.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-researcher.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-writer.md`
- `S04` `M` `src/vaultspec_core/builtins/reference/vault-schema.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/references/adr-status-taxonomy.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/references/reconciliation-playbook.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-documentation/SKILL.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-projectmanager/SKILL.md`
- `S04` `verify:` `uv run --no-sync pytest src/vaultspec_core/vaultcore/tests/test_fix_writer_concurrency.py::test_concurrent_edit_survives_a_fix_pass -q` -> `pass`
- `S04` `A` `.vault/audit/2026-09-08-framework-reword-audit.md`
- `S04` `M` `.vault/index/framework-reword.index.md`

## Notes

- `S03` 43 focused plan-check and supersession scenarios passed; full Ruff and Ty checks passed. Broader integration verification belongs to S04. Independent Astra review's PLAN002 finding was corrected before Step closure.
- `S03` CLI reference outputs commit with their owning help change so the generated-reference gate remains valid at this checkpoint.
- `S04` Cohesive independent Astra review PASS after resolving two high and one medium findings; rolling audit records initial findings and resolutions. Broader test run: 1108 passed, one Windows PermissionError in unchanged stress test; isolated rerun passed all 300 iterations. Seed/reference guards18 and rendering49 pass. Skill validation, Ruff, Ty, provider checks, generated references, byte-identical installed Markdown, and feature vault checks pass.
