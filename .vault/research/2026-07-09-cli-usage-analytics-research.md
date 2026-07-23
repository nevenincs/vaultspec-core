---
tags:
  - '#research'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
related: []
---

# `cli-usage-analytics` research: transcript tool-call analytics grounding

## 1. Scope and intent

This research grounds a dev-only, never-shipped analytics module at repo-root `statistic/` (sibling to `src/`, `tests/`, `docs/`, `scripts/`). It reads the two agent-CLI transcript corpora on this machine - Claude Code under `~/.claude/projects/` and Codex under `~/.codex/` - filters to vaultspec-core CLI invocations and vaultspec MCP tool calls, and produces statistics that empirically ground the upcoming MCP-server overhaul: which verbs are actually exercised, which declared capabilities are dead, where invocations miss, and what each command class costs in tokens and turns.

The packaging exclusion is confirmed. `pyproject.toml` line 100 declares `[tool.hatch.build.targets.wheel] packages = ["src/vaultspec_core"]`, so any top-level `statistic/` directory is inherently outside the wheel. Nothing further is needed to keep it unshipped; the residual risk is purely its generated report outputs, which mine personal data and must be gitignored (Section 5).

The window is fixed: analyze only transcripts with activity timestamp `>= 2026-06-09` (30 days before today, 2026-07-09). Older data predates version drift and is out of scope. Windowing is by transcript activity timestamp, not file mtime (Section 5).

## 2. The two transcript schemas

Both corpora were sampled from real, in-window files. Claude: `~/.claude/projects/<project-slug>/abaaaa78-13f1-41f1-8f8b-58cb53624e82.jsonl` plus a recent 80-file scan across all 47 project dirs (~5052 files). Codex: `~/.codex/sessions/2026/07/07/rollout-2026-07-07T09-34-45-...jsonl` plus `history.jsonl` and `session_index.jsonl`.

### 2.1 Claude Code (`.claude/projects/<project-slug>/*.jsonl`)

One JSON object per line. There are 47 project-slug directories; a slug is the workspace path with separators replaced by `-` (for example `Y--code-vaultspec-core-worktrees-feature-mcp`). The first line of a session file is a small session header carrying none of the per-turn fields, so parsers must skip non-conforming lines rather than assume field presence.

Per-turn lines carry these top-level fields: `timestamp` (ISO8601 Z, for example `2026-07-09T11:33:13.474Z`), `cwd`, `gitBranch`, `sessionId`, `version` (the Claude CLI version), `uuid`, `parentUuid`, `isSidechain`, `userType`, and `type` (`assistant` or `user`).

An assistant tool call is a line whose `message.content[]` array contains an entry `{"type":"tool_use","id":"toolu_...","name":<Tool>,"input":{...}}`. The same line's `message.model` gives the model and `message.usage` gives token cost as a rich object: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, plus nested `iterations[]`. This usage is per assistant message, not per tool call, so token attribution to a specific vaultspec-core invocation is approximate when a message emits multiple tool calls.

A vaultspec-core call is a `tool_use` where `name` is a shell tool - in practice both `Bash` and `PowerShell` are used heavily (7701 `Bash` vs 652 `PowerShell` in the recent scan) - and `input.command` contains the string `vaultspec-core`. `input.description` is a short human label. Crucially, the command is almost never a bare invocation. Of 1170 vaultspec-core commands in the scan, 361 (~31%) were multi-line, and the dominant shape is `cd "<path>" && uv run --no-sync vaultspec-core <args> [2>&1 | head ...]`. Explicit `-t`/`--target` is rare (11 occurrences) because operators `cd` into the worktree instead; the effective target is therefore usually the `cd` path or the line's `cwd`, not a flag. `--json` appeared 106 times.

