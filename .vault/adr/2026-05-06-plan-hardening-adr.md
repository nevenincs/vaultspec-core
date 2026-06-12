---
tags:
  - '#adr'
  - '#plan-hardening'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-05-plan-hardening-adr]]'
  - '[[2026-05-05-plan-hardening-research]]'
---

# `plan-hardening` adr: vault plan CLI surface | (**status:** `proposed`)

This ADR authorises **Wave 2** of the `#plan-hardening` plan
document: the `vault plan` CLI implementation. Wave 1
(language-only firmware rewrite) is authorised separately by
`2026-05-05-plan-hardening-adr.md` and lands first.

## Context

The convention ADR (`2026-05-05-plan-hardening-adr.md`) defines
the natural-language contract for plan documents: the
`Epic > Wave > Phase > Step` hierarchy, the four complexity tiers
`L1`-`L4`, the flat append-only immutable identifiers
`S##`/`P##`/`W##`, and the rule that canonical-identifier order
and document order are independent. That ADR is enforced
socially in wave 1.

This ADR specifies the `vault plan` CLI subcommand surface that
mechanises the convention. The CLI lets writers create,
inspect, validate, and manipulate plan documents while
preserving every immutability and ordering rule the convention
ADR defines. Implementation (Python parser, AST, integration
with the existing `vaultspec-core` CLI) is deferred to a
follow-up plan; this ADR specifies only the surface contract.

The CLI is the bridge between the social-enforcement window of
wave 1 and the programmatic-enforcement future. Subsequent
Waves of `#plan-hardening` add validators, fixers, and structural
manipulators against the contract this ADR defines.

## Subcommand surface

The CLI uses noun-verb subcommand grouping under `vault plan`.
Container nouns (`step`, `phase`, `wave`, `epic`, `tier`) carry
their operations as inner verbs. Plan-level operations
(`status`, `check`, `query`) sit at the `vault plan` root.

