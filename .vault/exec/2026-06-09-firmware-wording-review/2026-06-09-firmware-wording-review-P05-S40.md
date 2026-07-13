---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S40
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-researcher.md`

## Description

- Move the frontmatter `tier: MEDIUM` to `tier: STANDARD` in the researcher persona,
  cleared by the S34 code-binding verdict (UNBOUND) (D9)
- Verify no `tier: MEDIUM` remains anywhere under `src/vaultspec_core/builtins/` (the
  one surviving MEDIUM is the code-reviewer's finding-severity taxonomy, a different
  vocabulary, deliberately untouched)
- Run the full test suite once after this last enum move, per the phase guidance
- Fix the nine bare-CLI-reference offenders the suite surfaced (see Notes) and re-run
  to green

## Outcome

All six middle-tier personas now declare `tier: STANDARD` (standard-executor,
codifier, docs-curator, reference-auditor, project-coordinator, researcher), closing
the D9 enum unification. Full test suite result: first run 1 failed / 531 passed
(stopped at first failure with -x); after the prose fix, **2035 passed, 0 failed**
(`uv run --no-sync pytest -x -q`, 285s).

## Notes

Incident: the first suite run failed
`test_cli_language_contract.py::test_docs_do_not_teach_bare_cli_commands`, which
forbids backticked CLI snippets lacking the `vaultspec-core` entry point. None of the
nine offenders involved the tier enum: two were introduced by this phase's S27/S28
rewordings (the orchestrator-owned schema sentence in the code-reviewer and
adr-researcher personas), three by the P02 discipline-rule refresh
(archive-discipline `vault feature unarchive`; dry-run-discipline
`vault feature archive` and `install --upgrade --dry-run`), and four by the P04 skill
rewrites (the `vault add` scaffold sentence in the adr, research, write, and curate
skills). Fixed all nine by prefixing `vaultspec-core`, which also matches the CLI
rule's own invocation mandate. The pre-commit hooks do not run this test, which is
why the P02/P04 offenders landed; the suite is green again well before the P09.S124
gate.
