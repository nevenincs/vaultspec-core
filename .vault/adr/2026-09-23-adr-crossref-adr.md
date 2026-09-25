---
tags:
  - '#adr'
  - '#adr-crossref'
date: '2026-09-23'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:1a92a8c5dc85a830f3b75e2a07e099be76648a9474b10480a522f64672b9235e'
related:
  - "[[2026-09-23-adr-crossref-research]]"
  - "[[2026-09-23-typesafe-search-adr]]"
  - "[[2026-07-09-mcp-tool-schema-adr]]"
  - "[[2026-08-01-mcp-read-only-adr]]"
  - "[[2026-06-28-curator-reframe-adr]]"
  - "[[2026-07-09-firmware-mcp-primacy-adr]]"
  - '[[2026-08-23-envelope-optimization-adr]]'
  - '[[2026-09-23-adr-crossref-audit]]'
  - '[[2026-09-25-skill-audit-adr-authoring-audit]]'
---

# `adr-crossref` adr: `bounded ADR cross-referencing on TypeSafe Jev, as a core backend with one CLI and MCP surface` | (**status:** `accepted`)

## Problem Statement

A new ADR is accepted without being judged against the decisions already in the vault,
so its `related:` field holds only the links its author remembered. Both measured vaults
are missing most of their ADR cross-references, and curation compares ADRs by hand with
no bound on what it reads (`2026-09-23-adr-crossref-research`). Judging every pair
semantically is accurate but grows quadratically in requests, time and money, and no
production path may run an unbounded job against a paid external API. Core needs one
bounded classifier that the CLI, the MCP server and the framework's ADR and curation
workflows all call, so that ADRs are cross-referenced when they are written and the
corpus can be reconciled after the fact.

## Considerations

- Accuracy lives in the pair judgment over decision sections, not in the primitive; short
  cards score below word overlap (`2026-09-23-adr-crossref-research`).
- Metadata-only prefilters cannot narrow the candidates; a code-extracted artifact
  fingerprint plus a chunked Choice can (`2026-09-23-adr-crossref-research`).
- At 534 ADRs a fixed candidate cut keeps 0.91 of strong links and about three quarters
  of all links, at a per-source cost independent of corpus size
  (`2026-09-23-adr-crossref-research`).
- The relation Choice changes its answer on 29% of pairs when the sides are swapped
  (`2026-09-23-adr-crossref-research`).
- The hosted-search credential, transport, pinned model, sanitising, size bounds, typed
  failures, backend-resolved next step and thin-surface rules bind any new Jev caller
  (`2026-09-23-typesafe-search-adr`).
- Every reply fits the envelope budget: a hard ceiling of 10,000 tokens, a total and a
  truncation marker (`2026-08-23-envelope-optimization-adr`).
- The hot MCP tool list holds nine tools plus the two gateway tools under a
  single-digits rule, and hot tools were promoted for avoiding a host confirmation on
  every call (`2026-07-09-mcp-tool-schema-adr`); the read-only launch mode admits a tool
  only by deliberate classification (`2026-08-01-mcp-read-only-adr`).
- Firmware names the primary tool and one CLI fallback at the orchestrator; personas name
  CLI verbs only (`2026-07-09-firmware-mcp-primacy-adr`).

## Considered options

- **Exhaustive pair judgment.** Every ADR against every other with the three-Noul
  judgment. Most accurate, but quadratic: rejected as unbounded.
- **Metadata-only prefilter.** Titles, features and status on both sides. Cheap, but it
  recovers about half the links at 20 candidates: rejected as insufficient.
- **Per-candidate Score over headers as the prefilter.** Best single judgment for the
  tail, but it costs most of what it saves: rejected.
- **Code fingerprint, chunked Choice, fixed pair cut (chosen).** Linear code stage, a
  constant number of evaluations per source, recall concentrated on strong links.
- **Surface: a mode of `search`.** Keeps the tool count, but `search` takes a question
  and returns excerpts, while cross-referencing takes a record and returns link verdicts:
  one schema would carry two contracts. Rejected.
- **Surface: a CLI verb reached through the gateway only.** Keeps the tool count and
  costs no standing schema, but `invoke` confirms every call and is absent from read-only
  launches, so the orchestrator running the ADR workflow, and read-only orchestrated
  agents, would lose it or pay a confirmation per ADR. Rejected; the CLI verb exists
  either way.
- **Surface: a semantic check inside `check`.** `check` is local, deterministic and runs
  in commit hooks; a network call there would break that: rejected.
- **Surface: a tenth hot tool beside the CLI verb (chosen).**

## Constraints

