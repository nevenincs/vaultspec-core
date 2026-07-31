# typings

Type stubs for third-party dependencies that ship no annotations of their own, so
strict-mode checking can reason about them instead of degrading to `Unknown`.

Each stub declares only the surface this project actually calls, so it is deliberately
narrower than the upstream API. When a new upstream call is introduced, widen the stub
in the same change rather than reaching for an ignore comment.

`networkx` is the exception to the "ships no annotations" framing: it is typed by the
stubs basedpyright bundles from typeshed, but a handful of the functions this project
calls are declared there without return annotations, so their results degrade to
`Unknown`. The stubs under `typings/networkx/` restate only those.

A stub file here shadows its upstream counterpart whole, with no symbol-level merge, so a
narrow stub silently drops every other symbol the shadowed module defined. That is safe
only where the shadowed module's surface is fully redeclared, or where nothing else
resolves through it; each `typings/networkx/` stub records which case it is in.

Every stub is covered by `dev/guards/test_typings_fidelity.py`, which calls the declared
surface against real input. A `.pyi` is erased at runtime, so that guard - not the type
gate - is what catches an upstream package drifting out from under its declaration. A new
stub needs a new test class there in the same change.
