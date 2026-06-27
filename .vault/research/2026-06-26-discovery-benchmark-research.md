---
tags:
  - '#research'
  - '#discovery-benchmark'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-26-discovery-benchmark-reference]]'
  - '[[2026-06-26-rag-pipeline-enrollment-adr]]'
---

# `discovery-benchmark` research: `no-context agent codebase-discovery toolkit`

## Abstract

A controlled, multi-iteration benchmark to determine the combination of tools and the
tool-call sequence that lets a no-context agent discover, and ground an implementation of,
a feature in an unfamiliar codebase at the highest quality, lowest context cost, and
fastest. Approximately 47 agent runs spanning two codebases (a small well-documented
baseline and an 11,188-file production codebase), four probe families, scored on a
human-set weighted rubric (Quality 0.50, Cost 0.25, Speed 0.15, Appropriateness 0.10). The
converged result is a probe-adaptive HYBRID strategy - locate cheaply, read the epicenter
or nearest analogue file whole, then confirm exact symbols with targeted grep - which won
7 of 7 discovery batches and 2 of 3 grounding batches. A directed ADR filter
(`vaultspec-rag search ... --type vault --doc-type adr`) is strictly superior to the
catch-all `--type vault` for decision discovery. Quality converges across strategies on
well-architected code while context cost diverges sharply with codebase size. All
version-sensitive findings were re-validated on the latest semantic-search engine (0.2.25).

## Provenance and honesty disclaimer

This study was conducted agent-to-agent under human supervision, and its findings are
LLM-derived. Specifically:

- **Subjects** under test were fresh language-model agents (Claude Sonnet) given no prior
  context.
- **Ground truth** on the unfamiliar codebase was established by unconstrained
  language-model oracles (Claude Opus), then spot-verified by the orchestrator against the
  cited source via targeted grep - not exhaustively re-derived by a human.
- **Scoring** (quality, appropriateness) was performed by a single supervising
  language-model orchestrator.
- **Human supervision** was continuous and directive: the human set the scope, chose the
  testbeds, set the scoring weights, flagged a tooling-version confound mid-campaign, and
  approved each phase. The human did not independently re-verify every datum.

Consequence: the objective telemetry (context-token cost, tool-call count, wall-clock
duration) is machine-measured and is the most trustworthy layer. The judged layers
(quality, appropriateness) and the self-reported agent testimonials are softer and carry
the trust caveats in the Limitations section. This is engineering decision-support
evidence, not peer-reviewed science; the quantitative scores should be read as directional,
with the objective cost/speed telemetry and the objectively-countable recall/noise
measurements treated as load-bearing.

## Research question

For a no-context agent tasked with discovering a feature implementation (and grounding a
change to it) in an unfamiliar codebase, which combination of discovery tools and which
tool-call sequence yields the highest-quality understanding at the lowest context cost and
fastest, and how does the answer change with codebase scale and with the type of target
(code versus recorded decisions)?

## Methodology

### Roles

- **Subject agents:** fresh Claude Sonnet instances, no prior conversation context, one
  discovery strategy imposed per run by prompt instruction. Each returned a structured
  testimonial (ordered tool trace, time-to-first-signal, breakthrough call, most/least
  valuable tool, friction) plus its answer.
- **Oracle agents:** unconstrained Claude Opus instances, all tools, high thoroughness,
  used only to establish ground truth on the codebase the orchestrator did not know.
- **Orchestrator/scorer:** the supervising model scored each subject answer against held
  ground truth and recorded the runtime telemetry.
- **Human supervisor:** set scope and testbeds, set scoring weights, raised the
  version confound, and gated each phase.

### Strategy arms

- **GREP** - harness file tools only (glob, content grep, read); the keyword baseline.
- **RAG** - lead with semantic search (`vaultspec-rag search`), read surfaced files;
  grep only on fallback.
- **HYBRID** - two stage: semantic/structured locate, then targeted grep and whole-file
  read to confirm exact symbols.
- **CLI+RAG** - the project's own discovery verbs (`vaultspec-core status`, `vault list`,
  `vault graph`, `vault stats`) plus semantic search; no manual keyword grep.
- **FREE** - unconstrained; used to observe natural composition.

The arm set was evolved iteratively rather than fixed in advance, at the human's explicit
direction to maintain a research-and-evaluate posture and avoid presupposing the answer.

### Probe families

1. **Code discovery** - "where and how is feature X implemented" (5-part questions with a
   single ground truth).
1. **Intent/decision discovery** - find the governing decision records for a feature.
1. **Grounding/implementation** - "you must extend feature X; produce a precise
   implementation plan", scored on grounding completeness against the oracle's extension
   rubric.
