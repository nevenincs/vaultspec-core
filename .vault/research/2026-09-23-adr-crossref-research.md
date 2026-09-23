---
tags:
  - '#research'
  - '#adr-crossref'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:ee8a1e155a5c80d20e4a358cf8dcdae65f1196d6515db2e470cee2bcbcfc0d0b'
related:
  - "[[2026-09-23-typesafe-search-research]]"
  - "[[2026-09-23-typesafe-search-adr]]"
  - "[[2026-06-28-curator-reframe-adr]]"
  - "[[2026-07-09-mcp-tool-schema-adr]]"
  - "[[2026-08-01-mcp-read-only-adr]]"
---

# `adr-crossref` research: `bounded semantic cross-referencing of ADRs with TypeSafe Jev`

ADRs are scaffolded and accepted without being judged against the decisions that already
exist, so `related:` carries only the links an author happened to remember. This record
asks whether TypeSafe Jev can find the missing ADR-to-ADR links, which question shape and
state find them, and how to bound the cost so it scales past a few hundred ADRs. Measured
on this vault (131 ADRs) and on cadrumo (534 ADRs), both on 2026-09-23 with `jev-1.13.0`:
a three-Noul pair judgment over decision sections is accurate (AUC 0.945 against blind
labels) but cannot run over every pair; a code-only prefilter plus one chunked Choice
request, cut to a fixed candidate count, keeps 0.91 of strong links at a fixed per-ADR
cost. Both vaults are missing most of their cross-references.

## Findings

### Most ADR cross-references are missing in both vaults

- **This vault.** 81 ADR-to-ADR `related:` pairs exist across 131 ADRs; 49 ADRs link to
  no other ADR. A blind labeller judged 120 pairs from decision content alone, ignoring
  frontmatter: 47 of 72 unlinked, lexically closest pairs should link, and 5 of 30
  sampled declared links should not.
- **cadrumo.** 534 ADRs (commit `5b1c188d28`). The rigorous judgment below finds 9.1
  links per ADR (1.7% of candidates, 1.6 of them at composite 0.7 or more) against 1.3
  declared ADR links per ADR; 95% of judged links are undeclared, and only 11 of 32
  sampled declared links pass the judgment.
- **Lexical closeness is not relatedness.** Word overlap separates declared links from
  random pairs (AUC 0.95) but not from its own near-misses (AUC 0.53), which is where
  the missing links sit.

### A three-Noul pair judgment over decision sections is the accurate reference

- **State size dominates the primitive.** On 120 blind-labelled pairs, every question
  scored AUC 0.79 to 0.82 over short cards (title, 700-character problem lead, headings;
  about 1.4k tokens a pair), below word overlap (0.86). Over the decision sections
  (Problem Statement, Implementation, Constraints, Rationale, Consequences, 6,000
  characters each; about 3.5k tokens a pair) every question scored 0.92 to 0.95.
- **Question comparison, decision-section state (AUC / F1 at 0.5).** Mean of three Nouls
  (would applying one require reading the other; do both govern the same concrete
  artifact; would the link be useless noise, inverted): 0.947 / 0.894. Negative
  "merely share a topic" Noul: 0.938. Positive "need to read" Noul with true/false
  criteria: 0.936 / 0.870. Five-level coupling Score: 0.928 / 0.889. Relation-type
  Choice, summed linking mass: 0.920 / 0.850. Generic "are they related": 0.917.
- **The relation Choice labels, it does not decide.** Swapping `a` and `b` changes the
  Choice's argmax on 29% of pairs; Noul probabilities move 0.05 to 0.08 on average.
- **Negative and positive framings agree.** The "need to read" Noul and the inverted
  "merely share a topic" Noul differ by 0.215 on average and never both exceed 0.5.
- **As a reference.** The three-Noul mean over all 8,515 pairs of this vault took 250 s
  at 16 concurrent requests, 23.8M input tokens ($1.00). Against the blind labels it
  scores AUC 0.945, precision 0.97 and recall 0.84 at 0.5. It finds 384 links (4.5% of
  pairs, median 5 per ADR); 32 of them touch a superseded, deprecated or rejected ADR,
  so a status prefilter would drop real links.

### Exhaustive pair judgment does not scale

Pairs grow quadratically: 8,515 pairs at 131 ADRs, 142,011 at 534. At about 2.8k tokens a
pair, one ADR against cadrumo's corpus is 1.5M tokens and 533 requests; a whole-corpus
sweep is about 400M tokens ($17) and over an hour at the published 1,200 requests a
minute (`2026-09-23-typesafe-search-research`). A 24-source cadrumo reference (12,792
requests, 29.8M tokens, $1.25, 323 s) was run only to measure the prefilters below.

