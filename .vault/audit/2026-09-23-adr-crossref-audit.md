---
tags:
  - '#audit'
  - '#adr-crossref'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:ea921f6b384d7bce666088a7e5b83e44c85f2aec09112d97b49098d1675da64a'
related:
  - "[[2026-09-23-adr-crossref-plan]]"
  - "[[2026-09-23-adr-crossref-adr]]"
---

# `adr-crossref` audit: `plan-close review of bounded ADR cross-referencing`

## Scope

Plan-close review of `2026-09-23-adr-crossref-plan`, Steps S01 to S08, commits `55351624`
to `3a0f0023` on `feature/adr-crossref`, against `2026-09-23-adr-crossref-adr` and the
inherited `2026-09-23-typesafe-search-adr`. Two independent reviewers covered the
backend (the `crossref` package, the core link writer, `vault link add`) and the
surfaces (the CLI verb, the MCP tool and read-only guard, the handbook, the MCP guide,
the bundled reference, the ADR and curation firmware, the amendments). The review found
the per-run ceilings enforced in code and the worst-case reply at about 5,600 tokens,
under the 10,000-token envelope ceiling. Result: REVISION REQUIRED; S03, S04, S05, S06
and S08 were reopened.

## Findings

### sweep-resume | high | A failing ADR stalled every resumed sweep, and a run that failed first lost its cursor

`src/vaultspec_core/crossref/_service.py` stopped a sweep at any source that was not
`ok` and set `next_after` to the last judged source, or `None` when none was judged. An
ADR the provider always refuses (`content_rejected`, `request_too_large`) was retried by
every resumed run at up to 46 evaluations, so the documented loop "resume until
`remaining` is 0" never ended. Fixed in S03: those refusals fail only their source and
the cursor moves past them; any other failure keeps the cursor where the run began.

### apply-write-failure | high | A link the source's related: field could not take crashed the run

`link_document` raises `ValueError` for a `related:` value it cannot extend safely.
`_apply` did not catch it, so `--apply` printed a traceback after the evaluations were
paid for and lost the reply that said what earlier sources wrote. Fixed in S03: a failed
write is reported per verdict in `write_failed` and the run goes on.

### docs-vault-identifiers | high | The handbook used this vault's own ADR stems as examples

`docs/CLI.md` showed `vault adr crossref 2026-09-23-adr-crossref-adr` and
`--after 2026-03-23-roadmap-adr`. User documentation must not cite vault records.
Fixed in S04 with placeholder stems.

### curator-loop | high | The curation prose looped sweeps with no exit and no spend checkpoint

`vaultspec-curate`, its playbook and the curator persona said to resume "until
`remaining` is 0". A `not_configured` or stopped reply gave no exit, and one persona run
was told to exhaust the corpus: about 54 runs and 60 to 70 million input tokens on a
534-ADR vault. Fixed in S06: a curator run takes one bounded sweep, stops on
`not_configured` or `stopped`, and reports `next_after` and `remaining` so the
orchestrator authorises any further spend.

### failure-fan-out | medium | Queued evaluations were still sent after the source had failed

The engine's thread pool ran every submitted job to completion, so a rejected key sent
all of a source's requests. Fixed in S03: the first fatal failure cancels every job not
yet started.

### fingerprint-variables | medium | Configuration variable names were dropped from the fingerprint

The all-caps filter matched `VAULTSPEC_CORE_TYPESAFE_API_KEY` and discarded it, although
configuration variables are a named artifact class. Fixed in S03: only all-caps words
without an underscore are dropped.

### bounds-untested | medium | The ceilings were not exercised end to end

No test reached the 46-evaluation worst case, a deadline, a refused Choice chunk, the
fan-out stop, an apply failure or a resumed failure. Fixed in S03 with
`src/vaultspec_core/crossref/tests/test_bounds.py`.

### wire-parity | medium | MCP and CLI verdict rows differed on applied and a null status

The MCP model added `applied: false` to every row and pruned a null `status` that the
CLI printed. Fixed in S05: both fields are optional on both surfaces, and a parity test
compares a reply that carries verdicts.

### rerun-apply | medium | The firmware advised rerunning with --apply after reading the verdicts

A rerun judges again and writes its own verdicts, which nobody read, at the full cost
again. Fixed in S06: confirmed links are added with `vault link add`; `--apply` is for a
run whose every `link` verdict is accepted unread.

### schema-amendment | medium | The tool-schema amendment did not retire the single-digit constraint

`2026-07-09-mcp-tool-schema-adr` still stated the single-digits rule and an earlier note
that it "still holds". Fixed in S08: the amendment names the constraint it replaces.

### deadline-tail | low | A sweep could start a source with seconds of its budget left

Fixed in S03: a source needs 15 seconds of the run budget to start.

### cursor-input | low | The cursor was compared raw, and named sources silently ignored filters

Fixed in S03: the cursor resolves like any reference and must name an ADR; named
sources combined with `--feature` or `--isolated` are refused.

### refused-chunk-rank | low | A refused Choice chunk ranked its candidates below every answered one

Fixed in S03: those candidates are left out of the Choice ranking and keep their code
rank.

