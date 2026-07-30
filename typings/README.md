# typings

Type stubs for third-party dependencies that ship no annotations of their own, so
strict-mode checking can reason about them instead of degrading to `Unknown`.

Each stub declares only the surface this project actually calls, so it is deliberately
narrower than the upstream API. When a new upstream call is introduced, widen the stub
in the same change rather than reaching for an ignore comment.
