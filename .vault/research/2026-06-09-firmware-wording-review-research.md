---
tags:
  - '#research'
  - '#firmware-wording-review'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-03-11-naming-surface-audit]]'
  - '[[2026-02-22-skill-audit-research]]'
  - '[[2026-02-22-skill-audit-adr]]'
---

# `firmware-wording-review` research: `md firmware wording and consistency review`

A wording, consistency, and semantic-correctness review of the vaultspec
markdown firmware: the bundled rules, system prompt fragments, skills, agent
personas, and templates under `src/vaultspec_core/builtins/` (canonical
source) and their deployed mirror under `.vaultspec/rules/`. The Python
implementation was out of scope. Five parallel reviewers covered five slices:
skills, agent personas, templates, rules plus system fragments, and a factual
cross-check of every CLI invocation referenced in the firmware against the
live 0.1.26 CLI. Prior overlapping work (the 2026-03-11 naming-surface audit
and the 2026-02-22 skill audit) was consulted; none of the findings below
re-report items those resolved.

## Findings

### scope and method

- Canonical surface: 46 markdown files under `src/vaultspec_core/builtins/`
  (6 rules, 4 system fragments, 11 skill directories, 11 personas plus 2
  embedded documentation agents, 9 templates, 1 CLI reference).
- Severity vocabulary: critical (directs agents at something that does not
  resolve or contradicts itself with behavioral consequence), sharp
  (misleading, stale, or internally inconsistent), minor (polish).
- Raw finding count across reviewers: 98; deduplicated below into themes.

### critical: phantom skill name vaultspec-write-plan

The shipped skill is named `vaultspec-write`
(`builtins/skills/vaultspec-write/SKILL.md`), but the firmware routes the
entire Plan phase to `vaultspec-write-plan`, which does not exist:

- `builtins/system/03-vaultspec.md` line 25 (pipeline table) and line 68
  (intent table)
- `builtins/rules/vaultspec.builtin.md` line 35 (skill catalog)
- `builtins/skills/vaultspec-code-research/SKILL.md` line 24 (pipeline
  cross-reference)

The 2026-02-22 skill audit confirms the skill shipped as
`vaultspec-write-plan` before the directory migration; the rename left these
references dangling. Fix is a one-name decision applied everywhere.

### critical: the verify-phase artifact has three contradictory addresses

- `builtins/system/03-vaultspec.md` line 27 says the Verify artifact is
  `.vault/exec/.../review`.
- `builtins/skills/vaultspec-code-review/SKILL.md` lines 28 and 48 and the
  `vaultspec-code-reviewer` persona line 87 say
  `.vault/audit/yyyy-mm-dd-{feature}-code-review-audit.md` - a double-type
  suffix no convention documents.
- `builtins/rules/vaultspec.builtin.md` line 20 defines the audit artifact as
  `yyyy-mm-dd-<feature>-audit.md` only.
- `builtins/templates/code-review.md` line 3 hardcodes the `#audit` directory
  tag, which per the tag taxonomy requires the file to live in
  `.vault/audit/`, contradicting the system prompt's exec-folder path.
- The Documentation Hierarchy in `vaultspec.builtin.md` has no Audit node at
  all, even though ADRs and Plans "depend on: audits".

One canonical review-artifact path and tag must be chosen and propagated to
all five surfaces.

### critical: read-only personas carry unfulfillable persistence mandates

`vaultspec-code-reviewer`, `vaultspec-adr-researcher`, and
`vaultspec-reference-auditor` all declare `mode: read-only` with no Write or
Edit tool, yet each body mandates persisting an artifact to `.vault/`
(review report, research document, reference snapshot respectively). Either
the personas gain Write, or the firmware states that the dispatching skill
persists on their behalf. Related: `vaultspec-project-coordinator` is the
only read-write persona without Write/Edit, so the `mode:` field currently
guarantees nothing anywhere.

### sharp: skills teach hand-authoring that the CLI rule forbids

`builtins/rules/vaultspec-cli.builtin.md` forbids "hand-writing frontmatter,
filenames, or new `.vault/` documents" and mandates
`vaultspec-core vault add`. Yet every artifact-producing skill (adr,
research, write, code-review, code-research, curate) instructs saving
hand-authored documents from templates with hand-written frontmatter, and no
skill mentions `vault add`. Agents receive two always-on contradictory
mandates. The same file also contradicts itself internally: the absolute
Mandate at line 14 versus the "Allowed manual edits" section permitting body
prose edits. Skills should be rewritten to scaffold via `vault add`, then
edit body prose.

### sharp: discipline rules are anchored to a 0.1.19 CLI that 0.1.26 has outgrown

Verified against the live CLI:

