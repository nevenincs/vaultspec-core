---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S124
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# run the full test suite via uv run --no-sync pytest and the prek hooks on modified files, confirming green (D16)

## Scope

- `tests`

## Description

- Ran the full suite with `uv run --no-sync pytest -q`
- Ran `uv run --no-sync prek run --all-files`
- Recorded the exact tallies for both

## Outcome

Full test suite: `2041 passed in 309.49s (0:05:09)`, exit code 0. Zero failures, zero
errors, zero skips reported in the summary. The run includes the five new hydration tests
added in S126; the prior campaign audit recorded 19 targeted hydration tests passing, and
the suite total now reflects the REVIEW-005 remediation without regression elsewhere.

prek hooks: all hooks `Passed` on `--all-files`. The hook set covers Ruff lint, Ruff
format, Taplo TOML lint, Ty type-check, mdformat (both the plain and wrapped
user-facing passes), pymarkdown style, Vault Doctor (Fix and Check), Vault sanitize
annotations, provider-artifact check, and the CHANGELOG guard. No hook reported a
failure or rewrote a tracked file out from under the commit.

Both gates are green. No test failed, so no STOP condition was triggered and nothing was
papered over.

## Notes

The suite is run on the whole repository rather than a modified-file subset because the
S126 change touches a shared resolver (`get_template_path`) consumed across the vault
command surface; a full run is the honest proof that the resolver change is regression-free.
