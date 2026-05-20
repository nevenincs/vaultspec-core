---
tags:
  - '#research'
  - '#cli-next-step-hints'
date: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
---

# `cli-next-step-hints` research: `CLI never volunteers what to run next`

Synthesis note for the discoverability cluster — finding S3
(undiscoverable `vault repair`), round-1 [20] ("no suggestion of
what to run next anywhere"), plus the natural-language pipeline
mapping shortfall that the round-3a Bridge Gap meta-finding
amplifies.

## Findings

### Successful commands terminate silently

Round-1 finding [20]. Joan ran every command listed in
`vaultspec-core --help`. None of them ended with a "next step"
line. After `install` the output is a list of changed files.
After `vault add research` the output is `Created: <path>`.
After `vault check all` (when it passes) the output is a green
summary. Each command knows what it did; none knows what comes
next.

The only exception is the fix-it hint that `vault check`
produces against failed checks. The pattern "next: do X"
exists but only on the failure path. Successful work is
discoverability-silent.

### `vault repair` is the worst case

Round-1 S3. The single most useful command in the entire vault
surface is the one no `--help` text recommends. Joan independently
discovered it and called it "the single best command in the
entire CLI surface". Xavi never discovered it in three rounds;
he spent three commands (`vault sanitize annotations` →
`vault feature index` → `vault check all`) doing what `vault repair` does in one.

The CLI had every chance to surface it. The install summary
could have. Any `vault add` output could have. The `vault check all` clean output could have. None did.

### Round 3a Bridge Gap is the structural form

Across six agent-days, neither persona reached the `spec`
subtree organically. The pipeline (research, decide, plan,
execute, review) never pushes the agent toward `spec rules add` even though the spec subtree is the durable rule-
authoring surface the pipeline ostensibly exists to support.

The framework's natural-language verbs map exclusively to
`vault add`. The codify step (sibling memory-lifecycle ADR)
adds the missing verb. This ADR adds the discoverability
shape: the verb that exists must also be reached.

### What contextual hints can do

A successful `vault add research` knows two things the next
agent needs: the feature's name, and the natural follow-on
(decide). It could emit:

> `Created: .vault/research/2026-05-17-<feature>-research.md`
> Next: `vaultspec-core vault add adr --feature <feature> --related <stem>` (decide)

A successful `vault add audit` could emit:

> `Created: .vault/audit/2026-05-17-<feature>-audit.md`
> Next: `vaultspec-core vault rule promote --from-audit <stem> --as <rule-name>` (codify)

A clean `vault check all` could emit:

> `All checks passed.`
> Next: `git commit -m "..."` or `vaultspec-core vault repair`
> if you want a deeper pass.

The information needed to emit the hint is already available
at the point of emission. The work is the hint mechanism, not
the per-command logic.

### Constraints on usefulness

Hints become noise if they are wrong, generic, or absent of
context. The pattern should be:

- Conditional on actual state (don't suggest codify if the
  audit has no findings).
- Specific (named command, named arguments) rather than
  abstract ("consider whether to codify").
- Singular (one next-step hint, not three) on the common path.
- Suppressible (`--no-hints` or environment variable) for
  scripted contexts.

## Recommendation

Adopt a per-command next-step hint mechanism. Every successful
verb emits a single conditional next-step line when one exists.
The framework's pipeline becomes self-teaching: an agent
running the wrong command discovers the right one in the
output of the wrong one. Full design in the sibling ADR.