### docs-and-counts | low | Wording, fields and tool counts were stale in the guides and tests

The guides said the decline names "the listing" although rag may be named; omitted
`unjudged_declared`, `next_step`, `remediation`, `reason` and `write_failed`; described
the code stage as title overlap; did not state the `refs` limit; and `docs/MCP.md` and a
budget comment carried stale tool counts. The read-only guard's name no longer described
its scope. Fixed in S04 and S05.

### curate-autonomy | low | The curate skill's autonomy list lacked the new directly applied class

Fixed in S06.

### cli-rule-fallback | low | The CLI rule named crossref without its CLI verb

Fixed in S06.

### link-add-semantics | low | vault link add no longer treats a body wiki-link as an existing edge

`src/vaultspec_core/vaultcore/related_links.py` checks `related:` only, where the old
command consulted graph out-links that include body links. Accepted without change:
`related:` is the edge store, and record bodies carry no wiki-links under the vault
rules.

### transport-deadline | low | The deadline bounds each socket operation, not an evaluation's wall time

Inherited from `src/vaultspec_core/search/_transport.py`: a reply trickled byte by byte
can outlast the deadline, and a request resent on a stale pooled connection is not
counted as an attempt. Open; see Recommendations.

### aggregate-concurrency | low | Nothing caps concurrent crossref calls across one process

Each call builds its own client with 12 slots, so a host fanning out calls multiplies
in-flight requests and spend. Open; see Recommendations.

### governance | low | Snapshot refresh, another feature's ledger, and an unrecorded live check

The tracked `.vaultspec/` snapshot of the five changed firmware files is refreshed by
this repository's separate framework commits. S01 also stripped template hints from the
discovery-fallback ledger, which the annotation hook requires and which the other branch
will make identically. The plan's live ceiling check lacked a `verify:` row. Recorded in
the ledger at plan close.

## Recommendations

- A follow-on amendment to `2026-09-23-typesafe-search-adr` should decide whether the
  transport enforces a wall-clock bound per evaluation and whether a resend on a stale
  connection counts as an attempt.
- A follow-on decision should settle whether core caps Jev requests in flight, and
  spend, across concurrent `crossref` and `search` calls in one process.
- A follow-on decision should settle how spend is authorised for corpus-wide
  cross-referencing beyond one bounded sweep.

## Re-review 2026-09-23

Scope: the first fix round, commits `c2c4dad0` to `8755c794`. Result: PASS. All four high
findings above were confirmed resolved, with the medium and low findings below left; each
was fixed in a second round, commits `486d141c` to `42d21425`, and in the amendment note of
`2026-09-23-adr-crossref-adr`.

### cancel-on-any-failure | medium | Cancellation only happened when the first submitted job failed

The engine read results in submission order, so a failure in a later job let every queued
evaluation run while an earlier job was still in flight. Fixed: the engine waits for the
first exception from any job, cancels the jobs not yet started and raises at once; a test
fails a job other than the first.

### provider-wide-refusal | medium | A provider-wide block read as each ADR's own refusal

An edge refusing every request produces a content rejection per source, which the first
fix counted as per-source, so a sweep could skip its whole selection. Fixed and recorded
in the ADR amendment: a refusal counts as the ADR's own only after the provider has read
something in the sweep, and three in a row stop the sweep.

### cursor-drift | medium | The accepted ADR said the cursor names the last source judged

Fixed by the ADR's sweep-resume amendment note, authorised under the user's advance
approval of the feature.

### apply-lock-timeout | medium | A lock timeout while writing a link escaped apply

Fixed: `AdvisoryLockTimeoutError` is reported per verdict like any other write failure.

### curator-sweep-contract | medium | The curation prose gave an invalid resume command and two stop conditions

Fixed: resume repeats the selector with `--after`, and the persona, skill and playbook
stop on `not_configured` or `stopped`.

### refused-chunk-order | low | A refused chunk's candidates took no Choice position

Fixed: they take the Choice position their code rank gives them; `order_choice` is tested
directly.

### cli-write-failure | low | A failed write read as done in the terminal and exit status

Fixed: the source shows each link it could not write and the command exits 1.

### edge-paths | low | Small inconsistencies in selectors, cursor and summary

Fixed: named ADRs with `--all` are refused, a finished selection reports no cursor, the
MCP summary counts a sweep's outcomes, and the result's cursor is described as the last
source processed. The stop for a sweep with too little budget left to start a source has
no test, since it needs a run of five minutes; the rule is one comparison.

### budget-comment | low | Budget comments referred to the review

Fixed: they name the fields they measure.

## Re-review 2026-09-23, second round

Scope: the second fix round, commits `486d141c` to `42d21425`, and the sweep-resume
amendment. Result: REVISION REQUIRED on one high finding. The findings were fixed in a
third round, commits `daaaba89` to `023936ef`, and the amendment's Cursor and Selection
bullets were rewritten to match.

### refusal-resume-stall | high | A refusal before any read stopped every resume at the same ADR