- **Inherited unchanged.** The hosted-search credential and its resolver (the config
  layer's, once the environment-variable centralisation lands), consent by credential
  presence, the canonical model selector, the transport, sanitised state, request size bounds,
  validated answers, the typed failure taxonomy, the backend-resolved next step, no rag
  calls and no new runtime dependency, as `2026-09-23-typesafe-search-adr` sets them.
  The default test suite needs no network or key.
- **Sanitised options.** Option text is vault text inside a question, which the transport
  sends verbatim; the engine sanitises every option exactly as the transport sanitises
  state, and keys options by generated identifiers.
- **Measured parameters.** Pool of 192 code-ranked candidates; Choice questions of at
  most 32 options, dealt round robin into balanced questions, each with a `none` option;
  a cut of 32 fused candidates; fusion by reciprocal rank with constant 10, Choice
  weighted 2 and each code rank 1, ties broken by stem; `link` verdict at a pair score
  of 0.5. Decision input retains all sections, including custom and repeated headings,
  with Decision, Decision Outcome, Constraints and Implementation first. Long sections
  share the unchanged 6,000-character per-ADR budget, redistributing unused space from
  short sections. Source and candidate clipping is explicit in state and output.
- **Engineering ceilings**, code constants chosen so that no cost depends on the vault or
  the caller, not measured optima:
  - Corpus: at most 5,000 ADR files; a larger ADR directory is refused before any file is
    read. Recall above 534 ADRs is unmeasured.
  - Options: each at most 800 UTF-8 bytes after sanitising, so a Choice request stays
    under the published state bound whatever the script.
  - Declared links: up to 8 declared ADR links outside the cut are judged too, best fused
    rank first; the rest are reported unjudged.
  - Per source: at most 46 evaluations (6 Choice, 40 pair), each with at most the
    transport's attempts, at most 12 in flight, under one 15-second deadline.
  - Per sweep: at most 50 sources (default 10), judged one at a time under their own
    bounds and one 300-second run deadline.
  - Per reply: a source lists only `link` and `weak` verdicts; a sweep lists at most 80
    verdict rows in all; every cut carries its total and a truncation marker.
- **Writes stay narrow.** Applying adds only `link` verdicts the source does not declare,
  to the source's own `related:`, through the one core link writer `vault link add` also
  calls, under the document write lock, once that source is judged. Nothing is removed and
  no candidate is written to. A later failure in a sweep does not undo earlier writes.

## Implementation

A `crossref` package in core owns the classifier in five layers, reusing the search
package's transport and the hosted-search credential rather than duplicating them.

- **Corpus and fingerprint.** Reads the ADR directory, not the whole-vault graph: feature,
  title, status, lead, decision state, declared ADR links, and an artifact fingerprint of
  the body's inline code spans, normalised and weighted by inverse document frequency.
- **Code stage.** Ranks every other ADR by fingerprint overlap and by the source's
  decision text against each candidate's header, and fuses the two. No network.
- **Question set.** One module holds the Choice instruction and its qualifying
  criterion, the three pair Nouls (need to read, same concrete artifact, useless link),
  the relation Choice over the measured labels (supersedes, refines, depends on,
  conflicts, shared artifact, topic only, unrelated), the fusion weights, the measured
  parameters and the ceilings.
- **Engine.** The pool's Choice questions are sent one per request, with the source's
  decision state as state, and fused with the code ranks; a corpus whose candidates fit
  in the cut skips this stage. Each candidate in the cut, and each extra declared link,
  is judged in one request asking the three Nouls and the relation Choice, with the
  source always the `source` side. A pair's score is the mean of need, artifact and one
  minus useless. Verdicts: `link` at the threshold or above; a declared link below it is
  `weak`, never removed, and listed for a curator to read; other candidates are counted
  as dropped. A refused Choice request leaves its candidates at their code rank; a
  refused pair leaves that candidate unjudged; both are counted. When every pair is
  refused the source is `unavailable` with `content_rejected`, never "no links". Any
  other provider failure fails the source with its typed reason.
- **Service.** One entry point judges one ADR. Optional proposed body prose substitutes
  the source in memory, keeping its identity and declared links and marking its status
  proposed. It cannot apply links or be combined with a sweep. The single-source
  deadline starts before corpus and client setup. No accepted body is replaced.
  One entry point also supports sweeps. A sweep judges named ADRs, one feature's,
  the isolated ones (declaring no ADR link), or all, in stem order after an optional
  cursor; its outcome names the last source judged so the next run resumes after it,
  and no sweep state is stored. A sweep skips superseded and rejected sources unless they
  are named; candidates include every status, and each verdict carries the candidate's.

Surfaces are renderers over one backend result with identical fields:

- **CLI.** `vaultspec-core vault adr crossref [REF...] [--feature F] [--isolated] [--all] [--after STEM] [--max-sources N] [--apply] [--body-file PATH] [--json]`; out-of-range counts are
  refused.
- **MCP.** A hot `crossref` tool with a declared output schema, registered whether or not
  a key is present. Normal surface: judges one or several ADRs, may apply; not read-only,
  not destructive, idempotent (a repeated call against the same vault writes nothing
  new), open-world. Read-only surface: judges one ADR, never applies; read-only,
  idempotent, open-world. Both surfaces allow optional `body` prose for one ADR.
  The read-only server rejects arguments other than `ref` and `body`. Reply `coverage`
  reports corpus, pool and judged counts, source clipping, and the count of selected
  candidates with clipped input. Returned clipped candidates carry `input_truncated`;
  `draft` distinguishes a proposed-body result. Reply-row `truncated` stays separate.
- **Decline.** Without a key the outcome is `not_configured` and nothing is sent; a
  failure is `unavailable` with its reason. Both carry the next step hosted search
  resolves for ADRs.

Framework prose adopts the step:

- **`vaultspec-adr`.** When hosted search is configured, the author runs one advisory
  `crossref` pass on the populated draft before offering it. Amendments use `body` or
  `--body-file` to preserve accepted text. Reuse results for the same draft and relevant
  corpus; repeat only for materially changed commitments or evidence. The author reads
  relevant pairs and proposes concrete reconciliation of affected older wording. Labels
  flag, they never decide. No key means local discovery; service failure uses the named
  fallback without gating authoring. Incomplete input or bounded recall cannot certify
  absence of conflict. No network check is added to edit, commit, or deterministic check.
- **`vaultspec-curate`.** ADR-versus-ADR reconciliation starts from bounded `crossref`
  sweeps instead of hand-driven pairwise search; the curator reads the returned `link`
  verdicts and `weak` declared links and judges them.
- **Naming.** The CLI rule and the server instructions name the tool with its CLI
  fallback; personas name the CLI verb.

On acceptance this decision amends `2026-07-09-mcp-tool-schema-adr`, whose hot-tool
ceiling becomes ten tools plus the two gateway tools, and `2026-08-01-mcp-read-only-adr`,
whose restricted allowlist gains `crossref` in its one-ADR, judge-only form.
`2026-09-23-typesafe-search-adr` and `2026-06-28-curator-reframe-adr` are unchanged.

**Amendment note, 2026-09-23, sweep resume**: authorised under the user's advance approval of this feature in session on 2026-09-23 ("it's all yours to build and ship ... the adr, plans all preapproved"). Evidence: `2026-09-23-adr-crossref-audit`, findings sweep-resume, apply-write-failure, failure-fan-out and the re-review's per-source classification and cursor findings. It refines the Service clause and the write constraint; the funnel, bounds and surfaces are unchanged.

- **Cursor.** A sweep's cursor names the last source processed. A source the provider refuses to read is held open while the sweep judges on, past its size by at most two more sources if it must: a later source the provider reads shows the refusal was that ADR's own, and the cursor moves past both. A refusal no read settles, three refusals in a row, or any other failure stops the sweep, reported in `stopped`, with the cursor before the first refusal still open, so resuming retries them. A sweep therefore judges at most 52 sources.
- **Selection.** A sweep needs a selector. Named ADRs stand alone, and so does all; a feature and the isolated ADRs narrow together. Other combinations, an empty feature, and a cursor that names no ADR are refused.
- **Writes.** A link write that fails, including a lock timeout, is reported against its verdict and never discards the judgment; the CLI then exits 1.
- **Spend.** The first failure that decides a source cancels every evaluation not yet sent, and a sweep does not start a source with less than 15 seconds of its budget left.

**Amendment, 2026-09-25, authoring:** Authorized by the user's instruction to apply
the skill audit findings across skills, personas, wording rules and backend, with all
TypeSafe use conditional on the configured API key. Evidence:
`2026-09-25-skill-audit-adr-authoring-audit`. This refines input projection, exposes
coverage, adds nonpersisting amendment input, reduces the source deadline to 15 seconds,
and makes the authoring pass conditional on opt-in. It does not add a tool, automatic
acceptance, mandatory agent delegation, or a repeated review gate.

## Rationale

The chosen funnel is the only measured shape whose evaluations per source are a constant
while recall stays useful: the code stage is linear and free, the Choice stage is a
fixed number of requests whatever the corpus size, and the pair cut is a fixed number of
judgments, which is where accuracy was measured (`2026-09-23-adr-crossref-research`).
Strong links, the ones that change how a decision is applied, mostly survive the cut;
the recall it gives up is concentrated in weak links. Reusing the search stack keeps one
credential, one transport and one consent model for every Jev call core makes. A hot
tool is the only surface that the ADR workflow's orchestrator and read-only agents can
call without a confirmation per ADR, and it keeps a record-in, verdicts-out contract
separate from search's question-in, excerpts-out one. The standing schema it adds is
measured and ratcheted like every other hot tool's.

## Consequences

- **Gains.** New ADRs gain their governing links when written. The corpus can be
  reconciled in bounded, resumable sweeps whose cost ceiling is known before they start:
  typically about 110k to 135k tokens, 33 to 46 evaluations and a few seconds per source.
  Curation stops depending on how well a persona searches.
- **Recall is partial by design.** At 534 ADRs the cut loses about a quarter of all links
  and 9% of strong ones. A sweep may find a missed link from its other end; that recovery
  is unmeasured. The parameters were tuned on two vaults and one model version, so a
  serving model and projection affect results; measured recall is not a permanent guarantee.
- **Surface cost.** A tenth hot tool adds standing schema context to every MCP session.
- **Hollow records.** A template-only ADR yields no useful decision state; its verdicts
  stay weak until it is written.
- **Opens.** The corpus, fingerprint and funnel layers are record-type agnostic, so
  lineage checks and section-level quality signals (`2026-09-23-adr-crossref-research`)
  can reuse them under their own decisions.