The result of a call is a separate line, `type:"user"`, whose `message.content[]` holds `{"type":"tool_result","tool_use_id":"toolu_...","content":<str>,"is_error":<bool?>}`. Linkage is by `tool_use_id` matching the call's `id` (also reachable via `parentUuid`). There is no numeric exit code; success/failure is signalled by the `is_error` flag (766 error results in the 80-file scan) and by parsing the `content` text. Result `content` is ANSI-colored and Windows-CRLF, and frequently contains non-fatal `.venv` noise (a recurring `distutils-precedence.pth` traceback printed to stderr by `uv run`) that must not be misread as a vaultspec-core failure. This makes exit-status inference the single hardest parsing problem on the Claude side.

Subagent transcripts live under `<project-slug>/subagents/agent-*.jsonl` with the same line schema. They must be included and attributed distinctly from parent turns.

### 2.2 Codex (`.codex/`)

Two sources. `history.jsonl` is a flat prompt log, one object per line `{"session_id","ts":<unix int>,"text":<user prompt>}` - useful only for prompt-side context, not tool calls. The tractable, rich source is the rollouts: `sessions/<yyyy>/<mm>/<dd>/rollout-<ISO>-<uuid>.jsonl` (and `archived_sessions/rollout-*.jsonl`), indexed by `session_index.jsonl` (`{"id","thread_name","updated_at"}`).

A rollout is one JSON object per line with top-level `{"timestamp","type","payload"}`. Verified line-type distribution on the sample: `session_meta:1, turn_context:1, event_msg:34, response_item:117`. Semantics:

| Line `type`                                             | `payload` shape                                                                                                                                                                                    | What it gives the analyzer                                                                                                                            |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `session_meta`                                          | `session_id`, `cwd`, `originator`, `cli_version`, `source.subagent{...}`, `thread_source`, `agent_role`, `agent_nickname`, `model_provider`                                                        | Session identity, project (`cwd`), Codex version, and whether this is a subagent (`thread_source:"subagent"`, `agent_role:"vaultspec-code-reviewer"`) |
| `turn_context`                                          | `turn_id`, `cwd`, `current_date`, `model` (`gpt-5.5`), `approval_policy`, `sandbox_policy`                                                                                                         | Per-turn model and cwd                                                                                                                                |
| `event_msg` (`payload.type:"token_count"`)              | `info.total_token_usage{input,cached_input,output,reasoning,total}`, `model_context_window`, `rate_limits`                                                                                         | Cumulative token usage snapshots; cost is a running total, not per-call                                                                               |
| `response_item` (`payload.type:"function_call"`)        | `name` (`shell_command` in current builds - note this differs from the `shell`/`local_shell` in older docs), `arguments` (a JSON string to parse: `{"command","workdir","timeout_ms"}`), `call_id` | The tool call and the command                                                                                                                         |
| `response_item` (`payload.type:"function_call_output"`) | `call_id`, `output` (text starting `Exit code: N\nWall time: ...\nOutput:\n...`)                                                                                                                   | The result, linked by `call_id`, with an explicit numeric exit code                                                                                   |
| `response_item` (`message`, `reasoning`)                | assistant/user text, reasoning                                                                                                                                                                     | Narrative context                                                                                                                                     |

A vaultspec-core call on the Codex side is a `function_call` whose parsed `arguments.command` contains `vaultspec-core`; the same command shapes apply. Its result is the paired `function_call_output` matched on `call_id`, and unlike Claude it carries a real `Exit code:` line - the cleaner exit-status signal of the two.

### 2.3 Schema differences (cross-tool normalization surface)

