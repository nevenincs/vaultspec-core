---
tags:
  - '#audit'
  - '#cli-simplification-ux'
date: '2026-05-17'
modified: '2026-06-13'
related:
  - '[[2026-05-17-cli-simplification-ux-research]]'
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

## Findings — round 1

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
uncaught `PlanFrontmatterError: tier must be one of L1, L2, L3, L4; got 'L{#}'` and prints a full Python traceback whose paths reference internal
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

## Recommendations — round 1

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

## Findings — round 2

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

A direct cousin of B2 from Round 1. Running `vault plan tier promote ... --target L2` with the minimum flags writes a synthesised phase
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
`P01a → P01`) to clean up the alpha-suffix that `phase insert --before` had produced; the second renumber failed because `P01` is
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

## Recommendations — round 2

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

- Surface `vault repair`, `vault feature index`, and `vault check annotations --fix` as the recommended post-revision pipeline. Right
  now an agent has to discover the regen-and-recheck loop by trial.

## Findings — round 3

### Round 3a — spec customisation surface (Joan)

Methodology note: Joan reached the spec subtree only because his round-3
brief told him to. Across rounds 1 and 2 he authored a full feature
through to `vault check all` clean without ever reaching for
`spec rules`, `spec skills`, `spec agents`, `spec system`, `spec hooks`,
or `spec mcps`. That observation is itself a finding (see "Bridge gap"
below) and a confirmation of the framing problem: the spec tree is not
on the path from the pipeline.

Once accessed under explicit prompting, the surface produced its own
substantial friction.

#### B7. Blocker — `spec rules edit` silently fails

The verb hardcodes `zed` as the editor binary and ignores `$EDITOR` /
`$VISUAL`. With no `zed` available, the command emits a Python
traceback to stderr and **exits 0**. A pre-commit hook or CI step that
relies on `spec * edit` exit codes will silently miss every failure.
An internal configuration object exposes `editor` (Joan saw the
attribute in the traceback) but no CLI verb surfaces it — there is no
`vaultspec-core config get editor` or equivalent. Workaround discovered
by Joan: write directly to `.vaultspec/rules/<group>/<file>.md`, since
`spec * show` and `spec * sync` are file readers. The entire `edit`
verb is therefore optional today.

#### B8. Blocker — `rename` produces frontmatter desync

After `spec skills rename A B`, `spec skills list` shows `B`. Yet
`spec skills show B` returns a body whose `name:` frontmatter field
still says `A`. The verb renames the file but does not update the
frontmatter the file declares about itself. Any downstream consumer
that trusts the filename and any that trusts the frontmatter will
disagree silently. The same path runs for `spec rules rename` and
`spec agents rename`.

#### S9. Sharp — CRUD parity is uneven across spec resource types

`spec rules`, `spec skills`, and `spec agents` look like a noun
trinity that should share the same verb shape, but the `add` flag
sets diverge: `rules add` accepts `--content`, `skills add` and
`agents add` accept `--description`. The output verbs also diverge
across the three. `spec mcps` has a `status` verb that `rules`,
`skills`, and `agents` do not. `spec system` is its own shape entirely.
Same-shaped nouns, different lifecycles.

#### S10. Sharp — five distinct sync vocabularies across five sync-shaped surfaces

Joan collected: `added` and `skipped` from `spec * sync`, `updated`
from top-level `sync`, `re-seeded` from `install --upgrade`, and
`new` from `install --dry-run`. Five vocabularies on five surfaces
that ostensibly do the same conceptual thing — reconcile state in one
place against state in another. Round 1's S2 hypothesis is now backed
by decisive evidence.

#### S11. Sharp — `revert` is restoration, not undo; semantics are undocumented

`spec rules revert <authored-rule>` fails with a terse error. The verb
applies only to customised builtins; for authored content the right
verb is `remove`. The distinction is invisible in `--help`. A user
who customises a rule, then changes their mind, expects "revert" to
mean "undo my change". Today it means "drop in the framework's copy
over yours". The word does not match the operation.

