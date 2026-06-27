---
tags:
  - '#reference'
  - '#discovery-benchmark'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - "[[2026-06-26-discovery-benchmark-research]]"
  - '[[2026-06-26-rag-pipeline-enrollment-adr]]'
---

# `discovery-benchmark` reference: `workflow codification suggestions for the builtins discovery pipeline`

## Summary

This reference translates the empirical findings of the `discovery-benchmark` study into
concrete, ready-to-encode suggestions for the firmware under
`src/vaultspec_core/builtins/` - the rules, skills, agent personas, and system prompt that
govern how agents discover and ground feature work. It is the bridge document between the
research and the eventual Phase-2 builtins ADR and edits; it does not itself change
firmware. Every suggestion is evidence-backed (see the companion research document) and is
written to be hedged and parity-safe.

These are suggestions derived from LLM-generated benchmark data under human supervision.
They are decision-support, not law: the firmware author should apply judgement, and the
strongest-supported items (the directed-ADR filter, the locate-then-read-whole sequence,
the cost discipline at scale) should be encoded before the softer ones.

## Codification principles (what the evidence licenses)

1. **Encode a sequence, not a single tool.** The winning strategy is a probe-adaptive
   pipeline (locate cheaply, read the epicenter or nearest analogue whole, confirm with
   targeted grep), not "use semantic search." Firmware prose should teach the sequence.
1. **Make the locate step probe-type-aware.** Code targets, decision/intent targets, and
   small well-named module clusters each have a different cheapest locate move.
1. **Hedge every tool mention.** Semantic search (`vaultspec-rag`) is an optional sister
   tool; every mandate that names it must carry the established fallback (grep plus
   `vaultspec-core vault list`/`status`) for installs without it. Assert no infrastructure
   that may be absent.
1. **Cite only shipped surface (reference parity).** Name only verbs and flags verified
   present in the current engine (0.2.25): `--type docs|vault|code`, `--doc-type adr`, the
   code filters `--language`/`--path`, and the `vaultspec-core status`/`vault list`/`graph`
   verbs. Do not invent a `--type adr`; the taxonomy is area (`--type`) plus doc-type
   filter (`--doc-type`).
1. **Do not duplicate the rag rule.** `vaultspec-rag` ships and installs its own builtin
   rule and MCP; core firmware weaves the discovery mandate into its own personas, skills,
   and system prompt, and must not author a competing rag rule.

## The canonical sequence (proposed firmware prose block)

A single mandate block, suitable for the system fragment and referenced by the discovery
personas and skills. Suggested wording:

> Before grepping blindly or guessing identifiers, locate by meaning, then confirm by
> reading. Discovery is a sequence:
>
> 1. Locate cheaply, choosing the tool by what you seek:
>    - code (where/how something is implemented) - `vaultspec-rag search "<concept and domain nouns>" --type code` (narrow with `--language`/`--path`);
>    - recorded decisions/intent - `vaultspec-rag search "<intent>" --type vault --doc-type adr` (the directed ADR filter), or `vaultspec-core status [target]` and
>      `vaultspec-core vault list` for orientation;
>    - a small, well-named module or folder - list the directory directly.
> 1. Read the epicenter file (or, when extending a feature, the nearest existing analogue)
>    in full - this is almost always the breakthrough.
> 1. Confirm exact symbols, signatures, and insertion points with a targeted grep.
> 1. For decision discovery, close with a directory backstop over the records folder
>    (for example list `.vault/adr/` and filter by feature) - semantic search alone misses
>    lower-ranked or opaquely-named decision records.
>
> When `vaultspec-rag` is not installed, fall back to `vaultspec-core vault list` plus grep
> for the locate step; the sequence is otherwise unchanged.

## Surface-by-surface suggestions

### System fragment (`builtins/system/03-vaultspec.md`)

The "Ground in existing intent" block is the cleanest existing model and already leads with
semantic search. Two additions: (a) name the directed `--doc-type adr` filter for the
decision-grounding half (it currently uses catch-all `--type vault`); (b) add the
locate-then-read-whole-then-confirm sequence as the one-paragraph canonical move so the
lower layers can point to it.

### Skills (`builtins/skills/.../SKILL.md`)

- `vaultspec-research`, `vaultspec-adr`, `vaultspec-code-research` already open with a
  "Ground ... first" step citing semantic search. Upgrade their decision-lookup line from
  catch-all `--type vault` to `--type vault --doc-type adr`, and add the directory backstop
  for ADR completeness.
- These three are the discovery-heavy entry skills; they are where the sequence belongs at
  the orchestration level.

### Agent personas (`builtins/agents/*.md`) - the main gap

The personas that actually perform discovery do not yet encode the sequence. Suggested
per-persona edits, each carrying the hedged fallback:

- `vaultspec-researcher` - currently a methodology-free stub; give it the canonical
  sequence as its discovery method.
- `vaultspec-adr-researcher` - heavily external-source oriented; develop its internal-
  grounding half with the decision-discovery variant (directed ADR filter plus
  `vaultspec-core status`/`vault list`, then read, then the directory backstop).
- `vaultspec-reference-auditor`, `vaultspec-code-reviewer`, `vaultspec-writer`,
  `vaultspec-docs-curator` - currently drive discovery through `rg`/`fd` only; add the
  locate-by-meaning-first step (code variant) with grep retained as the confirm step, not
  the locate step.

### Grounding/implementation guidance

For personas that implement or extend features, encode the grounding meta-pattern: find and
read the nearest existing analogue, then diff the requirements against it. This was the
decisive move in every grounding run and is cheap to teach.

## Cost and scale discipline (worth stating explicitly)

The evidence shows broad keyword discovery cost scales badly with codebase size (roughly
1.3 to 2 times the tokens of the hybrid sequence on an 11k-file tree). Firmware should
discourage broad `Glob **/*` and broad multi-term greps as a locate step on large
codebases, and reserve grep for targeted confirmation. This is a context-economy mandate,
not a style preference.

## What NOT to encode

- Do not assert `vaultspec-rag` as required; always hedge.
- Do not name a `--type adr` (does not exist); use `--type vault --doc-type adr`.
- Do not author a core-owned rag rule; rag owns it.
- Do not over-claim quality gains: the evidence is that semantic/hybrid discovery wins on
  cost and speed at scale and on noise-free decision recall, while quality converges on
  well-architected code. Encode the efficiency and recall claims; do not promise it makes
  agents "smarter."

## Sequencing into Phase 2

This reference grounds the Phase-2 builtins ADR (decision: enrol the discovery sequence and
directed-ADR filter into the personas/skills/system, hedged, parity-safe). Recommended
order of edits: (1) reference-parity path fixes already scoped under
`rag-pipeline-enrollment`; (2) system fragment sequence + directed filter; (3) the three
entry skills; (4) the discovery personas; (5) the grounding meta-pattern. Validate with the
firmware reference greps and the unit gate; no Python behavior changes are implied.

## Sources

Findings and raw data: the companion `discovery-benchmark` research document and
`campaign-data/discovery/` (`runs.jsonl`, `MATRIX.md`, `aeat-groundtruth.md`). Measured on
`vaultspec-rag` 0.2.25.
