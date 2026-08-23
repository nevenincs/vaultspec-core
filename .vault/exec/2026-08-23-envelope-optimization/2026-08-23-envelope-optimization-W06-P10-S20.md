---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:04ca9e11d2d79713fdf1e41dd878f41603131fd027504d04553a19a32a7d1398'
step_id: 'S20'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---
# Build the vault graph once and reuse it across features in the index preview

## Scope

- `src/vaultspec_core/vaultcore/repair.py`

## Description

- Pass the shared graph's per-feature nodes into the index-preview call so the generator stops
  rebuilding a cache-disabled graph of the whole vault once per feature.
- Record in the function why passing shared nodes is safe on this path and not on the mutating
  one, so the distinction is not lost to a later reader.

## Outcome

The preview built a fresh, cache-disabled vault graph — a full parse of every document — once
per feature, giving a cost proportional to features multiplied by documents. On a
1,229-document vault with 130 features that is 159,770 document parses.

| corpus | before | after |
| --- | --- | --- |
| 1,229 documents, 130 features | 115,100 ms | 3,350 ms |
| 2,500 documents, 405 features | 865,900 ms | measured linear thereafter |
| 10,476 documents, 660 features | killed at 600,000 ms, no output | 20,495 ms |

Three independent methods agreed on the cause before anything was changed. Profiling put 97.8%
of wall clock in the preview stage. An ablation that skips the stage and runs everything else
collapsed the runtime by 91%, which is the causal experiment rather than a correlation.
Bisection named the commit that introduced it and measured a nineteen to twenty-six fold step
change with no gradual ramp before it.

After the change the cost per document is flat at roughly three microseconds across a twenty
fold corpus range, and the fitted growth exponent moves from 1.74 to 1.00. The post-fix times
match the ablation almost exactly, which is the correct outcome: the stage now costs
approximately nothing rather than merely less.

The work performed is unchanged. Planned-index counts are identical before and after at every
corpus size where both were measured — fifty-two at five hundred documents, one hundred and
seventeen at two thousand — so the change removed repeated parsing rather than removing output.

## Notes

The parameter carrying the shared nodes is documented as one that production callers omit so
that membership is refreshed under the index lock. Passing it everywhere would therefore look
like the obvious fix and would quietly defeat the guarantee the introducing commit was added to
provide.

It is safe on this path for a specific reason: the preview branch takes a null context and holds
no lock at all, so there is no lock-ordering property to preserve. It computes what would change
and writes nothing.

The mutating refresh still rebuilds a cache-disabled graph per feature and is deliberately left
alone. It holds a real advisory lock and re-reads membership under it, so it needs a remedy that
keeps that guarantee rather than a copy of this one. That work is tracked separately.

The introducing commit was itself a correctness fix, for body-hash integrity across rewrites.
This change is not a revert of it and does not weaken it.
