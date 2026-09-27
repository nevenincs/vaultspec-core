---
tags:
  - '#research'
  - '#skill-audit'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:1fc670e2577da575bbb5c7d9420988dabec8ce7bca592dccae1b4d071ebe58b7'
related:
  - "[[2026-09-25-skill-audit-code-review-audit]]"
  - "[[2026-09-23-typesafe-search-adr]]"
---

# `skill-audit` research: `TypeSafe review context ranking spike`

TypeSafe selected the relevant review context in all six frozen cases. The assisted
reviewer identified all three historical defects and left all three corrected controls
clear, matching full-context review with eighteen percent fewer reported reviewer input
tokens. A cheap lexical shortlist missed the actual MCP subclass-rejection mechanism.
This supports further work on optional context selection; it does not establish a
production review gate or a reliable speedup.

## Findings

### Design isolates context selection from review instructions

`dev/experiments/review_context_spike.py` freezes three historical changes: ledger
evidence preservation (`8373e597`), MCP factory smoke-check compatibility (`0cadfc9b`),
and the acquisition workflow's executable path (`066eee76`). Each supplies a reversed
regression and a corrected control. Twelve source passages form a hand-assembled pool
shared across the cases. The diff and target code always remain visible; only supporting
context is selected. Labels were frozen before calls and verified separately through
the historical code or, for acquisition, the extraction and invocation paths.

Eighteen isolated Codex CLI sessions used `gpt-6-sol` at low effort: one per case per
condition, in a fixed shuffled order. Full context supplied all twelve passages. Lexical
and TypeSafe selection each supplied three. Every prompt included the remaining passage
locators and allowed local reads. No reviewer saw the labels, the historical commit
messages, the other condition's answers, or the fact that its case was a regression or
control. The static-review instructions and absence of test results were identical.
No VaultSpec skill or team persona ran.

The fixture SHA-256 is
`d7e1312c282e10657a8fa5c476926a1fe4e4b0e0cdc9086f9d5e24cb6b76f89e`.
Rebuilding from Git produces identical bytes. Formatting changes preserved all eighteen
prompt byte sequences. `dev/experiments/review_context_results.json` carries the raw
answers, grades, usage, and ranking results; detailed CLI events remain in ignored
`dev/statistics/out/review-context/`.

### Narrow live judgments fit the time budget

The existing Jev transport sent six recorded requests, each with twelve independent
Score questions over one case and the candidate pool. Questions ask about a passage's
concrete contribution to judging the changed behavior, not topic similarity. All calls
use the canonical core enum; TypeSafe resolves the actual model. Calls took 0.235 to
0.765 seconds, totaling 1.995 seconds, with 48,048 reported input and 1,104 output tokens.
No timeout, service failure, or lexical fallback occurred in these six calls.

At the published rate of USD 0.042 per million input tokens, those calls cost an estimated
USD 0.002018. This is not an invoice measurement. One earlier successful call encountered
a harness serialization error before its usage was saved; it is additional unmetered
spike cost. The harness was corrected to serialize the validated immutable answers
explicitly. Its failure was not a TypeSafe service error.

The registered key was read from the main worktree's explicitly authorized environment
file for the evaluation process. It was not persisted in this worktree or sent to a
reviewer. No production credential precedence or feature enrollment changed.

### TypeSafe preserves the observed failure mechanisms while pruning context

| Condition          | Known defects found | Alerts on clean controls | Reviewer input tokens | Cached input, included | Output tokens | Reviewer seconds | Ranking seconds |
| ------------------ | ------------------: | -----------------------: | --------------------: | ---------------------: | ------------: | ---------------: | --------------: |
| Full context       |                 3/3 |                      0/3 |               125,190 |                 24,064 |         1,295 |           58.018 |               0 |
| Lexical top three  |                 2/3 |                      0/3 |               166,604 |                 88,064 |         1,653 |           78.854 |               0 |
| TypeSafe top three |                 3/3 |                      0/3 |               102,654 |                 36,096 |         1,026 |           51.678 |           1.995 |

TypeSafe retained the preidentified key passage in all six top-three selections; lexical
selection retained it in four. On the MCP regression, the lexical reviewer suggested
restoring the type check but explained a hypothetical unrelated class with the same name.
It did not identify the actual `_LeanToolServer` rejection. This is counted as an
off-target mechanism rather than a detected historical defect. The author adjudicated
the explanations against the confirmed failures; no independent grader was used.

All methods produced no findings on the corrected controls. Both full and TypeSafe
context produced the actual failure mechanism for each regression. The lexical result
shows a possible benefit beyond blindly reducing the amount of text, but this is a
simple lexical baseline, not a comparison against a tuned retriever.

### Latency and tool-use conclusions are limited