| Form                                                                                     | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| :--------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `vault plan status [PATH]`                                                               | Report plan health, structure, completion.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `vault plan check [PATH] [--fix]`                                                        | Validate convention compliance; with `--fix`, apply autofixable items.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `vault plan query [PATH] FILTER`                                                         | Filter rows by container, tier, or completion state.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `vault plan step add [--phase P##] [--wave W##] -- "verb action; \`scope\`"\`            | Append a Step at the next-available `S##`, placed in document order at the tail of the target container.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `vault plan step insert (--before S## \| --after S##) -- "verb action; \`scope\`"\`      | Place a new Step at the named document position; canonical ID is next-available. The anchor Step's parent Phase is the new Step's parent.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `vault plan step move S## (--to-phase P## \| --before S## \| --after S##)`               | Re-parent (`--to-phase`) or re-position (`--before`/`--after`); canonical ID unchanged. `--before`/`--after` require the anchor to share the moving Step's current parent; cross-parent moves require `--to-phase`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `vault plan step remove S##`                                                             | Remove a Step; canonical ID retired and never re-used.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `vault plan step check S##`                                                              | Mark the Step closed (idempotent: already-closed Steps are unchanged).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `vault plan step uncheck S##`                                                            | Mark the Step open (idempotent: already-open Steps are unchanged).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `vault plan step toggle S##`                                                             | Flip the Step's checkbox state. Convenience for interactive use.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `vault plan step edit S## (--action "..." \| --scope "...")`                             | Edit the row's action statement or scope clause.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `vault plan phase add [--wave W##] -- "title"`                                           | Append a Phase at the next-available `P##`, placed in document order at the tail of the target Wave (or document at `L2`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `vault plan phase insert (--before P## \| --after P##) -- "title"`                       | Place a new Phase at the named document position; canonical ID is next-available.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `vault plan phase move P## (--to-wave W## \| --before P## \| --after P##)`               | Re-parent (`--to-wave`) or re-position (`--before`/`--after`); canonical ID unchanged. `--before`/`--after` require the anchor to share the moving Phase's current parent Wave; cross-parent moves require `--to-wave`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `vault plan phase remove P##`                                                            | Remove a Phase. Cascading retirement: every child Step's canonical ID is retired with the Phase. To preserve Steps under a different parent, `step move` them first.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `vault plan phase edit P## (--title "..." \| --intent "...")`                            | Edit the Phase title or intent paragraph.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `vault plan wave add -- "title"`                                                         | Append a Wave at the next-available `W##`, placed in document order at the tail of the document.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `vault plan wave insert (--before W## \| --after W##) -- "title"`                        | Place a new Wave at the named document position.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `vault plan wave move W## (--before W## \| --after W##)`                                 | Re-position in document order; the Epic frame is implicit so there is no `--to-epic`. All descendant display paths recompute against the new position.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `vault plan wave remove W##`                                                             | Remove a Wave. Cascading retirement: every descendant Phase and Step canonical ID is retired with the Wave.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `vault plan wave edit W## (--title "..." \| --intent "...")`                             | Edit the Wave title or intent paragraph.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `vault plan epic intent (--show \| --edit "...")`                                        | Inspect or edit the Epic intent block (`L4` only).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `vault plan tier --show`                                                                 | Print the current tier. Read-only.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `vault plan tier promote [--to L#] [--phase-title T] [--wave-title T] [--epic-intent S]` | Promote up one or more tiers per the convention ADR's *Promotion is non-renumbering and transitive* rule. With `--to L#`, the target tier is explicit (transitive across non-adjacent jumps). Without it, advance one tier. Existing identifiers are preserved; intermediate containers are instantiated with the next-available identifier in the target container's sequence. New containers require a title (or intent) string: `--phase-title` for a new Phase, `--wave-title` for a new Wave, `--epic-intent` for the new Epic intent paragraph. Missing flags are accepted in non-interactive mode by writing a `TODO: title` sentinel and emitting a `check` warning; interactive mode prompts. |
| `vault plan tier demote [--to L#] [--force]`                                             | Demote down one or more tiers. Demotion is refused (exit 1) if the collapsing tier contains more than one non-retired child container; `--force` overrides the refusal and lets the writer consolidate or accept the loss explicitly. Successful demotion retires the outermost containers' canonical identifiers. With `--to L#`, the target tier is explicit.                                                                                                                                                                                                                                                                                                                                        |

The Epic frame has no `add`/`remove`/`move` because there is
exactly one Epic per `L4` plan (per the convention ADR's
*Hierarchy and tiers* section). The Epic is materialised by
`tier promote --to L4` and dematerialised by `tier demote` from
`L4`.

## Identifier and ordering rules

Every mutating operation respects the convention ADR's
*Identifiers and addressing* and *Promotion is non-renumbering
and transitive* sections. The CLI contract is:

- New canonical identifiers (`S##`, `P##`, `W##`) are always
  next-available within the plan document. The CLI never
  reassigns existing identifiers.
- Removed canonical identifiers are retired permanently. Gaps
  in the sequence are visible and never re-used.
- **Cascading retirement**: when a parent container is removed
  (`phase remove`, `wave remove`), every descendant canonical
  identifier is retired with it. Writers who wish to preserve
  child Steps (or Phases) under a different parent must `step move` (or `phase move`) them before issuing the parent
  removal. The CLI may offer a `--require-empty` flag in a
  later Wave that errors if the parent has descendants;
  reserved, not exposed in wave 1.
- Re-parenting (`step move`, `phase move`) preserves canonical
  identifiers; only the display path recomputes against the new
  ancestor chain.
- Document order is independent of canonical identifier order.
  `insert --before/--after` and `move --before/--after` operate
  on document order; they never touch canonical identifiers.
- Tier promotion is transitive (`L1` to `L4` in one revision is
  legal); existing identifiers are preserved at every step;
  intermediate containers are instantiated with the
  **next-available** identifier in the target container's
  sequence. In a freshly-promoted plan with no prior history of
  the new container type, the next-available is `P01` or `W01`;
  in a plan where prior containers were created and retired,
  the next-available skips the retired identifiers.

