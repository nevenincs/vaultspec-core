---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S30
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# document once in the agents section the mode field semantics: declared file-mutation intent via harness tools, with the Bash caveat acknowledged (D3)

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Add one paragraph to the Agents section documenting the persona frontmatter `mode:`
  field: it states declared file-mutation intent via the harness file tools
  (Write/Edit); `read-write` personas mutate files directly; `read-only` personas
  carry no Write or Edit tool and return findings as their final message for the
  dispatching orchestrator to persist via `vault add` scaffold plus body-prose edit
  (D3)
- Acknowledge the Bash caveat: the declaration is intent, not a sandbox - Bash can
  technically write files in either mode, so honoring the mode is persona discipline,
  not tooling enforcement
- Run mdformat --wrap 88 on the edited file

## Outcome

The `mode:` field is now defined once, in the system fragment's Agents section, where
every persona's contract is anchored. The research finding that "the `mode:` field
currently guarantees nothing anywhere" is resolved by stating exactly what the field
does guarantee (declared intent) and what it does not (sandboxing), making the S27-S29
return-findings rewordings and the S31 coordinator note interpretable against a single
definition.

## Notes

Placed the paragraph between the dispatch-mechanism bullets and the
artifacts-persisted-in-vault paragraph so the mode semantics precede the persistence
claim that depends on them.