- `vault feature archive` now has `--dry-run`, a paired `unarchive` verb,
  and exits 1 with an error on a nonexistent tag. The archive-discipline and
  dry-run-discipline rules still assert "no --dry-run, no reversal verb" and
  "exit 0 with a silent no-op" (`vaultspec-archive-discipline.builtin.md`
  lines 21-22 and 64; `vaultspec-dry-run-discipline.builtin.md` lines 22 and
  60).
- `install --upgrade --dry-run` now prints a populated preview; the dry-run
  rule line 66 still calls it empty.
- Every plan mutator now carries `--dry-run` and an opt-in `--canonicalise`
  ("strip unknown prose blocks"), implying the plan-body-preservation fix
  landed; the plan-editing-discipline rule still describes prose destruction
  as current behavior (needs one live confirmation against a real plan).
- The version anchor "verified against 0.1.19" is stale.

Each rule's own Status section already prescribes the shortening now due.

### sharp: reference/cli.md lags the live CLI surface

The bundled machine-facing reference omits flags that sibling rules depend
on: `vault add` is missing `--tier`, `--step`, `--all-steps`, `--no-hints`;
`vault feature archive` is documented with `--json` only (no `--dry-run`,
`--no-hints`); `vault feature unarchive` has no prose section; the
`vault check` prose list omits `rename-integrity`; plan verbs omit
`--phase`, `--wave`, `--dry-run`, `--canonicalise`; no section documents the
sync output vocabulary that `vaultspec-cli.builtin.md` describes (the rule's
description itself verified accurate against live `--json` output).
Positively: every CLI invocation referenced anywhere in the firmware
resolves; no command is misspelled or nonexistent.

### sharp: orphaned firmware members

- `builtins/templates/ref-audit.md` is referenced by zero skills and zero
  personas; `vaultspec-code-research` (its producer) names no template and is
  the only artifact-producing skill without a frontmatter-and-tagging
  mandate.
- Personas `vaultspec-researcher` and `vaultspec-reference-auditor` are
  loaded by nothing.
- Shipped skills `vaultspec-team` and `vaultspec-projectmanager` appear in
  no catalog or intent table.
- The reference doc type carries four names across the firmware: file
  `ref-audit.md`, heading and tag "reference", hierarchy node "Reference
  Audit", pipeline phase "1 Reference", produced by "code-research". One
  noun should win.

### sharp: executor trio incoherence

- `vaultspec-low-executor` lines 10-12 carry the high-tier mission statement
  verbatim ("sophisticated code patterns, deep architectural integrity"),
  contradicting its own low-tier description.
- Low-executor lacks the "Critical Requirement" mandatory-code-review
  section the other two carry, with no documented exemption.
- The middle tier is named three ways: filename "standard", description
  "medium-tier", frontmatter `tier: MEDIUM`.
- `vaultspec-writer` routes Steps only to standard and high executors;
  low-tier Steps have no routing target anywhere.
- The trio's Documentation sections are non-parallel; only low points at the
  `exec-step.md` template.

### sharp: skill and persona contract drift

- `vaultspec-adr` drafts ADRs "using `vaultspec-writer`", but that persona is
  exclusively a plan architect whose tagging mandate covers `#plan` only; no
  persona owns ADR authorship. The adr-researcher's description claims it
  "formalizes decisions into an ADR" while its body forbids exactly that.
- `vaultspec-curate` says the curator persists an audit report and fixes
  violations in-place; the docs-curator persona says it rarely edits
  directly, delegates all modifications, and persists nothing.
