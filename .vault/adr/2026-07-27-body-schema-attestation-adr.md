---
tags:
  - '#adr'
  - '#body-schema-attestation'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
related:
  - "[[2026-07-27-vault-scale-performance-adr]]"
  - "[[2026-07-27-markdown-feature-scope-adr]]"
  - '[[2026-07-27-body-schema-attestation-reference]]'
---

# `body-schema-attestation` adr: `body-schema provenance warning default` | (**status:** `proposed`)

## Problem Statement

`vault check all` reports 1,049 body-sections provenance warnings across the
corpus (`adr` 99/100, `audit` 59/62, `exec` 668/699, `plan` 88/88, `reference`
20/20, `research` 115/115; `index` 0/116). Every one of these traces to
`resolve_body_schema`'s `missing` source: the document declares no
`body_schema` and no entry for it exists in the legacy-attestation ledger at
`.vaultspec/body-schema-baseline.json`. That ledger has never been populated -
no CLI verb, MCP tool, or migration writes it; the only code that has ever
produced its JSON shape is test setup that hand-constructs it directly. A
warning whose only remedy today is a hand-authored `.vault/` mutation
contradicts the owning-verb mandate this project enforces everywhere else, and
`check_body_sections` currently collapses `missing` into the same diagnostic as
`attestation_required` and `unknown`, even though only the latter two represent
a document or ledger entry making a claim the evidence contradicts. A decision
is needed on the default behavior for the `missing` source before this warning
volume is treated as a backlog to clear or a design gap to close.

## Considerations

- `resolve_body_schema` and `BodySchemaResolution` already distinguish three
  non-attested outcomes by `source`: `missing` (no declaration, no ledger
  entry), `attestation_required` (a declared or ledger-recorded legacy id that
  the evidence contradicts - path absent, hash mismatch, or shape mismatch),
  and `unknown` (a `body_schema` value that is neither `body-v1` nor a
  recognized `legacy-*` id). `check_body_sections` does not currently read
  `source`; it emits the same warning whenever `required_sections` is `None`.
- The ledger file does not exist in this workspace and has no writer anywhere
  in `src/`; `BaselineEntry`'s docstring calls it a "reviewed ledger," meaning
  population is designed as a human-attested act, not an inferred one.
- Several `legacy-*` schemas are byte-identical in `required_sections` to the
  current `body-v1` schema for the same `(DocType, is_summary)` shape (e.g.
  `legacy-adr-v3`, `legacy-audit-v1`, `legacy-exec-v3`, `legacy-exec-v4`,
  `legacy-index-v1`, `legacy-plan-v1`, `legacy-reference-v1`,
  `legacy-research-v2`). Heading text alone cannot disambiguate these from
  `body-v1` or from each other; only the ledger's `(path, sha256)` pair can.
- `2026-07-27-vault-scale-performance-adr` decision D4 states a general rule -
  workspace-scoped facts are read once per run - and names the "baseline
  ledger memoization" as its first application, not as a decision that the
  ledger is populated or that its provenance model changes. That record's
  scope is read-cost, not the attestation contract.
- `2026-07-27-markdown-feature-scope-adr` governs a narrow, unrelated
  boundary (bounding `scan_vault`'s lazy-migration side effect behind an
  opt-in parameter for `check_markdown --feature`); it contains no content on
  body-schema provenance and does not bear on this decision beyond sharing the
  `vault check` surface.
- `check_modified_stamp` already ships a `--fix` path (`atomic_write` plus
  `.bak` safety, exact-match reconciliation) for a structurally similar
  CLI-maintained frontmatter provenance stamp, establishing the safety
  template this project expects of any future mutating checker.
- The CLAUDE.md owning-verb mandate forbids hand-writing `.vault/`
  frontmatter; today the only way to silence a `missing` warning is exactly
  that forbidden act, since no verb exists to populate the ledger or declare
  `body_schema` at scale.

## Considered options

- **Build a populator verb now** (heading-tuple exact-match against
  `BODY_SCHEMA_REGISTRY`, split into an auto-declare tier for `body-v1`
  matches and a ledger-write tier for unambiguous `legacy-*` matches, plus a
  human-review report for the remainder). Rejected: heading-tuple equality is
  not the hash-based body attestation the ledger's own contract requires: the
  registry itself proves at least eight `legacy-*` ids are heading-identical to
  `body-v1` or to each other for the same shape, so a heading-only matcher
  cannot honestly choose among them and would auto-write a ledger entry - or a
  `body_schema` declaration - that is a guess wearing the shape of a
  attestation. It also introduces a new mutating writer subsystem and a
  corpus-wide `.vault/` mutation into a change this project wants tightly
  scoped, and requires its own ADR before landing.
