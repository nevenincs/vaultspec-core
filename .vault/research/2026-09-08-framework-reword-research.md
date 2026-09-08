---
tags:
  - '#research'
  - '#framework-reword'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:a63a055f1ee695c65ccb719a7f9ac137ef6ce465507b623e9e7d0b39d64f4a23'
related: []
---

# `framework-reword` research: `pipeline decision coverage and proportional workflow routing`

The bundled workflow does not consistently distinguish an existing decision that
authorizes execution from a new decision that requires a new ADR. Three independent,
context-free `gpt-5.6-sol` reviews converged that accepted ADRs are reusable and formal
Code Review is plan-only. They also found that decision-free multi-session work has no
coherent route, because horizon language mandates an ADR while the ADR contract forbids
decisionless records. Several adjacent lifecycle contracts disagree across prose,
templates, checks, and tests. The ADR must settle the normalized routing contract and
the authority of each surface before wording changes begin.

## Findings

### Review protocol prevented conclusion anchoring

Three reviewers received the same neutral brief without conversation context. Each
worked read-only from canonical bundled sources, implementation checks, and tests. They
reconstructed direct-work eligibility, ADR creation and reuse, the decision-versus-
execution boundary, formal review cadence, contradictory authorities, and unnecessary-
work paths. Their conclusions were compared by claim rather than majority vote. The raw
responses are session evidence; repository locators below support every converged claim.

### Reviewer A found a dead route between horizon and decision semantics

Reviewer A ranked decision-free multi-session work as the primary contradiction. The
system says such work always gets an ADR, while the record rule limits an ADR to one
decision and the ADR skill enters only for costly-to-reverse decisions
(`src/vaultspec_core/builtins/system/03-vaultspec.md:44`,
`src/vaultspec_core/builtins/rules/vaultspec.builtin.md:23`,
`src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:8`). The writer nevertheless
requires an accepted ADR before planning
(`src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md:8`). Mechanical or lengthy
work with no new decision must therefore invent an ADR, violate a prerequisite, or stop.

Reviewer A also found existing ADR reuse implied but unstated. The writer locates
accepted ADRs and enters ADR only when none exists, while the system says a plan executes
an ADR or cluster (`src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md:8`,
`src/vaultspec_core/builtins/system/03-vaultspec.md:80`). Creation-shaped phrases such as
"gets an ADR" make a duplicate record a plausible reading.

Its other findings were: Research/Reference-only grounding prose conflicts with Audit-
accepting checks; decision, scope, and costly-to-reverse are underdefined; sizing can
over-trigger; generic reviewer metadata can route unplanned verification into formal
Audit; plan grounding has duplicated authorities; and semantic routing lacks tests.

### Reviewer B confirmed reuse and exposed enforcement and tier escalation gaps

Reviewer B concluded that a new plan may execute an existing accepted ADR, including an
ADR tagged for another feature. The writer enters ADR only if an accepted authorizing
record cannot be located, and feature checks explicitly sanction a cross-feature ADR
link (`src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md:8`,
`src/vaultspec_core/vaultcore/checks/tests/test_features.py:74`). "Concurrent" is not
defined in the rule preventing one ADR from spanning concurrent plans
(`src/vaultspec_core/builtins/system/03-vaultspec.md:84`), so historical or inactive
plans may be misread as blocking reuse.

Reviewer B found that accepted status is a prose gate rather than a consistently tested
executable gate. Plan authoring requires accepted ADRs, but plan-backing and grounding
fixtures accept statusless ADR-shaped files
(`src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md:8`,
`src/vaultspec_core/vaultcore/checks/tests/test_features.py:39`,
`src/vaultspec_core/tests/cli/test_check_adr_grounding.py:40`).

It also identified disproportionate tier promotion: several workers at once makes work
multi-week even when short, selecting L4 and external tracking
(`src/vaultspec_core/builtins/system/03-vaultspec.md:35`,
`src/vaultspec_core/builtins/templates/plan.md:53`). L1 has no Phase, but review and
executor surfaces assume Phase close, creating extra or malformed review work
(`src/vaultspec_core/builtins/templates/plan.md:123`,
`src/vaultspec_core/builtins/agents/vaultspec-low-executor.md:38`).