#### S12. Sharp — `spec rules sync` rejects a provider positional the top-level `sync` accepts

`vaultspec-core sync claude` accepts the provider. `vaultspec-core spec rules sync claude` rejects it. Same verb, two incompatible
argument schemas across two surfaces, no `--help` text reconciling them.

#### S13. Sharp — `spec * sync` duplicates a slice of top-level `sync`

For every group `g` in `{rules, skills, agents, system, mcps}`,
`vaultspec-core spec g sync` produces output that overlaps
significantly with `vaultspec-core sync`. The relationship between
the granular and the global surfaces is unstated. Should pre-commit
call the global form or the granular form? The CLI does not say.

#### S14. Sharp — `install --upgrade` has no preview; success line omits the preservation guarantee

`install --upgrade --dry-run` emits an empty preview. The actual
run preserved all three of Joan's authored resources cleanly and
re-seeded 42 builtin files. That is correct behaviour, but the
success line (`Re-seeded 42 builtin files. Upgrade complete.`)
never advertised that authored content was preserved. The highest
blast radius verb in the CLI ships without a preview and without
explicit preservation messaging.

#### S15. Sharp — `spec hooks` is CRUD-less

`spec hooks list` enumerates events; `spec hooks run` invokes them.
There is no `add`, no `edit`, no `enable`, no `disable`. The
example hook ships disabled and the only way to turn it on is to
edit the configuration directly. The verb pair invites the natural
question "how do I add a hook?" and the surface has no answer.

#### S16. Sharp — `spec mcps` has `status`; the other spec noun groups do not

A verb that exists on one same-shaped noun and not on the others is
the canonical sign of unfinished CRUD parity. Either `status` is
useful (in which case rules / skills / agents should have it) or it
is not (in which case mcps should not).

#### S17. Sharp — `vault check all` + `spec doctor` together still leave the operator guessing

Joan's terminal state was `vault check all` exit 0 and `spec doctor`
exit 0. He noted he still could not answer "am I safe to commit?"
without a third command. There is no single "is the workspace
green?" entry point.

### Smaller paper cuts (Round 3a)

- `spec * add` prints `... updated` on a fresh create. The state
  transition is creation; the past-tense verb is `created`, not
  `updated`.
- Positive: `spec doctor` is well-shaped, with one verbosity gap noted
  by Joan. The verb does not overlap with `vault repair` despite
  surface similarity.
- `spec system show` describes a sync target that does not exist on
  the workspace Joan tested against. The verb is wired before the
  feature is.
- `spec hooks list` truncates the event-name column; `spec hooks run`
  requires the untruncated name. Output column truncation breaks the
  input contract.
- `migrations status` claims `applied 0.1.17 index_subfolder`. Only
  one migration is registered. Joan flagged the report as suspicious
  but could not confirm without source.
- Outcome line shape varies even within the same group:
  `Rule source updated` versus `Reverted rule`. Subject-first vs.
  verb-first.

### Bridge gap (Round 3a — meta-finding)

Across rounds 1 and 2 (six agent days, two sandboxes, full feature
implementations end-to-end), neither agent reached the `spec` subtree
organically. Round 3a required an explicit instruction. The framing
problem first surfaced in Round 1 (S5 — `.vault/` versus `.vaultspec/`
naming and opposite gitignore policies) is therefore not a wording
nit; it is a structural barrier between the pipeline (`vault`) and
the durable rule layer (`spec`).

Concretely: the framework's natural-language pipeline verbs
("research", "decide", "plan", "execute", "review") all map to
`vault add <type>`. None maps to `spec rules add` or any of its
siblings. There is no verb in the pipeline for "we just learned
something durable; codify it as a project rule so future agents
inherit it". This is the gap that prevents the spec subtree from
being touched in the natural course of work.

The implementation of the spec surface exists. The path to reach it
from the pipeline does not.

### Round 3b — archive, parallel features, machine-readable outputs (Xavi)

