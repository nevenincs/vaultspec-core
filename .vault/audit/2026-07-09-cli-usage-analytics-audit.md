---
tags:
  - '#audit'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-09'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# `cli-usage-analytics` audit: `dev-only transcript analytics module`

## Scope

Full review of the `statistic/` dev package and `tests/statistic/` added this session (diff `23a76f2..HEAD`), plus the `.gitignore` and `pyproject.toml` edits, against the accepted ADR and plan. Audited for the operator's non-negotiable no-committed-personal-metadata constraint, correctness of the tokenizer/adapters/metrics, privacy of stored data, test integrity, and project standards. Tooling verified live: `ruff check` clean, `ty check` clean, 64/64 tests pass with zero mocks/skips. Relevant files: `statistic/normalize/tokenize.py`, `statistic/normalize/extract.py`, `statistic/normalize/models.py`, `statistic/parsers/claude.py`, `statistic/parsers/codex.py`, `statistic/metrics/*.py`, `statistic/report/render.py`, `statistic/__main__.py`, `tests/statistic/*`.

## Findings

### committed-metadata-clean | none | The operator's non-negotiable constraint is fully satisfied

A tree-wide search for drive letters, home-path prefixes, ISO calendar dates, and real usernames returns nothing in `statistic/` and only synthetic redaction fixtures in tests (an invented `redact_home` sample, not a real path). Roots are injected constructor params with `Path.home()`-derived defaults; the window is `window_days`-parameterized with the cutoff computed at runtime from `datetime.now(tz=UTC)`; no baked-in date exists anywhere. `statistic/out/` is gitignored and untracked. Raw command bodies are never stored on `CallRecord` (only `command_hash`, a SHA-256) and never written to any artifact. This is the load-bearing requirement and it holds.

### records-jsonl-cwd-unredacted | medium | `records.jsonl` serializes raw `cwd`/`project` paths, contradicting the plan's own verification criterion

`CallRecord` carries `cwd` and `project`, and `write_records_jsonl` emits `model_dump_json()`, so the full raw working-directory path (on a real run, a home-rooted personal path) lands in `statistic/out/records.jsonl`. The plan's Verification section asserts `records.jsonl` contains no personal paths, yet `cwd` is a personal path serialized verbatim. This is not a committed leak (`out/` is gitignored, and the ADR permits personal paths in gitignored generated output), so it does not violate the non-negotiable, but it is a real spec-vs-implementation inconsistency. The defensive `redact_home` helper is applied nowhere. Fix: drop `cwd`/`project` from the serialized record, or route them through `redact_home` at serialization.

### connector-inside-quotes-drops-record | medium | A shell connector char inside a quoted argument silently drops the whole invocation

Stage-one splits on `&&`/`||`/`;`/newline/`|` with no quote-awareness, so a quoted argument containing one of those is cut mid-quote; the segment has an unbalanced quote, `shlex.split` raises, and the segment is dropped. Reproduced: `vault add adr --feature x --title "one; two | three"` yields 0 records instead of 1. This silent undercount contradicts the ADR guarantee that pathological shapes surface as `unknown` status rather than silent misclassification. Likelihood is bounded (vaultspec-core args rarely embed these chars in quotes). Fix: mask quoted spans before the connector split, or emit an `unknown`-status record when a segment mentioning the executable fails to tokenize.

### for-loop-token-cost-multiplied | medium | Per-call token cost is duplicated across for-loop iterations, over-attributing cost N-fold

Claude divides a message's `usage` by the number of `tool_use` entries, not the number of expanded logical records. A single `tool_use` carrying a `for` loop is one call but `extract_records` returns N records, each stamped with the full per-call cost. Reproduced: a 300-token message produces three records at 300 each = 900, a 3x over-count. The Codex bracket-delta has the same shape. Cost is directional-by-design, but this is an avoidable systematic inflation of metric (g) on exactly the multi-call shapes the module cares about. Fix: divide the per-message/bracket cost by the count of expanded records, or attribute cost once per physical call and mark loop siblings unattributed.

### retry-sequencing-not-by-retry-key | low | Miss detection sequences by session+timestamp, not by the `retry_key` field the ADR/plan specify

The plan states miss detection sequences by `retry_key`, but `_retry_corrections` groups by `session_id` and orders by `timestamp`; `retry_key` is populated yet consumed nowhere downstream. This is arguably the better choice (Codex `retry_key` is the per-call-unique `call_id`, against which literal sequencing is meaningless), so it reads as a sound deviation rather than a bug, but it is an unflagged departure from the written plan and leaves `retry_key` an effectively dead field. Recommend genuinely keying the Claude-side sequence off `parentUuid` chains, or noting the deviation.

### per-call-cost-integer-truncation | low | Even token split discards remainder tokens

`_per_call_cost` uses integer floor division, so 100 tokens across 3 calls attributes 99, losing 1. Negligible and consistent with directional cost; noted for completeness.

### subagent-role-dead-branch | low | The `is_subagent` guard in Codex `_subagent_role` is redundant

`_subagent_role` returns the role whenever it is a string regardless of the `is_subagent` computation, so the `thread_source`/`source.subagent` detection never changes the result. Harmless; remove the dead guard or make the non-subagent path return `None` if that was the intent.

### standards-and-tests | none | Standards and test integrity are met

`ty` and `ruff` pass clean; docstrings are Google-style with Sphinx cross-refs; dependencies are stdlib plus Pydantic only (no pandas); style matches `src/vaultspec_core/`. Tests use synthetic real-filesystem fixtures via `tempfile.TemporaryDirectory`, zero mocks/stubs/skips, exact-value assertions. The pre-existing `tests/_windows_temp_compat.py` bug (calls `make_numbered_dir_with_cleanup()` without the `register` kwarg pytest 9.1.1 requires) is confirmed genuinely pre-existing (untouched by this diff) and out of scope. The P04/P05 deviation from the ADR committed-static-fixture choice (fixtures built at test time as `now - timedelta` to avoid a hardcoded date) is sound: it is the only way to satisfy both the deterministic-window assertion and the no-baked-in-date rule, with generous 2-day/45-day margins, and is not a mock.

## Recommendations

Status: PASS - no critical or high findings; the module is safe to merge. The operator's non-negotiable constraint is fully and verifiably met, the packaging exclusion is structural and tested, and the pipeline runs clean under `ruff`/`ty` with a green, mock-free suite.

Three medium items are worth addressing before this instrument's output is trusted for the MCP-overhaul decision, though none block the merge: redact or drop `cwd`/`project` in `records.jsonl` so the artifact matches the plan's stated no-personal-paths contract; make the connector split quote-aware, or emit an `unknown`-status record instead of silently dropping a segment `shlex` cannot tokenize; and divide for-loop token cost across expanded records rather than duplicating it. The two low drift/dead-code items can be cleaned up opportunistically. Because these are correctness refinements on a dev-only, never-shipped analysis instrument, not safety, crash, or committed-privacy issues, they are fix-recommended, not fix-required.