The `--allow-id-change` flag is reserved as a global escape
hatch for any future operation that would mutate canonical
identifiers (e.g., a `compact` subcommand). It is not exposed
on any subcommand in wave 1. When un-reserved, it will require
an audit-trail line in the plan document recording the
mutation.

### Cascading retirement and execution artefacts

When a parent container is removed, every descendant Step's
canonical identifier is retired. Step Records that exist on
disk in `.vault/exec/` for those retired Steps are NOT deleted
by the CLI; they are left in place and become orphans
referencing retired identifiers. The `vault check` vault-wide
sweep flags such orphans as warnings (not errors) so writers
can decide whether to archive them manually. A future Wave may
add `--cascade-exec` to opt into archive-on-remove; that flag
is reserved, not exposed in wave 1.

### Move-flag precedence

`step move` accepts `S##` plus one of three flag groups:
`--to-phase P##` (re-parent only); `--before S##` or `--after S##` (re-position within the current parent); or `--to-phase P## --before S##`/`--after S##` (re-parent AND position within
the new parent). The combination is legal only if the anchor
Step resides in the destination Phase post-move. Any other
combination is a usage error (exit code 2) with a message
naming the conflict. The same precedence applies to `phase move` against `--to-wave`. `wave move` accepts only
`--before/--after` (Epic is implicit; no `--to-epic`).

### Parent resolution for `step add` / `step insert`

At `L1` neither `--phase` nor `--wave` may be specified; Steps
land at the document root. At `L2`, `--phase P##` is required
when no `--before/--after` anchor is given; with an anchor, the
parent is inferred from the anchor's Phase. At `L3` and `L4`,
`--phase P##` is required when no anchor is given; `--wave` is
not accepted because `P##` is plan-scope-unique (every Phase
identifier resolves to exactly one Wave). The same rule applies
to `phase add`/`phase insert` against `--wave`.

## Operation classification

Every subcommand is classified by side-effect class. The class
determines default safety semantics.

| Class                                 | Subcommands                                                                       | Default semantics                                                                                                                        |
| :------------------------------------ | :-------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------- |
| Read                                  | `status`, `check` (without `--fix`), `query`, `tier --show`, `epic intent --show` | No file modification. Always safe.                                                                                                       |
| Write (idempotent)                    | `check --fix`, `step check`, `step uncheck`                                       | Re-running produces the same result. Operates on autofixable items or already-converged state.                                           |
| Write (additive)                      | `step add`, `step insert`, `phase add`, `phase insert`, `wave add`, `wave insert` | Creates new identifiers. Existing content unchanged.                                                                                     |
| Write (state)                         | `step toggle`, `step edit`, `phase edit`, `wave edit`, `epic intent --edit`       | Modifies existing content; canonical identifiers unchanged.                                                                              |
| Write (re-parenting / re-positioning) | `step move`, `phase move`, `wave move`                                            | Canonical identifiers unchanged; ancestor chain or document order changes.                                                               |
| Write (destructive)                   | `step remove`, `phase remove`, `wave remove`, `tier promote`, `tier demote`       | Retires identifiers (remove or demotion) or restructures the document. Requires `--confirm` if interactive; supports `--dry-run` always. |

## `status` output

`vault plan status PATH` reports a structured snapshot of the
plan. The snapshot has both human and JSON forms.

The human form is one block:

```
Plan: 2026-05-05-plan-hardening-plan
Tier: L3 (Wave > Phase > Step)
PM association: n/a (only L4 plans declare one)
Counts: 2 Waves, 5 Phases, 23 Steps
Completion: 14 of 23 (61%)
Numbering health: clean
```

If the plan lacks a `tier:` frontmatter field (legacy / loose),
the snapshot reports `Tier: legacy (assumed L2)` and adds a
suggested migration line.

If numbering health is not clean, the snapshot lists the
specific issues (gaps with non-trivial size, padding drift,
display-path drift between document and current grouping).

The JSON form (`--json`) emits a structured object with the
same fields plus per-container completion arrays for scripting
use.

