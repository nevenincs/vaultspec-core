# Review context experiment

`review_context_spike.py` compares full context, a deterministic lexical shortlist, and
a TypeSafe shortlist for static code review. Each condition uses the same reviewer
model, effort, target code, diff, instructions, and candidate pool. The shortlisted
conditions receive three of twelve passages; every reviewer may read omitted passages
locally.

The six cases replay three historical defects and their corrected controls. Git supplies
the frozen source definitions. `verify` exercises the historical ledger and smoke-check
implementations and checks the acquisition paths to establish the labels independently
of model answers. Expected findings never enter a model prompt.

Run from the repository with its Python environment:

```sh
python -m dev.experiments.review_context_spike build
python -m dev.experiments.review_context_spike verify
python -m dev.experiments.review_context_spike rank
python -m dev.experiments.review_context_spike review --model gpt-6-sol --effort low
```

Ranking uses the existing credential resolver and `TypeSafeModel.JEV`. An explicit
`--credential-file PATH` may supply `VAULTSPEC_CORE_TYPESAFE_API_KEY` when this
workspace has none. The key is never copied to a result or reviewer environment. Ranking
makes one request per case, with twelve independent Score questions and a fifteen-second
deadline. Unavailable rankings fall back to lexical selection and retain the failure
status.

Review requires the Codex CLI and its existing authentication. It runs solo, read-only
sessions outside the repository, with user configuration disabled and no framework skill
invocation. Only local context reads are permitted by the experiment prompt. Tests and
network tools are excluded equally from every condition. Raw CLI events retain reported
usage; the runner counts completed command, MCP, and search tool events.

Results default to ignored `dev/statistics/out/review-context/`. Use `--output PATH` on
each stage to keep repeats separate. A completed review with matching model, effort, and
prompt is reused; differing or failed results require another output directory.
`--limit N` bounds the review stage to the first N entries in its fixed shuffled order.
The runner retains temporary reviewer directories and result logs for inspection.

`review_context_results.json` contains the measured runs, rankings, usage, findings,
oracle results, and author adjudication. Token counts come from the providers; cached
input is included in total input. TypeSafe dollar estimates use its published input
rate, not an account invoice. The authenticated reviewer CLI does not expose dollar
billing.

This is a small context-selection experiment. It does not measure repository discovery,
test scheduling, production review reliability, or general defect recall. A historical
fix and its reversed regression are related observations. Read the limitations and
per-run findings before using the aggregate figures.
