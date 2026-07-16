---
tags:
  - '#plan'
  - '#code-boundary-check'
date: '2026-07-16'
modified: '2026-07-16'
tier: L1
related:
  - '[[2026-07-16-code-boundary-check-adr]]'
  - '[[2026-07-16-code-boundary-check-research]]'
---

# `code-boundary-check` plan

## Description

This plan executes the code-boundary-check decision (see related): the opt-in
read-only source-boundary scanner as a standalone vault check code-boundary verb.
Needles are the vault's enumerable document stems (plus wiki-link forms); the walk
excludes vault, harness, provider, git, and cache directories with decode and size
guards; findings are WARNING severity and never affect the exit code;
run_all_checks membership is unchanged.

## Steps

- [x] `S01` - Implement the code-boundary checker module: needle enumeration from vault stems, excluded-dir source walk, decode guard, size cap, WARNING diagnostics; `src/vaultspec_core/vaultcore/checks/code_boundary.py`.
- [x] `S02` - Add the standalone vault check code-boundary subcommand with --json and --feature following the existing standalone-verb pattern; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `S03` - Add unit tests covering stem and wiki-link hits, literal-path non-hit, exclusions, feature filter, skip guards, and advisory exit code; `src/vaultspec_core/vaultcore/checks/tests/test_code_boundary.py`.
- [x] `S04` - Regenerate the bundled CLI reference and confirm the drift test; `src/vaultspec_core/builtins/reference/cli.md`.
- [x] `S05` - Run the gates and open the PR closing the issue; `src/vaultspec_core`.

## Parallelization

S01 lands first (the checker is the authority); S02 follows; S03 and S04 then
parallelize; S05 is last.

## Verification

- Scanner reports stem and wiki-link hits in source files and nothing for the
  literal vault path string alone; vault, harness, and provider dirs excluded.
- Exit code 0 with findings; no mutation surface.
- check all output byte-identical before and after.
- CLI reference drift test green; prek and the unit gate pass.
- Code review audit passes; PR closes the issue.