## Relationship to `vault check`

The existing `vault check` subcommand (see `.vaultspec/CLI.md`)
runs vault-wide health checks across all `.vault/` documents
(structure, frontmatter, links, schema, etc.). `vault plan check`
is distinct: it operates on a single plan document and applies
the plan-contract validation that this ADR specifies. The two
do not duplicate enforcement:

- `vault check` enforces vault-wide invariants: directory layout,
  frontmatter schema, wiki-link resolution, cross-document
  references, tag taxonomy.
- `vault plan check` enforces plan-document-internal invariants:
  hierarchy correspondence with declared tier, identifier
  hygiene, display-path correctness, Step row contract, the
  canonical structural-noun list defined in the convention
  ADR's *Hierarchy and tiers* section.

A plan document that passes both is fully compliant. The Python
implementation may share parsers and check-helpers between the
two surfaces, but the user-facing commands remain separate so
that `vault plan check` can target a specific plan during
authoring without invoking the vault-wide sweep.

## `check` and `check --fix`

`vault plan check PATH` validates compliance against the
convention ADR. The check covers:

- Frontmatter contract: presence and value of `tier:`; presence
  of `related:` for non-trivial plans.
- Hierarchy correspondence: the document's headings match the
  declared tier (`L1` no Phase / Wave / Epic headings; `L2` has
  Phase headings; etc.).
- Identifier hygiene: monotonic non-overlapping sequences;
  zero-padding present; no duplicate canonical identifiers.
- Display-path correctness: every Step row's display path
  matches its current ancestor chain.
- Row contract: checkbox shape, separator (ASCII spaced
  hyphen), action verb present, scope in inline backticks,
  trailing period, no `_Refs:_` footer (forbidden in body).
- Approved structural vocabulary: structural nouns appearing in
  heading lines (`#`/`##`/`###` rows), in container-identifier
  code spans (`` `S##` ``, `` `P##` ``, `` `W##` ``), and in
  the row-label position immediately preceding `--` in a Step
  row are restricted to the canonical four (`Epic`, `Wave`,
  `Phase`, `Step`). The check does not fire on free prose
  inside Phase intent paragraphs, Wave intent paragraphs, or
  the Epic intent block; writers may discuss content that
  mentions other terms in narrative.
- Separator convention: no em-dash (U+2014), no en-dash
  (U+2013) anywhere in the body or headings.

`check` without `--fix` reports findings with severity
(`error`, `warning`, `info`) and a fix hint per finding. Exit
codes match the existing vaultspec convention: `0` if no
findings; `1` if one or more `error` findings; warnings and
info findings alone do not fail the exit code. `check --fix`
exits `0` if no findings remain after autofixes; exits `1` if
findings persist (autofix incomplete or unfixable findings
present).

`check --fix` applies the following autofixable items
idempotently. Every autofix preserves canonical identifiers
exactly; no autofix mutates a `S##`, `P##`, or `W##` token.

- Checkbox spacing normalisation: `- []` becomes `- [ ]`;
  `- [X]` becomes `- [x]`; non-canonical states are flagged but
  not auto-fixed.
- Separator normalisation: em-dash and en-dash characters in
  body or headings are replaced with ASCII spaced hyphens.
- Trailing whitespace removal on row sentences.
- Display-path recomputation: rows whose display path does not
  match their current ancestor chain are recomputed against the
  current grouping. The canonical identifier is unchanged. This
  autofix exists defensively, to recover from hand-edits or
  interrupted multi-step operations; routine CLI workflows do
  not produce display-path drift.

Padding violations (e.g., a hand-written `S1` instead of `S01`,
or a hand-written `S007` when the current field width is 2) are
reported as errors but **not** auto-fixed: the convention ADR's
*Identifiers and addressing* section requires existing
identifiers to remain at their assigned padding, and rewriting
`S1` to `S01` would mutate a canonical identifier. Padding
violations indicate hand-authored content that bypassed the
CLI; the writer resolves them manually.