| Concern          | Claude                                                       | Codex                                                                 |
| ---------------- | ------------------------------------------------------------ | --------------------------------------------------------------------- |
| Call marker      | `content[].type == "tool_use"`, `name in {Bash,PowerShell}`  | `payload.type == "function_call"`, `name == "shell_command"`          |
| Command location | `input.command` (native string)                              | `payload.arguments` is a JSON string; parse then read `.command`      |
| Result linkage   | separate `user` line, `tool_result.tool_use_id` == call `id` | separate `function_call_output`, `call_id` == call `call_id`          |
| Exit status      | no exit code; infer from `is_error` + text (venv noise trap) | explicit `Exit code: N` in `output`                                   |
| Timestamp        | per-line `timestamp` (ISO8601 Z)                             | per-line `timestamp` (ISO8601 Z); `history.jsonl` uses unix `ts`      |
| Project/cwd      | per-line `cwd` + `gitBranch`                                 | `session_meta.cwd` / `turn_context.cwd` / arg `workdir`; no gitBranch |
| Model            | `message.model` per assistant line                           | `turn_context.model` per turn                                         |
| Token cost       | `message.usage` per message (attributable per-message)       | `token_count` event, cumulative per session (not per call)            |
| Subagents        | `subagents/agent-*.jsonl`, same schema                       | inline, flagged via `session_meta.source.subagent` / `agent_role`     |
| CLI version      | top-level `version`                                          | `session_meta.cli_version`                                            |

Edge cases to handle for both: `uv run --no-sync` prefix stripping; leading `cd "<path>" &&`; pipes and redirects (`2>&1 | head`, `| Select-Object -First 60`); `for`-loop bodies that invoke vaultspec-core repeatedly (one line, N logical calls); heredocs (`python - <<'PY'`) that are not vaultspec-core calls but contain the string; `-t/--target DIR` vs implicit cwd target; `--json`; and `--help` probes (which should likely be classed separately from real invocations). ANSI escape codes and CRLF must be stripped before text matching.

## 3. Declared-capability baseline (the denominator)

`.vaultspec/reference/cli.md` is the locally-resident ground truth for the full command surface; its command inventory sits between the `vaultspec:generated:begin/end command-inventory` markers and is generator-owned (`vaultspec-core spec reference generate`). Encoding this as the module's ground-truth denominator lets every miss and dead-surface metric be computed against a closed set. The declared surface, as read in full:

Top-level: `install`, `uninstall`, `sync`, `doctor`, `status`.

vault (direct): `set-body`, `set-frontmatter`, `edit`, `rename`, `add`, `stats`, `list`, `graph`, `repair`.
vault feature: `list`, `index`, `archive`, `unarchive`, `rename`.
vault check: `all`, `body-links`, `annotations`, `markdown`, `placeholders`, `dangling`, `orphans`, `frontmatter`, `modified-stamp`, `links`, `features`, `references`, `schema`, `adr-status`, `structure`, `rename-integrity`, `encoding`, `feature-rename-integrity`.
vault sanitize: `annotations`.
vault rule: `promote`.
vault adr: `supersede`.
vault plan: `status`, `check`, `query`; `step {toggle,check,uncheck,add,insert,edit,move,remove}`; `phase {add,insert,edit,move,renumber,remove}`; `wave {add,insert,edit,move,remove}`; `epic intent {show,edit}`; `tier {show,promote,demote}`; `trailer {emit,validate}`.
vault link: `list`, `add`, `remove`.

spec: `doctor`; `rules/skills/agents` each `{list,add,show,edit,remove,rename,sync,restore,status}`; `system {show,sync}`; `hooks {list,add,show,edit,rename,remove,restore,sync,status,run}`; `mcps {list,status,add,remove,sync}`; `reference generate`.

migrations: `status`, `run`. config: `get`, `set`, `unset`, `list`.

Global flags the parser must recognize: `--target/-t`, `--debug/-d`, `--version/-V`, `--help`. Command-scoped flags to canonicalize include the high-signal `--feature/-f TAG`, `--json`, `--dry-run`, `--force`, `--fix`, `--tier`, `--step`, `--all-steps`, `--limit`, `--since`. Exit codes are non-uniform and matter for the miss metric: `vault check`/`plan check` return `1` on findings (an expected non-zero, not a usage error); `spec doctor` uses `0/1/2` (ok/warnings/errors); `migrations status` returns `1` when migrations are pending. The module must not conflate "check found issues" (exit 1 by design) with "invocation was malformed."

