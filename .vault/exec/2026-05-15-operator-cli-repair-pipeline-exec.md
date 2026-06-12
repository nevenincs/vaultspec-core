---
tags:
  - '#exec'
  - '#operator-cli-repair-pipeline'
date: '2026-05-15'
modified: '2026-05-15'
step_id: S01
related:
  - '[[2026-05-15-operator-cli-repair-pipeline-plan]]'
---

# operator-cli-repair-pipeline exec: P01.S01

Intake captured direct operator feedback and converted it into a VaultSpec
pipeline feature. The follow-on implementation added the first working repair
pipeline command and closed the plan steps.

- Created: `.vault/reference/2026-05-15-operator-cli-repair-pipeline-reference.md`
- Created: `.vault/research/2026-05-15-operator-cli-repair-pipeline-research.md`
- Created: `.vault/audit/2026-05-15-operator-cli-repair-pipeline-audit.md`
- Created: `.vault/adr/2026-05-15-operator-cli-repair-pipeline-adr.md`
- Created: `.vault/plan/2026-05-15-operator-cli-repair-pipeline-plan.md`
- Created: `src/vaultspec_core/vaultcore/repair.py`
- Created: `src/vaultspec_core/tests/cli/test_vault_repair.py`
- Created: `src/vaultspec_core/vaultcore/checks/tests/test_structure_case_rename.py`
- Modified: `src/vaultspec_core/cli/vault_cmd.py`
- Modified: `src/vaultspec_core/vaultcore/checks/structure.py`
- Modified: `.vaultspec/CLI.md`

## Description

Verified that the worktree exists at the current branch based on `main`.
Installed dependencies with `uv sync --all-extras --dev`. Confirmed
`vaultspec-core --help`, `vaultspec-core spec doctor --json`, and
`vaultspec-core vault check all --json` execute successfully in this worktree.

Used a Researcher/Author/Editor documentation workflow. The Researcher gathered
current CLI, check, index, migration, path, and test context. The Author drafted
bounded artifacts from that brief. The Editor applied the final `.vault/`
documents, preserving vault naming, frontmatter, body-link, plan-row, and exec
step conventions.

Implemented `vaultspec-core vault repair` as an operator pipeline with
`preflight`, `check`, `fix`, `index`, `postcheck`, and `summary` phases. The
command supports `--dry-run`, `--json`, `--feature`, `--verbose`, and
`--include-index/--no-index`.

Added Windows-aware case-only rename handling to the structure fixer. The
rename path now distinguishes exact casing from case-insensitive path equality
and uses a same-directory temporary hop when the final filename differs only by
case.

## Tests

Validation commands run during intake:

- `uv sync --all-extras --dev`
- `uv run vaultspec-core --help`
- `uv run vaultspec-core spec doctor --json`
- `uv run vaultspec-core vault check all --json`
- `uv run pytest src\vaultspec_core\tests\cli\test_vault_repair.py src\vaultspec_core\vaultcore\checks\tests\test_structure_case_rename.py -q`
- `uv run pytest src\vaultspec_core\tests\cli\test_vault_repair.py src\vaultspec_core\vaultcore\checks\tests\test_structure_case_rename.py src\vaultspec_core\tests\cli\test_cli_language_contract.py -q`
- `uv run ruff check src\vaultspec_core\vaultcore\repair.py src\vaultspec_core\vaultcore\checks\structure.py src\vaultspec_core\vaultcore\checks\tests\test_structure_case_rename.py src\vaultspec_core\cli\vault_cmd.py src\vaultspec_core\tests\cli\test_vault_repair.py`
- `uv run ty check src\vaultspec_core\vaultcore\repair.py src\vaultspec_core\vaultcore\checks\structure.py src\vaultspec_core\vaultcore\checks\tests\test_structure_case_rename.py src\vaultspec_core\cli\vault_cmd.py src\vaultspec_core\tests\cli\test_vault_repair.py`