Xavi's round-3 brief delivered three threads in parallel: archive the
snippets feature ("retire / archive"), develop two new features
(exports, stats) in alternation under context-switching pressure, and
survey `--json` outputs across nine commands for CI usability. The
brief also told him explicitly that the paper trail had to stay
readable.

#### B9. Critical blocker — `vault feature archive` is structurally broken

The single most severe finding of the audit. Five compounding failures
in one verb:

- **No `--dry-run`.** The only first-class memory-retirement verb in
  the CLI cannot be previewed. Three other vault verbs (`add`, `sync`,
  `check`, plus `install`) all expose `--dry-run`; archive does not.
- **No reversal verb.** No `vault feature unarchive`, no
  `vault feature restore`, no path through the CLI to undo. Archive
  is one-way from the user's perspective.
- **Cross-feature `--related` wiki-links break silently.** Xavi
  authored exports and stats with `--related 2026-05-18-snippets-adr`
  pointing at the round-2 supersession ADR — exactly the kind of
  provenance link the team lead said must stay readable. After
  archiving snippets, all four of those links became dangling. The
  CLI emitted no warning at archive time; `vault check dangling`
  discovered the breakage post-hoc.
- **The only available auto-fix amputates provenance.**
  `vault repair --dry-run --json` reports the dangling-link
  diagnostics as `fixable: true`, with a fix description that
  instructs the user to remove the offending stem from the
  `related:` frontmatter list. Running repair without
  `--dry-run` would silently delete the cross-feature provenance the
  team lead explicitly said must remain. The "fix" is the opposite of
  what the rule says.
- **`vault check structure` rejects the directory `vault feature archive` just created.** `Vault violation: Unsupported directory found in .vault/: '_archive'`. `vault repair --json` reports this
  structure error as `fixable: false`. Two first-class verbs disagree
  about legal vault layout, and the auditor flatly refuses what the
  archiver writes.

Plus a sixth, lower-grade: `vault feature archive <typo>` returns
exit 0 with `No documents found for feature '<typo>'.` Silent
no-op on a typo means CI cannot catch a mis-typed archive target.

After archive, Xavi's vault is in a permanent error state: `vault check all` exits 1 with five errors that no clean-fix path can
resolve. The lead's expectation ("trail should stay readable") and
the CLI's enforcement ("vault check fails after archive, fix means
deleting links") are in direct conflict. The verb the lead invoked
by name does exactly what the lead said not to do.

#### S18. Sharp (positive) — parallel features work cleanly

Two simultaneous features (`exports`, `stats`) with same-day
documents did not collide. The filename schema includes the feature
segment, so cross-feature same-day collisions do not exist. Xavi
alternated `vault plan step add` invocations between the two plans
(`exports S01`, `stats S01`, `exports S02`, `stats S02`, ...) for
eight calls; each step landed on the correct plan with the correct
identifier, no cross-talk, no implicit "active plan" state. The CLI
is fully stateless across plans. Plan-revision under
context-switching pressure works.

This is the framework's structural memory model behaving correctly
at the leaf level. The breakdown is at the operations on that model
(B3 supersession, B9 archive), not at the model itself.

#### S19. Sharp — `--json` consistency across the CLI is uneven

Xavi surveyed nine commands. Findings:

- **Gold standard**: `spec mcps status --json` has a top-level
  `status: "ok"` string. CI gate is a single string compare.
- **CI-ready**: `migrations status --json`, `vault list --json`,
  `vault stats --json`, `spec doctor --json`, `vault repair --json`,
  `vault graph --json`. All have either top-level summary fields or
  clean per-row arrays.
- **Weakest**: `vault check all --json` returns a bare per-check
  array with no top-level success/failure wrapper, no diagnostic
  counts at the array level, no schema version. To answer "did
  vault check pass" CI must iterate the array.

Four of the nine outputs carry a top-level status field; the most
important one for CI (the all-checks gate) does not. The same
inconsistency shape as the sync-vocabulary fragmentation
(S2, S8, S10) — design-by-accretion rather than design-by-policy.

#### S20. Sharp — `vault feature list` text rendering bug

