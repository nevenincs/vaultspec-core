---
tags:
  - '#adr'
  - '#review-context'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:a3580f08e057ae498268a887f20e833a025bf85984c91fbb8521c342ae75fa72'
related:
  - "[[2026-09-25-skill-audit-review-context-research]]"
  - "[[2026-09-23-typesafe-search-adr]]"
  - "[[2026-09-25-environment-provisioning-adr]]"
---

# `review-context` adr: `Optional selection of review evidence from explicit repository locators` | (**status:** `accepted`)

## Problem Statement

Reviewers can spend context on weak supporting evidence or repeat the same selection across workers. Selection must reduce that overhead without turning hosted inference into a review or verification gate.

## Considerations

The bounded experiment in `2026-09-25-skill-audit-review-context-research` supports a production trial, not a general claim about review accuracy, latency or total cost. Existing hosted transport and credential decisions cover model selection, failure handling and enrollment.

## Considered options

- Supply every discovered passage: preserves detail but consumes reviewer context indiscriminately.
- Apply lexical ranking: cheap and local, but the recorded caller-contract case exposed missed evidence.
- Optionally score explicit candidate passages: chosen for targeted evidence selection with a deterministic fallback.

## Constraints

- The registered TypeSafe credential resolver is the only enrollment path. Explicit disable wins. Missing credentials and hosted failures preserve local review; a configured credential is not proof of connectivity.
- The command reads an explicit Git scope and tracked repository-relative candidate locators. It returns verbatim passages with hashes and reports exclusions and unselected locators. It does not import or call the RAG backend.
- Environment stores, conventional private-key paths, symlinks and paths outside the repository are excluded. Bounded input is sent only through the canonical Jev transport. This is not general secret scanning.
- Ranking is advisory supporting-context selection. It cannot authorize changes, establish a review verdict, suppress required verification or replace the full diff and governing decisions.
- One owner can share a result. Unchanged inputs can reuse judgments with a finite lifetime; hosted reuse still requires enrollment and is distinguished from a successful live call. Failed or incomplete judgments never partially reorder fallback.

## Implementation

We will expose `review context` through the CLI and existing MCP gateway, using one bounded Score batch and discovery-order fallback. The implementation covers collection, credential opt-in, judgment reuse, safe failure reporting, focused tests, documentation and concise review-skill/persona guidance. Working-tree reads are explicitly non-atomic and omit untracked files; an explicit head reads committed evidence.

Accepted under the user's instruction on 2026-09-25 to implement the promising selector while keeping TypeSafe optional and dependent on the current environment's working token. This is cohesive direct work; no sequencing plan is needed. Collection sizes and deadlines are implementation bounds that may be tuned without changing these commitments.

## Rationale

The selector builds on the existing hosted-search and environment-provisioning decisions without changing their contracts. A cold command gives agents a useful tool when discovery yields competing supporting passages, without adding always-loaded context or a mandatory review stage. Explicit locators avoid copying source into agent-authored requests.

## Consequences

A usable key permits sending bounded review content to TypeSafe. A failed request costs one bounded attempt before local continuation. Selection remains incomplete evidence and may miss important context; reviewers must expand it when needed. Broader claims about quality or savings require larger evaluations.
