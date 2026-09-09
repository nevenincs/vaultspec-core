# dev

The development harness: the `just` verbs and every instrument they drive. Nothing here
ships in the wheel.

`toolchain.py` is the registry - it declares each verb and target, so `just` is a thin
delegate and a lane cannot exist without being declared. The instruments it invokes sit
beside it: `audit/` (dependency advisories), `binaries/` (standalone release builds),
`health/` (the code-health report), `statistics/` (transcript analytics), and `smoke/`
(the packaging check CI runs against a built wheel and sdist).

Four modules own what a step communicates, and between them they cover all of it:
`exit_codes.py` says what a status MEANS, `ci_formats.py` what a tool prints FOR
MACHINES, `reporting.py` what a run prints FOR A HUMAN, and `testing.py` what a status
cannot carry at all. The rule the third follows is that the harness owns the VERDICT and
the tool owns the DIAGNOSIS: a read-only gate is declared through `toolchain.gate`, so
on a clean pass it reports one verdict row instead of its tool's house-style narration,
and on a failure it replays the command and everything it printed. Set
`VAULTSPEC_VERBOSE=1` to stream every step instead.

The fourth covers the gap that rule leaves. A test lane's exit code says whether
anything failed and cannot say how many tests there were, so a lane narrowed by a typo
passes and reads like the full suite. Every lane is declared through `toolchain.lane`,
which attaches a JUnit record; the harness reads the population back and reports it —
run, skipped, and the slowest test when one is genuinely slow. That last part is why no
standing duration reporter is configured: a flag prints its header whether or not
anything crossed the floor, and this speaks only when there is an outlier.

`guards/` is the exception to the cohabitation rule. Every other test in this repository
lives beside the module it exercises; these have no module to sit beside, because their
subject is this checkout's own committed configuration - the CI contracts, the packaging
metadata, the stub fidelity, the handbook drift. They carry the `repo` marker, which is
what gates them, not their location.