- `03-vaultspec.md` line 82 asserts "team dispatch tools" as available
  infrastructure; the team and research skills explicitly hedge ("a
  coordination policy, not a shipped MCP API contract"). The hedged wording
  should win.
- The reference-auditor's snapshot template instructs body-text `Related:`
  lines - exactly the Class A "Drifted Content" violation the docs-curator
  is told to repair.
- The codify trio (rule, skill, persona) agrees on destination and naming
  but drifts on supersession mechanics (three different marking procedures)
  and on whether codification requires a completed execution cycle (persona
  and skill say yes, the rule omits it).

### sharp: template placeholder-system leaks

Measured against the placeholder tables in `vaultspec.builtin.md`:

- `plan.md` line 6 uses the only angle-bracket placeholder (`tier: <tier>`),
  unquoted.
- `plan.md` line 93's H1 (`{feature} {phase} plan`) is a fossil of the
  pre-tier one-plan-per-phase model; a plan spans all phases, and the
  filename pattern has no phase segment. The rules' heading example
  faithfully canonizes the same fossil.
- Undefined and convention-violating placeholders: `{TOPIC}`, `{LEVEL}`,
  `{Summary}`, `{DESCRIPTION}` (code-review.md, uppercase, partly outside
  comments); `{heading}`, `{scope_block}`, `{step_id}`, `{plan_stem}`
  (exec-step.md, snake_case); `{file1}`, `{file2}` plus instructional prose
  outside comment blocks (exec-summary.md, survives sanitize).
- `audit.md` is the sole template seeding `related: []` against the
  always-populate rule its own hint states.
- `code-review.md` H1 uses Title Case, breaking the all-lowercase heading
  convention every sibling follows.
- Hint blocks in 7 templates use uppercase `YYYY-MM-DD` against the
  lowercase `{yyyy-mm-dd}` convention; templates quote the date value while
  the rules' example shows it unquoted; 7 templates repeat the garbled hint
  "DO NOT add frontmatter fields outside the frontmatter."
- `index.md` declares an undocumented `generated:` frontmatter field.
- `plan.md` line 173's verification hint assumes Waves exist at every tier.

### sharp: source/mirror drift

`reference/cli.md`, `vaultspec-codify.builtin.md`, and the codify SKILL.md
differ between `src/vaultspec_core/builtins/` and `.vaultspec/rules/`. The
diff is pure line-reflow (88 versus 80 column wrap), src side newer (commit
`5b22a25`). `install --upgrade --dry-run` confirms: 3 updated, 46 unchanged.
One `vaultspec-core install --upgrade` reconciles it.

### minor: catalog gaps and vocabulary drift

- `vaultspec.builtin.md` skill catalog omits `vaultspec-code-review` and
  `vaultspec-curate`.
- Three names for one artifact: "Execution Records" (hierarchy), "Execution
  Logs" (summaries dependency), "execution-log artifact" (system prompt).
- "the .vault vault" doubled phrasing in curate skill and docs-curator
  persona; `read_file` host-specific tool id in vaultspec-writer;
  "safety auditors" referenced by reference-auditor though the persona is
  retired; "project-bondedness" neologism in codifier versus "project-bound"
  elsewhere.
- Announce-line convention: 8 of 11 skills carry the canonical line;
  execute and team have none; write uses a divergent form.
- Literal `'#feature'` tag examples in five skills invite verbatim copying;
  the convention placeholder is `#{feature}`.
- `vaultspec-execute` instructs "Start with Phase P##" which is impossible
  at L1 (steps only).
- Embedded documentation agents (wireframe, editorial-reviewer) have no
  frontmatter at all while all 11 top-level personas share a schema;
  wireframe-agent repeats its mandatory-read instruction twice and uses
  square-bracket placeholders.
- Style drift: mixed British/American spelling (serialiser, behaviour,
  centre versus favor); em dashes in three rules versus spaced hyphens in a
  fourth; numbered procedural lists in rules whose sibling fragment mandates
  bullets; three bold-label conventions in `01-core.md`; fragile ordinals
  ("Second worked example", "Third worked example") across discipline rules;
  orphan `<!-- end conventions -->` marker in `03-vaultspec.md`.

### minor: typo inventory

- `vaultspec-adr/SKILL.md`: "fundations", "considere null and void",
  missing conjunction at line 20.
- `vaultspec-write/SKILL.md`: "agent personaa".
- `vaultspec-code-review/SKILL.md`: "continously", garbled "rolling log of
  task queue" phrase.
- `vaultspec-research/SKILL.md`: grammatically broken description fragment.
- `templates/adr.md`: "constrainst", "condense but clear", "descision".
- `templates/exec-step.md`: "Succint", "failiures" twice, "Scafolds", stray
  `(;` punctuation.
- `system/02-operations.md`: "Use **Concise & Direct:** tone", "i.e." where
  "e.g." is meant.
- `vaultspec-codifier.md`: verb-less sentence "the back-pointer structures."
- Positive: the gross errors of older deployed copies ("facour", "hight
  quality", "Must confirming") are already fixed in canonical src.

## Recommendations

- Decide the two naming questions first, since everything else propagates
  from them: the plan skill's name (`vaultspec-write` versus
  `vaultspec-write-plan`) and the verify-phase artifact's canonical home and
  tag. These are ADR-worthy decisions.
- Refresh the three audit-derived discipline rules against 0.1.26 per their
  own Status clauses, and regenerate `reference/cli.md` from the live Typer
  surface (or add the missing rows by hand).
- Resolve the hand-authoring contradiction by rewriting skill persistence
  steps around `vault add` plus body-prose editing.
- Adopt one persona contract: either grant Write to artifact-producing
  read-only personas or move persistence to the dispatching skill, and fix
  the executor trio (low-tier mission, review requirement, tier naming,
  routing).
- Sweep templates for the placeholder leaks and run a single typo/style
  pass (spelling locale, dash convention, label style, announce lines).
- Run `vaultspec-core install --upgrade` to clear the cosmetic 3-file
  mirror drift.
