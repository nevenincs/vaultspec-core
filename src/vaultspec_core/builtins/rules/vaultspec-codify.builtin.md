---
name: vaultspec-codify
---

# Codify durable lessons as project rules

The `vaultspec-core` workflow has a research → decide → plan → execute → review arc. The
audit-derived sixth phase is `codify`: when a review surfaces a durable lesson - a
constraint that should bind future agents across sessions - write that lesson down as a
rule the next agent inherits on load.

This rule defines when to codify, what to codify, and how to author the artifact.

## When to codify

Not every observation in a review is a rule. The bar is durability. A
codification-worthy lesson satisfies all three:

- **Cross-session.** A new agent who has never seen this feature should still benefit
  from the rule.
- **Constraint-shaped.** The lesson can be rendered as a positive obligation ("always
  X") or a negative one ("never Y"), not as a description.
- **Project-bound.** The lesson is specific to this project's conventions, stack, or
  constraints. Generic engineering advice belongs in external documentation.

Never codify on the first encounter with a constraint. A lesson qualifies only after it
has held across at least one full execution cycle; the first encounter is an audit
finding, not yet a rule.

Examples that codify well: "harbor-notes runtime data lives under `~/.harbor-notes/`;
never under `$TMPDIR`", "every destructive verb must accept `--dry-run`", "step records
use the canonical filename schema". Examples that do not: "we considered library X,
picked library Y" (that is an ADR), "the deploy failed last week" (that is an audit
finding without a durable lesson).

## What to codify

The rule body names the constraint precisely. Three sections, in order:

- **Rule.** One sentence stating the obligation. Imperative voice. No backstory.
- **Why.** Two or three sentences naming the constraint's origin - the audit document or
  ADR that surfaced the lesson, the failure mode it prevents.
- **How.** Concrete worked examples of the rule applied and the rule violated.

Keep the rule short. A rule longer than its own justifying audit finding has lost the
plot. If the rule needs more than a page, it is actually a reference document; produce
`.vault/reference/yyyy-mm-dd-{feature}-reference.md` instead.

## How to author

A codification produces a file under `.vaultspec/rules/rules/` that captures the rule.
Today's canonical authoring path is the existing CLI:

- `vaultspec-core spec rules add <rule-name>` scaffolds the rule file. The `<rule-name>`
  is the kebab-case slug naming the rule's subject (e.g., `harbor-notes-runtime-data`,
  `destructive-verbs-need-dry-run`).
- The author then opens the scaffolded file and fills the three sections above.

Today the CLI places authored project rules in the same directory as the framework's
builtin rules (`.vaultspec/rules/rules/`). Project-authored rules are distinguished from
builtins by name convention (builtins use the `*.builtin.md` suffix; authored rules do
not). A planned `--scope project` flag on `vaultspec-core spec rules add` will separate
authored rules into `.vaultspec/rules/rules/project/`; see the sibling
`cli-spec-crud-parity` ADR.

A higher-level codification verb is planned: a promote command that will take an audit
stem and a target rule name, read a designated finding from the audit document, and seed
the rule file with the audit's evidence pre-populated. See the sibling
`cli-memory-lifecycle` ADR for the proposed verb and its command group. Until it lands,
copy the relevant audit text into the rule body by hand and reference the audit stem in
backticks.

## How to find an existing rule

Before authoring a new rule, check whether one already covers the intent.
`vaultspec-core spec rules list` enumerates all project-shared rules.
`vaultspec-core spec rules show <name>` prints any single rule. If an existing rule
partially covers the intent, edit it via the standard CRUD path
(`vaultspec-core spec rules edit <name>`) rather than producing a near-duplicate;
partial rules are worse than complete ones because they fragment the discipline.

## Where the rule lives, and why

Project-authored rules live under `.vaultspec/rules/rules/` alongside the framework's
builtin rules (the framework distinguishes authored from builtin by name convention:
builtins use the `*.builtin.md` suffix; authored rules do not). The framework's install
policy is for that directory to be tracked by git so the rule reaches every teammate on
clone. (Pre-existing installs may have an older policy that gitignored the directory;
see the framework manual's section on sharing policy and the sibling ADR
`cli-spec-gitignore` for the migration story.)

A rule that exists only on one developer's machine is not a codification; it is a
personal note. The whole point of writing the rule down is that the next agent inherits
it on the next session, on the next teammate's clone, on the next CI run.

## When a rule itself becomes wrong

Rules age. A rule that captured a constraint last quarter may no longer hold this
quarter. Two paths:

- **Edit in place** when the constraint has shifted at the margins. The rule's name
  stays; the body changes.
- **Supersede** when the constraint has changed at the center. Author a new rule with a
  new name and add a `## Status` section to both rule bodies: the prior rule's Status
  names the successor's slug, and the new rule's Status names the rule it supersedes.
  Once teammates are aware, remove the prior rule via
  `vaultspec-core spec rules remove <name>`. (A structured supersession mechanism
  mirroring the ADR-supersession story is planned in the sibling ADR
  `cli-memory-lifecycle`; until it ships, the Status sections are the declaration.)

A rule should never be silently deleted. The rule's removal is itself a project-level
event; record it.

## Audit-driven codification

The framework supports an audit-first codification flow. The sequence:

- A review at the end of a feature surfaces lessons in
  `.vault/audit/yyyy-mm-dd-{feature}-audit.md`.
- One audit can produce zero, one, or many rules - most produce zero (the lesson is
  feature-specific), some produce one, and a rare audit (the kind that surfaces a
  framework-wide pattern) produces several.
- Each rule's body names the audit stem in backticks as its origin. Once the planned
  `derived_from:` frontmatter field lands, the rule will carry the back-pointer in
  structured form too.

Audit-driven codification is the natural follow-on to the `review` phase. The pipeline
reads as research → decide → plan → execute → review → codify, with codify as the
discretionary sixth step. Most features end at review; the features whose lessons
outlast the feature itself end at codify.