Any other finding is reported but not auto-fixed; the writer
or the user resolves it manually or with a more targeted
subcommand.

## `query`

`vault plan query PATH FLAGS` returns rows or containers that
match a combination of selectors and predicates. The two are
distinct:

- **Selectors** scope the query to a container subtree. At most
  one selector applies per invocation; the most-specific
  selector wins (`--phase` over `--wave`).
- **Predicates** filter Step rows within the selected scope.
  Predicates compose with `AND` semantics.

| Selector      | Returns                                |
| :------------ | :------------------------------------- |
| (none)        | The full plan body.                    |
| `--wave W##`  | The Wave block (intent + descendants). |
| `--phase P##` | The Phase block (intent + Steps).      |

| Predicate   | Filters Steps to ...                                                                       |
| :---------- | :----------------------------------------------------------------------------------------- |
| `--open`    | Steps with checkbox state `[ ]`.                                                           |
| `--closed`  | Steps with checkbox state `[x]`.                                                           |
| `--tier L#` | Returns the matching plan only when the plan's declared tier equals `L#`; otherwise empty. |

Selectors and predicates compose. `--phase P02 --open` returns
the Phase `P02` block with only its open Steps. Negation
(`--not-in`, etc.) is reserved for a later Wave; not exposed in
wave 1.

`vault plan query PATH --tier-only` is a separate read shortcut
that prints only the declared tier (matching the previous
`--tier` filter intent without overloading the predicate
column). Output respects `--json` for scripting.

## Common flags

The following flags apply to every subcommand unless noted.

| Flag                      | Purpose                                                                                                               |
| :------------------------ | :-------------------------------------------------------------------------------------------------------------------- |
| `--target DIR` / `-t DIR` | Operate on a target directory other than the current working directory. Matches existing `vaultspec-core` convention. |
| `--json`                  | Machine-readable output. Supported on every read subcommand.                                                          |
| `--dry-run`               | Preview without writing. Supported on every write subcommand.                                                         |
| `--confirm`               | Required for destructive operations when the CLI is run interactively. Skipped automatically in non-interactive mode. |
| `--help`                  | Show usage.                                                                                                           |

`PATH` is required (or `--feature TAG`, which resolves to the
single plan document for that feature). The CLI does not
attempt to infer a "current feature" from the working
directory; this matches the existing vaultspec convention where
`--feature TAG` is explicit on every command. If both `PATH`
and `--feature TAG` are given, `PATH` wins.

## Rollout surface

Implementation of the CLI (Python module under
`vaultspec_core`, parser for plan documents, integration with
the existing `vaultspec-core` Click app) is the scope of the
Wave 2 segment of the `#plan-hardening` plan document. This ADR
specifies the contract; the plan specifies the work.

The convention ADR's wave-1 surface mapping (the language-only
rewrite of `.vaultspec/` files) is unaffected by this ADR. The
language firmware lands first; the CLI lands second.

### Implementation-specifics delegation

This ADR specifies the architecture: subcommand surface, verbs,
flags, classes, identifier rules, gate semantics. It does NOT
specify implementation specifics that two reasonable Python
implementers could pick up and unify only with rework: the JSON
schemas for `--json` outputs (field names, types, envelope
shape), the finding object schema and stable code namespace
for `check` diagnostics, the regex or parser-traversal
predicates for each detection rule, the deterministic
input-output rules for each autofix transformation. Those
belong in the Wave 2 plan, where the implementer authors them
and they become contract-bound on plan approval.

The rule-extension prose mandated below (binding directives
inserted into each surface file) is similarly authored in the
Wave 2 plan, gated by the `vaultspec-docs-curator` and
`vaultspec-writer` reviewers, and bound on approval.

### Rule-extension mandate

When the CLI lands, the `.vaultspec/` rule files governed by
the convention ADR's surface mapping MUST be extended with
concise summary language that names the `vault plan` CLI as the
canonical surface for plan manipulation and binds writers and
executors to use it. Without this extension the CLI rollout is
incomplete: the contract exists, the implementation exists, but
nothing in the firmware tells writer or executor agents to
prefer the CLI over hand-editing.