The module should encode this inventory as a static, versioned table (verb -> valid subcommands -> valid flags), regenerable from `cli.md`, so the analyzer can classify any observed token stream as declared-and-used, declared-but-unused (dead), or undeclared (a miss).

## 4. Metric taxonomy

Each metric names the exact transcript signal it reads, so the ADR can spec data structures directly. All operate on a normalized `CallRecord` stream (Section 6) unified across both tools.

| #   | Metric                            | Definition                                                                                    | Signal read                                                                                                                                                                                                                                                                                                                                                                                                             |
| --- | --------------------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| a   | Command/subcommand hotspots       | Frequency of each `(verb, subcommand)` leaf                                                   | Parsed command tokens after stripping `uv run --no-sync`/`cd`/pipes; counted per CallRecord                                                                                                                                                                                                                                                                                                                             |
| b   | Command+flag n-grams              | Repeated full patterns, for example `vault add exec --feature X --step Y`; flag co-occurrence | Canonical flag set per CallRecord; n-gram over the normalized token sequence                                                                                                                                                                                                                                                                                                                                            |
| c   | Features utilized                 | Which vaultspec verbs are actually exercised at all                                           | Distinct `(verb, subcommand)` present in the CallRecord set, intersected with the Section 3 inventory                                                                                                                                                                                                                                                                                                                   |
| d   | Feature-tag usage                 | Distribution of `--feature <tag>` / `-f <tag>` values                                         | Flag-value extraction of `--feature`/`-f`; also the `cd` worktree name as weak project signal                                                                                                                                                                                                                                                                                                                           |
| e   | Tool-call misses                  | Invocations that errored, used non-existent/wrong flags, or were corrected on retry           | Codex: `Exit code != 0` in `function_call_output` (excluding by-design `1`s from check/doctor/migrations). Claude: `is_error==true` and/or result text patterns (`No such command`, `Usage:`, `Error`), guarding against venv `distutils-precedence.pth` noise. Retry-correction: consecutive same-verb calls where an errored call is followed by a materially different flag set within the same session/parent chain |
| f   | Overuse vs declared capability    | Verbs invoked disproportionately; declared-but-never-used dead surface                        | (a) counts vs the Section 3 denominator; dead surface = inventory minus observed `(verb,subcommand)` set                                                                                                                                                                                                                                                                                                                |
| g   | Token/turn cost per command class | Approx token and turn cost grouped by verb class                                              | Claude: `message.usage` on the calling assistant message (per-message, divided when multiple tool calls share a message). Codex: delta between adjacent `token_count.total_token_usage` snapshots bracketing the call; turns counted as distinct assistant messages / `turn_context` boundaries                                                                                                                         |

For (e) and (f) the by-design non-zero exit codes documented in Section 3 are the critical correctness guard: a `vault check all` that exits `1` is a finding, not a miss. The retry-correction sub-signal is the most valuable and most fragile - it needs the `parentUuid` (Claude) / `turn_id`,`call_id` (Codex) linkage to sequence calls within a session.

## 5. Design constraints and risks

30-day windowing mechanics. The filter is by activity timestamp, not file mtime (mtime is unreliable - archived/copied files, and a session may span days). The tractable approach: for each transcript, scan line `timestamp`s (Claude per-line; Codex per-line, or `history.jsonl` unix `ts`) and admit the file/records only where activity `>= 2026-06-09`. Because files are large, prefer a cheap first-line/last-line timestamp probe to skip wholly-old files before full parse, then filter records individually so a long session contributes only its in-window turns.

Privacy. Transcripts contain personal data, absolute home paths, git branches, and potentially secrets echoed in commands/outputs. The module must: gitignore all generated report outputs; never ship (already guaranteed by the wheel-packages exclusion, Section 1); never write secrets or raw command bodies into committed artifacts; and treat the `statistic/` outputs directory as untracked by default. Consider redaction of home-path prefixes in any shareable report.