Assisted reviewer input fell 18.0 percent; supplied prompt bytes fell 56.8 percent.
Reviewer output fell 20.8 percent. These token counts include the CLI harness and, when
present, multiple model turns. Cached input is a subset, not an additional token total.
The separate TypeSafe usage must also be counted when considering cost. The reviewer
CLI uses account authentication and exposes no actual dollar charge, so a total-dollar
saving cannot be established.

Adding measured ranking time to reviewer time gives 53.673 seconds for TypeSafe versus
58.018 seconds for full context, a 7.5 percent aggregate reduction. Median per-case time
including ranking is 9.109 seconds versus 8.654 seconds for full context, slightly
slower. The slow full-context ledger control drives the aggregate difference. With one
observation per condition and varying cache state, this is not evidence of a reliable
latency improvement.

Every reviewer emitted zero tool calls. Optional local reads were allowed but unused.
Some emitted an intention to inspect context without a tool event; intention was not
counted as execution. The experiment therefore measures prompt selection and static
finding quality, not fewer tool calls, shared-test coordination, or cheaper test runs.

### Next experiment should test candidate discovery and harder omissions

The three bug families are a small convenience sample. Controls share code with the
regressions, reversed fixes expose useful base behavior, and the source pool was selected
by the author. These conditions limit recall and workflow-efficiency claims. The stable
model alias also means a later run may use a different provider-resolved release.

The useful follow-on is an opt-in context selector fed by actual discovery results on
unseen diffs, with repeated comparisons against both ordinary agent discovery and a
stronger deterministic shortlist. Include cross-file defects and cases where the needed
evidence never entered the pool. Measure abstention, fallback reading, and omissions;
do not tune thresholds on these six cases and call them held out.

The findings do not justify model-controlled check ownership, evidence freshness,
completion, or PASS decisions. Those remain deterministic or agent-owned under the
existing review contract. No production backend or bundled instructions were changed
by this spike.

### Validation

All six historical/control labels were confirmed independently of model answers. All
six recorded hosted ranking requests and eighteen reviewer runs completed. The runner
passes Ruff lint and formatting, the project's type check, and the eighteen precommit
repository guards. Markdown and vault record checks cover the persisted evidence.
Resuming the same eighteen reviews performed no new model calls; changing the model
refused reuse before invocation. Raw CLI events contain only agent-message items,
confirming the reported zero tool calls. The existing reference edits were preserved.

## Sources

- `dev/experiments/review_context_spike.py`: fixture construction, independent label
  checks, score questions, explicit live calls, and isolated reviewer runner.
- `dev/experiments/review_context_results.json`: all eighteen answers, judgments,
  aggregate and per-run usage, timings, and adjudication.
- Git fixes `8373e597`, `0cadfc9b`, and `066eee76`; source snapshot
  `2fb7779276e693d0a2a8c8784336d25a54fe8c0b`.
- `https://docs.typesafe.ai/api`: current request, answer, and usage contracts.
- `https://docs.typesafe.ai/primitives/score`: comparable, concrete ordered criteria.
- `https://docs.typesafe.ai/cookbooks/rerank_typesafe`: candidate reranking pattern;
  its published legal-data results are not evidence for code-review accuracy.
- `https://typesafe.ai/blog/introducing-system-one-models-and-jev`: published input
  price and free output-token pricing, read on 2026-09-25.
- `https://developers.openai.com/codex/noninteractive`: structured CLI evaluation
  output, supplemented by the installed CLI's help.

## Production command smoke

On 2026-09-25 the implemented `review context` command was exercised against the historical factory fix at `0cadfc9b`, with its parent as base. Candidate locators were `src/vaultspec_core/mcp_server/app.py:75-104`, `src/vaultspec_core/mcp_server/app.py:166-199`, and `dev/smoke/smoke_check.py:98-105`. The registered key was supplied only in the child process environment; the production command used its normal credential resolver.

The final payload returned the two factory passages in one request: 1,879 input tokens, 46 output tokens, 589.76 ms hosted time and 1,061.58 ms service time including local collection. An earlier wiring call included redundant content hashes in hosted state and used 2,109 input tokens; removing that unused metadata saved 230 input tokens on the same three candidates. Both live calls together used 3,988 input and 92 output tokens. The identical-input invocation with `--previous` reported `reused`, made zero requests and consumed zero hosted tokens. Clearing the process key, while supplying the same previous result, reported `not_configured`, made zero requests and restored discovery order. These smoke observations establish wiring and optionality, not a general latency or review-quality improvement.

The focused production suite passed 71 tests covering real Git collection, committed versus dirty sources, private-path exclusion, bounded input, provider rejection and timeout, cache invalidation, the MCP gateway and generated CLI references. Initial discovery for this implementation used targeted local reads after the configured semantic search tool failed.