The text output trails each feature with an unexplained `plan`
token: `snippets  9 docs  (adr, audit, index, plan, research) plan`.
The `--json` form has `has_plan: true` instead. The text render
appears to be trying to surface plan-ness in a way that does not fit
the per-feature one-liner.

### Smaller paper cuts (Round 3b)

- `vault feature archive` help text is the thinnest of any
  vault-mutating verb: one sentence, no mention of destination, no
  mention of reversibility, no mention of link-graph impact. The
  verb with the highest blast radius in the vault layer has the
  least documented surface.
- `vault add adr` and `vault add plan` template-placeholder warnings
  (round 1) still fire in round 3, three rounds later, unchanged.
  Long-standing noise.
- `tier: L{#}` placeholder on `vault add plan` (round 1 B2) still
  requires a hand edit in round 3. No `--tier` flag yet.
- `vault add exec` (round 1 B1) still has no `--step` / `--phase` /
  `--wave` flag in round 3. Three rounds, same wall.
- `vault plan step add` body destruction (rounds 1, 2 B6) was avoided
  in round 3 by ordering Steps before prose. The bug is unchanged;
  the workaround is now folklore.
- Positive: `vault graph --json` produces a node-link export
  immediately consumable by NetworkX-shaped graph tooling. The
  graph layer is the cleanest machine-readable surface in the CLI.
- Positive: `migrations status` reports `up_to_date` cleanly even
  when no run is needed, listing applied migrations as provenance.
  Migration verbs are uneventful — which is exactly right.

### Memory-lifecycle gap (Round 3 meta-finding)

Across rounds 1, 2, and 3 the framework's memory operations have a
consistent failure shape:

