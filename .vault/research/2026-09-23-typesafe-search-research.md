---
tags:
  - '#research'
  - '#typesafe-search'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:26c0b250940b25e8e83b18eb021552c086ff45b2775b93262c6dd2cda3826240'
related:
  - '[[2026-08-26-rag-search-exposure-adr]]'
  - '[[2026-08-23-envelope-optimization-adr]]'
  - '[[2026-07-09-mcp-tool-schema-adr]]'
  - '[[2026-08-01-mcp-read-only-adr]]'
  - '[[2026-02-16-environment-variable-adr]]'
---

# `typesafe-search` research: `TypeSafe Jev as the vault search engine`

Should vault search in vaultspec-core run on TypeSafe Jev, enrolled by
`VAULTSPEC_CORE_TYPESAFE_API_KEY`, with vaultspec-rag kept as the fallback? Core has
no vault search today: `find` matches stems and features, and semantic search reaches
agents only as prose telling them to run rag. A live, labelled evaluation on this
vault used `jev-1.13.0` on 2026-09-23: 24 development queries, then 20 held-out
queries over features the first set never touched. A two-stage Jev engine ranked the
right record first more often than rag (0.83 against 0.72 held out). It located the
answering excerpt where rag almost never does, and abstained on most unanswerable
questions. It runs in about one second without an index, and costs about half a cent
per query. Its misses are recall of answers buried in body detail, a weakness rag does
not share. The same evidence exposes four things the ADR must settle: rag as an
in-core fallback contradicts an accepted decision; a Cloudflare rule in front of the
API blocks 2.8% of vault records unless text is sanitised; where the credential may be
read from; and how a new surface fits the fixed MCP tool set and the envelope budget.

## Findings

### Core has no vault search, and an accepted decision forbids core calling rag

`find` (`src/vaultspec_core/mcp_server/tools/documents.py:942`) filters by feature,
type and date. Its `text` filter matches stem and feature only, never the body
(`documents.py:1029`), and results are unranked. The rag path exists only as agent
guidance (`src/vaultspec_core/core/discovery_guidance.py:48`) and a presence probe
(`src/vaultspec_core/core/diagnosis/collectors_companion.py:56`, floor `0.4.4`).
`2026-08-26-rag-search-exposure-adr` requires that core calls no rag API, imports no
rag module, opens no socket to rag's service, places no rag-derived content in its
output, and keeps its MCP tool list a pure function of its own version. Any fallback in
which core invokes rag therefore needs that decision superseded, not merely extended.

### Jev's contract fits record-and-excerpt retrieval within hard request bounds

