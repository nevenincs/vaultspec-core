---
tags:
  - '#audit'
  - '#cli-simplification-ux'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-research]]"
---

# `cli-simplification-ux` audit: `CLI UX rolling audit — Joan and Xavi sessions`

## Scope

Rolling UX audit of the `vaultspec-core` command-line interface, focused on
agent-facing ergonomics. Methodology:

- Two persona subagents, **Joan** and **Xavi**, operate in disposable
  sandboxes outside this repository.
- Both are forbidden from reading any file under the `vaultspec-core` source
  tree, the editable install inside their venvs, or the public docs and
  repository surface. The CLI itself is their only source of truth.
- Joan is briefed in plain technical terms with named CLI verbs in scope.
  Xavi is briefed exclusively in natural-language pipeline phrasing
  ("start researching", "write down the decision", "make a plan", "execute",
  "review") and must map intent to commands himself.
- Each agent maintains a per-command friction log in their sandbox. The
  findings below are distilled from those logs across rounds.

Tracking issue: GitHub `#113`. Scope note in the sibling research document.

## Findings

### Round 1 — onboarding and first-feature implementation

#### B1. Blocker — `vault add exec` cannot produce conformant Step Records

The framework's own rules require per-Step execution records at
`.vault/exec/{date-feature}/{date-feature}-S##.md` with a populated
`step_id` frontmatter field. The CLI's `vault add exec` accepts neither a
`--step` nor a `--phase` nor a `--wave` flag, ignores `--title` for the
output path, and emits a single flat document with the literal string
`step_id: '{S##}'`. Two `vault add exec` invocations for two different
Steps collide on the same generated filename. Xavi (briefed only in
natural language) correctly mapped "execute the plan" to `vault add exec`,
hit this wall, and chose to skip exec records entirely rather than
hand-write filenames in violation of the framework's own no-hand-edit
rule. Net effect: an agent following framework rules strictly produces an
incomplete paper trail by design.

#### B2. Blocker-grade UX bug — `vault add plan` ships an unparseable plan by default

The scaffolded plan document contains `tier: L{#}` as the literal value in
frontmatter. The plan validator then rejects the same document with an
uncaught `PlanFrontmatterError: tier must be one of L1, L2, L3, L4; got
'L{#}'` and prints a full Python traceback whose paths reference internal
source files. Joan crashed on this within minutes of first install. Xavi
spotted the placeholder and hand-patched it before invoking any plan
command. The scaffolder owns enough context to require or accept
`--tier`; today it does not.

#### S1. Sharp — `vault plan step add` silently rewrites plan body

The plan template emits HTML-comment guidance instructing the author to
fill in Description, Parallelization, and Verification prose sections.
The first invocation of `vault plan step add` after that prose is in
place rewrites the entire body and discards those sections, with no
warning, no diff, no `--dry-run`-required gate, and no mention in the
post-command summary. Both Joan and Xavi reproduced this independently.
The template and the editor command issue mutually destructive
instructions.

#### S2. Sharp — `install` versus `sync` versus `install --upgrade` overlap unpredictably

Three sync-shaped operations coexist with overlapping flag surfaces and
subtly different overwrite semantics:

- `install` "scaffolds the workspace structure and syncs all managed
  resources".
- `sync` is the "authoritative complete sync from `.vaultspec/` to
  enrolled provider outputs" — described as both authoritative and
  non-destructive in the same paragraph, which contradicts itself in
  agent-facing wording.
- `install --upgrade` does a third sync-shaped operation: "re-sync
  builtin rules and firmware".
- `install --force` overwrites; `sync --force` prunes and overwrites.
  Same flag, different overwrite semantics across two surfaces.

Net: from `--help` alone a fresh agent cannot tell which of the three
to run, and gets different blast radii for the same flag depending on
which it picked.

#### S3. Sharp — `vault repair` is the most useful command on the surface and is undiscoverable

`vault repair` runs preflight, the full check battery, fixes, refreshes
the feature index, rebuilds the graph, performs a postcheck, and prints
a clean summary including a changed-file list. Joan called it "the
single best command in the entire CLI surface". Xavi never discovered
it — he ran `vault sanitize annotations` then `vault feature index` then
`vault check all` to do the same work in three commands instead of one,
because the CLI never pointed him at `vault repair`. No `--help` text at
any level recommends it as the pre-commit hygiene command.