The rule "a refusal counts as the ADR's own only after the provider has read something"
stopped a sweep whose first source was refused, so a resume that landed on such an ADR
stopped there every time. Fixed: a refused source is held open while the sweep judges
on; a later read settles it as the ADR's own, and three refusals in a row stop the sweep
before the first of them. Tests resume onto a refused ADR, end a batch on one, and end
the selection on one.

### refusal-run-skip | medium | The first two refusals of a provider-wide block were passed for good

Fixed by the same rule: no refusal is passed until a later read confirms it, so a block
leaves the cursor before its first refusal.

### interrupt-spend | medium | An interrupt while waiting left queued evaluations to run

Fixed: an exception while waiting shuts the pool down without waiting and cancels what is
queued.

### amendment-selection | low | The amendment said "exactly one selector"

Fixed in code and text: named ADRs and all each stand alone, a feature and the isolated
ADRs narrow together, and an empty feature is refused.

### stale-docstrings | low | Service and CLI docstrings described the earlier sweep rule

Fixed.

### cli-resume-hint | low | The resume hint omitted the selector a resume needs

Fixed: it says to repeat the selector with `--after`.

### mcp-selector-test | low | No test showed all_adrs reaching the backend or the sweep summary

Fixed, with a stdio call and a summary test; the summary also names why a sweep stopped.

### too-large-read-flag | low | A request refused before sending counted as a provider read

Fixed: a read is counted from answered input tokens.

### run-of-own-refusals | low | Three ADRs refused on their own text in a row stop every sweep there

Accepted as designed: the sweep cannot tell such a run from a provider-wide block
without stored state. The curation prose says to confirm the provider reads with a
single-ADR run and then resume past the refused ADRs, recording them.

### watchdog-timing | low | One unrelated watchdog timing test failed once under parallel load

`src/vaultspec_core/mcp_server/tests/test_watchdog.py::test_fallback_grace_window_prunes_transient_ancestor`
failed once in a full parallel run and passed three times alone. This branch does not
touch the watchdog. Recorded only.

## Re-review 2026-09-23, third round

Scope: the third fix round, commits `daaaba89` to `023936ef`. Result: REVISION REQUIRED on
one high finding, fixed in a fourth round, commits `51a7bf52` to `90432dc4`, with the
amendment's Cursor bullet rewritten.

### unsettled-refusal-stall | high | A batch ending on unsettled refusals reported no stop and repeated forever

With refusals still open when the batch ended and no vouching, `stopped` stayed unset and
the cursor stayed before them, so a one-source sweep landing on a refusal, a resume at
the end of the selection, or a selection of refused ADRs alone repeated itself while
looking like progress. Fixed: a sweep holding a refusal open may judge up to two more
sources past its size to find a settling read, and any refusal still open when it ends
sets `stopped` with the cursor before it. The absolute ceiling is 52 sources.

### tail-vouching | medium | End-of-selection vouching could pass a provider-wide block

Fixed by removing vouching: no refusal is passed without a later read. This makes the
second round's refusal-run-skip entry hold without exception.

### escape-after-block | low | The curator's escape could skip ADRs refused only during a cleared block

Fixed: after one other ADR is judged, the curator judges the first refused ADR alone and
skips it only if it is refused again.

### mcp-empty-feature | low | MCP judged one ref with an empty feature that the CLI refuses

Fixed: any feature value is passed to the backend, which refuses an empty one.

### interrupt-window | low | An interrupt during job submission left queued jobs to run

Fixed: submission sits inside the interrupt guard. No unit test raises an interrupt
inside the pool, which cannot be triggered deterministically.

### watchdog-timing, again | low | A second watchdog timing test failed once under parallel load

`src/vaultspec_core/mcp_server/tests/test_watchdog.py::test_armed_worker_exits_when_dead_client_pid_signals`
failed once in the parallel full run and passed three times alone. The branch changes
neither the watchdog nor its tests.

## Re-review 2026-09-24, fourth round

Scope: the fourth fix round, commits `51a7bf52` to `90432dc4`. Result: PASS. A simulation
of every ok, refused and rate-limited script of eight sources at sweep sizes 1, 2, 3 and
5 confirmed that no run can stall silently, that no refusal is passed without a later
read, and that no sweep judges more than its size plus two sources. The remaining
findings were fixed in commits `7e8114ef` to `86ea3f72`.

### settled-refusal-unrecorded | medium | A refusal settled in a sweep that then stopped was never recorded

Fixed: the curation prose records every refused source at or before `next_after`,
whether or not the sweep stopped.

### stopped-reason | low | An unsettled request_too_large refusal was reported as content_rejected

Fixed: `stopped` carries the reason of the first refusal still open.

### next-after-contract | low | next_after can be absent while sources remain

Fixed in the model docstring and both guides: without a processed source and a given
cursor, a resume starts from the beginning.

### empty-cursor | low | An empty cursor was treated as none

Fixed: it is refused like any cursor that names no ADR.

### ceiling-test | low | No test pinned the sources judged past the size

Fixed: a test ends a batch on a refusal at the size limit and shows the sweep stopping
two sources past it.

## Result

PASS. Every Step is closed, the full suite passed at 5,741 tests after the fourth round,
and the final round's changes pass the crossref, CLI, MCP, documentation and framework
contract suites.
