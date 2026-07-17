---
tags:
  - '#adr'
  - '#code-boundary-check'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-code-boundary-check-research]]"
  - "[[2026-07-16-firmware-code-boundary-adr]]"
  - '[[2026-06-13-commit-linkage-adr]]'
---

# `code-boundary-check` adr: `opt-in read-only source-boundary scanner` | (**status:** `accepted`)

## Problem Statement

The firmware-code-boundary decision made the one-way vault reference boundary
explicit in wording and registered mechanical enforcement as a follow-up (GitHub
issue 213): a read-only checker that sweeps source-file content for references to the
project's own vault records. Wording-only enforcement depends on agent compliance and
detects nothing already embedded. The decision: the scanner's scope, its needles, its
place in the check surface, and its default posture.

## Considerations

- The governing firmware-code-boundary decision fixes the constraints: advisory-only
  (report, never block), record-stem scanning rather than path-string matching (the
  self-hosting nuance), commit trailers and commit messages out of scope, and
  false-positive risk as the acceptance criterion for any default-on posture.
- The grounding research establishes: warnings exit 0 (advisory needs no new
  machinery); `check all` is vault-scoped and snapshot-driven with explicit
  membership; standalone check verbs are an established shape; record stems are
  enumerable, date-prefixed, high-precision needles; a source-tree walk needs its own
  exclusion set, decode guard, and size cap; pure-offline operation follows the
  commit-linkage precedent.

## Considered options

- **Standalone opt-in verb, warnings-only, excluded from check all (chosen).**
  `vault check code-boundary` walks the source tree on demand; `check all` stays
  vault-scoped and its cost profile unchanged.
- **Member of check all.** Rejected for now: adds a repo-walk to every gate run and
  puts an unproven false-positive profile into the default pipeline; membership is
  revisitable by amending this record once field experience exists (the issue's own
  acceptance criterion).
- **Scan for Step ids and the literal vault path too.** Rejected: `S##` and `.vault`
  are false-positive-prone in vault-domain codebases; stems (plus explicit wiki-link
  forms of stems) are the high-precision needle set the self-hosting constraint
  admits.
- **Git-based scan set (git ls-files).** Rejected: pure-offline walk with explicit
  exclusions keeps the checker dependency-free and deterministic per the
  commit-linkage precedent; git remains unrequired by any core command.

## Constraints

- Diagnostics are WARNING severity only; the verb never exits nonzero for findings
  and never mutates anything (`supports_fix` false).
- Needles are the stems of every `.vault/` document (date-prefixed authored records
  and `<feature>.index.md` indexes), matched as plain substrings and in wiki-link
  form; nothing else.
- The walk excludes `.vault/`, `.vaultspec/`, every provider directory from the
  central enum, `.git`, and common cache directories; skips files above a size cap
  and files that do not decode as UTF-8.
- The scanner scans tracked source-file content only in the boundary's sense (code,
  docs, config in the working tree); commit metadata is out of scope.
- No new dependency; no change to `run_all_checks` membership or order.

## Implementation

One new checker module in the checks package exposing the scan as a `CheckResult`
producer: enumerate needle stems from the vault, walk the source tree under the
exclusion set, and emit one WARNING diagnostic per (file, stem) hit with the matched
stem named in the message. One new CLI subcommand `vault check code-boundary`
following the existing standalone-verb pattern, with `--json` and `--feature`
(restrict needles to one feature's documents) supported. The MCP surface is
unchanged; the gateway reaches the verb as it reaches every CLI verb. Unit tests
cover: hit in source file, wiki-link form hit, no hit on the literal vault path
string alone, exclusion of vault/harness/provider dirs, feature filtering, undecodable
and oversized file skips, and exit code 0 with findings. The bundled CLI reference
regenerates; the firmware is not touched (the boundary wording already shipped, and
naming a specific optional verb in always-on firmware is bloat the mcp-primacy
posture avoids).

## Rationale

The standalone opt-in shape is the only posture consistent with the governing
decision's acceptance criterion: it ships mechanical detection for teams that want it
now, keeps the unproven false-positive profile out of every default gate, and leaves
default-on membership as a one-line amendment once evidence accumulates. Stem-only
needles are what make the scanner usable at all in vault-domain codebases - the
governing decision's self-hosting constraint rules out the cheaper literal-path scan.
Warnings-only falls out of the existing exit-code contract, so the
enrichment-never-prerequisite discipline costs no new machinery.

## Consequences

Good: embedded dev-metadata references become mechanically discoverable; the
boundary gains its first enforcement instrument; downstream vaults can wire the verb
into their own hooks. Bad: opt-in means silent non-adoption is the default; a
repo-walk verb has an unbounded worst-case runtime on very large trees (mitigated by
exclusions and the size cap, and it runs only when invoked). Neutral: check all is
byte-identical in behavior; membership and a pre-commit hook entry remain open
adoption questions to revisit against field evidence by amending this record.

## Codification candidates

- **Rule slug:** `boundary-scan-before-audit`.
  **Rule:** A feature audit in a vault-managed project should run
  `vault check code-boundary` and triage its findings; scanner warnings are advisory
  and never block a commit or a merge.