#### S4. Sharp — destructive blast radius gating is asymmetric

`install` writes about 70 files into the target on first run — including
silently appending a managed block to `.gitignore`, writing
`.mcp.json`, and creating `CLAUDE.md` — with no `--force`. `uninstall`
requires `--force` explicitly because "uninstall is destructive". The
gating logic is inverted: adding 70 files into a workspace is at least
as hard to undo as removing them, but only removal is gated. Joan
flagged this on first contact.

#### S5. Sharp — `.vault/` and `.vaultspec/` naming + opposite git policies

The two top-level managed directories differ by a single suffix, and
the install operation puts one in git (`.vault/`) and the other not
in git (`.vaultspec/`, `.claude/`, `CLAUDE.md`, `.mcp.json`). The CLI
never explains the policy. As an outcome, the same verb pattern
(`vault add` vs. `spec rules add`) produces opposite team-visibility
results — one document is shared with collaborators, the other is
local-only — and the user is not told.

#### S6. Sharp — fresh install warns about a missing version baseline

On a clean target with no prior install, the very first `--dry-run`
output prefix is:

```
! No version baseline for builtins - cannot verify integrity.
  Run 'vaultspec-core install --upgrade' to establish baseline.
```

The recommended remedy is the upgrade flag, which is documented as
re-syncing an existing install — exactly what a new user does not
have. Both agents flagged the warning as alarming and the suggested
fix as contradictory in this state.

### Smaller paper cuts

- `vault feature` group contains no `add`, `create`, `new`, `remove`, or
  `delete`. Features come into existence as a side effect of
  `vault add <doctype> --feature <kebab-tag>`, which is verb-first
  generic creation. The `vault feature` group is in practice a
  query/maintenance group misnamed as a CRUD group.
- `vault sanitize annotations` and `vault check annotations --fix` do the
  same job under different verbs. Two-surface CRUD without deprecation
  signaling.
- `vault check` is a group whose docstring describes a behavior the
  group itself does not have. Typing `vault check` (no subcommand)
  prints help; typing `vault repair` runs. The verbs read as peers but
  the CLI shape is not peer-shaped.
- `vault graph --help` advertises a `COMMAND [ARGS]...` usage line
  despite being a leaf with no subcommands.
- `--dev` is repeated on `install`, `uninstall`, `sync`, and
  `migrations run`, with help text that references the source-repo
  guard. The flag is meaningful only to maintainers of the framework
  itself; it leaks framework internals to every consumer's `--help`.
- "Unhydrated placeholder" warnings fire on `vault add adr`,
  `vault add plan`, and `vault add exec` against tokens inside HTML
  guidance comments meant for the author. Both agents learned to
  ignore them within the first round.
- `vault add` template warnings co-occur with a `Created:` success line
  on the same invocation. Mixed signals; both agents independently
  asked "did it work or didn't it".

### Natural-language pipeline mapping

Xavi was briefed in plain English by an imagined team lead and had to
discover the CLI verbs himself. Mapping results:

- "start by researching" maps cleanly to `vault add research`.
- "write down the decision" maps cleanly to `vault add adr`.
- "make a plan" maps cleanly to `vault add plan` (modulo the `tier`
  placeholder, B2).
- "execute the plan" maps to `vault add exec`, which is the wall in B1.
- "review your work" maps to `vault add audit`. Note the semantic gap:
  "audit" is not how a developer says "review".

Four of five pipeline verbs map cleanly. The fifth, "execute", is the
structural break.

### CLI command-tree consistency observations

- `vault` mixes verb-first generic creation (`vault add`) with
  noun-first subgroups (`vault feature`, `vault plan`). For a
  consistent mental model, creation should live in one place — either a
  generic `vault add <type>` or per-noun `vault <noun> add` — not both.
- CRUD parity is uneven across noun groups. `vault plan step` has
  `add`, `insert`, `edit`, `move`, `check`, `uncheck`, `remove`,
  `toggle`. `vault plan phase` has `add`, `insert`, `edit`, `move`,
  `renumber`, `remove`. `vault plan wave` has the same minus
  `renumber`. `vault feature` has `list`, `index`, `archive` — no
  create, no remove. The cognitive load of remembering which noun
  group supports which verbs is real.
- The same noun appears under multiple verb roots. `annotations` is a
  noun used both under `vault check annotations` (read-with-fix-flag)
  and `vault sanitize annotations` (write directly).