### Reviewer C confirmed the core model and found unsafe ADR transitions

Reviewer C reconstructed the same reuse contract: reuse an accepted ADR unchanged when
it settles the requested decision; amend for refinement; supersede for a reversal or
invalidated rationale; create a separate ADR for a distinct costly-to-reverse choice
(`src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:31`). This model appears only
indirectly and omits unchanged reuse from the ADR skill's existing-record path
(`src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:16`).

Reviewer C found two additional state hazards. An ADR amendment needs approval, but the
skill rewrites the accepted record while its status remains accepted, leaving pending
text indistinguishable from approved text
(`src/vaultspec_core/builtins/system/03-vaultspec.md:87`,
`src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:35`). A reversal can run
supersession before the successor is approved, and a CLI test demonstrates that a
proposed successor can supersede an old accepted ADR
(`src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:38`,
`src/vaultspec_core/tests/cli/test_vault_adr_supersede.py:139`).

It also confirmed cross-feature discovery risk, overloaded grounding terminology,
Research-biased knowledge-gap routing, broad reviewer metadata, conflicting plan-link
authorities, and missing semantic contract tests.

### The three reviews converged on the central contract

| Contract question                                         | Reviewer A                     | Reviewer B                       | Reviewer C                         | Evidence picture                      |
| --------------------------------------------------------- | ------------------------------ | -------------------------------- | ---------------------------------- | ------------------------------------- |
| Can a plan reuse an accepted ADR?                         | Yes, implied                   | Yes                              | Yes                                | Yes, but not stated directly          |
| Does a new plan require a new ADR?                        | No                             | No                               | No                                 | No                                    |
| When is a new ADR needed?                                 | New or changed costly decision | New or unsettled costly decision | New, refined, or reversed decision | Decision change, not execution effort |
| Does decision-free multi-session work have a valid route? | No                             | No                               | No                                 | Corpus contradiction                  |
| Is formal Code Review plan-only?                          | Yes                            | Yes                              | Yes                                | Yes, but metadata is broader          |
| Is Audit valid ADR grounding?                             | Prose/check conflict           | Prose/check conflict             | Prose/check conflict               | Policy choice required                |
| Are plan links ADR-only or flattened?                     | Conflict                       | Conflict                         | Conflict                           | Policy choice required                |
| Can cross-feature ADRs be reused?                         | Implied                        | Yes, tested                      | Yes, tested                        | Yes, discovery is incomplete          |
| Is decision versus execution defined globally?            | No                             | No                               | No                                 | Always-on definition required         |
| Are semantic routing contracts tested?                    | No                             | No                               | No                                 | Scenario guards required              |

The differences are additive findings, not incompatible reconstructions. More readers
cannot infer a unique answer for Audit grounding, plan-link flattening, or decision-free
multi-session routing because the repository itself encodes competing answers.

### Formal review is plan-only, but entry metadata can over-trigger it

Formal `vaultspec-code-review` produces an Audit only for work executed under a plan; a
planless diff is reviewed in the reply
(`src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md:8`). Planned work is
reviewed at Phase close, plan close, and before handoff, with one review for coincident
gates; Step closure does not wait on review
(`src/vaultspec_core/builtins/system/03-vaultspec.md:95`). The reviewer persona's generic
"final verification before done" and the intent table's generic "Verify" can nevertheless
select formal Audit for unplanned work
(`src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:2`,
`src/vaultspec_core/builtins/system/03-vaultspec.md:146`).

### Grounding and plan linkage have no single current authority

System, record rule, ADR skill, and ADR template permit Research or Reference as ADR
grounding (`src/vaultspec_core/builtins/system/03-vaultspec.md:50`,
`src/vaultspec_core/builtins/rules/vaultspec.builtin.md:23`,
`src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:10`,
`src/vaultspec_core/builtins/templates/adr.md:45`). Executable tests also accept Audit
and call it first-class plan grounding
(`src/vaultspec_core/tests/cli/test_check_adr_grounding.py:85`,
`src/vaultspec_core/tests/cli/test_check_adr_grounding.py:191`).

