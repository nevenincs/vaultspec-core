---
tags:
  - '#audit'
  - '#firmware-wording-review'
date: '2026-06-10'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` audit: `firmware reconciliation code review`

## Scope

Gate review before the P09 close-out of the firmware reconciliation campaign:
132 commits covering plan Steps S01-S120, comprising markdown firmware edits
under `src/vaultspec_core/builtins/`, two trivial Python remaps in
`src/vaultspec_core/vaultcore/hydration.py` plus one new hydration test, and
the template rename to `templates/reference.md`. Two parallel reviewers: a
firmware-consistency pass verifying the plan's Verification contract and
hunting campaign-introduced damage, and a structural pass over the Python
diff, rename integrity, frontmatter enums, execution trail, and commit
hygiene. This document is the rolling task queue; entries move to resolved as
remediation lands.

## Findings

### HIGH

- `REVIEW-001` | HIGH | open - severity-vocabulary contradiction in the
  Verify trio, introduced by P07.S63. `templates/code-review.md` line 35 hint
  says the severity scale is "critical, sharp, minor", while
  `agents/vaultspec-code-reviewer.md` mandates CRITICAL/HIGH/MEDIUM/LOW and
  `skills/vaultspec-code-review/SKILL.md` says "triaged LOW->CRITICAL". An
  agent obeying all three receives two incompatible scales. Fix: align the
  template hint to the persona's published taxonomy (critical, high, medium,
  low).
- `REVIEW-002` | HIGH | open - exec-record authoring path self-contradictory,
  sharpened by P07.S64. `templates/exec-step.md` and the machine-filled
  placeholder class in `rules/vaultspec.builtin.md` forbid filling
  `{step_id}`/`{plan_stem}`/`{heading}`/`{scope_block}` by hand, yet
  `skills/vaultspec-execute/SKILL.md` and all three executor personas
  instruct hand-constructing Step Record filenames and frontmatter and never
  name the existing `vaultspec-core vault add exec --step` scaffold verb.
  Fix: add the scaffold instruction to the execute skill and the executor
  trio's Documentation sections.

### MEDIUM

- `REVIEW-003` | MEDIUM | open - literal `'#feature'` tag examples survive
  in four personas (`agents/vaultspec-adr-researcher.md`,
  `agents/vaultspec-code-reviewer.md`, `agents/vaultspec-docs-curator.md`,
  `agents/vaultspec-writer.md`) after P08 converted the five skills to
  `'#{feature}'`; skill and persona now state the same schema with different
  placeholder forms, failing the plan's Verification grep as written.
- `REVIEW-004` | MEDIUM | open - phantom skill name survives in
  `docs/framework.md` ("call the `vaultspec-write-plan` skill"); outside the
  builtins scope but reached via the CLI rule's manual link.
- `REVIEW-005` | MEDIUM | open - interim verb breakage at HEAD:
  `vault add reference --dry-run` errors with "No template found" because
  the Python remap landed ahead of the mirror sync (deployed mirror still
  ships `ref-audit.md`). P09.S122 is the planned fix; P09.S126 must log the
  downstream-upgrade hazard (workspaces upgrading the package without
  re-running `vaultspec-core install --upgrade` hit the same error with no
  remediation hint).

### LOW

- `REVIEW-006` | LOW | open - British spellings beyond the research
  inventory: "authorising/AUTHORISING" in `templates/plan.md`,
  `skills/vaultspec-write/SKILL.md`, `agents/vaultspec-writer.md`;
  "parallelised" in `templates/plan.md`; "summarised" in `templates/adr.md`;
  "synthesised" in `reference/cli.md`.
- `REVIEW-007` | LOW | open - "execution-log artifact" stragglers in
  `agents/vaultspec-writer.md` and `templates/plan.md` against the unified
  Execution Records noun.
- `REVIEW-008` | LOW | open - unbalanced parenthesis in the
  `templates/adr.md` implementation hint.
- `REVIEW-009` | LOW | open - stray space "vaultspec- research" in
  `skills/vaultspec-write/SKILL.md`.
- `REVIEW-010` | LOW | open - fragmented bullet pair in
  `skills/vaultspec-code-review/SKILL.md` ("**Mandatory:** At the end of
  every cycle" / "- before marking a feature as Done").

### Verification contract status

D1, D2, D3, D5, D6, D7, D8, D9 verify PASS; D4 passes with the REVIEW-002
caveat; the D14/D15 grep bullet is PARTIAL (REVIEW-003, REVIEW-006). The
structural pass is a clean sign-off: Python diff exactly within the ADR's
trivial-remap allowance with a real non-tautological test (19 targeted tests
pass), rename complete at source with zero stale references outside
historical vault documents, frontmatter enums total (no `tier: MEDIUM`
anywhere), 120 Step Records plus 8 phase summaries all schema-clean, plan
checker exit 0, and no commit in the range touches the deployed mirrors.

## Recommendations

- Resolve REVIEW-001, REVIEW-002, and REVIEW-003 in a remediation pass
  before P09 propagation so the mirror inherits a clean state; ride
  REVIEW-004 and REVIEW-006 through REVIEW-010 along in the same pass.
- Execute P09.S121-S126 immediately after; S126 must capture the
  REVIEW-005 downstream-upgrade remediation (a one-release template-name
  fallback in `get_template_path` or an actionable error hint naming
  `vaultspec-core install --upgrade`).
- Re-run the failed Verification greps after remediation and record the
  evidence in the P09 summary.

## Codification candidates

- **Source:** findings REVIEW-001 and REVIEW-002 (and the campaign's root
  cause: renamed artifacts leaving dangling prose references), matching the
  candidate the feature ADR already names.
  **Rule slug:** `firmware-reference-parity`.
  **Rule:** Every skill, persona, template, or CLI verb named in firmware
  prose must resolve to a shipped artifact of exactly that name, and a
  rename must update every referencing surface in the same change.