Final validation should regenerate the feature index and rerun vault checks
after this execution record is updated.

## Follow-up execution: sync authority

Captured the follow-up operator testimonial as a sync authority design problem
and extended the active plan with Phase `P07`.

- Created: `.vault/research/2026-05-15-operator-cli-sync-authority-research.md`
- Created: `.vault/adr/2026-05-15-operator-cli-sync-authority-adr.md`
- Created: `.vault/index/operator-cli-sync-authority.index.md`
- Modified: `.vault/plan/2026-05-15-operator-cli-repair-pipeline-plan.md`
- Modified: `src/vaultspec_core/cli/root.py`
- Modified: `src/vaultspec_core/cli/spec_cmd.py`
- Modified: `src/vaultspec_core/tests/cli/test_sync.py`
- Modified: `.vaultspec/CLI.md`
- Modified: `.vaultspec/rules/rules/vaultspec-cli.builtin.md`

Implementation made `vaultspec-core sync` the explicit authoritative complete
sync surface for rules, skills, agents, system prompts, provider config stubs,
and MCPs. Narrow `vaultspec-core spec <resource> sync` commands now present
themselves as resource-scoped maintenance operations and tell operators to use
top-level sync for a complete provider-facing refresh.

`vaultspec-core spec rules add` now prints human follow-up guidance after
source-side rule creation: provider-facing outputs were not updated, and the
next normal command is `vaultspec-core sync`. JSON output remains structured
and unchanged.

Regression coverage now proves the operator path directly: create a rule with
`vaultspec-core spec rules add`, run top-level `vaultspec-core sync`, and assert
that `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` include the new rule reference.

Additional validation commands run for the sync authority follow-up:

- `uv run ruff check src\vaultspec_core\cli\root.py src\vaultspec_core\cli\spec_cmd.py src\vaultspec_core\tests\cli\test_sync.py`
- `uv run ty check src\vaultspec_core\cli\root.py src\vaultspec_core\cli\spec_cmd.py src\vaultspec_core\tests\cli\test_sync.py`
- `uv run pytest src\vaultspec_core\tests\cli\test_sync.py -q`
- `uv run pytest src\vaultspec_core\tests\cli\test_sync.py src\vaultspec_core\tests\cli\test_spec_cli.py src\vaultspec_core\tests\cli\test_cli_language_contract.py -q`

## PR review follow-up execution

Actioned Codex review findings posted to PR `112`.

- Modified: `src/vaultspec_core/vaultcore/checks/structure.py`
- Modified: `src/vaultspec_core/vaultcore/repair.py`
- Modified: `src/vaultspec_core/cli/vault_cmd.py`
- Modified: `src/vaultspec_core/cli/root.py`
- Modified: `src/vaultspec_core/cli/spec_cmd.py`
- Modified: `src/vaultspec_core/vaultcore/checks/tests/test_structure_case_rename.py`
- Modified: `src/vaultspec_core/tests/cli/test_vault_repair.py`
- Modified: `src/vaultspec_core/tests/cli/test_sync.py`

Fixes applied:

- Custom docs directories are now respected when structure repair rewrites
  incoming `related:` references after filename normalization.
- Repair changed-file fingerprints now scan the configured docs directory
  instead of hardcoding `.vault/`.
- Dry-run index planning now matches mutating behavior and skips unknown
  feature names with no graph nodes.
- Human repair output filters INFO diagnostics before truncating the
  unresolved list, so later errors and warnings remain visible.
- Provider-scoped top-level sync now renders only the requested provider.
- Skills, agents, and MCP source mutations now emit the same top-level sync
  follow-up guidance as rule mutations.
- Rule removal guidance now reports the canonical `.md` source path.

Additional regression coverage added for custom docs-dir repair, custom
docs-dir changed-file reporting, dry-run unknown feature planning, unresolved
diagnostic rendering, provider-scoped sync output, JSON output purity, and
non-rule source mutation guidance.