Scale and performance. ~5052 Claude files across 47 dirs plus Codex rollouts; individual files reach hundreds of KB. The analyzer must stream line-by-line (never load a whole corpus into memory), skip the 4GB `logs_2.sqlite`, `state_5.sqlite`, and `memories_1.sqlite` entirely (jsonl rollouts are the tractable primary source), and use the window probe to prune before full parse.

Windows path handling. All paths are backslash Windows paths with drive letters; project slugs encode paths with `-`. cwd values appear as `Y:\...` in transcripts but the same worktree may be referenced as `Y:/...` inside `cd "Y:/..."` commands. Normalization must be case-insensitive and separator-agnostic.

Cross-tool normalization. The two schemas (Section 2.3) must collapse into one `CallRecord`. Divergences to reconcile: exit-status source (flag vs numeric), token-cost granularity (per-message vs cumulative-delta), and subagent representation (separate files vs inline meta).

Reproducibility and determinism. As a dev analysis tool feeding an ADR, runs over a frozen corpus must be deterministic: stable ordering, fixed window boundary, no wall-clock-dependent output beyond the window anchor. This also enables real-fixture tests (Section 6).

Downstream use. The output feeds MCP tool-surface design: hotspots (a) and n-grams (b) suggest which verbs deserve first-class MCP tools; misses (e) reveal ergonomic gaps the MCP surface should eliminate; dead surface (f) flags candidates to omit; cost (g) informs which operations benefit most from a single MCP round-trip versus shelling out.

## 6. Open architecture questions for the ADR

- Module layout under `statistic/`. Package structure (parsers / normalization / metrics / report), and CLI entrypoint vs importable library vs both. Is there a single `python -m statistic ...` run command?
- Normalized `CallRecord` schema. The unified record: fields for tool source, session id, timestamp, cwd/project, git branch (nullable for Codex), verb, subcommand, canonical flags plus values, `--feature` tag, raw-command hash (not raw command, for privacy), exit status (normalized across flag/numeric), token cost, subagent role, retry-linkage key. Pydantic (already a dep) vs stdlib `dataclass`.
- Parser abstraction across the two tools. A common `TranscriptSource` interface with Claude and Codex adapters emitting `CallRecord`s, versus two independent pipelines. How to encode the exit-status divergence and the venv-noise guard once.
- Shell-command tokenizer. How deeply to parse compound/piped/looped/heredoc commands to isolate the real vaultspec-core invocation(s) - a full shell-aware tokenizer vs a pragmatic regex-plus-splitter, and how to handle one line that fires N calls in a `for` loop.
- Declared-capability encoding. How the Section 3 inventory is stored and kept in sync with `cli.md` (hand-encoded table vs parsed from the generated markers), and how strictly to validate observed flags against it.
- Output formats. JSON (machine, for the ADR to cite) and/or a human Markdown report; where outputs land under `statistic/` and how they are gitignored.
- Dependency posture. Stdlib-only (`json`, `re`, `pathlib`, `collections`) versus pulling `pandas`/`polars` for the aggregation. Project convention favors a light footprint; `pandas` is not a current dependency.
- Testing strategy. Real fixture transcripts (small, redacted, committed) with zero mocks/stubs/skips per project standard; `ty` for typing, `prek`/`ruff` for lint; whether fixtures live under `statistic/tests/` or the repo `tests/` tree, and how to assert against the real filesystem without depending on the operator's personal `~/.claude` and `~/.codex`.
- Cost-attribution model. How to define per-call token cost given Claude's per-message usage and Codex's cumulative snapshots - accept per-message granularity, or attempt delta-based per-call estimation.

## 7. Sources

Files read for grounding: `.vaultspec/reference/cli.md`; `pyproject.toml`; `~/.claude/projects/<project-slug>/abaaaa78-13f1-41f1-8f8b-58cb53624e82.jsonl` plus an 80-file recent-scan across all 47 `~/.claude/projects/*` dirs and their `subagents/`; `~/.codex/` root listing, `history.jsonl`, `session_index.jsonl`, and `sessions/2026/07/07/rollout-2026-07-07T09-34-45-...jsonl`.