- **Addition / codification** (the "we just learned X; mandate X for
  future agents" verb) does not exist in the pipeline. Round 3a
  Bridge Gap.
- **Supersession** (the "this decision overrides that one" verb)
  does not exist (B3). Reconstructed from prose plus flat `--related`
  links plus emergent feature-index rendering.
- **Retirement / archive** (the "preserve forever, hide from active
  view" verb) exists but actively destroys the relationship layer it
  was supposed to preserve (B9).

Three points on the memory lifecycle, three CLI failures of three
different shapes. The framework's structural model of memory
(frontmatter + wiki-links + feature indexes + per-feature isolation)
is sound; the operations on that model — addition, supersession,
retirement — are weak at every endpoint. This is independent of the
vocabulary-fragmentation and tactical-bug findings; it is a
systemic gap in how the CLI lets a project mutate its memory.

## Recommendations — round 3

### Highest leverage (round 3 update)

- Fix `vault feature archive` end to end (B9). At minimum: add
  `--dry-run`, add `vault feature unarchive`, rewrite incoming
  `related:` links into `.vault/_archive/` on archive (or teach
  `vault check dangling` to resolve into the archive before declaring
  a link dead), reconcile `vault check structure` with
  `vault feature archive` on legal layout, exit non-zero on typo'd
  archive targets. The verb the team lead invokes by name must
  preserve the trail the team lead asked to preserve.
- Address the memory-lifecycle gap as a single architectural
  decision rather than three separate bugs. The pipeline needs a
  first-class verb for each lifecycle event: codify, supersede,
  retire. Today none of the three is properly surfaced.
- Reverse the `.vaultspec/` gitignore default (Round 1 S5). The
  memory mechanism is moot while the framework signals it as
  per-machine state.

### Vocabulary, shape, and machine-readable outputs

## Translation — findings to ADRs

Every finding cluster in this audit has been formalised into a
sibling ADR (and supporting research note) under its own feature
tag, per the framework's own pipeline. The mapping below is the
single-source-of-truth index from finding to architectural
decision. References use backtick-quoted stems rather than
wiki-links so cross-feature provenance lives in document bodies
and survives the archive verb (per the memory-lifecycle ADR's
fix).

| Cluster                              | Findings                                                                | ADR feature tag              |
| ------------------------------------ | ----------------------------------------------------------------------- | ---------------------------- |
| Memory-lifecycle verbs               | B3, B9, Bridge Gap                                                      | `cli-memory-lifecycle`       |
| Spec-layer gitignore reversal        | S5 (Round 1)                                                            | `cli-spec-gitignore`         |
| Sync-shaped vocabulary normalisation | S2, S8, S10                                                             | `cli-sync-vocabulary`        |
| Scaffolder integrity                 | B2, B5                                                                  | `cli-scaffolder-integrity`   |
| Plan-body preservation               | B6                                                                      | `cli-plan-body-preservation` |
| Exec per-step records                | B1                                                                      | `cli-exec-step-records`      |
| Spec edit safety                     | B7                                                                      | `cli-spec-edit-safety`       |
| Rename integrity                     | B8                                                                      | `cli-rename-integrity`       |
| Spec CRUD parity                     | S9, S15, S16                                                            | `cli-spec-crud-parity`       |
| Next-step hints / discoverability    | S3, Round 1 [20]                                                        | `cli-next-step-hints`        |
| Destructive blast-radius gating      | S4, S14                                                                 | `cli-blast-radius-gating`    |
| Machine-readable output consistency  | S19                                                                     | `cli-json-consistency`       |
| Duplicate-surface consolidation      | S12, S13, Round 1 [13]                                                  | `cli-surface-consolidation`  |
| Residual paper cuts                  | Round 1 [03], [06], [18], Round 3a [53], [54], [57], [58], Round 3b S20 | `cli-paper-cuts`             |

Each ADR is paired with a research synthesis note under the same
feature tag. Each ADR includes a Companion language updates
section that names the rule files, agent personas, templates,
and manual sections that must change alongside the code. This is
the dual-track translation the audit's findings demand: code
changes for the bugs, language changes for the framing.

The loop the user opened on this audit terminates here on the
ADR list. Downstream work — plans, exec records, implementation —
flows out of each ADR via the framework's own pipeline.

## Findings — round 4

### Round 4 — convergence test on the language-track delivery

Round 4 ran the same two persona subagents (Joan and Xavi) back
through their sandboxes after the language-track delivery for the
memory-addition cluster shipped. The codify triad
(rule + persona + skill) plus the pipeline-table edit, the audit
template's Codification candidates section, and three worked-
example discipline rules (archive, plan-editing, dry-run) were
under test. The convergence test asks one question: do agents
discover and use the new artifacts organically, without explicit
prompting at the language they speak?

#### B10. Confirmed positive — bridge gap closes when language-track lands

Joan v4 and Xavi v4 both reached the spec subtree organically.
Joan's command log shows him scanning `spec rules list`,
`spec agents list`, and `spec skills list` after `install --upgrade` — without being told to. Joan codified a finding
(`harbor-notes-empty-filter-contract`) from his work without any
explicit instruction to do so. Xavi codified
`archive-post-mortem-trail` from the recovery audit he had been
asked to write. Both crossed the bridge that across rounds 1, 2,
and 3 had never been crossed organically.

This is the round-3a Bridge Gap meta-finding's structural arm
closing under load. Six prior agent-days produced zero
organic spec-subtree contact; one round after the language-track
landed, both agents reached it and both produced project rules.

#### B11. Sharp — codify is real in language but not in CLI; verb gap surfaces immediately

Joan v4 finding [62]. The pipeline now has a sixth phase. The
audit template has a Codification candidates section. The skill,
persona, and discipline rules all describe codification. But
`vault rule --help` returns exit 2 ("No such command 'rule'") —
Joan tried the planned verb organically and found it missing.
Codification is authored via `spec rules add` and a hand-patched
body today; the higher-level `vault rule promote` verb that the
codify language-track names is `cli-memory-lifecycle` plan step
W02.P04.S12 work, not shipped.

The visible-but-unfinished surface is itself a fresh audit
finding: agents that read the system prompt's pipeline table see
phase 6 and reach for a command that does not exist. The
language-track outran the code-track. The disposition is the
work in W02.P04.S12; the rule and skill have to be honest about
the today-shape until then.

#### B12. Sharp — codification rules cite forward-pointing CLI surfaces

Two reproductions in round 4.

- Joan v4 finding \[69\]: the codify skill, persona, and rule all
  named `.vaultspec/rules/project/` as the authored-rule home;
  `spec rules add` actually writes to `.vaultspec/rules/rules/`
  alongside builtins. Fixed in commit `6553796` (round-4
  hardening).
- Joan v4 finding \[65\]: the `vaultspec-dry-run-discipline` rule's
  "Good" worked example invoked `vault add plan --tier L1`. The
  CLI rejects `--tier` (exit 2, "No such option `--tier`"). Fixed
  in commit `9e90ff7` (round-4 hardening).

The pattern: a rule authored against a planned-but-unshipped CLI
surface gives agents wrong instructions today. The codify rule
itself prescribes the discipline ("DO NOT name unshipped framework
verbs except as planned forward-pointers explicitly marked as
such"), and the rule violated its own discipline twice in its
first iteration. Both violations were caught and fixed within
round 4 itself, validating the convergence loop's self-correcting
property — but the framing problem is structural: codification
preceded implementation across the round, and the language
artifacts must reflect today's CLI honestly while pointing at
planned verbs only as marked-as-planned asides.

#### S21. Sharp — `vault plan step add` body destruction still reproduces, four rounds in

Joan v4 finding [67]. The bug Joan first observed in round 1
[17], reproduced by Xavi round 1 [08] and Xavi round 2, persists
unchanged in round 4. Joan ran a `Write` against the plan body
after `step add`, lost the Steps, and had to re-add them. The
`vaultspec-plan-editing-discipline` rule warned about a related
direction (structural mutation destroying prose) but did not
cover the inverse (prose mutation destroying structure). Both
directions are the same underlying bug; the rule's coverage is
half.

Disposition: the `cli-plan-body-preservation` ADR's serialiser-
preservation fix (W03.P07.S23–S26) closes the full bidirectional
case. The rule will widen in the same round.

#### S22. Sharp — `tier: L{#}` placeholder survives four rounds and a framework upgrade

Joan v4 finding [66]. The longest-lived friction in the audit
log. The fix is in `cli-scaffolder-integrity` plan step W01.P03.S08
which has not landed. The language-track upgrade explicitly added
new discipline rules referencing the workaround but did not fix
the underlying scaffolder antipattern. This is the clearest
illustration that language-track delivery alone does not move a
bug forward; the code-track must follow.

#### S23. Sharp — no next-step hint volunteers codify

Joan v4 finding [68]. The codify discipline is documented in the
system prompt, in the skill, in the persona, in the audit template
(Codification candidates section). But no CLI output anywhere
points the user at codification as a follow-on. After
`vault add audit ...` finishes, the operator sees `Created: ...`
and stops. After `vault check all` exits zero on a feature whose
audit has populated codification candidates, the operator sees
the all-clear and stops. The follow-on is invisible.

The `cli-next-step-hints` ADR (P13) is the disposition. Until
that ships, the operator is the discipline.

#### S24. Sharp — `spec doctor` does not validate language-track integrity

Joan v4 finding [71]. The path mismatch (B12 above) was a real
bug in three shipped builtin files. `spec doctor` ran clean
through every round. The doctor checks framework state but does
not cross-validate that the language-track's instructions match
the CLI's actual behaviour. This is a missing check class —
either an extension to `spec doctor` or a new `vault check language-track-consistency` verb that walks every rule, skill,
and persona for CLI-surface claims and runs them against today's
CLI.

Disposition: candidate sub-step under `cli-paper-cuts` P14, or a
new ADR if the scope expands beyond paper-cut work.

#### Smaller paper cuts (Round 4)

- Joan v4 finding \[70\]: `vault add plan --dry-run` on an L1 plan
  with no Steps emits an empty preview. Same shape as `install --upgrade --dry-run` from round 3a S14. Empty preview on a
  state-changing verb is worse than no preview; both belong in
  the same `cli-blast-radius-gating` (P11) fix family.

- Joan v4 finding [62] additional surface: `vault rule --help`
  exit 2 produces no hint at the canonical authoring path. A
  user who guesses the planned verb shape gets no redirect to
  `spec rules add`. The next-step-hint mechanism (P13) is the
  proper disposition; a small fix in the meantime is to detect
  the noun `rule` at the top-level verb and suggest `spec rules`.

- Positive: Xavi v4 produced a `### Codification candidates`
  block in his recovery audit doc. The audit template's new
  section did exactly the discoverability work it was meant to
  do.

### Round 4 meta — self-correcting convergence loop

The round produced four artifacts that the loop itself then fixed:

- Path mismatch in codify rule + persona + skill — found by Xavi,
  fixed mid-round.
- Path mismatch reproduced by Joan independently — confirms the
  bug was structural, not session-specific.
- `--tier` flag invocation in dry-run-discipline rule — found by
  Joan, fixed mid-round.
- `vaultspec-codify` skill missing from `vaultspec.builtin.md`'s
  skill list — found by Xavi, fixed mid-round.

Four bugs in newly-shipped language artifacts, all surfaced and
closed within the same round that introduced them. The
convergence loop's self-correcting property is now empirically
validated: language-track artifacts that ship against unshipped
CLI surfaces will be caught by the next fresh-eyes agent and
corrected before they harden into folklore.

The remaining round-4 findings (B11 codify-verb gap, S21 plan
body destruction, S22 tier placeholder, S23 missing next-step
hint, S24 spec-doctor language-track integrity check) are
dispositioned through the existing ADR set. None require a new
cluster ADR; all extend or refine existing ones.

## Codification candidates

Backfilled per the audit template's new `## Codification candidates` section (which post-dated the original audit
authoring). The audit's findings have already produced four
builtin discipline rules through the codify pipeline phase. Each
entry below names the source finding, the rule slug, and a
one-sentence statement of the constraint codified.

- **Source:** Round-3a Bridge Gap meta-finding.
  **Rule slug:** `vaultspec-codify`.
  **Rule:** Promote durable cross-session lessons surfaced in
  audit or ADR documents into project-shared rules via the codify
  pipeline phase, satisfying the three durability criteria
  (cross-session, constraint-shaped, project-bound).

- **Source:** Finding B9 (critical archive blast radius).
  **Rule slug:** `vaultspec-archive-discipline`.
  **Rule:** Before invoking `vault feature archive` against a
  feature, audit incoming cross-feature `related:` references and
  classify each as preserve, drop, or block-archive; do not run
  the amputating auto-fix on the post-archive dangling errors.

- **Source:** Finding B6 (plan-body destruction reproduced four
  times).
  **Rule slug:** `vaultspec-plan-editing-discipline`.
  **Rule:** When authoring or revising a plan, complete every
  Wave / Phase / Step structural mutation through the CLI verbs
  first; author prose sections last; until the
  `cli-plan-body-preservation` ADR's serialiser fix lands,
  interleaving structure and prose destroys prose.

- **Source:** Findings S4, S14, and the gating dimension of B9.
  **Rule slug:** `vaultspec-dry-run-discipline`.
  **Rule:** Before invoking any vaultspec CLI verb that writes or
  removes state, run the verb with `--dry-run` first when the
  flag is available; treat an empty preview as a warning, not as
  confirmation; until the `cli-blast-radius-gating` ADR's
  universal-dry-run fix lands, the operator is the discipline.

Round-4 self-corrections (commits `6553796`, `9e90ff7`, `166822d`)
hardened the codify-cluster rules against the discipline they
themselves prescribe. The Round 4 audit-of-audit confirms that
fresh-eyes agents catch language-track violations within the same
round; the codify discipline holds under recursive application to
itself.

Remaining round-4 findings (B11, S21, S22, S23, S24) did not
produce additional codification candidates because their
disposition is code-track work in the umbrella plan, not durable
cross-session constraints. The plan steps that deliver them carry
forward the language-track updates each cluster ADR specifies.