## Recommendations

### Highest leverage

- Make `vault add exec` aware of Step identifiers and produce the
  per-Step folder layout that the framework rules require, OR change the
  framework rules to match the current scaffolder's output. The two
  cannot continue to disagree.
- Make `vault add plan` require or accept `--tier`, and never ship the
  literal `L{#}` as a frontmatter value.
- Make `vault plan step add` either preserve author-written prose
  sections or surface the rewrite explicitly with an opt-out flag.
- Recommend `vault repair` from at least one `--help` surface — the
  top-level install summary is the natural place — and from every
  command that hands the user a fix-it follow-up.

### Vocabulary and shape

- Pick one verb pattern per noun and enforce it. Either everything is
  `vault add <type>` (verb-first generic) or everything is
  `vault <noun> add` (per-noun group). Mixing produces the asymmetry
  both auditors flagged.
- Normalize outcome-state vocabulary across all surfaces: pick one
  word per state (`installed`, `unchanged`, `synced`, `drifted`,
  `repaired`, `skipped`) and render it identically.
- Hide `--dev` from rendered help. Document developer-mode in
  contributor documentation.
- Stop conflating warnings emitted by the scaffolder itself with
  warnings emitted against author content. The "unhydrated
  placeholder" warnings fire against the scaffolder's own templates.

### Discoverability

- Top-level help should include a one-line quickstart that points at
  the recommended first command. After `install`, suggest the natural
  next step verbally rather than expecting the agent to guess.
- After `vault add <type>`, suggest the natural next document in the
  chain. The CLI already volunteers next-command hints when checks
  fail; extend that behavior to scaffolding.
- Document and surface the `.vault/` versus `.vaultspec/` git policy
  inside the install summary itself — one line, plainly stated.

### Asymmetric blast radius

- Gate `install` on first run with either a confirmation or a
  `--dry-run`-required-by-default discipline equivalent to what
  `uninstall` requires today. The current asymmetry punishes the more
  common operation (install in the wrong directory) and protects the
  less common one (intentional removal).

## Findings

### Round 2 — revision, supersession, override

#### B3. Blocker — no `supersede` verb anywhere in the CLI

For a tool whose elevator pitch is "spec-driven development with a paper
trail", the lack of any first-class way to express "this decision
supersedes that one" is structural, not cosmetic. Xavi was briefed by
his imagined team lead to "mark yesterday's design decision as
superseded by a new one" — natural English for the exact thing the
framework is built around. He walked every `--help` page and found
nothing. The audit trail had to be reconstructed from three unrelated
mechanisms:

- Hand-editing the prior ADR's H1 status token (`accepted` → `superseded`)
  in body prose, which is the only place the framework's link rules
  allow manual edits.
- `--related` back-pointers on the new ADR, plan, and audit.
- Body prose in the new documents that names the supersession
  explicitly.

The `--related` field is flat. It cannot distinguish "supersedes" from
"informs" from "authorised-by" from "refines". The only reason a
reader can follow the chain at all is that the auto-generated feature
index renders each document's H1 verbatim, so the supersession token
flows through by accident. The intentional path through the CLI does
not surface the relationship.

#### B4. Blocker — same-feature, same-day documents collide on filename

A second ADR (or plan, or research note) for the same feature on the
same day cannot be created via `vault add <type> --feature <tag>`. The
generated filename is `YYYY-MM-DD-{feature}-{type}.md` and the
existing file blocks the write. The only escape Xavi found was to
override `--date` to a future date, which puts a lie into the
artifact's frontmatter. Within-day revisions are a normal occurrence
when supersession is the workflow's first-class operation (B3); the
filename scheme makes them impossible to record honestly.

#### B5. Sharp/Blocker — `tier promote` writes literal `TODO` placeholders into the doc

A direct cousin of B2 from Round 1. Running `vault plan tier promote
... --target L2` with the minimum flags writes a synthesised phase
containing `TODO: Phase title` as the phase title. The very next
`vault check all` then flags the document as failing. The scaffolder
emits an invalid value that the validator on the same surface
rejects. As with `vault add plan` and `tier: L{#}`, the right call is
to require or accept the missing values up front, not paste a TODO
and hope.

#### B6. Sharp — `vault plan step add` body destruction reproduced a third time

