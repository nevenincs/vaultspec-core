---
tags:
  - '#adr'
  - '#mcp-tool-schema'
date: '2026-09-19'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:9dedc7852363bec6be58d33158a52999449ee0183fc977bd576b3f13ad3780ae'
related:
  - "[[2026-07-09-mcp-tool-schema-adr]]"
  - "[[2026-09-19-mcp-tool-schema-surface-conformance-audit]]"
---

# `mcp-tool-schema` adr: `Proposed amendment: a read-only gateway executor alongside invoke` | (**status:** `proposed`)

## Problem Statement

This record holds a proposed amendment to the accepted gateway decision. It exists as a separate proposed record so the accepted body stays intact while the revision is reviewed, and it is retired once the amendment is applied or declined.

The accepted decision annotates `invoke` as destructive unconditionally, because the catalog it dispatches against mixes mutating and read-only verbs and an MCP annotation is static per tool rather than per call. That record names the cost in its own consequences: a single broad `invoke` forces conservative host confirmation on every long-tail call, including read-only ones. Operating experience since confirms the cost is not theoretical. A host that would auto-approve a read-only tool cannot auto-approve any long-tail read, so orientation verbs that mutate nothing - listing vault documents, reading a graph, reporting status - interrupt the operator exactly as a write would. The catalog already knows more about each verb than the annotation can express; the surface simply has no way to say it.

The question this amendment settles is whether that expressiveness gap is closed by a second advertised tool, and if so, where the read classification comes from.

## Considerations

- An MCP tool annotation is static per tool, not per call. A single executor dispatching a mixed catalog can only carry the most dangerous annotation any of its targets would need, so the conservative hint is correct for `invoke` and cannot be narrowed by making it smarter at call time.
- Hosts differentiate on the read-only hint: it is what makes a tool eligible for auto-approval and, on some hosts, for concurrent dispatch. The hint is the only channel through which that differentiation is available.
- The catalog is built by introspecting the CLI application, so a per-verb attribute is available at the same point and from the same source as the flags and arguments already collected. Nothing new has to be parsed, and the generated marker block that serves as the verb-existence source does not change.
- A classification maintained in the MCP layer would be a second source of truth about verbs, which is the failure mode the accepted record rejected when it refused a hand-curated catalog.
- The audit that grounds this record found a guard that could not fail because it tested a substring. Any new invariant introduced here has to be demonstrably capable of failing, not merely present.

## Considered options

**Q1 - closing the expressiveness gap.** Chosen: a second advertised executor, `invoke_read`, annotated read-only and idempotent, restricted to verbs the catalog classifies as read-only, with `invoke` unchanged beside it. Rejected: varying the annotation by call, which the protocol does not permit. Rejected: dropping the destructive hint from `invoke` and relying on the host to judge each verb, which moves a safety decision to a party that cannot see the catalog. Rejected: promoting individual read verbs to first-class tools, which reopens the surface-breadth problem the accepted record exists to prevent.

**Q2 - where the read classification lives.** Chosen: introspected from each verb's own declaration at catalog build time, defaulting to not-read-only. Rejected: a maintained list in the MCP layer, which is a second source of truth that rots as the CLI surface changes - the same objection the accepted record raised against a hand-curated catalog. Rejected: inferring from the verb path or from the absence of mutating flags, because a heuristic that is wrong once is wrong in the direction of promoting a mutating verb into the auto-approvable path.

**Q3 - failure direction.** Chosen: fail closed. An undeclared verb is not read-only, so it stays behind `invoke`, and a verb absent from the read classification is refused by `invoke_read` before any process starts rather than falling through to the write executor. Rejected: fall-through, which would make the read executor silently equivalent to the write one and defeat the annotation it advertises.

**Q4 - guarding the classification.** Chosen: a build-time invariant that fails catalog construction when a verb declared read-only exposes a mutating flag, plus a test that builds the real catalog and asserts both that the invariant held and that the read set contains the orientation verbs it must. Rejected: trusting the declaration alone, because the declaration is the thing most likely to be wrong and nothing else would notice.

