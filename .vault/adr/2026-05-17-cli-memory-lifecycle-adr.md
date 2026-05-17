---
tags:
  - '#adr'
  - '#cli-memory-lifecycle'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
  - "[[2026-05-17-cli-memory-lifecycle-research]]"
---

# `cli-memory-lifecycle` adr: `First-class memory-lifecycle verbs: codify, supersede, retire` | (**status:** `accepted`)

## Problem Statement

The `vaultspec-core` CLI's structural memory model — frontmatter,
wiki-links, feature indexes, per-feature isolation — holds up under
stress (round 3b S18 confirmed clean parallel features). What does
not hold up is the set of CLI verbs that mutate that memory across
its lifecycle. Three operations fail in three different shapes:

- **Codification.** The pipeline (research, decide, plan, execute,
  review) terminates without ever surfacing a verb for "we just
  learned something durable; promote it into a project rule so the
  next agent inherits it". Across six agent-days in the audit, no
  persona reached `spec rules add` organically. The round-3a Bridge
  Gap meta-finding documents the omission.
- **Supersession.** Finding B3. No first-class way to express "this
  decision supersedes that one". The relationship has to be
  reconstructed from hand-edited H1 status tokens, flat `related:`
  links, and the emergent property that the auto-generated feature
  index renders H1 lines verbatim. The relationship type is prose,
  not data.
- **Retirement.** Finding B9 (critical). `vault feature archive`
  exists but is structurally destructive: no `--dry-run`, no
  reversal verb, silently breaks cross-feature `related:` links,
  creates a directory `vault check structure` declares illegal, and
  the only auto-fix path amputates the very provenance the verb was
  invoked to preserve.

The framework is a paper-trail tool whose paper trail breaks at the
exact operations a paper trail exists to support.

## Considerations

- The structural model itself works. Whatever new verbs land must
  layer on top of frontmatter + wiki-links + indexes rather than
  replace them.
- The feature-index renderer is the system's accidental
  source-of-truth for the override trail today. Any change to
  supersession semantics must keep the feature index honest or
  rewrite the renderer alongside.
- A real team will rarely run an `unarchive` verb but will frequently
  preview an archive before committing to it. The asymmetry in
  expected use should drive what gets surfaced first.
- The pipeline's natural-language vocabulary (research, decide, plan,
  execute, review) has cultural weight in the codebase, in agent
  personas, and in builtin rules. Adding a sixth verb is not free.
- Cross-feature `related:` links are the framework's existing
  affordance for "this feature's work depends on that feature's
  decisions". They must remain navigable through archive, otherwise
  retirement defeats supersession.

## Constraints

- The frontmatter schema is documented and consumed by multiple
  internal modules (graph, checks, indexes). Adding new fields
  requires a migration entry per the existing migrations registry.
- `vault check structure` and `vault repair` must agree with whatever
  layout `vault feature archive` writes. Today they do not (B9).
- The audit doc cannot be amended in place to reference these new
  verbs by `related:` — wiki-link integrity rules forbid forward
  references to documents that do not yet exist on disk.
- `cli-simplification-ux` is the umbrella feature tag for the audit;
  this ADR lives under its own feature tag `cli-memory-lifecycle` so
  it does not collide on filename with sibling ADRs (B4 finding).

## Implementation

Three new first-class CLI verbs, one per lifecycle endpoint, plus a
small set of frontmatter additions.

**Codify.** Introduce a single command that promotes a finding from
an audit document into a durable project rule.

- `vaultspec-core vault rule promote --from <audit-stem> --as
  <rule-name>` writes `.vaultspec/rules/project/<rule-name>.md` with
  a `derived_from: ['audit:<audit-stem>']` frontmatter field, plus a
  short body templated from the audit finding.
- The originating audit document gains a `promoted_to:
  ['rule:<rule-name>']` back-pointer.
- The pipeline gains a sixth lifecycle phase: "codify". Builtin
  rules and agent personas are updated to teach that codify follows
  review and is part of the completion criteria for any feature
  whose review surfaces a durable learning.
- The verb is opt-in. Not every audit produces a rule; not every
  feature requires one.

**Supersede.** Introduce a single command that records that one
decision overrides another.

- `vaultspec-core vault adr supersede <old-adr-stem> --by
  <new-adr-stem>` writes `superseded_by: '<new-adr-stem>'` on the
  old ADR's frontmatter and `supersedes: ['<old-adr-stem>']` on the
  new one. Optionally rewrites the old ADR's H1 status token from
  `accepted` to `superseded` to keep the feature-index renderer
  honest.
