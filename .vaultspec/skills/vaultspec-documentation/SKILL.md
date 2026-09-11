---
name: vaultspec-documentation
description: Create or substantially rewrite one user-facing README, guide, or feature document. Focused maintenance edits use a direct evidence-and-review pass.
---

# Documentation Pipeline

Produce one user-facing document grounded in its sources. For creation or substantial
rewriting, use the pipeline below. For focused maintenance, inspect the affected claims,
edit within the established structure, and verify technical accuracy and readability; do
not restart the full pipeline.

The system's approval contract applies throughout. Reuse supplied scope and audience;
ask only for material missing choices. Explicit prior authorization can cover a
wireframe and final delivery within that scope. These document stages are not plan
Phases and do not create additional framework review gates.

## The Pipeline

```
Phase 1: Wireframe -> Phase 2: Refinement -> Phase 3: User Approval -> Phase 4: Context Gathering -> Phase 5: Drafting -> Phase 6: Technical Review -> Phase 7: Editorial Review -> Phase 8: User Approval
```

For the full pipeline, complete each stage's purpose before the next. If delegation is
unavailable, perform the passes sequentially and state that review was not independent.
Section-level passes feed a cohesive whole-document review.

______________________________________________________________________

## Phase 1: Wireframe

The wireframe is a human-readable outline that defines the document's skeleton. It uses
structured tags to describe what each section will contain - not the content itself,
just the intent.

### Content tags

The wireframe uses two types of human-readable tags:

- `<Title: ...>` - A major heading that frames the sections beneath it
- `<Section: ...>` - A content block described by a plain-language summary of what the
  reader will find there

These are not syntax or markup - they are plain text descriptions meant for humans to
read and reason about. The text after the colon should describe the section's purpose
clearly enough that someone unfamiliar with the project can understand what they'd learn
by reading it.

Each tag is a **contract** - it promises the reader will find that information in that
location. The wireframe is the document's table of promises.

### How to build the wireframe

- Establish what to document and its audience from the request; ask if materially
  unclear.
- **Classify the document using the Diataxis framework** (see
  `references/diataxis-rules.md`): Tutorial, How-to Guide, Reference, or Explanation.
  For documents that span types (e.g. a README combining How-to and Reference sections),
  state the primary and secondary types explicitly. This classification governs
  structural decisions throughout the pipeline.
- Draft the wireframe with `<Title>` and `<Section>` tags
- Confirm any unresolved scope, audience, or classification choice before refinement.
  Reuse the user's established direction without an additional approval turn.

Keep tags descriptive but concise. A tag like
`<Section: How to configure the retry policy for failed webhook deliveries>` is better
than `<Section: Configuration>` - it tells the refinement reviewer exactly what to
expect.

______________________________________________________________________

## Phase 2: Wireframe Refinement

This is the most critical quality gate. A fresh subagent - one that has **never seen the
codebase or any prior context** - reviews the wireframe as a naive user would.

The reason this works: if someone who knows nothing about the project can look at the
wireframe and understand what they'd learn from each section, the structure is sound. If
they can't, no amount of good writing will save the document.

### Refinement process

Spawn a subagent with **no project context**. The subagent must:

- **Read** `agents/wireframe-agent.md` - the full agent persona and instructions.
- **Read** `references/diataxis-rules.md` in full - the documentation framework that
  grounds all structural evaluation.
- **Receive only the wireframe** as input. No project summary, no background, no hints.

The agent instructions contain the persona, the 8 evaluation questions, the response
format, and the Diataxis compliance review. Do not override or paraphrase them - use
them as written.

The subagent returns a single unified review: findings only, no methodology explanation.

### Handling refinement feedback

Read the subagent's feedback and categorize each point:

- **Minor** (wording tweaks, reordering, small additions): Apply automatically.
- **Substantial** (missing sections, structural changes, scope questions): Present to
  the user when they exceed the authorized scope or require a missing choice.

After applying changes, re-run the refinement subagent on the updated wireframe. Repeat
until the refinement reviewer has no "I would NOT understand" responses on any of the 8
questions.

### Approval gate

Once the refinement reviewer gives the all-clear on all 8 questions, the wireframe is
ready for user approval. Do not present the wireframe to the user until the refinement
reviewer has fully signed off - the user should only see a wireframe that has passed
this quality gate.

______________________________________________________________________

## Phase 3: User Approval (Wireframe)

Present the refined wireframe. Establish its authorization under the system contract:
record the basis when prior scoped approval covers it, or ask before proceeding.

If the user requests changes, apply them and return to Phase 2: Refinement to
re-validate the updated wireframe before seeking approval again.