- **Widen self-declaration to trust any registry-known `body_schema` id
  directly, retiring the ledger.** Rejected: this reverses the deliberate
  trust asymmetry `resolve_body_schema` encodes on purpose - `body-v1` is
  trusted by direct declaration precisely because it is the live template a
  document was authored against, while `legacy-*` ids require external,
  path-and-hash-scoped evidence because no such live-authorship guarantee
  exists for them. Collapsing that boundary the same day
  `2026-07-27-vault-scale-performance-adr` treats the ledger as existing,
  load-bearing infrastructure is a premise reversal, not a refinement, and its
  own bulk-declaration step still requires the same unproven heading-match
  judgment the first option makes explicit.
- **Silence the `missing` source by default; keep `attestation_required` and
  `unknown` as warnings (chosen).** `check_body_sections` inspects
  `resolution.source` and skips the diagnostic only when `source == "missing"`.
  A document that declares nothing and has no ledger entry is not making a
  claim the evidence can contradict, so there is nothing to warn about; a
  document or ledger entry that does make a claim - a declared legacy id
  absent from the ledger, a path/hash/shape mismatch, or an unrecognized
  schema id - keeps warning exactly as today. This changes zero validation
  behavior: `required_sections` is `None` for `missing` today and stays
  `None` after, so no section-completeness check is gained or lost for these
  documents; only the redundant, unactionable notice is removed.

## Constraints

- No change to `BODY_SCHEMA_REGISTRY`, `BaselineEntry`, or the ledger file
  format is authorized or required by this decision; the registry stays
  append-only exactly as tested today.
- The fix is confined to `check_body_sections`'s diagnostic-emission branch and
  its module docstring; `resolve_body_schema`'s resolution logic, its `source`
  values, and the `declared`/`attested` trust boundary are unchanged.
- This decision does not authorize populating the ledger, building a `--fix`
  path for provenance, or widening self-declaration; any of those remains a
  separately-decided, separately-ADR'd expansion per the owning-verb mandate.
- `2026-07-27-vault-scale-performance-adr` D4's premise - that the ledger is
  read-once, workspace-scoped, load-bearing state - is unaffected: this record
  changes only what a checker does when the ledger and the document agree
  there is nothing to attest, not whether the ledger exists or how it is read.

## Implementation

`check_body_sections` reads `resolution.source` in addition to
`resolution.required_sections`. When `required_sections` is `None` and
`source == "missing"`, the function continues without appending a
`CheckDiagnostic` for that document. When `source` is `attestation_required`
or `unknown`, the existing warning path is unchanged. The module docstrings
for `check_body_sections` and `BodySchemaResolution` are revised to state the
new default explicitly: absence of a `body_schema` declaration and a ledger
entry is silence, not a finding; only a contradicted or unrecognized claim is
reported. A real-filesystem regression test asserts a document with no
`body_schema` field and no ledger entry produces zero body-sections
diagnostics, while a document declaring a legacy id absent from the ledger, or
one with a hash or shape mismatch against an existing entry, still warns.

## Rationale

The `missing` source is not a case among several equally-live findings; by
construction, because the ledger has never been populated and no pre-existing
document declares `body_schema` outside of scaffold-time injection, it accounts
for the overwhelming majority of the 1,049 warnings and will continue to fire
on every document scaffolded before this feature existed, forever, with no
tool-mediated remedy. A warning that fires true by construction on 93%+ of the
non-index corpus and cannot be honestly cleared without either the forbidden
hand-edit or a not-yet-built, not-yet-decided populator trains operators to
skim past `vault check all` output, eroding trust in the warnings that are
actionable today (`attestation_required`, `unknown`, and the unrelated
checkers in the same report). Silencing `missing` costs nothing this project
currently relies on: no section-completeness validation runs for these
documents before or after the change, so the fix removes noise around an
acknowledged gap rather than disabling an active protection. It is also the
only option of the three that introduces no new mutating capability and no
corpus-wide `.vault/` write, keeping this change reversible with a single-file
diff and leaving the harder, still-open question - whether and how to build a
ledger populator - for a dedicated future ADR informed by real operator
demand rather than warning-volume pressure.

## Consequences

- The 1,049 `missing`-source warnings drop to zero on this workspace without
  any `.vault/` document being touched; `attestation_required` and `unknown`
  continue to surface exactly as today, so any document making a provenance
  claim the evidence contradicts still fails `vault check all`.
- Operators lose default visibility into how much of the corpus remains
  unattested; if that visibility is wanted later, it belongs as an opt-in
  info-level count (e.g. under `--json` or a dedicated report flag), not as a
  per-document warning, and is left unscoped here.
- If a populator or a widened self-declaration mechanism is authorized by a
  future ADR, `missing` should be revisited: once population is tooled, an
  unattested document represents a declined attestation rather than an
  unbuilt remedy, and restoring a lighter-weight nudge at that point would be
  reasonable friction rather than the current unconditional warning.
- This record does not reopen or contradict `2026-07-27-vault-scale-performance-adr`
  D4 or `2026-07-27-markdown-feature-scope-adr`; it narrows one checker's
  default behavior within the boundaries both already leave untouched.