### Headers alone cannot narrow the candidates

With only feature names, titles and status on both sides, the best prefilter recovered
0.53 of the reference's links in its top 20 (a Noul per title pair, which alone cost 26.7M
tokens, more than the reference). Title word overlap reached 0.38 and a roster Choice
over titles 0.47. Parsing the headers of all 131 ADRs from their first 2 KB took 89 ms,
so parsing is not the bottleneck; the evidence in the header is.

### Rich source state against superficial candidates, and a code fingerprint, close most of the gap

The ADR being judged is read in full (its decision sections); the candidates are
represented superficially. Measured on this vault against the reference, 40 sources:

| Prefilter                                        | Tokens per source | R@20 | R@30 | Candidates for 90% (median) |
| ------------------------------------------------ | ----------------- | ---- | ---- | --------------------------- |
| One Choice over all 130 headers                  | 7k                | 0.52 | 0.56 | 106                         |
| Choice, header plus 200-character lead, 4 chunks | 10k               | 0.71 | 0.78 | 68                          |
| Score per candidate, header plus lead            | 211k              | 0.72 | 0.77 | 36                          |
| Artifact fingerprint overlap, no API             | 0                 | 0.63 | 0.74 | 53                          |
| Artifact plus word overlap, rank-fused, no API   | 0                 | 0.76 | 0.82 | 33                          |
| Choice with artifacts in options, 8 chunks       | 13.7k             | 0.77 | 0.84 | 31                          |
| That Choice fused with artifact and word overlap | 13.7k             | 0.85 | 0.91 | 18                          |

- **Artifact fingerprint.** Backticked identifiers in each ADR body (module and file
  paths, CLI verbs, configuration variables, tool names), normalised and weighted by
  inverse document frequency, extracted by code in 150 to 350 ms for 131 ADRs. An option
  reads `[feature] title. lead. Artifacts: a, b, c`, carrying the six most distinctive
  fingerprint entries shared with at least one other ADR.
- **Chunking the Choice.** Choice probabilities are relative within one question, so one
  question over 130 options concentrates on a handful; splitting the roster into
  questions of 16 to 32 options, each with a `none` option, raises recall (0.52 to 0.71 at
  20). The chunks ride in one request as parallel questions over the same state.
- **Per-candidate Score** is the sharpest single judgment for the long tail, but at
  211k tokens a source it costs 58% of judging every candidate rigorously (about 364k),
  so it is not a prefilter. Its levels do make a usable threshold: level 1 of 0 to 4
  keeps about 35 candidates at 0.85 recall.
- **Rejected angles.** Three shuffled Choice runs add about two points of recall for 3x
  the tokens; four facet Choices (depends on, constrains, same artifact, refines or
  reverses) cost 4x for no gain at scale; a feature-first two-step Choice reached 0.56
  at 20.
- **What the cut loses.** At the top-30 cut on this vault no link at composite 0.8 or
  more was missed and 2 of 63 at 0.7 or more were; the 37 other misses are marginal
  (0.5 to 0.7).

### At 534 ADRs the bounded funnel keeps strong links and loses weak ones

cadrumo, 24 sources, reference as above:

| Stage                                      | Tokens per source | R@32 all | R@32 0.6 to 0.7 | R@32 strong (0.7+) |
| ------------------------------------------ | ----------------- | -------- | --------------- | ------------------ |
| Code-only rank fusion                      | 0                 | 0.61     | 0.69            | 0.88               |
| Top 128 to one Choice, 32 per chunk, fused | 13.0k             | 0.71     | 0.84            | 0.91               |
| Top 192, 32 per chunk, Choice weighted 2x  | 18.7k             | 0.74     | 0.84            | 0.91               |
| Top 256, 32 per chunk, Choice weighted 2x  | 24.5k             | 0.75     | 0.87            | 0.89               |

- **Code-only cost stays negligible.** Parsing 534 ADRs (6.5 MB) took 845 ms, building the
  fingerprint index 52 ms, and ranking 7.6 ms per source.
- **The whole-vault graph is not.** A cold `VaultGraph` build over cadrumo's 4,755 nodes
  took 28.9 s, against 0.85 s to read and parse the ADR directory alone; the graph reads
  every record type to answer a question about one.