______________________________________________________________________

## Phase 4: Context Gathering

With an approved wireframe in hand, you now gather the information needed to write each
section.

### One tag at a time

Dispatch subagents to research content for **one wireframe tag per wave**. This
constraint exists because mixing research across sections leads to unfocused, sprawling
context dumps that confuse the drafting stage.

For each `<Section>` tag:

- Spawn a subagent tasked with finding everything relevant to that section
- The subagent should explore the codebase, read relevant files, check tests, configs,
  CLI help output - whatever is needed to populate that section accurately
- Collect the subagent's findings as structured context for that section

For each `<Title>` tag: titles typically don't need deep research - they frame the
sections below them.

### Context format

Each section's gathered context should include:

- Key facts, names, paths, commands relevant to the section
- Code snippets or config examples if applicable
- Any caveats, gotchas, or edge cases discovered
- Source locations (file paths, line numbers) for technical review later

______________________________________________________________________

## Phase 5: Documentation Drafting

Each section is drafted by an isolated subagent that receives ONLY:

- The current wireframe tag (just the one it's writing)
- The gathered context for that tag
- The editorial guidelines (see `references/prose-style-rules.md`)
- The document's title and audience (for tone calibration)

The subagent does NOT receive:

- The full wireframe
- Other sections' context
- Direct codebase access

This isolation is intentional. A drafter who can see the whole document tends to repeat
information across sections, add tangential details, and lose focus. A drafter who can
only see its own section stays on task.

### Assembly

After all sections are drafted, assemble them into a single markdown document following
the wireframe's order. Add transitions between major sections if needed, but keep them
minimal - the wireframe structure should carry the flow.

______________________________________________________________________

## Phase 6: Technical Review

The assembled document now goes through technical verification. This catches errors that
drafting subagents introduce - wrong function names, incorrect flags, outdated paths,
misleading descriptions of behavior.

### Review process

Spawn parallel subagents, each responsible for verifying a portion of the document. Each
reviewer should:

- Read the section(s) assigned to it
- Cross-reference every technical claim against the actual codebase:
  - Are module names, function names, and class names correct?
  - Do CLI commands and flags actually exist and work as described?
  - Are file paths and config keys accurate?
  - Do code examples actually run?
  - Are described behaviors true to the implementation?
- Report findings as a list of corrections needed, with evidence (file path, line
  number, actual behavior vs. documented behavior)

Apply all corrections to the document. If a correction changes the meaning of a section
significantly, flag it - the section may need partial redrafting.

Then verify the assembled document end to end: terminology, prerequisites, sequence, and
cross-section claims must describe one usable workflow. Section reviews alone do not
satisfy technical review.

______________________________________________________________________

## Phase 7: Editorial Review

A subagent with **zero context** reviews the document purely on the merit of the
writing. It receives the assembled, technically-reviewed document and nothing else - no
codebase access, no wireframe, no knowledge of what the project is or does.

The subagent must:

- **Read** `agents/editorial-reviewer.md` - the full agent instructions.
- **Read** `references/prose-style-rules.md` in full - the prose and style rule system
  that grounds all editorial evaluation. Every finding must cite a specific rule.
- **Receive only the document** as input. No codebase, no wireframe, no project context.

The agent returns findings only - issues with location, rule citation, and suggested
fix.

### Applying editorial feedback

Apply editorial feedback to the document. For changes that alter technical content
(e.g., the reviewer suggests simplifying a paragraph that contains important nuance),
use your judgment - readability matters, but not at the cost of accuracy.

______________________________________________________________________

## Phase 8: User Approval (Final)

Present the finished document to the user. Include a brief summary of:

- What the refinement reviewer flagged and how it was addressed
- What the technical reviewer corrected
- What the editorial reviewer improved

Deliver within the established authorization; ask for acceptance only where it remains
an explicit gate. If changes are requested, determine which pipeline phase they affect:

- Structural changes - return to Phase 1: Wireframe
- Content gaps - return to Phase 4: Context Gathering
- Writing quality - return to Phase 7: Editorial Review
- Factual errors - return to Phase 6: Technical Review
- Minor tweaks - apply directly

______________________________________________________________________

## Working with the user

Throughout the pipeline, keep the user informed at natural milestones:

- "Here's the wireframe - the refinement reviewer flagged X, I've addressed Y, here's
  what I need your input on for Z"
- "Context gathering complete for all sections. Moving to Phase 5: Drafting."
- "Technical review found 3 corrections. Editorial review suggested 5 improvements.
  Here's the final document."

Ask for missing choices that materially affect the authorized scope or audience. Resolve
ordinary content and structure details within that scope.