- `supersedes` and `superseded_by` are first-class frontmatter
  fields with their own pair of vault checks: a dangling-supersedes
  check (the target must exist) and a status-coherence check (a
  document with `superseded_by` set must have `status: superseded`).
- Plans gain the same pair of fields for plan-level retirement.

**Retire.** Fix `vault feature archive` end to end.

- Add `vault feature archive --dry-run` that lists the documents
  that would be moved and the cross-feature `related:` links that
  would need rewriting. Show both before any mutation.
- Add `vault feature unarchive <feature-tag>` as the reversal verb.
- On archive, rewrite incoming `related:` links across the rest of
  the vault so they continue to resolve. Strategy: the archived
  document keeps its original stem; the dangling-link checker
  learns to resolve into `.vault/_archive/` before declaring the
  link dead.
- `vault check structure` legitimises `.vault/_archive/` as a
  first-class directory.
- `vault feature archive <typo>` exits non-zero when no documents
  match the supplied tag, instead of returning exit 0 with a
  silent no-op.

**Frontmatter schema additions.**

- `supersedes: [<adr-stem>, ...]`
- `superseded_by: <adr-stem>`
- `derived_from: ['audit:<stem>', 'finding:<stem>:<id>', ...]`
- `promoted_to: ['rule:<rule-name>', ...]`
- `archived: <ISO-date>` (on archived documents only; set by
  `vault feature archive`; cleared by `vault feature unarchive`)

A versioned migration records these as additive fields. Existing
documents do not need rewriting.

**Language and template updates.**

- ADR template: replace the freeform "status" line with a structured
  Status section that uses the standard tokens
  (`accepted`/`superseded`/`deprecated`/`rejected`) and references
  the supersession frontmatter explicitly.
- Pipeline rule files (the builtin rules that teach agents the
  research-decide-plan-execute-review flow): add the codify phase
  as the sixth step, with worked-example language for when to
  invoke `vault rule promote`.
- Agent personas: update completion criteria to include codify
  when a review surfaces a durable learning, and to use
  `vault adr supersede` instead of prose for override events.
- Install summary: print a one-line policy statement after `install`
  about how memory is shared with teammates. This is the language
  counterpart to the gitignore reversal recorded in a sibling ADR.

## Rationale

The audit's round-3 meta-finding observed that the framework's
failures cluster at three points on a single shared axis: the
memory lifecycle. Treating B3 (supersession), B9 (archive), and the
Bridge Gap (codification) as three independent bugs would mean three
parallel fix paths with no shared design, three different
relationship-type vocabularies in frontmatter, and a fourth round
of audit findings in a year about the inconsistency between them.

A single architectural pass over the lifecycle verbs lets one
frontmatter-schema decision serve all three operations, lets the
vault checks share their relationship-graph machinery, and gives
agent personas a single coherent story for how a feature ends — not
when its plan is done, but when its lessons are durable.

The verb names map cleanly onto natural English ("codify",
"supersede", "retire") so a team lead's chat brief and a CLI
invocation use the same vocabulary. This is the inverse of the
round-2 finding that "execute" mapped to `vault add exec` but the
artifact did not match the framework's own rules.

## Consequences

Gains. The paper-trail thesis becomes mechanically true rather than
emergent. Cross-feature provenance survives archive. Agents that
follow the pipeline's natural-language verbs reach the correct CLI
commands without translation. The framework gains a coherent answer
to "what does it mean for a feature to be done" beyond "the plan is
green".

Difficulties. Three first-class verbs is a larger CLI footprint;
the existing `vault add adr` and `vault feature archive` surfaces
have to remain accepting their current arguments while the new
forms land. Migrations on the frontmatter schema have to land before
any audit-doc tooling depends on the new fields.

Pitfalls. The codify phase is opt-in; teams that never invoke it
will not produce durable rules, and the framing problem
re-emerges. The pipeline-rule update is the language lever that
prevents that — without it, the verb exists and gets ignored.
Likewise the install summary's policy line is the language lever
that prevents a `.vaultspec/`-gitignored team from forgetting that
memory is supposed to be shared.

Pathways. Once the lifecycle verbs land, the audit doc itself
becomes the canonical input for `vault rule promote`. The
findings stop being prose recommendations and become data the
framework can act on. That is what closes the loop the audit was
written to identify.