Joan reproduced this in Round 1 against tag-search. Xavi reproduced it
in Round 1 against snippets. Xavi reproduced it again in Round 2
against the new SQLite plan. Three independent reproductions across
two agents and two sandboxes. The plan-step add path silently rewrites
the document body and discards author-written prose sections.

#### S7. Sharp — retired phase IDs cannot be reused

`vault plan phase renumber P01 --to P02` retires the identifier `P01`
permanently. Joan tried to chain two renumbers (`P01 → P02`, then
`P01a → P01`) to clean up the alpha-suffix that `phase insert
--before` had produced; the second renumber failed because `P01` is
retired. The retirement semantics are not surfaced in `--help` and
the recovery path the user reaches for first is closed. Related to
the existing open issue `#109`.

#### S8. Sharp — outcome vocabulary across the plan-revision surface is incoherent

Joan collected seven distinct result words from one noun's verbs:
`Closed`, `Retired`, `Renumbered`, `Promoted`, `Inserted`, `Added`,
`Moved`. The grammar is inconsistent — some are past-perfect verbs,
some are simple past, some refer to the operation performed, some
refer to the state of the affected entity. A normalised set would
have made all seven readable at a glance and made `--json` output
straightforward.

### Smaller paper cuts (Round 2)

- `vault add exec` template emits both `step_id: '{S##}'` and a
  literal `<display-path>` token, and substitutes `--title` into the
  example display-paths twice. Joan and Xavi both flagged it on first
  invocation. The CLI has plan-parsing surface to do better but does
  not connect it to exec scaffolding.
- `vault plan step check` is idempotent and silent. Running it twice
  on an already-closed step gives no indication of whether anything
  changed. A `(no change)` annotation would make the silence less
  ambiguous.
- `vault feature index` regenerates without a "what changed" line.
  When the regeneration is part of a fix-up sequence, the user has no
  signal whether the regeneration mattered.
- `<!-- RETIRED: P01, S01 -->` survives `vault check annotations --fix`
  (positive — the stripper has a structural-metadata discriminator)
  but the discriminator is undocumented. New hires cannot predict
  what the fix step will and will not preserve.
- `vault plan step add --phase` enforces phase membership at command
  time, but the enforcement is not surfaced in the help text. Joan
  flagged this after trial-and-error.
- Positive: `vault plan step move --after` is the cleanest revision
  verb either agent met across both rounds. Use it as the pattern
  template for normalising the rest of the revision surface.
- Positive: monotonically allocated canonical step IDs make plan
  history easy to reason about, even when intermediate IDs retire.

### Override semantics — emergent, not designed

Xavi's reconstruction of the supersession trail worked only because
the feature index regenerates from H1 lines. The override story is
therefore an emergent property of one specific renderer, not a
designed semantic. If a future change moves the index off H1 parsing,
the trail breaks silently. The right fix is to make supersession a
first-class concept (frontmatter field `supersedes:`, CLI verb
`vault adr supersede <old> --by <new>` or similar) so the relationship
is data, not prose.

## Recommendations

### Highest leverage (updated)

- Make supersession a first-class concept (B3). Add a frontmatter
  relationship type beyond flat `related:` and a CLI verb that writes
  it. The whole framework is built on relationship semantics; this
  one cannot be inferred from prose.
- Allow multiple same-feature documents per day (B4). Either let
  `vault add <type>` accept a `--slug` suffix, or auto-append a
  monotonic suffix when a collision would occur. Forcing date fakery
  defeats the audit trail.
- Stop emitting TODO/placeholder values from scaffolders (B5, B2).
  Either require the missing inputs up front or refuse to write the
  document until they are supplied.
- Make `vault plan step add` preserve author prose, or surface the
  rewrite explicitly (B6). Three reproductions across two agents and
  two sandboxes is decisive evidence.

### Vocabulary and shape (updated)

- Normalise outcome verbs across the plan-revision surface (S8).
  `step move --after` is the template; align the rest of the surface
  to that shape.
- Document or remove retirement semantics for phase / step IDs (S7).
  The current behavior is correct in spirit (you cannot accidentally
  reuse a retired identifier) but invisible in `--help`.

### Discoverability (updated)

- Surface `vault repair`, `vault feature index`, and `vault check
  annotations --fix` as the recommended post-revision pipeline. Right
  now an agent has to discover the regen-and-recheck loop by trial.