**Q5 - rollout.** Chosen: `invoke_read` and the classification field on `discover`'s verb schemas ship together. Rejected: shipping the executor first, because a caller with no way to learn which verbs are read-only must either guess or attempt and fail, which is worse than the confirmation it replaces.

## Constraints

- The accepted gateway decision stands unchanged except where this amendment narrows it: the catalog remains the single verb-existence source, the denylist applies to both executors, `invoke` keeps its name, semantics and annotations, and the long tail is still never registered as individual tools.
- The generated marker block in the shipped CLI reference does not change shape; the classification is introspected from the application, not added to that block.
- Validation verbs carrying a repair flag stay behind `invoke` whatever they declare.
- The advertised first-class surface stays in single digits plus the gateway.
- Concurrent-request isolation and the pre-spawn argument screens apply identically to the new executor.
- No advertised count appears in the orientation string; its enumeration derives from the registered surface.

## Implementation

A declaration marker on the CLI command callback records that a verb is read-only. Catalog construction reads it alongside the flags and arguments it already collects, and the catalog entry gains a read-only attribute defaulting to false. Construction raises when a verb declared read-only exposes a mutating flag.

`invoke_read` is registered with read-only and idempotent annotations and a closed-world hint, sharing the argument validation, reserved-flag screening, environment composition and subprocess path of `invoke`; it differs only in refusing any verb the catalog does not classify as read-only, and in refusing it before a process starts. A denied verb reports denial rather than misclassification, so the two refusal reasons stay distinguishable. `discover` carries the classification on each verb schema. The read-only server mode registers `invoke_read` and its positive-allowlist test is updated to match.

Verification is by tests that can fail: the invariant test builds the real catalog and asserts the read set is non-empty and contains the orientation verbs; a write verb submitted to `invoke_read` is refused with the subprocess runner patched to raise if it is ever reached; `discover` reports the classification truthfully for a known read verb and a known write verb; and the read-only server advertises exactly its five tools.

## Rationale

The accepted record booked the confirmation cost knowingly and left it standing because the alternative available at the time was a worse surface. What changed is not the trade-off but the observation that the catalog already carries the information the annotation needs; the gap is one of expression, not of knowledge. Adding one tool to express it is the smallest change that recovers host auto-approval for reads, and it leaves the write path exactly as conservative as it was.

Deriving the classification from each verb's own declaration is what keeps this from becoming the hand-curated catalog the accepted record rejected. The declaration sits with the verb, travels with it, and is read by the same introspection that already builds the schema, so the classification cannot drift from the surface independently. Failing closed makes the worst outcome of a forgotten declaration a verb that is harder to reach, never a mutating verb that is easier to approve. The build-time invariant exists because the declaration is a claim, and a claim that nothing checks is the defect pattern the grounding audit documented in this very surface.

## Consequences

Good: read-only long-tail calls become eligible for host auto-approval and for concurrent dispatch on hosts that treat read-only tools that way, which is the cost the accepted record booked and left standing. The classification is derived from the declaration that already defines each verb, so it cannot drift from the surface the way a maintained list would, and the build-time invariant fails loudly rather than silently promoting a mutating verb into the read path.

Bad: the advertised surface grows by one tool, which is a compatibility commitment and consumes context on every request. The classification is a new attribute every future verb should carry, and a verb whose author forgets it is silently confined to the write path - a failure that is safe but invisible until someone notices the verb missing from `invoke_read`. The invariant catches a mutating flag on a read verb; it cannot catch a verb that mutates without declaring a flag, so the declaration remains a claim the author is trusted to make honestly.

Neutral: the advertised count in the orientation string rises again, which is why that string no longer states a count and derives its enumeration from the registered surface. The accepted record's consequence about conservative confirmation narrows rather than disappears: `invoke` keeps it, and keeps it correctly.
