---
tags:
  - '#plan'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-09'
tier: L2
related:
  - '[[2026-07-09-cli-usage-analytics-adr]]'
  - '[[2026-07-09-cli-usage-analytics-research]]'
---

# `cli-usage-analytics` plan

Build the dev-only `statistic/` transcript analytics module that empirically grounds the MCP-server overhaul.

## Description

This plan implements the accepted `cli-usage-analytics` ADR: a dev-only, never-shipped package at repo-root `statistic/` that normalizes the two agent-CLI transcript corpora (Claude Code project JSONL and Codex rollout sessions) into one comparable `CallRecord` stream and produces the seven required metric families. The package is structurally unshippable because the hatchling wheel packages `src/vaultspec_core` exclusively, so `statistic/` sits outside it by construction.

The work decomposes into five phases. `P01` lays the package skeleton and the shared contracts every later phase imports: the Pydantic `CallRecord` model, the four-value exit-status enum, and the `TranscriptSource` protocol. `P02` parses the declared-capability denominator from the `vaultspec:generated` markers in `.vaultspec/reference/cli.md`, giving every dead-surface and miss metric a closed ground-truth set. `P03` builds the two-stage normalizer (strip and mask, split and unroll, then `shlex` argv extraction into a canonical `CallRecord`). `P04` implements the `ClaudeSource` and `CodexSource` adapters against committed redacted fixture trees, each owning its own linkage, exit-status derivation, and cost attribution. `P05` implements the seven metric families as pure functions, the `records.jsonl` and `report.md` renderers, the `python -m statistic` entrypoint, and a real end-to-end run over the operator's in-window corpus.

Every module carries Google-style docstrings with Sphinx cross-references, passes `ty` type checking and `prek`/`ruff` lint, and depends on stdlib plus Pydantic only. Tests run entirely against committed redacted fixtures under `tests/statistic/fixtures/` with exact-value assertions and zero mocks, stubs, or skips. The activity window is fixed at timestamps at or after `2026-06-09`, filtered on transcript activity timestamps and never file mtime. Generated outputs land in gitignored `statistic/out/` and carry only aggregates, hashes, and verb paths, never raw command bodies.

Recommended executors: `P01` and `P02` steps suit `vaultspec-standard-executor`; the tokenizer, adapter, and metric-logic steps in `P03`, `P04`, and `P05` carry the core logic and suit `vaultspec-high-executor`; fixture-authoring and gitignore steps suit `vaultspec-low-executor`.

## Steps

### Phase `P01` - Skeleton and contracts

Scaffold the statistic package tree and the shared CallRecord model, exit-status enum, and TranscriptSource protocol that every later phase imports.

- [x] `P01.S01` - Scaffold the statistic package tree with an __init__.py for the root package and each of the parsers, normalize, metrics, and report subpackages; `statistic/__init__.py, statistic/parsers/__init__.py, statistic/normalize/__init__.py, statistic/metrics/__init__.py, statistic/report/__init__.py`.
- [x] `P01.S02` - Define the CallRecord Pydantic model at the normalization boundary with every field the ADR schema mandates; `statistic/normalize/models.py`.
- [x] `P01.S03` - Define the four-value ExitStatus enum (ok, findings, error, unknown); `statistic/normalize/exit_status.py`.
- [x] `P01.S04` - Define the TranscriptSource protocol with iter_sessions and iter_calls; `statistic/parsers/base.py`.
- [x] `P01.S05` - Add the statistic/out/ gitignore entry and a regression test confirming the built wheel excludes statistic/; `.gitignore, tests/statistic/test_packaging_exclusion.py`.

### Phase `P02` - Declared-capability denominator

Parse the cli.md generated-marker inventory into the verb-path and flag ground-truth set that dead-surface and miss metrics measure against.

- [x] `P02.S06` - Implement the capability parser that reads the cli.md vaultspec:generated command-inventory markers into a verb-path and declared-flag ground-truth set; `statistic/metrics/capability.py`.
- [x] `P02.S07` - Commit a redacted cli.md marker fixture and assert the capability parser produces the exact verb-path and flag denominator; `tests/statistic/fixtures/cli_reference.md, tests/statistic/test_capability.py`.

### Phase `P03` - Normalization

Build the two-stage command tokenizer and extractor that turn a raw command string into a canonical CallRecord.

- [x] `P03.S08` - Implement the stage-one tokenizer that strips ANSI and CRLF, masks heredoc bodies, splits on shell connectors, and unrolls single-line for loops into N logical segments; `statistic/normalize/tokenize.py`.
- [x] `P03.S09` - Implement the stage-two extractor that shlex-parses each segment, strips cd and uv-run wrappers and trailing pipes, canonicalizes flags and the feature tag, computes the SHA-256 command hash, and constructs a CallRecord; `statistic/normalize/extract.py`.
- [x] `P03.S10` - Add normalization edge-case tests covering multi-line commands, for-loop unroll, heredoc false positives, wrapper and pipe stripping, flag canonicalization, and command hashing; `tests/statistic/test_normalize.py`.

### Phase `P04` - Source adapters

Implement the ClaudeSource and CodexSource adapters against committed redacted fixture trees, each owning its own linkage, exit-status derivation, and cost attribution.

