---
tags:
  - '#adr'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-firmware-code-boundary-research]]"
  - '[[2026-06-13-commit-linkage-adr]]'
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-07-09-firmware-mcp-primacy-adr]]'
---

# `firmware-code-boundary` adr: `one-way vault reference boundary - code stands alone, dev metadata never crosses into source` | (**status:** `accepted`)

## Problem Statement

The vaultspec premise is that `.vault/` and `.vaultspec/` are a removable development
harness layered over a codebase, not an integrated part of it. Yet the firmware never
states the boundary: no rule, system mandate, persona, or skill forbids an executing
agent from embedding the project's own dev metadata - `.vault/` document stems,
plan/ADR/audit identifiers, Step ids, wiki-links, harness paths - into source code,
and one execute-skill requirement is misreadable as inviting exactly that
(`2026-07-16-firmware-code-boundary-research`). Every such reference encodes
development metadata into the codebase, weakens the boundary contract, and breaks the
"code must stand on its own" mandate: strip the harness and the code carries dangling
pointers into a corpus that no longer exists. The decision is the exact boundary
wording, which firmware surfaces carry it, and what stays out of scope - without
bloating the framework.

## Considerations

- The grounding research establishes: the prohibition is absent everywhere; the
  one-way convention (vault cites code, never the reverse) is already implicit in the
  documentation hierarchy and locator rules; five surfaces write or gate code; the
  mcp-primacy placement architecture (canonical statement once, load-bearing echoes
  only) is the proven anti-bloat shape.
- The commit-linkage decision (`2026-06-13-commit-linkage-adr`) already owns the
  sanctioned commit-to-vault channel (opt-in git trailers, enrichment-only); boundary
  wording that swept in commit metadata would contradict it.
- Self-hosting: vault-domain codebases (this repo included) legitimately handle
  `.vault/` paths as product functionality; the forbidden class must be the project's
  own development records, not a literal path string.
- Firmware edits land in the builtin sources and propagate by `vaultspec-core sync` to
  every managed project; per the firmware-wording-review constraint
  (`2026-06-09-firmware-wording-review-adr`), a wording pass is documentation-only and
  behavioral (Python) work becomes a logged follow-up.

## Considered options

- **System-mandate-only (one bullet in the core mandates, nothing else).** Cheapest,
  but dispatched executors never see the system prompt; the personas that actually
  write code would carry no trace of the boundary. Rejected.
- **Blanket sweep (state the rule on every rule, persona, and skill).** Maximal recall,
  but restates one invariant up to twenty times, the exact bloat the mandate forbids;
  surfaces with no code-writing footprint gain nothing. Rejected.
- **Targeted placement (chosen).** One canonical mandate at the always-on core, one
  boundary characterization where the framework introduces `.vault/`, one identical
  bullet in each code-writing executor, one review dimension at the gate, one clause
  closing the hierarchy's implicitness, and one in-place disambiguation of the
  misreadable Traceability line.
- **Mechanical enforcement now (a `vault check` source scanner).** Deterministic, but
  Python work with false-positive risk in vault-domain codebases; out of scope for a
  wording pass. Rejected for now; registered as a follow-up candidate.

## Constraints

- Documentation-only: every edit lands in markdown firmware sources under
  `src/vaultspec_core/builtins/`; no Python changes, no schema or template renames, no
  persona `tools:` or `mode:` changes.
- The boundary scopes to tracked source-file content: code, comments, docstrings,
  identifiers, tests, configuration, and user-facing documentation. Git commit
  trailers and commit messages stay governed by the commit-linkage convention and are
  explicitly out of scope.
- The wording must forbid references to the project's own development records, never
  the literal `.vault` string, so vault-domain product code stays legal.
- The executor trio stays structurally parallel (D9 of
  `2026-06-09-firmware-wording-review-adr`): the new bullet is byte-identical across
  the three personas.
- Tests may assert builtin content; the full test gate and prek hooks must stay green,
  and the deployed `.vaultspec/` mirror is reconciled by `vaultspec-core sync`, never
  edited directly.

## Implementation