1. **Directed-ADR A/B** - a controlled comparison: recall every governing ADR for one
   feature, catch-all vault search versus the directed ADR filter, 3 repetitions per arm.

### Corpora

- **vaultspec-core** (small, well-documented baseline; roughly 4,600 indexed code units) -
  orchestrator-held ground truth.
- **aeat-476** (production testbed; 11,188 Python files, 7,364 vault documents; a hexagonal
  / domain-driven Spanish-tax codebase) - oracle-established, orchestrator-verified ground
  truth. Probes targeted three genuinely nested features: Clave Movil authentication and
  session persistence; Modelo 303 IVA compensation carry routing; and the bank/PDF import
  persistence pipeline.

### Scoring

A weighted composite, weights set by the human supervisor:
`composite = 0.50*(quality/100) + 0.25*cost_norm + 0.15*speed_norm + 0.10*appropriateness`.
Quality is absolute (0-100) against ground truth; cost is subagent output tokens; speed
combines tool-call count and wall-clock duration; appropriateness captures tool-fit,
confidence calibration, and a wasted-call penalty. Cost and speed were min-max normalized
within an iteration; quality was kept absolute to avoid distortion when answers tie high.

### Tooling

The semantic-search engine is the sister project `vaultspec-rag` (server-first, hybrid
dense + sparse retrieval with cross-encoder reranking, cwd-scoped per project). The
campaign began on engine version 0.2.21; the human flagged that 0.2.24 had shipped an
intent-aware pipeline-role ranking for vault search, so the version-sensitive vault batches
were re-run on 0.2.25 after a full reindex (34,379 code chunks + 15,507 vault chunks).

## Results

### Discovery (code) - HYBRID wins across scale and difficulty

| Regime / probe             | HYBRID            | RAG        | GREP           | Winner |
| -------------------------- | ----------------- | ---------- | -------------- | ------ |
| vaultspec-core (4 batches) | 1st in all        | strong 2nd | 3rd            | HYBRID |
| aeat F1 auth               | 0.858 (50.7k tok) | 0.722      | 0.685          | HYBRID |
| aeat F2 IVA-carry (hard)   | 0.902 (67.3k)     | 0.783      | 0.660 (156.8k) | HYBRID |
| aeat F3 import             | 0.843             | 0.805      | 0.663          | HYBRID |

On the hard F2 probe every arm reached the correct, trap-aware answer (the IVA-wallet
decision, not the registry relation, owns casilla 110), so quality converged; the spread
fell entirely on cost - GREP's broad `Glob`/grep over 11k files cost roughly twice HYBRID's
tokens for equal quality.

### Grounding (implement a feature) - HYBRID 2 of 3, margin narrows

| Probe                 | HYBRID | RAG   | GREP  | Winner |
| --------------------- | ------ | ----- | ----- | ------ |
| extend auth provider  | 0.766  | 0.879 | 0.685 | RAG    |
| extend IVA-carry rule | 0.851  | 0.804 | 0.680 | HYBRID |
| extend import format  | 0.814  | 0.621 | 0.710 | HYBRID |

Grounding forces broad reading (the analogue, the contract, the registration sites, the
governing ADRs) that every arm must pay, shrinking the locate-efficiency edge; on the
distributed auth wiring, leaner RAG edged the more thorough HYBRID on token cost.

### Directed-ADR A/B - directed strictly better, version-robust

| Mean of 3 reps                           | CATCHALL `--type vault`                           | DIRECTED `--doc-type adr` |
| ---------------------------------------- | ------------------------------------------------- | ------------------------- |
| 0.2.21 recall / noise / calls / duration | ~17 (needed `ls` fallback) / ~20 docs / 42 / 504s | ~19 / ~0 / 22 / 387s      |
| 0.2.25 recall / noise / calls / duration | ~14 (needed `ls`) / present / 32 / 329s           | ~14 / ~0 / 18 / 198s      |

On both engine versions the directed filter returned more or equal governing ADRs with
near-zero non-ADR pollution, about half the tool calls, and markedly faster wall time. The
0.2.24 intent-aware ranking did not close the gap: catch-all still interleaved audit and
research documents and still required a `ls .vault/adr/` directory scan to reach full
recall in every repetition.

### Version re-validation

After upgrading the engine to 0.2.25 and reindexing, a code-discovery spot-check re-ran the
hard F2 probe under HYBRID and reproduced the trap-aware answer at 66.1k tokens, essentially
identical to 0.2.21's 67.3k. Code-discovery behavior is stable across the version bump; the
directed-ADR conclusion holds on both versions.