Each extension is one paragraph per file (one sentence for
low-importance surfaces); cross-references this ADR by document
stem; is phrased as a binding directive ("MUST use", not "may
use"); and respects the convention ADR's approved structural
vocabulary.

Surfaces that receive a rule-extension:

- `rules/templates/plan.md` - extend the embedded hint blocks
  to name `vault plan` as the canonical surface for structural
  manipulation of the rendered plan.
- `rules/agents/vaultspec-writer.md` - persona-binding
  paragraph: the writer agent dispatches `vault plan`
  subcommands for structural manipulation rather than
  hand-editing the plan body.
- `rules/skills/vaultspec-write/SKILL.md` - canonical
  manipulation-surface paragraph naming `vault plan`.
- `rules/skills/vaultspec-execute/SKILL.md` - executors use
  `vault plan step check` / `step uncheck` to update Step state
  upon completion of a `<Step Record>`.
- `rules/agents/vaultspec-low-executor.md`,
  `vaultspec-standard-executor.md`,
  `vaultspec-high-executor.md` - one sentence each, mirroring
  the execute skill's CLI directive.
- `rules/system/03-vaultspec.md` - one paragraph in the
  pipeline description naming `vault plan` as the structural
  manipulation surface for plan documents.
- `README.md` - public-facing paragraph in the Planning
  subsection introducing the CLI to external readers.

Every rule-extension MUST be reviewed and gated by **both** the
`vaultspec-docs-curator` agent (documentation hygiene,
wiki-link correctness, rule consistency, frontmatter and tag
compliance) and the `vaultspec-writer` agent persona (prose
clarity, canonical-vocabulary compliance, mandate-shape
phrasing) before it lands. Extensions that have not passed both
reviewers are not authorised to merge. This gating mirrors the
multi-reviewer cadence used during the `#plan-hardening` ADR
rounds and keeps the firmware coherent as the CLI rolls out.

## Rationale

Noun-verb subcommand grouping is chosen over verb-noun because
the operation count per container is high (six on Step alone).
A flat verb-noun namespace produces a sprawling `vault plan add-step / move-step / remove-step / toggle-step / edit-step / insert-step` surface that conflicts with the existing
`vault add <type>` shape. Grouping by container (`vault plan step add`, `vault plan step move`) keeps the surface
discoverable and matches the plan document's own hierarchy.

`normalize` and `compact` were considered and dropped. The
convention ADR's immutability rule rules out renumbering by
default. `normalize` (cosmetic-only) is folded into `check --fix`; `compact` (destructive renumbering) is not exposed in
wave 1 and would require an explicit `--allow-id-change` flag
when added.

`fix` as a separate subcommand was considered and dropped in
favour of `--fix` on `check`. This matches the existing `vault check --fix` convention and keeps the validation and fix
surfaces co-located.

`add` and `append` are unified. There is no behavioural
difference between "add a Step" and "append a Step" once the
contract is fixed: both go to the next-available canonical
identifier and append at the end of the target container.
`insert` carries the only meaningful position semantic via
`--before` / `--after`.

The classification table separates safety semantics by
side-effect class. This is the contract a future Python
implementation upholds; it also gives reviewers a single table
to audit when assessing whether a new subcommand belongs in the
surface.

## Consequences

Once landed, the CLI replaces ad-hoc plan-document editing for
contributors who prefer a programmatic surface. The writer
agent persona may invoke the CLI internally for structural
operations once the implementation lands; the social
enforcement of the convention ADR remains the wave-1 fallback.

The contract this ADR defines is what a future Python
plan-management module implements. Implementation drift from
this contract is treated as a defect against this ADR; any
future revision of the surface edits this ADR first and the
implementation re-syncs.

External tools that link to canonical identifiers in commit
messages, PR descriptions, or issue trackers continue to
resolve correctly across CLI operations. The CLI's
identifier-stability guarantee is the user-facing contract;
the plan document is implementation-detail beneath it.
