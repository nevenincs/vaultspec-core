---
tags:
  - '#research'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - '[[2026-07-09-firmware-mcp-primacy-adr]]'
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-06-13-commit-linkage-adr]]'
---

# `firmware-code-boundary` research: `where to state the code-must-not-reference-.vault boundary`

The question: where in the bundled firmware (rules, system prompt, agent personas,
skills) should language land that forbids executing agents from embedding dev metadata
\- `.vault/` document stems, plan/ADR/audit identifiers, Step ids, wiki-links, harness
paths - into the codebase, without bloating the framework. The premise under review:
`.vault/` is a removable harness, not an integrated part of the codebase; code must
stand on its own; the reference direction is one-way (vault documents cite code, never
the reverse). The evidence picture: the prohibition is entirely absent today - no
firmware surface states it and one requirement is misreadable as inviting the reverse
direction - but the one-way convention is already implicit in the documentation
hierarchy and the locator rules, so the fix is a small number of well-placed sentences
on the surfaces that write or gate code, following the placement architecture the
mcp-primacy decision validated. One adjacent decision (commit-linkage trailers) and one
self-hosting nuance (this repo's own product domain is the vault) constrain the wording.

## Findings

### The boundary is unstated everywhere in the firmware

No firmware surface forbids code-to-vault references. A sweep of
`src/vaultspec_core/builtins/` for boundary language (dev metadata, cross-reference,
"stand on its own", code-referencing-`.vault` phrasings) returns nothing relevant: the
only hits are the vault-internal `check references` verb (`reference/cli.md:103`), the
documentation skill's claim-grounding instruction
(`skills/vaultspec-documentation/SKILL.md:204`), and the curate skill description. The
nearest analogue mandate - the Comments bullet at `system/01-core.md:27` ("*NEVER*
describe changes through comments") - polices comment content but says nothing about
vault or harness references. The gap is absence, not weak wording.

### The one-way direction is already implicit, and one line invites misreading

The framework's own conventions already run vault-to-code only. The documentation
hierarchy (`rules/vaultspec.builtin.md:54-57`) states that artifacts lower in the
hierarchy reference those above them - and source code does not appear in the hierarchy
at all. The research template's link rules mandate citing code from vault documents as
backtick locators (`templates/research.md`, LINK RULES hint block), and Step Records
list modified files (`agents/vaultspec-standard-executor.md:49`). Nothing instructs the
reverse. The one misreadable line is the execute skill's Traceability requirement -
"All changes must be mapped to their respective Step Records"
(`skills/vaultspec-execute/SKILL.md:102`) - which an executor can satisfy wrongly by
annotating code with Step ids instead of listing files in the record. Any new wording
should disambiguate this sentence in place.

### Surface inventory: three audience classes, five candidate homes

The mcp-primacy decision's audience split governs placement (recorded in the related
ADR): always-on rules and the assembled system prompt address the orchestrating
session; the ten personas address dispatched subagents; skills load per phase. The
surfaces that write or gate code:

- `system/01-core.md:11-61` Mandates list - the only always-on surface addressing every
  code-writing session, orchestrator or not; the Comments bullet at line 27 is the
  structural analogue for a new boundary bullet.
- `system/03-vaultspec.md:12-17,111` - names `.vault/` as the artifact store but never
  characterizes it as a removable harness; the natural home for the one-sentence
  boundary characterization.
- The executor trio, `agents/vaultspec-{low,standard,high}-executor.md` - the personas
  that actually write code; structurally parallel by prior decision (D9 of the
  firmware-wording-review ADR), so any bullet must land identically in all three (Core
  implementation mandate section, e.g. `agents/vaultspec-standard-executor.md:20-49`).
- The review gate, `agents/vaultspec-code-reviewer.md:54-64` (Intent Domain) plus the
  severity taxonomy at lines 108-121 - the enforcement surface; a boundary violation
  needs a named severity to be actionable (drift detection at line 64 is the nearest
  existing dimension).
- `rules/vaultspec.builtin.md:54-57` - the hierarchy prose can state the one-way
  direction in one clause, closing the implicitness.

Surfaces with no code-writing footprint (researchers, auditors, writer, coordinator,
curator personas; research/adr/write/curate/team/projectmanager skills) need nothing;
touching them is pure bloat. The wording pattern precedent is the mcp-primacy Q4 shape:
state the invariant once at the canonical home, echo only where load-bearing, one
clause per surface rather than per sentence.

### Commit trailers are the sanctioned linkage channel and must stay carved out

The commit-linkage decision (recorded in the related ADR, 2026-06-13) deliberately
created an opt-in, enrichment-only channel for commit-to-vault association: git
trailers `Vaultspec-Step:` / `Vaultspec-Feature:`, advisory validation, never
load-bearing. Commit metadata is not source-file content, and that decision already
guards the reverse risk (its codification candidate forbids code paths depending on
trailers). New boundary wording must scope to tracked source-file content - code,
comments, docstrings, identifiers, user-facing docs, configuration - and explicitly
leave git trailers (and commit messages generally) to the commit-linkage convention,
or the two decisions contradict.

### Self-hosting nuance: forbid referencing the project's own records, not the string `.vault`

vaultspec-core's product domain is the vault: its source legitimately constructs and
manipulates `.vault/` paths (e.g. `src/vaultspec_core/config/workspace.py:348`) and its
tests build vault trees. A wording that forbids the literal path string would flag this
repo's entire codebase and any downstream tool in the same domain. The forbidden class
is references to the project's *own development records*: this project's plan/ADR/audit
document stems, Step and container identifiers, feature-index entries, wiki-links, and
`.vaultspec/` harness contents, appearing in product source or user-facing docs. The
evidence favors wording the mandate as record-reference-directed ("the project's own
`.vault/` documents and identifiers") rather than path-string-directed.

### Enforcement is wording-only today; a mechanical check is possible but noisy

No `vault check` family checker inspects source code; the check engine's scope is
`.vault/` documents and spec state. A future checker sweeping tracked source for the
project's own document stems or `Vaultspec-`-style identifiers is implementable (the
stems are enumerable from `.vault/`), but ships false-positive risk in vault-domain
codebases and is Python work - out of scope for a documentation-only firmware pass
under the same constraint the firmware-wording-review ADR set
(behavioral changes become logged follow-ups). What the ADR must settle: whether to
register the checker as a follow-up issue.

### Not investigated

Provider-specific rendered outputs (`.claude/`, other provider directories) were not
audited beyond the synced rule mirrors; they regenerate from the builtins, so source
edits propagate by construction. Downstream managed projects' actual violation
frequency was not measured; the premise is taken from the user mandate, not from an
observed-defect corpus.

## Sources

- `src/vaultspec_core/builtins/system/01-core.md:11-61`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:12-17`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:111`
- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md:54-57`
- `src/vaultspec_core/builtins/reference/cli.md:103`
- `src/vaultspec_core/builtins/skills/vaultspec-documentation/SKILL.md:204`
- `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md:102`
- `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md:39`
- `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md:20-49`
- `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:54-64`
- `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:108-121`
- `src/vaultspec_core/config/workspace.py:348`