- [x] `P04.S11` - Implement the ClaudeSource adapter: discover project and subagent session files, apply the per-line 30-day window filter, link tool_use to tool_result, infer exit status from is_error plus result text with the distutils-precedence.pth venv-noise guard, and attribute per-message token cost; `statistic/parsers/claude.py`.
- [x] `P04.S12` - Implement the CodexSource adapter: discover rollout and archived sessions via session_index.jsonl, apply the per-line window filter, decode JSON-string function_call arguments, link function_call to function_call_output by call_id, extract the numeric Exit code, and derive token cost from cumulative snapshot deltas; `statistic/parsers/codex.py`.
- [x] `P04.S13` - Commit a synthetic redacted Claude project fixture tree exercising every schema edge and assert ClaudeSource record counts, hashes, exit statuses, and subagent attribution; `tests/statistic/fixtures/claude, tests/statistic/test_claude_source.py`.
- [x] `P04.S14` - Commit a synthetic redacted Codex session fixture tree exercising every schema edge and assert CodexSource record counts, hashes, exit codes, and token-delta costs; `tests/statistic/fixtures/codex, tests/statistic/test_codex_source.py`.

### Phase `P05` - Metrics, report, and entrypoint

Implement the seven metric families as pure functions, the records.jsonl and report.md renderers, the python -m statistic entrypoint, and a real end-to-end run over the operator corpus.

- [x] `P05.S15` - Implement the verb-hotspots metric as a pure function counting each (verb, subcommand) leaf over the CallRecord stream; `statistic/metrics/hotspots.py, tests/statistic/test_metrics.py`.
- [x] `P05.S16` - Implement the command-and-flag n-gram metric as a pure function over the canonical flag and token sequence; `statistic/metrics/ngrams.py, tests/statistic/test_metrics.py`.
- [x] `P05.S17` - Implement the features-utilized metric as a pure function intersecting distinct (verb, subcommand) pairs with the capability inventory; `statistic/metrics/features.py, tests/statistic/test_metrics.py`.
- [x] `P05.S18` - Implement the feature-tag-usage metric as a pure function distributing --feature and -f values; `statistic/metrics/feature_tags.py, tests/statistic/test_metrics.py`.
- [x] `P05.S19` - Implement the tool-call-misses metric as a pure function sequencing records by retry_key to separate corrected retries and genuine misses from by-design non-zero exits; `statistic/metrics/misses.py, tests/statistic/test_metrics.py`.
- [x] `P05.S20` - Implement the overuse-and-dead-surface metric as a pure function comparing observed counts against the declared-capability denominator; `statistic/metrics/surface.py, tests/statistic/test_metrics.py`.
- [x] `P05.S21` - Implement the token-and-turn-cost-per-class metric as a pure function grouping cost by verb class; `statistic/metrics/cost.py, tests/statistic/test_metrics.py`.
- [x] `P05.S22` - Implement the report renderers writing records.jsonl as the full CallRecord stream and report.md as the seven metric families, both aggregates and hashes only with no raw command bodies; `statistic/report/render.py, tests/statistic/test_report.py`.
- [x] `P05.S23` - Implement the python -m statistic entrypoint wiring source discovery, normalization, metrics, and report rendering into the full pipeline; `statistic/__main__.py, tests/statistic/test_main.py`.
- [ ] `P05.S24` - Run python -m statistic over the operator in-window corpus and verify it emits the real records.jsonl and report.md into gitignored statistic/out/; `statistic/out/records.jsonl, statistic/out/report.md`.

## Parallelization

`P01` is a hard prerequisite for every other phase: it defines the `CallRecord` model, the exit-status enum, and the `TranscriptSource` protocol that `P02` through `P05` all import, so nothing may begin until `P01` lands. Once `P01` is complete, `P02` (capability denominator) and `P03` (normalization) are mutually independent and may run concurrently, and both are largely independent of `P04` (source adapters) except that `P04` consumes the `CallRecord` construction delivered by `P03`, so `P04` should follow `P03`. `P05` is the integration phase and depends on `P02`, `P03`, and `P04` all being complete: the metric families join the denominator from `P02`, the adapters from `P04` feed the record stream, and the normalizer from `P03` underlies both. Within `P05`, the seven metric-family steps (`P05.S15` through `P05.S21`) share no interdependency and may be executed in parallel; the report renderer, entrypoint, and end-to-end run steps (`P05.S22` through `P05.S24`) are sequential and must follow the metric steps.

## Verification

The plan is complete when every Step is closed (`- [x]`). Success criteria, each independently verifiable:

- `python -m statistic` runs the full pipeline end to end and writes both `statistic/out/records.jsonl` and `statistic/out/report.md` over the operator's in-window corpus.
- `report.md` and `records.jsonl` contain only aggregates, hashes, and verb paths, with no raw command bodies, secrets, or personal paths.
- The full `statistic/` and `tests/statistic/` test suite passes with real committed fixtures and zero mocks, stubs, or skips.
- `ty` type checking and `prek`/`ruff` lint pass clean over `statistic/` and `tests/statistic/`.
- A packaging test confirms the built wheel excludes `statistic/`, and `statistic/out/` is gitignored.
- By-design non-zero exits (`vault check` and `plan check` findings, `spec doctor` 1/2, `migrations status` pending) map to exit status `findings`, and the Claude `distutils-precedence.pth` venv noise never inflates the miss rate, both asserted by fixture tests.
- The declared-capability denominator is parsed live from the `vaultspec:generated` markers in `.vaultspec/reference/cli.md` and matches the fixture ground-truth set.
