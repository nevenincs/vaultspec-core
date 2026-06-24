---
name: vaultspec-codify
---

# Project rules are shipped, not manufactured by default

vaultspec ships the builtin rules that describe how to work. Growing the project rule
set is **not** a routine output of doing work, **not** a pipeline phase, and **not**
something the framework asks you to do on your own initiative. A review that surfaces a
durable lesson records it in the vault (`.vault/audit/...`, `.vault/adr/...`); it does
not oblige you to mint a standing rule.

Author a new project rule **only when the user explicitly requests it** - "codify this",
"promote this to a rule". On that explicit request, and only then, invoke the on-demand
`vaultspec-codify` skill, which carries the durability bar, the authoring path
(`vaultspec-core vault rule promote` from an audit, or `vaultspec-core spec rules add`
otherwise), and the supersession discipline.

Absent an explicit request, do not codify. The durable decision already lives in the
vault, and the next agent reaches it by retrieval -
`vaultspec-rag search "<intent>" --type vault` - rather than by inheriting a restated
copy in always-on context. Prefer discovering the decision over duplicating it as a
rule.