The canonical mandate, stated once and echoed in compressed form. Canonical shape:
"The `.vault/` corpus and the `.vaultspec/` harness are removable development
scaffolding, not part of the codebase. Code must stand on its own: never embed
references to the project's own development records - `.vault/` document stems,
plan/ADR/audit identifiers, Step ids, wiki-links, or harness paths - in source code,
comments, docstrings, tests, configuration, or user-facing documentation. The
reference direction is one-way: vault documents cite code by locator; code never cites
the vault. Opt-in git commit trailers are the only sanctioned linkage channel."

Placement, six surfaces:

- `system/01-core.md` Mandates list gains one **Code stands alone** bullet carrying
  the canonical shape, beside the Comments mandate it structurally mirrors.
- `system/03-vaultspec.md` gains one sentence where `.vault/` is introduced,
  characterizing it as a removable harness with one-way reference direction.
- `agents/vaultspec-low-executor.md`, `agents/vaultspec-standard-executor.md`,
  `agents/vaultspec-high-executor.md` each gain one identical bullet in the core
  implementation mandate: deliverable code, comments, docstrings, tests, and configs
  never reference the plan, Step ids, vault documents, or harness paths; traceability
  lives in the Step Record, which cites the code, never the reverse.
- `agents/vaultspec-code-reviewer.md` Intent Domain gains one **Boundary integrity**
  check - flag any dev-metadata reference in delivered source as an architectural
  violation (existing HIGH severity class; no taxonomy change).
- `rules/vaultspec.builtin.md` Documentation Hierarchy gains one clause: source code
  sits outside the hierarchy entirely; documents cite code by locator and code never
  references `.vault/` or harness contents.
- `skills/vaultspec-execute/SKILL.md` Traceability requirement is disambiguated in
  place: mapping lives in the Step Record (record cites code), never as annotations in
  the code itself.

All other personas and skills are untouched. Rollout follows the established firmware
path: edit builtin sources, `vaultspec-core sync`, verify `vault check all` plus the
test gate, ship in the next release. A read-only `vault check` source-boundary scanner
is registered as a follow-up issue, not implemented here.

## Rationale

Targeted placement wins because the audiences are disjoint and the failure sites are
few: the research shows only the executor trio writes deliverable code, only the
reviewer gates it, and only two always-on surfaces address every session, so six edits
buy full coverage of the write path and the review path while leaving fourteen-plus
surfaces untouched. Stating the invariant once in canonical form and echoing it
compressed is the shape the mcp-primacy decision already validated for exactly this
firmware. The record-reference scoping (not path-string) is forced by the self-hosting
evidence, and the trailer carve-out is forced by the standing commit-linkage decision;
both alternatives would make the firmware self-contradictory. Deferring mechanical
enforcement keeps this shippable as an ordinary sync-propagated wording change under
the same documentation-only discipline the firmware-wording-review pass proved out.

## Consequences

Good: the boundary contract becomes explicit on every surface that can violate or
catch it; managed projects receive the rule on next sync with zero migration; the
reviewer gains a named, severity-mapped check so violations fail review rather than
accumulate; the "code must stand on its own" premise is finally written down where
agents read it.

Bad: wording-only enforcement depends on agent compliance; existing violations in
downstream codebases are not detected or cleaned by this change; six surfaces gain a
few lines each (bounded, but nonzero standing-context cost); every managed project's
provider rules change on next sync, surfacing as diff noise where provider directories
are committed.

Neutral: commit trailers, commit messages, and vault-internal cross-references are
untouched; the mechanical scanner remains an open follow-up whose adoption can be
decided independently; if a future decision ever wants code-to-vault references (e.g.
generated traceability manifests), it supersedes this record rather than eroding it.

## Codification candidates

- **Rule slug:** `code-stands-alone`.
  **Rule:** The reference direction between the vault and the codebase is one-way:
  vault documents cite code by locator; tracked source-file content (code, comments,
  docstrings, tests, configuration, user-facing docs) never references the project's
  own `.vault/` documents, identifiers, or harness contents. Opt-in git commit
  trailers are the only sanctioned linkage channel.
