---
tags:
  - '#adr'
  - '#typesafe-search'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:f8cf7c0b26d8849404e4174229ae52c23a21ea0b0fda4b69632d8e37338a82e4'
related:
  - "[[2026-09-23-typesafe-search-research]]"
  - '[[2026-08-26-rag-search-exposure-adr]]'
  - '[[2026-07-09-mcp-tool-schema-adr]]'
  - '[[2026-08-01-mcp-read-only-adr]]'
  - '[[2026-08-23-envelope-optimization-adr]]'
  - '[[2026-02-16-environment-variable-adr]]'
---

# `typesafe-search` adr: `hosted vault search on TypeSafe Jev, with rag as the agent-level fallback` | (**status:** `proposed`)

## Problem Statement

Agents and users ask the vault natural-language questions: why a decision was taken,
which constraint applies, what a limit is. Core cannot answer them. `find` matches
identifiers only. The semantic path is a prose instruction to run rag, and rag returns
records without the passage that answers.

TypeSafe Jev returns calibrated typed judgments. The evaluation in
`2026-09-23-typesafe-search-research` shows that Jev can rank records and locate the
answering passage in the vault as stored on disk. It needs no index, and it abstains
when nothing answers. The user asked for this engine to become primary, enrolled by a
TypeSafe key in the executing environment, with rag as the fallback. Doing so puts
core's first network call, first secret, and first external data flow into a surface
that governing decisions keep local, fixed and root-bound. The terms need deciding
before any code lands.

## Considerations

- **Retrieval quality.** On held-out queries a two-stage Jev engine ranked the right
  record first in 0.83 of cases, against rag's 0.72, and located the answering excerpt
  in 13 of 18 cases, against rag's 1. It abstains where rag cannot, and misses answers
  that live only in body detail (`2026-09-23-typesafe-search-research`, the
  evaluation, abstention and held-out findings).
- **Request bounds.** Stage 1 must see summaries, not full records: 64k tokens per
  request, 255 options per Choice, and accuracy that falls with irrelevant state (same
  research, request bounds).
- **Content blocking.** A Cloudflare rule rejects 2.8% of vault records unless the
  quoting characters are mapped. The rejection is an HTML 403, distinct from a
  credential failure (same research).
- **No rag inside core.** `2026-08-26-rag-search-exposure-adr` forbids core calling,
  importing or proxying rag, and requires a tool list that does not vary with the
  environment.
- **Tool budget.** `2026-07-09-mcp-tool-schema-adr` caps first-class tools at single
  digits plus the gateway. Eight are registered today.
- **Read-only allowlist.** `2026-08-01-mcp-read-only-adr` allowlists `status`, `find`,
  `discover` and a validation-only `check` in read-only mode.
- **Envelope budget.** `2026-08-23-envelope-optimization-adr` bounds discovery replies
  at 4,000 tokens, with a total and a truncation marker.
- **Variable naming.** `2026-02-16-environment-variable-adr` requires `VAULTSPEC_`-
  prefixed variables documented in `.env.example`.

## Considered options

**Engine.**

- Keep `find` plus the rag guidance. Rejected: no body-aware ranking, no excerpt, no
  abstention.
- Jev over every record's full text per query. Rejected: about 1.2M tokens per search,
  bound by the rate limit, and accuracy loss from irrelevant state.
- Jev as a reranker over rag's recall. Rejected: that is rag's own hosted mode, and
  core may not call rag.
- One Noul per record summary as the recall stage. Rejected: it lost four gold records
  that grouped Choice kept.
- Grouped Choice over summaries, then a full read of the shortlist. **Chosen.**

**Fallback without a key.**

- Core calls rag. Rejected: it supersedes the rag-exposure decision and imports rag's
  service failure surface.
- In-process BM25 answers in rag's place. Rejected: it ranks below rag and would steer
  agents away from the better fallback.
- A typed "not configured" outcome, plus generated guidance that routes agents to rag.
  **Chosen.**

**Transport.**