## Discussion - key findings

- **One robust pattern.** The decisive action in nearly every successful run was reading
  the epicenter file (or, for grounding, the nearest analogous file) whole. Strategies
  differ mainly in how cheaply they locate that file.
- **Quality converges, efficiency diverges.** On a well-architected codebase (consistent
  naming, docstrings, recorded decisions), every strategy avoids deliberately planted
  traps once it reads the right file, so quality ties high; the discriminator becomes
  context cost and speed, and the cost gap widens with codebase size.
- **The locate tool is probe-type-dependent.** Code targets favor `--type code` semantic
  search plus grep confirmation; decision targets favor the directed `--type vault --doc-type adr` filter or the project's `status`/`vault list` verbs; small well-named
  module clusters are found fastest by listing the directory directly.
- **Semantic search strengths and weaknesses.** It excels at fast first-signal and at
  surfacing intent through prose and docstrings, but it is weak at exact-symbol lookup and
  at small infrastructure/contract modules, and it tends to over-search; it also misses
  lower-ranked or opaquely-named decision records, so a directory backstop is needed for
  recall completeness.
- **Grounding equals discovery plus read-the-nearest-analogue**, at roughly 1.5 times the
  cost of pure discovery.

## Limitations and trust issues

The data is generated by language models and must be read with these caveats:

- **LLM subjects.** The "no-context agents" are themselves language models; their tool
  choices may not generalize to other models, sizes, or future versions.
- **Self-reported testimonials.** Tool traces, breakthroughs, and friction notes are the
  subjects' own accounts and are subject to confabulation and post-hoc rationalization. An
  observed discrepancy between a reported trace and the runtime tool-call count confirms
  the testimonials are not perfectly faithful; they were used for qualitative insight, not
  as primary measurement.
- **Single-rater LLM scoring.** Quality and appropriateness were judged by one orchestrator
  model with no inter-rater reliability check, and that orchestrator also formed the HYBRID
  hypothesis - a confirmation-bias risk. The objective telemetry (tokens, calls, duration)
  and the objectively-countable A/B measures (ADR recall, non-ADR noise) do not depend on
  that judgment and carry the strongest claims.
- **LLM-derived ground truth.** On the production codebase, ground truth came from an LLM
  oracle and was only spot-verified by grep against cited locations, not exhaustively
  audited; un-spot-checked oracle claims could be wrong.
- **Small sample, loose significance.** At most 3 repetitions per cell; "significance" here
  means means and ranges, not formal p-values. Because quality converged, the headline
  comparisons effectively reduce to cost/speed, which is the more trustworthy layer.
- **Confounds.** The harness `Glob` tool was unreliable on Windows drive-letter paths,
  forcing the GREP arm into `find`/`ls` fallbacks and inflating its cost somewhat; the
  semantic index ranks test files highly (their imports name symbols), aiding discovery
  indirectly; subject agents inherited the project's always-on rules, which already nudge
  toward semantic search, biasing the FREE arm; and the engine version changed mid-campaign
  (mitigated by the 0.2.25 re-validation).
- **Construct validity.** "Appropriateness" is a subjective composite; "quality" is scored
  against ground truth that is itself partly LLM-derived. Treat absolute composite numbers
  as directional and trust the direction and magnitude of the cost/speed gaps and the A/B
  noise/recall counts.

## Conclusions

The evidence supports a single, probe-adaptive strategy for no-context discovery: locate
cheaply with the tool that fits the target (semantic code search, the directed ADR filter,
the project status/list verbs, or a direct directory listing), read the epicenter or
nearest-analogue file whole, then confirm exact symbols with targeted grep, and for
decision discovery close with a directory backstop over the records folder. This HYBRID
sequence was the top or near-top performer in every batch and degrades gracefully. The
directed ADR filter should be preferred over catch-all vault search for any
decision-discovery step. The companion `discovery-benchmark` reference document translates
these conclusions into concrete firmware-encoding suggestions.

## Data availability

Raw per-run records, the full scored matrix, agent testimonials, and the verified
ground-truth rubric are persisted under `campaign-data/discovery/` (`runs.jsonl`,
`MATRIX.md`, `aeat-groundtruth.md`). Measurements were taken on `vaultspec-rag` 0.2.25
(with a 0.2.21 baseline retained for the version comparison). Corpora: this repository
(`vaultspec-core`) and the `aeat-476` worktree
(`Y:/code/aeat-worktrees/chore-476-restructure-execution`).