The record rule and writer link plans to governing ADRs, while the plan template and
repair tests also require direct links to each ADR's grounding
(`src/vaultspec_core/builtins/rules/vaultspec.builtin.md:30`,
`src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md:21`,
`src/vaultspec_core/builtins/templates/plan.md:27`,
`src/vaultspec_core/tests/cli/test_check_adr_grounding.py:141`). The ADR must choose
whether evidence is inherited transitively or duplicated on plans.

### Discovery and persisted evidence need separate names

The discovery rule uses grounding for semantic search, whole-file reading, and grep at
every horizon (`src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md:7`). The
pipeline uses grounding for persisted Research or Reference records
(`src/vaultspec_core/builtins/system/03-vaultspec.md:50`). "Sizing never skips grounding"
can therefore make a direct edit appear to require a persisted artifact
(`src/vaultspec_core/builtins/system/03-vaultspec.md:58`).

### The ADR must settle a narrow set of policy choices before rewording

The evidence favors expressing the plan invariant as accepted decision coverage rather
than record creation, but the ADR must settle: the route for decision-free multi-session
work; the coverage test separating execution from a new, amended, or superseding
decision; cross-feature and sequential ADR reuse; concurrent plans; valid ADR grounding
types; direct versus transitive plan grounding; accepted-status enforcement; pending-
amendment and supersession ordering; tier selection for short parallel work; and tier-
aware review cadence. Wording should then centralize each fact once and derive skill,
persona, template, checker, and test language from it.

Not investigated: the preferred policy for each unresolved choice, behavioral testing of
candidate wording with fresh agents, and the implementation cost of checker changes.

### Cohesive Steps and expected file creation need consistent execution rules

The plan template permits a cohesive Step but requires one row per repeated action (`src/vaultspec_core/builtins/templates/plan.md:89`). The executor treats any nonexistent path as a blocker, including a file the Step intends to create (`src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md:25`). The system requires renewed approval even for a corrected path (`src/vaultspec_core/builtins/system/03-vaultspec.md:90`). These rules prevent a broad but cohesive approved revision from being executed proportionately.

The plan template supports Step-level parallelism at L1, while the team skill only assigns Phases or Waves (`src/vaultspec_core/builtins/templates/plan.md:185`, `src/vaultspec_core/builtins/skills/vaultspec-team/SKILL.md:15`). Review must test the combined workflow across these surfaces; isolated document checks cannot establish a coherent route.

## Sources

- `src/vaultspec_core/builtins/system/03-vaultspec.md:35`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:44`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:50`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:58`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:80`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:84`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:87`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:95`
- `src/vaultspec_core/builtins/system/03-vaultspec.md:146`
- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md:23`
- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md:30`
- `src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md:7`
- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:8`
- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:16`
- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:31`
- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:35`
- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:38`
- `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md:8`
- `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md:21`
- `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md:8`
- `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:2`
- `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md:38`
- `src/vaultspec_core/builtins/templates/adr.md:45`
- `src/vaultspec_core/builtins/templates/plan.md:27`
- `src/vaultspec_core/builtins/templates/plan.md:53`
- `src/vaultspec_core/builtins/templates/plan.md:123`
- `src/vaultspec_core/vaultcore/checks/tests/test_features.py:39`
- `src/vaultspec_core/vaultcore/checks/tests/test_features.py:74`
- `src/vaultspec_core/tests/cli/test_check_adr_grounding.py:40`
- `src/vaultspec_core/tests/cli/test_check_adr_grounding.py:85`
- `src/vaultspec_core/tests/cli/test_check_adr_grounding.py:141`
- `src/vaultspec_core/tests/cli/test_check_adr_grounding.py:191`
- `src/vaultspec_core/tests/cli/test_vault_adr_supersede.py:139`
