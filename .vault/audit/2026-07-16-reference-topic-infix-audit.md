---
tags:
  - '#audit'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-reference-topic-infix-plan]]"
  - "[[2026-07-16-reference-topic-infix-adr]]"
---

# `reference-topic-infix` audit: `topic-infix scaffolding review` | (**status:** `PASS (after revision)`)

## Scope

Read-only review of branch `feat/issue-205-reference-topic-infix` versus `main`
(PR 217, GitHub issue 205) against the governing decision, plan, and research:
the scaffolder topic parameter, the CLI `--topic` flag, the MCP `DocumentSpec`
field, firmware wording, and tests. Reviewed by the `vaultspec-code-reviewer`
persona dispatched as an independent read-only subagent; initial verdict
REVISION REQUIRED, resolved in the same session.

## Findings

### topic-flag-leaves-body-placeholder-residue | high | --topic left the template heading placeholder unhydrated (RESOLVED)

The flag filled only the filename; a no-title invocation produced a document whose
`{topic}` heading placeholder survived and failed `vault check placeholders`
(exit 1), forcing the hand-editing the owning-verb mandate forbids. Resolved: the
humanized topic hydrates the heading when no title is given, an explicit title
still wins, and residue assertions were added to the scaffolder and CLI tests.
Verified end-to-end: a fresh workspace scaffold via
`vault add reference -f my-feat --topic engine-wire` now passes
`vault check placeholders` clean with heading `# my-feat reference: engine wire`.

### cli-reference-option-table-omits-topic | medium | bundled reference option table lacked --topic (RESOLVED)

The `vault add` option table in the bundled CLI reference did not list the new
flag. Resolved: the table row was added in the hand-authored zone of
`src/vaultspec_core/builtins/reference/cli.md` and the file re-normalized through
`spec reference generate`; the drift suite (22 tests) passes.

### regeneration-swept-unrelated-mcps-drift | low | reference regeneration bundles pending generator-owned churn (ACCEPTED)

Regenerating the generator-owned region swept in pending `spec mcps` signature
wording unrelated to this feature. Benign and noted in the PR body.

### mcp-batch-partial-semantics-uncovered | low | no mixed-batch coverage (RESOLVED)

A mixed-batch test (valid infixed reference + topic-rejected adr + plain
research) now locks in per-item failure semantics.

### Positive confirmations

Guards intact on the infixed path (exists- and stem-collision), omitted-topic
byte-identical, CLI and MCP transports converge on the shared normalizer and one
builder call, firmware wording consistent with the audit-infix convention and
the code-stands-alone clause, zero em dashes, no drift beyond the decided
surfaces.

## Recommendations

None outstanding; all blocking findings resolved and verified. Final gates:
scaffolder, CLI, and MCP suites green; drift suite green; unit gate green.

Status: PASS after revision. Safe to merge.