- `typesafe-sdk`. Rejected: its API broke twice in its first week of releases.
- A stdlib client against the single published endpoint. **Chosen.**

**Surface.**

- CLI and gateway only. Rejected: `invoke` demands host confirmation on every call.
- A tool registered only when a key is present. Rejected: an environment-dependent
  tool list.
- A first-class `search` tool that is always registered, also in read-only mode, plus
  a CLI verb. **Chosen.**

**Credential source.**

- The workspace `.env` in every install mode. Rejected: a cloned repository could
  supply credentials to a globally installed tool.
- The process environment only. Rejected: it fails the requested development-
  dependency workflow.
- The process environment, then the workspace `.env` in DEPENDENCY or DEV mode.
  **Chosen.**

## Constraints

- **Credential.** Enrollment is `VAULTSPEC_CORE_TYPESAFE_API_KEY` alone.
  - The generic `TYPESAFE_API_KEY` and rag's variable never enrol core.
  - The key is read from the process environment. Only when it is absent there, and
    the workspace declares DEPENDENCY or DEV install mode, is it read from the
    workspace-root `.env`, and only that one variable.
  - The endpoint, model and every other setting are code constants that no `.env`
    can change.
  - The key never appears in output, logs, diagnostics or errors. Surfaces report only
    whether it is configured and from which source.
- **No rag.** Core still calls no rag API, imports no rag module and opens no socket to
  rag. `2026-08-26-rag-search-exposure-adr` holds unchanged.
- **Fixed tool list.** The MCP tool list stays a pure function of core's version.
  `search` is registered whether or not a key is present.
- **Filters in code.** Explicit filters (record type, feature, date) are applied in
  code before any model call. The model never widens or overrides them.
- **Verbatim excerpts.** Returned excerpts are the record's own text, addressed by
  local block identifiers. The model never authors returned text.
- **Pinned model.** The model is pinned by version ID (`jev-1.13.0` at adoption), not
  a moving alias. Question texts, weights and thresholds live in one module.
- **Sanitised requests.** Model-facing text maps backticks and angle brackets to
  typographic equivalents. Every request is size-checked against the published request
  bounds before sending.
- **Validated answers.** Every answer is validated against the question it answers:
  keys, finite probabilities, and options.
- **Separate failure types.** Credential rejection, content rejection, rate limiting,
  transport failure and deadline expiry are distinguished.
  - A content rejection makes only that record unscored.
  - Any other failure yields a typed unavailable outcome, never partial rankings mixed
    with unscored records.
- **Envelope.** Replies fit the discovery budget of
  `2026-08-23-envelope-optimization-adr`. The default is 5 results, with a hard
  ceiling. Excerpts are bounded at a line boundary, and every reply carries a total
  and a truncation marker.
- **Dependencies.** No new runtime dependency.
- **Tests.** The default suite needs no network or key. Live evaluation runs only on
  explicit selection.

## Implementation

A search package in core owns five layers, top to bottom.

- **Corpus.** It reads vault records from disk per query. From each record it derives
  a summary (title, lead, distinctive headings) and fenced-code-aware paragraph blocks
  with line ranges.
- **Question set.** One module holds every question text, option, weight, threshold and
  the pinned model ID.
- **Engine.** Hard filters are applied first.
  - Stage 1 sends the query as state. There is one Choice per record type over
    summaries, each with a `none` option, packed into bounded requests run
    concurrently. A Choice classifying the kind of record the query needs rides in one
    of those requests, because it asks about the same state.
  - The shortlist is the leaders per type, plus an in-process lexical top-N.
  - Stage 2 reads each shortlisted record in full, in windows under the state bound.
    For each window it asks whether the record answers the query, whether it is about
    the query's subject, and whether it contradicts a premise of the query (Nouls).
    A Choice with an explicit "no block answers" option picks the answering block. A
    second block is returned when its probability is at least a set floor.
  - Records rank by the answer probability plus a weighted record-kind probability.
    That weight held on held-out queries. A per-record Score and a finalist Choice
    were tested and are not used: the Score cannot separate sibling records, and the
    finalist Choice added latency without a held-out gain.
  - The highest answer probability becomes an `answered` verdict against a threshold.
  - Premise conflicts are reported as their own flag, not folded into the ranking.