Jev evaluates a `state` against typed questions: Choice (one of up to 255 options,
distribution plus confidence), Score (up to 10 ordered levels) and Noul (probability
of yes, no separate confidence). Questions in one request run in parallel and cannot
see each other (https://docs.typesafe.ai/primitives). A Choice is relative, so some
option always wins; an absolute Noul is needed to say that nothing answers
(https://docs.typesafe.ai/cookbooks/semantic_find,
https://docs.typesafe.ai/model-jaggedness/jev-1.13).

- **Request limits:** 64k tokens per request, and 32k for state plus the longest
  question.
- **Price:** $0.042 per million input tokens; output is free.
- **Rate limits:** 250,000 tokens/s and 1,200 requests/min, described as "adjusting
  dynamically" (https://docs.typesafe.ai/models).

Large irrelevant state lowers accuracy, so retrieval must narrow before judging
(jaggedness page, "Large state"). The skill-suggestion cookbook's shape maps onto vault
records: a cheap Choice over a whole roster, then Nouls over a shortlist read in full
(https://docs.typesafe.ai/cookbooks/skill_suggestion). `jev-latest` is a moving alias,
so thresholds tuned on a version need the pinned ID `jev-1.13.0`.

### rag already uses Jev, as a gated reranker over its own recall

vaultspec-rag enrols through `VAULTSPEC_RAG_TYPESAFE_API_KEY` and reclassifies at most
64 retrieved candidates in batches of 8 (`vaultspec_rag/search/_typesafe_policy.py:21`).
It uses a stdlib transport with its own pool, cache, 2-slot concurrency and a pinned
`jev-1.13.0` (`vaultspec_rag/search/_typesafe_transport.py:22`,
`vaultspec_rag/search/_typesafe_answers.py:9`). It deliberately ignores the generic
`TYPESAFE_API_KEY` (`vaultspec_rag/tests/test_typesafe_transport.py:197`).

rag's own evaluation, on its code corpus, found meaningful precision gains. Median
latency was 4.13 s with the key against 1.71 s without it, before connection pooling
(`vaultspec-rag: .vault/research/2026-09-21-typesafe-classifier-research.md`). That is
Jev as a precision layer over an embedding index. The question here is Jev as the
retriever, with no index at all.

### A two-stage Jev engine matches rag on finding the record and far exceeds it on the excerpt

**Corpus.** 672 records: adr, research, reference, audit, plan and exec. `index/` and
`_archive/` are excluded. Together they hold about 4.9 MB, roughly 1.2M tokens, so
reading every record in full per query is out of reach of the request and rate bounds.

**Stage 1 (summary pass).** The query is the state. There is one Choice per record
type, and each option is a record summary: title, a 240-character lead, and the
non-template headings. Each Choice also has a `none` option. The summaries total about
84k tokens and are split into requests of about 22k tokens, run in parallel. One more
Choice classifies which kind of record the query needs.

**Stage 2 (full read).** Candidates are the top records per record group (reference
and audit share one group), at most 4 per group
with probability at least 0.02 and 8 in total, plus the BM25 top 3. Each candidate gets
one request over its full text, split into paragraph blocks, asking:

- whether the record answers the query (Noul);
- whether it is about the query's subject (Noul);
- whether it contradicts a premise of the query (Noul);
- which block answers (Choice).

**Ranking.** The answer probability plus 0.2 times the record-kind probability.

**Queries.** 24 labelled queries, written by a separate agent from the documents
alone, across 15 features, with every evidence string verified verbatim:

- 12 direct, 8 of them paraphrased;
- 4 lookalike;
- 3 multi-record;
- 3 with no answer in the vault;
- 2 false premise.

Harness, queries and raw outputs are in `tmp/typesafe-search-eval/`.

| engine (21 answerable queries)           | hit@1       | hit@3       | MRR           | excerpt holds the gold evidence | abstained (3 unanswerable) | median latency |
| ---------------------------------------- | ----------- | ----------- | ------------- | ------------------------------- | -------------------------- | -------------- |
| Jev two-stage, run 1 / run 2             | 0.86 / 0.90 | 0.95 / 0.95 | 0.905 / 0.929 | 18/21 / 18/21                   | 2/3 / 2/3                  | 986 / 999 ms   |
| Jev two-stage without the kind prior     | 0.76        | 0.95        | 0.849         | 18/21                           | 2/3                        | 1,166 ms       |
| Jev with one Noul per summary as stage 1 | 0.67        | 0.76        | 0.726         | 16/21                           | 2/3                        | 1,181 ms       |
| `vaultspec-rag@0.4.35`, keyless service  | 0.81        | 0.90        | 0.853         | 0/21                            | 0/3                        | 2,186 ms       |
| BM25 over full text, in-process          | 0.57        | 0.86        | 0.725         | 11/21                           | 0/3                        | 13 ms          |

rag's vault results carry no section, anchor or line range. Its only excerpt is a
200-character `snippet` from the start of the matched chunk, which is up to 3,000
characters (`vaultspec_rag/search/_searcher.py`, `_map_vault_results`). That snippet
contained the gold evidence in 0 of 21 cases and showed the gold section heading in 8.
This is filed as https://github.com/nevenincs/vaultspec-rag/issues/531. Jev's excerpt
is a located block (median 638 characters) whose heading matched the gold section in 19
of 21 cases. rag's latency includes a CLI process per query. Between the two runs, the
"does anything answer" value moved by at most 0.03 per query.

Limits of this evidence:

- 21 answerable queries give 0.05 steps per query.
- The 0.2 kind weight was picked on these same queries. Weights 0.1 and 0.2 score
  identically; 0.3 scores higher. The held-out finding below confirms 0.2 on unseen
  queries.
- Queries written from the documents favour lexical overlap, which flatters BM25.
- One unanswerable case (FreeBSD builds) is arguably answered by a release target list,
  and Jev's 0.70 there is defensible.
- rag was run from its own development checkout, because no core environment carries
  `vaultspec-rag[gpu]`.

### "Does this record answer" separates answerable from unanswerable questions

The highest answer probability exceeded 0.5 on all 21 answerable queries, in both runs.
It stayed at 0.03 and 0.07 for log rotation and signed commits, which no record covers.
rag and BM25 always return a full page; rag returned 10 hits for each unanswerable
query.

The premise Noul flagged the refuting ADR at 0.91 for the release-please false premise,
while another record ranked first. A premise conflict is therefore a separate signal to
surface, not a ranking term.

### Siblings of one feature tie on "answers"; a record-kind prior resolves most ties

The research, ADR, plan and audit of one feature all score 0.93-0.97 on the answer Noul
when each restates the decision. Their order was arbitrary, and the ADR ranked 2 or 3
in four cases. Adding the kind probability lifts hit@1 from 0.71 to 0.86 in the same
run without changing excerpts. rag's default "orientation" intent prior lifts decisions
for the same reason (`vaultspec-rag: .env.example`,
`VAULTSPEC_RAG_VAULT_INTENT_DEFAULT`).

Using one Noul per summary as the recall stage lost four gold records that the grouped
Choice kept. The Choice's relative ranking within a record type is the better recall
signal here.

One paraphrased query, asking why the markdown hook stopped repairing vault findings,
was missed by every engine except BM25, which ranked it 5. A summary cannot carry every
body detail, so how deep the BM25 top-N added to the shortlist should go is still open.

### Held-out queries confirm the kind prior; per-record judgments cannot rank siblings

Revisions guided by the TypeSafe skill were measured on the dev set; the one that
showed a gain was then checked on 20 held-out queries.

**Held-out set.** A second agent wrote the 20 queries over 12 features that the dev set
does not touch, verified the same way: 10 direct, 4 sibling, 2 multi-record, 2 with no
answer, 2 false premise (`tmp/typesafe-search-eval/heldout.json`).

**Per-record Score.** The skill's "comparable per-item Scores for graded ranking"
guidance does not separate siblings. A four-level Score on how directly a record answers
("primary account" down to "does not address") returned at least 0.98 of the scale for
research, ADR and plan alike. On the dev set, answer plus Score ranked hit@1 0.71, the
same as the answer Noul alone. Judged alone, each sibling does state the answer with its
reasons. Which record owns it is relational, and no per-record question can see it.

**Finalist Choice.** A Choice over the top four finalists, read side by side, asked
which record is the authoritative source, following the skill-suggestion cookbook's
second request. It reached hit@1 0.95 on three saved dev shortlists, at about 1.3k
tokens and a 276 ms serial request. On the held-out set it matched the kind prior.

| engine (18 answerable held-out queries) | hit@1 | hit@3 | MRR   | excerpt holds the gold evidence  | abstained (2 unanswerable) | median latency |
| --------------------------------------- | ----- | ----- | ----- | -------------------------------- | -------------------------- | -------------- |
| Jev, answer plus 0.2 kind (v2)          | 0.83  | 0.83  | 0.844 | 13/18                            | 1/2                        | 957 ms         |
| Jev, finalist Choice (v4)               | 0.83  | 0.83  | 0.847 | 13/18, 14/18 with a second block | 1/2                        | 1,260 ms       |
| `vaultspec-rag@0.4.35`, keyless         | 0.72  | 0.83  | 0.797 | 1/18                             | 0/2                        | 2,355 ms       |
| BM25                                    | 0.33  | 0.61  | 0.496 | 11/18                            | 0/2                        | 17 ms          |

The two Jev rankings differ on one case, rank 4 against 5. The kind prior is therefore
not overfit to the dev set, and the finalist request adds latency without a measured
gain.

**Recall.** The remaining Jev misses are recall, not ranking. For two held-out queries
the gold record never reached stage 2, because the answer sits in a body detail that
its summary does not carry: an fsync setting, and a Windows config-merge defect. Their
stage-1 rank was past 20 and their BM25 rank 9 and 8, so the BM25 top-3 union missed
them. rag ranked both first. rag in turn missed or buried three records that Jev ranked
first. Summary-based recall and embedding recall fail on different queries.

**Excerpt Choice.** Adding an explicit "no block answers" option did no harm. That
option's probability on the top record was 1.0 and 0.98 for the two dev queries with no
answer. Returning a second block when its probability is at least 0.25 added one
correct excerpt on each set.

**Kind question.** The record-kind Choice asks about the same state as stage 1. Carrying
it inside a stage-1 request, the skill's fan-out advice, saved one request per search
(15.3 against 16.3) at unchanged latency.

### The shipped search keeps the prototype's ranking once blocks fit the byte-bounded excerpt

`search_vault` itself was measured on both labelled sets with
`tmp/typesafe-search-eval/run_product_eval.py` against this vault on 2026-09-23. The
sets are small: one case moves dev hit@1 by 0.05 and held-out hit@1 by 0.06.

| shipped code                                       | dev hit@1 | dev excerpt | held-out hit@1 | held-out excerpt | median latency | cost per search |
| -------------------------------------------------- | --------- | ----------- | -------------- | ---------------- | -------------- | --------------- |
| 900-character excerpt, 1,400-character blocks      | 0.86      | 19/21       | 0.89           | 15/18            | about 1.4 s    | about $0.005    |
| 700-byte excerpt, 1,400-character blocks           | 0.95      | 15/21       | 0.89           | 11/18            | 1,806 ms       | $0.0052         |
| 700-byte excerpt, blocks of at most 700 characters | 0.90      | 19/21       | 0.94           | 12/18            | 1,778 ms       | $0.0052         |

**Clipped blocks.** Bounding excerpts by bytes, which the reply ceiling requires
(`src/vaultspec_core/search/_models.py:85`), shrank the excerpt below the block size. The
clip keeps a block's leading lines (`src/vaultspec_core/search/_engine.py:796`), so an
answer that closed its block was cut away. In four of the six cases that smaller blocks
recovered, the evidence sat one to four lines below the returned range. Cutting blocks
at the excerpt size (`src/vaultspec_core/search/_corpus.py:367`) makes the block the
provider picks the text returned, at unchanged cost and latency.

**Remaining misses.** Of the eight misses left:

- Two are single lines longer than 700 bytes, with the evidence past the cap.
- Five are a neighbouring or unrelated block chosen by the excerpt Choice.
- One is the recall miss described above.

### Cloudflare in front of the API rejects 2.8% of vault records unless text is sanitised

The API answered some requests with an HTML 403 from Cloudflare rather than its JSON
error. Probing each record once with a trivial question blocked 19 of 672 records
(`tmp/typesafe-search-eval/results/waf_raw.json`). Bisecting lines found these
triggers:

- a quoted `python -m ...` command (in backticks or single quotes; the bare command
  passes);
- `python -m <module>`;
- `/etc/passwd`;
- `../../` traversal.

Replacing backticks, `<` and `>` with typographic equivalents in model-facing text
cleared all 19 (`waf_sanitized.json`). Returned excerpts remain the original text,
because blocks are addressed by local ID.

Consequences:

- An HTML 403 is a content rejection and must be handled per request, not as a
  credential failure.
- rag's transport treats every 403 as a permanent credential failure
  (`vaultspec_rag/search/_typesafe_transport.py:260`). Reproduced on
  `vaultspec-rag@0.4.35`: one candidate quoting `python -m pytest` returned
  `credential_rejected`, and every later request was refused with `credential_disabled`
  until restart. The same body sent without a key also returns the HTML 403, so the
  block happens at the edge before authentication. Filed as
  https://github.com/nevenincs/vaultspec-rag/issues/532.
- A missing key returned 403 with `authentication_error`, not the 401 the API reference
  lists (https://docs.typesafe.ai/api). Status alone does not identify the cause.

### Latency and cost are bounded by request size and account rate limits

- **Per-request latency:** a warm request took about 230 ms and a cold one about
  410 ms. Summary requests of about 55k tokens took about 690 ms, so latency grows with
  tokens. Splitting stage 1 into requests of about 22k tokens cut the median search
  from 1,166 to 986 ms.
- **Per-search cost:** a search averaged 16 requests and 122k input tokens, $0.0051.
- **Throughput per key:** at the published limits, one key sustains roughly 75
  searches a minute before hitting the 1,200 requests/min limit. The 250k tokens/s
  limit allows about two searches a second.
- **Scaling:** stage 1 grows by about 110 tokens per record, so a vault several times
  larger needs a type or lexical pre-filter before the summary pass.
- **Against rag:** rag needed a 90.6 s service cold start and a 60 s index rebuild
  (2,714 chunks) before its first answer on this worktree. Jev reads the records from
  disk per query and has no index to go stale.

### Credential resolution: the process environment, the workspace `.env`, and who controls each

Core reads configuration only from `os.environ`, through `CONFIG_REGISTRY`
(`src/vaultspec_core/config/config.py:375`), and loads no `.env` at runtime; `.env` is
generated for `just` only. `InstallMode` TOOL, DEPENDENCY and DEV (`core/enums.py:328`)
record how the workspace launches core. Nothing detects whether the running process is
a project venv, a uv tool or a PyApp binary.

A workspace `.env` is repository content. Honouring it from a globally installed core
lets a cloned repository supply a credential. Letting it supply a base URL would send
the user's own key to another endpoint. rag reads only its dedicated variable from the
executing environment: "no key in root-controlled configuration"
(`vaultspec-rag: .vault/adr/2026-09-21-typesafe-classifier-adr.md`).

The options are:

1. The process environment only (rag parity).
1. The process environment first, then the workspace `.env` only when the workspace
   declares DEPENDENCY or DEV mode.
1. The workspace `.env` always.

Whichever is chosen, the endpoint needs to stay fixed in code.
`VAULTSPEC_CORE_TYPESAFE_API_KEY` satisfies the `VAULTSPEC_` prefix rule of
`2026-02-16-environment-variable-adr` and is documented in `.env.example`.

### Transport: the SDK adds one package to core's lock, but its API is churning

`typesafe-sdk@0.7.1` requires `httpx2`, `pydantic`, `pydantic-core`, `tenacity` and
`typing-extensions` (https://pypi.org/pypi/typesafe-sdk/json). Core's lock already
carries all of them except `tenacity`, through `mcp@2.2.0` and `pydantic` (`uv.lock`).

The SDK went 0.5.7, 0.6.0, 0.7.0, 0.7.1 between 2026-09-14 and 2026-09-21, with
breaking changes in 0.6.0 (Score criteria shape) and 0.7.0 (msgspec to pydantic)
(https://docs.typesafe.ai/sdk/python/changelog). The wire contract, by contrast, is one
POST endpoint with a published schema
(`tmp/typesafe-search-eval/typesafe-openapi-0.2.0.json`). The harness client is about
120 lines of `http.client`.

Release binaries install the package without extras (`dev/binaries/build_pyapp.py:817`).
An optional extra would therefore be absent from them; a base dependency or a stdlib
transport would not.

### Fallback: four shapes, one of which supersedes the rag-exposure decision

1. **Core calls rag when no key is set.** This delivers the requested behaviour
   literally. It supersedes `2026-08-26-rag-search-exposure-adr` and imports rag's
   service failure surface. Observed here: the service was down, the GPU extras are
   missing from core's environments, and the index was `index_unverifiable` until a
   rebuild.
1. **Core returns a typed "hosted search not configured" outcome naming
   `vaultspec-rag search`.** Generated discovery guidance routes agents to rag when no
   key is present. rag remains the fallback, at the agent layer, and no decision is
   superseded.
1. **Core falls back to in-process BM25 over the vault.** It is always available and
   locates an excerpt in 11 of 21 cases, against rag's 0, but ranks below rag.
1. **The second and third together.**

### Surface: tool budget, read-only mode and the envelope budget

- **Tool budget.** `2026-07-09-mcp-tool-schema-adr` caps first-class tools at single
  digits plus the gateway. Normal mode registers eight today, plus `discover` and
  `invoke`; read-only mode registers four (`src/vaultspec_core/mcp_server/app.py:142`).
  A search reached only through `invoke` would need host confirmation on every call, so
  a first-class tool amends that set.
- **Tool-list invariance.** The rag-exposure invariance principle implies registering
  the tool regardless of whether a key is present, and returning a typed unavailable
  outcome.
- **Read-only mode.** `2026-08-01-mcp-read-only-adr` allowlists the read-only surface.
  Search writes nothing locally but sends vault content off the machine, which the ADR
  must weigh.
- **Envelope.** `2026-08-23-envelope-optimization-adr` caps discovery replies at 4,000
  tokens, with a total and a truncation marker. Five hits, each with a 600-character
  excerpt and a line range, fit in about 1,200 tokens.

### Not investigated

- Accuracy beyond the 44 queries of the two sets, and whether a deeper or paragraph-level
  lexical union closes the recall gap. Tuning that gap on the held-out set would
  consume it, so a third set is needed.
- Vaults an order of magnitude larger.
- rag's own hosted mode on this vault.
- Non-English records.
- Behaviour under a rate-limited or unfunded key.
- Data-retention terms beyond the models page statement that Jev is not trained on
  customer requests (https://docs.typesafe.ai/models).

## Sources

- https://docs.typesafe.ai/primitives
- https://docs.typesafe.ai/primitives/choice
- https://docs.typesafe.ai/primitives/noul
- https://docs.typesafe.ai/primitives/score
- https://docs.typesafe.ai/confidence
- https://docs.typesafe.ai/models
- https://docs.typesafe.ai/api
- https://docs.typesafe.ai/model-jaggedness/jev-1.13
- https://docs.typesafe.ai/cookbooks/semantic_find
- https://docs.typesafe.ai/cookbooks/skill_suggestion
- https://docs.typesafe.ai/cookbooks/rerank_typesafe
- https://docs.typesafe.ai/cookbooks/classifying_rag_passages
- https://docs.typesafe.ai/sdk/python/changelog
- https://pypi.org/pypi/typesafe-sdk/json
- https://github.com/nevenincs/vaultspec-rag/issues/531
- https://github.com/nevenincs/vaultspec-rag/issues/532
- `src/vaultspec_core/mcp_server/tools/documents.py:942`
- `src/vaultspec_core/mcp_server/tools/documents.py:1029`
- `src/vaultspec_core/core/discovery_guidance.py:48`
- `src/vaultspec_core/core/diagnosis/collectors_companion.py:56`
- `src/vaultspec_core/config/config.py:375`
- `src/vaultspec_core/mcp_server/app.py:142`
- `src/vaultspec_core/core/enums.py:328`
- `dev/binaries/build_pyapp.py:817`
- `uv.lock` (`mcp@2.2.0`, `httpx2@2.13.0`, `pydantic@2.13.5`)
- `vaultspec_rag/search/_typesafe_policy.py:21`
- `vaultspec_rag/search/_typesafe_transport.py:22`
- `vaultspec_rag/search/_typesafe_transport.py:260`
- `vaultspec_rag/search/_typesafe_answers.py:9`
- `vaultspec_rag/tests/test_typesafe_transport.py:197`
- `vaultspec-rag: .vault/research/2026-09-21-typesafe-classifier-research.md`
- `vaultspec-rag: .vault/adr/2026-09-21-typesafe-classifier-adr.md`
- `tmp/typesafe-search-eval/` (harness, `queries.json`, `results/`)
