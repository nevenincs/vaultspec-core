# dev

The development harness: the `just` verbs and every instrument they drive. Nothing here
ships in the wheel.

`toolchain.py` is the registry - it declares each verb and target, so `just` is a thin
delegate and a lane cannot exist without being declared. The instruments it invokes sit
beside it: `audit/` (dependency advisories), `binaries/` (standalone release builds),
`health/` (the code-health report), `statistics/` (transcript analytics), and `smoke/`
(the packaging check CI runs against a built wheel and sdist).

`guards/` is the exception to the cohabitation rule. Every other test in this repository
lives beside the module it exercises; these have no module to sit beside, because their
subject is this checkout's own committed configuration - the CI contracts, the packaging
metadata, the stub fidelity, the handbook drift. They carry the `repo` marker, which is
what gates them, not their location.