- **Transport.** A stdlib HTTPS client with the properties listed under Constraints,
  plus persistent connections, bounded concurrency, a per-search deadline, and
  backoff that honours `retry-after`.
- **Credential resolver.** It implements the precedence in Constraints and reads the
  workspace install mode from the existing workspace-mode machinery.

The engine is exposed three ways:

- **MCP tool.** `search` is annotated read-only, idempotent and open-world. It joins
  the first-class set, making nine tools plus the gateway, and the read-only allowlist.
- **CLI verb.** `vaultspec-core vault search`.
- **`status` field.** Hosted search reports as configured or not configured. This is
  local configuration, not liveness.

When no key is configured, both surfaces return a typed `not_configured` outcome whose
remediation names the rag invocation from the shared discovery vocabulary. The
discovery guidance is regenerated to route agents to core's search when it is
configured, and to rag otherwise. On acceptance, this decision amends the tool
enumeration of `2026-07-09-mcp-tool-schema-adr` and the restricted allowlist of
`2026-08-01-mcp-read-only-adr`, each by adding `search`.

## Rationale

The chosen engine is the only evaluated design that meets all three requirements the
user set: the right record, the right excerpt, and an honest "nothing answers". It does
so within the request bounds, and without an index that can go stale or a GPU service
that can be down (`2026-09-23-typesafe-search-research`). Grouped Choice wins stage 1
because a relative choice among one record type's summaries recalled what absolute
per-summary judgments dropped. The full read of the shortlist gives the absolute
answer, subject and premise signals that a relative ranking cannot.

Routing the fallback at the agent layer delivers "rag when there is no key" without
reopening the rag-exposure decision. Keeping rag out of core's process keeps rag's
failure surface out of core's contract. A typed `not_configured` outcome keeps the tool
list invariant and tells the caller exactly what to run instead.

The stdlib transport wins on stability and control. The wire contract is one endpoint,
the SDK's API is churning, and the content-rejection case needs the raw status and body.

The credential precedence satisfies the requested development-dependency workflow.
Pinning the endpoint and model in code means repository content can at most supply a
key, never redirect one.

## Consequences

**Gains.**

- Vault search answers with the passage, with its line range, and with a verdict on
  whether anything answers. Excerpt location is where rag scored zero.
- Nothing needs provisioning beyond one environment variable.
- Results always reflect the vault on disk.

**Costs and risks.**

- **Data egress.** Vault text is sent to `api.typesafe.ai` on every search. The key's
  presence is the only consent, and read-only mode now includes an external data flow.
- **Latency and spend.** About a second and about half a cent per search.
- **Throughput.** Account rate limits bound it to roughly 75 searches a minute per key.
- **Vault size.** Stage-1 cost grows linearly with vault size, so a much larger vault
  will need a pre-filter decision later.
- **Settings.** The kind weight held on 18 held-out queries. The `answered` threshold
  abstained on 3 of 5 unanswerable questions across both sets, so it needs a larger
  labelled set before an empty result is treated as proof of absence.
- **Recall.** Summary-based recall misses answers that live only in body detail: 2 of
  18 held-out queries, both of which rag ranked first. The "not configured" routing
  keeps rag available to agents, but a configured key does not. Deepening the lexical
  union is the first remedy to measure, on a fresh query set.
- **Blocking rule.** Correctness depends on a third party's blocking rule staying
  within what the sanitiser covers. A new trigger would surface as unscored records,
  not a wrong answer.
- **Model upgrades.** Each Jev upgrade is a deliberate re-evaluation, not a silent
  change.

**Pathways.**

- The same question module can serve other judgments over vault records, such as
  finding which accepted decisions govern a plan.
- vaultspec-rag should treat HTML 403 as a content rejection rather than a credential
  failure. That fix is rag's to make.
