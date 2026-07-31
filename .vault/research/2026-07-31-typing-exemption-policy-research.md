---
tags:
  - '#research'
  - '#typing-exemption-policy'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
body_hash: 'sha256:fa7aa9f26bc7405b413edd84f67ef3e417d5a59736f11757b495222af0cb1b40'
related:
  - "[[2026-07-28-dev-scaffolding-parity-adr]]"
---

# `typing-exemption-policy` research: `reportPrivateUsage exemption census`

The question is whether the repository's per-directory `reportPrivateUsage`
exemptions for co-located test trees constitute exemption creep - grants issued
before anything needs them - or the encoding of a single categorical rule. The
evidence: 19 entries exist, exactly 2 currently suppress real findings, the
intensional form of the rule is not expressible in the tool, and a repository guard
derives the entry set from the tree and asserts completeness. The evidence favors
reading the set as one categorical decision encoded extensionally; whether that
reading stands, and the resulting policy, is the ADR's to settle.

## Findings

### The census: 19 entries, 2 load-bearing today

`pyproject.toml` carries 19 `[[tool.basedpyright.executionEnvironments]]` entries
setting `reportPrivateUsage = false`, one per co-located `tests/` tree (entries span
`pyproject.toml:375-512`). Measured against the current tree, exactly 2 entries
suppress real findings - 27 `reportPrivateUsage` diagnostics across two test trees -
and the other 17 mask nothing today. The rule stays fully ON for all production
code; every other strict rule stays ON inside the test trees too
(`pyproject.toml:369-373`).

### The intensional rule is not expressible in the tool

`executionEnvironments[].root` matches by literal directory prefix only. A glob root
such as `src/vaultspec_core/**/tests` is accepted, matches nothing, and raises no
warning - verified directly against this tree and recorded in the config itself
(`pyproject.toml:378-390`): a glob "fix" looks correct while checking nothing. A
per-directory `pyrightconfig.json` is never discovered because one config resolves
per invocation, and per-file `# pyright:` header pragmas work but scatter
suppressions through tracked test source, which the project's ban on inline ignores
exists to prevent (`dev/guards/test_automation_contracts.py:697-704`). The only
expressible encodings of "co-located test trees are exempt" are therefore one
literal entry per tree, or nothing.

### A guard derives the set and asserts completeness

`test_basedpyright_private_usage_exemption_covers_every_tests_directory`
(`dev/guards/test_automation_contracts.py:693-726`) walks the tree for co-located
`tests/` directories and asserts every one has a `reportPrivateUsage = false` entry.
The set is machine-derived: no one grants an entry by judgment; the guard makes an
omission loud and self-explaining. Its docstring names the failure mode it
forecloses: a new co-located suite hitting the gate invites the one fix the config's
own comment warns against - making internals public to appease the checker.
Consequence for the option space: dropping the 17 currently-inert entries fails this
guard as written; any drop must also rewrite the guard's completeness contract.

### The principle at stake, and what it targets

The project's stated concern is that an exemption granted before anything needs it
is how a gate stops meaning anything. The concern's target is discretionary
per-case suppression: a human choosing, finding by finding, to silence the gate,
with each grant lowering the bar for the next. The census set has the opposite
anatomy: the scope is a closed category (co-located `tests/` trees), the rationale
is uniform and recorded in place (in-package tests exercise the private internals of
the module they test, a trust-boundary false positive - `pyproject.toml:369-372`),
membership is derived from the tree by a guard rather than chosen, and the exempted
rule is a single diagnostic with everything else left ON. Whether that anatomy
places the set outside the principle's target is the decision, not a finding.

### Alternatives visible in the option space

Dropping the 17 inert entries makes the config need-driven but fails the guard,
requires a load-bearing/inert classifier (running the checker per tree to measure
need), and converts routine test authoring into a two-step dance: hit the gate, then
add the entry - re-litigating the identical categorical question every time with the
publicize-the-internal shortcut always one keystroke away. Keeping the entries with
documentation is the status quo; the config already carries the rationale inline,
but no decision record governs it - `grep -rln reportPrivateUsage .vault/` returns
nothing prior to this feature. A structural single rule is not expressible per the
glob finding. Not investigated: whether future basedpyright versions add glob or
inheritance support for execution environments; the config records the glob behavior
as a judgment about today's tool.

## Sources

- `pyproject.toml:369-512` - the exemption entries, the trust-boundary rationale,
  and the recorded glob-no-op verification.
- `dev/guards/test_automation_contracts.py:693-726` - the completeness guard and
  its docstring.
- Measurement, 2026-07-31: 27 `reportPrivateUsage` findings across two test trees
  with exemptions removed; 17 entries currently suppress zero findings.
