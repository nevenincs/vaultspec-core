---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S126
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# remediate the template-rename downstream-upgrade hazard in code (D16, REVIEW-005)

## Scope

- `src/vaultspec_core/vaultcore/hydration.py`
- `src/vaultspec_core/vaultcore/tests/test_hydration.py`
- `.vault/audit/2026-06-10-firmware-wording-review-audit.md`

## Description

- Added a `_LEGACY_TEMPLATE_NAMES` mapping (`DocType.REFERENCE -> ref-audit.md`) and a
  legacy-filename fallback branch to `get_template_path`: when the renamed
  `reference.md` is absent, the resolver returns the legacy `ref-audit.md` if it exists
  and warns, naming `vaultspec-core install --upgrade` as the remedy
- Strengthened the `create_vault_doc` "No template found" `FileNotFoundError` to name
  the same remedy when neither filename resolves
- Added five real unit tests in `test_hydration.py` covering current-name preference,
  legacy fallback with warning assertion, both-missing `None` return, end-to-end
  scaffolding from a legacy template, and the actionable-error message
- Ran the targeted hydration suite, the type checker, and the linter; flipped REVIEW-005
  to resolved in the audit with evidence

## Outcome

The plan row's verbatim instruction was to "log follow-up issues for any Python work
surfaced by the tier-enum and template-filename code-binding checks". The user explicitly
overrode that wording for this Step: the template-filename hazard is remediated in code
here rather than logged, and no `gh issue create` was run.

Design chosen: option (a) legacy-filename fallback AND an actionable message, the cleaner
of the two the Step contract offered. The resolver now degrades gracefully on a stale
workspace (it keeps resolving the REFERENCE template from the pre-rename `ref-audit.md`)
while steering the operator to the durable fix via a warning that names
`vaultspec-core install --upgrade`. The mapping is data-driven, so any future template
rename gains the same one-release grace by adding a single entry. The hard-failure path
(`create_vault_doc` raising when neither filename exists) carries the same remedy in its
message, so even a mirror with no template at all produces an actionable error rather
than a bare "No template found".

REVIEW-005 cleared. Evidence:

- `uv run --no-sync pytest -q src/vaultspec_core/vaultcore/tests/test_hydration.py`
  reports `21 passed` (16 prior + 5 new). New test names:
  `TestTemplatePathLegacyFallback::test_reference_resolves_to_current_filename`,
  `::test_reference_falls_back_to_legacy_filename`,
  `::test_reference_missing_both_names_returns_none`,
  `::test_create_vault_doc_reference_uses_legacy_template`,
  `::test_create_vault_doc_missing_template_names_remedy`.
- `vault add reference -f review005-check --dry-run` resolves to
  `2026-06-10-review005-check-reference.md` with no "No template found" error.
- `ty check` and `ruff check` on both modified Python files report "All checks passed!".

The five tests are non-tautological: each constructs a temp content root on the real
filesystem with a specific template-file population (current only, legacy only, neither,
or both) and asserts the resolver's real branch behavior; the error test derives its
expected substring from the remedy command the specification names, not from a captured
run.

Tier-enum check (P05.S34): the S34 record's verdict is UNBOUND - the persona frontmatter
`tier:` value is never parsed, mapped, or asserted as an enum in any Python loader or
test (the agent renderers drop the key; the only `MEDIUM` literals in tests assert the
key is dropped). The MEDIUM-to-STANDARD frontmatter move in S35-S40 was therefore a pure
documentation change with no code binding. No separate enum follow-up issue is needed,
and none was created. The only Python work the two code-binding checks surfaced is the
template-filename hazard remediated above.

## Notes

The plan body said "log issue" for both code-binding checks; the user directed in-line
remediation for the template-filename hazard and confirmed the tier-enum check is
UNBOUND. The new Python (resolver fallback plus five tests) is in scope for orchestrator
re-review before final feature sign-off.