- **Recall at 48 rather than 32** rises from 0.74 to 0.78 for the 192 pool, at 16 more
  rigorous requests.
- **The missed links are mostly weak**: at 0.5 to 0.6 the 192 pool finds 0.62 of them at 32.

### Cost envelope of a bounded run

At $0.042 per million input tokens (`2026-09-23-typesafe-search-research`), a source judged
through a 192 pool (about 19k tokens, one request) and 32 rigorous pairs (about 90k
tokens) costs about 110k tokens, $0.005, and 33 requests, which at 12 to 16 concurrent
requests and a 300 ms median finishes in 1 to 3 s. The request count and tokens are
independent of corpus size once the pool is capped; only the code-only stage grows with
the corpus, linearly and without network calls.

### Section-level and lineage signals are separable, and out of this record's scope

- **Planted-defect test.** 58 sections from 29 records were judged clean and with one
  planted defect each; the matching negative Noul fired at AUC 0.94 to 1.00 (filler,
  repetition, vagueness, off-subject paragraph, decision wording in evidence, evidence
  dumped into a decision). "Would a developer learn nothing useful" never moved; a
  general quality Score moved on every defect and diagnoses none.
- **Lineage chains.** Research-to-ADR and ADR-to-plan Nouls separate a feature's own
  chain from the lexically closest foreign record at AUC 0.91 to 0.94. Their weakest
  in-feature chains were real defects: template-only research records (`cli-restructure`,
  `roadmap`, `test-quality`, `cli-test-coverage`), the catch-all `framework` feature tag,
  and a `docs-curation` ADR dated after its plan.

These signals ground a later body-quality and lineage decision; ADR linking does not
depend on them.

### The existing hosted-search stack is reusable as is

- **Transport.** `JevClient` pins the model, sanitises state against the edge firewall,
  preflights request size, bounds concurrency and a deadline, retries, and validates
  every answer (`src/vaultspec_core/search/_transport.py:632`, bounds at
  `src/vaultspec_core/search/_transport.py:117`). The firewall refuses unsanitised ADR
  text that quotes module invocations with an HTML 403; the scratch harness reproduced it
  on two ADRs and the shipped sanitiser clears it.
- **Credential and consent.** One variable enrols hosted search and the rest is code
  constants (`src/vaultspec_core/search/_credential.py:1`), as
  `2026-09-23-typesafe-search-adr` requires.
- **Surfaces.** `search` is a thin MCP wrapper over one backend service
  (`src/vaultspec_core/mcp_server/tools/search.py:1`), registered on the read-only surface
  (`src/vaultspec_core/mcp_server/app.py:146`). `2026-07-09-mcp-tool-schema-adr` holds the
  hot tool list to single digits plus the gateway, and nine hot tools exist today.
- **Link writing** lives in the CLI command (`src/vaultspec_core/cli/link_cmd.py:195`)
  over `append_related_entry` (`src/vaultspec_core/vaultcore/related_surgery.py`); no
  backend service writes a `related:` edge.
- **Curation** is a persona instructed to search, read and judge ADR pairs by hand
  (`src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md:1`), with no bound on
  what it reads.

### Not investigated

- Links between record types other than ADR-to-ADR at scale; lineage chains were measured
  only on this vault.
- The labelled evidence is one blind model labeller on this vault; cadrumo was judged
  only against the rigorous reference, not labelled independently.
- Candidate pools above 256, other chunk sizes than 16 and 32, and models other than
  `jev-1.13.0`.
- The scratch harness was not committed; its numbers are pinned here by model, date and
  corpus commit.

## Sources

- `src/vaultspec_core/search/_transport.py:13`
- `src/vaultspec_core/search/_transport.py:117`
- `src/vaultspec_core/search/_transport.py:632`
- `src/vaultspec_core/search/_credential.py:1`
- `src/vaultspec_core/mcp_server/tools/search.py:1`
- `src/vaultspec_core/mcp_server/app.py:146`
- `src/vaultspec_core/cli/link_cmd.py:195`
- `src/vaultspec_core/vaultcore/related_surgery.py`
- `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md:1`
- vaultspec-core vault at commit `84c4098a`; cadrumo vault at commit `5b1c188d28`
- https://docs.typesafe.ai/primitives/choice
- https://docs.typesafe.ai/primitives/noul
- https://docs.typesafe.ai/primitives/score
- https://docs.typesafe.ai/cookbooks/rerank_typesafe
- https://docs.typesafe.ai/patterns/composite-scoring
- https://docs.typesafe.ai/api
