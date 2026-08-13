# Third-party typing boundaries

This reference explains how VaultSpec describes incomplete third-party typing without
claiming APIs that the installed packages do not provide.

## Definitions and failure model

A **declaration** is a hand-written `.pyi` file that describes only the third-party API
VaultSpec calls. BasedPyright consumes it; Python never imports it. A declaration cannot
create or modify runtime behavior. Widen it in the same change that introduces a new
owned call.

A **runtime surface** is the actual set of classes, functions, attributes, and return
shapes supplied by the installed dependency. In this reference, **owned code** means
VaultSpec code maintained in this repository. Local declarations cover the third-party
API that owned code uses, not the complete upstream API. Because a local `.pyi` shadows
its upstream module wholesale instead of merging symbols, omitted symbols can disappear
from static resolution.

A **fidelity test** calls the genuine installed package with trivial real input. It
checks declared types, attributes, and coarse invariants while avoiding unstable exact
scores or layout. This detects dependency drift that static analysis cannot.

An **untyped adapter** is an owned runtime boundary that admits the dependency as `Any`,
calls the real API dynamically, validates the output shape, normalizes it when
necessary, and returns a stable type defined by owned code.

Treat divergence between declarations and the runtime surface as a boundary failure. The
[NetworkX runtime boundary](#networkx-runtime-boundary) shows this failure mode and its
remedy.

Do not assume every affected dependency lacks annotations; its usable static surface may
instead be absent or incomplete. In this reference, **stub** means only a `.pyi` file,
never a test double.

## Contributor setup and verification

Use Python `>=3.13,<3.14`. For a fresh clone or worktree, install
[uv](https://docs.astral.sh/uv/getting-started/installation/) and
[just](https://just.systems/man/en/packages.html), then run `just bootstrap`. This is
the canonical provisioning path and performs a locked development dependency sync. Use
`just deps sync` only for a narrow environment refresh.

Keep third-party declarations under the root `typings/` directory. BasedPyright
discovers it through the default `stubPath` of `./typings`; the project intentionally
does not set `stubPath` explicitly. The `[tool.basedpyright]` configuration in
[`pyproject.toml`](../pyproject.toml) analyzes `src`, `dev`, and `docs`, targets Python
3.13, enables strict mode, and adds curated diagnostics. See the
[BasedPyright configuration reference](https://docs.basedpyright.com/latest/configuration/config-files/)
for configuration semantics.

For declaration changes, run the focused test before the repository gates:

- `uv run --no-sync pytest -q dev/guards/test_typings_fidelity.py` checks focused
  declaration fidelity.
- `just test repo` runs the broader repository-health guard lane that includes the
  fidelity coverage.
- `just lint type-strict` runs the strict BasedPyright gate enforced by CI.
- `just lint` runs the complete lint gate, including BasedPyright and the separate Ty
  checks.

See [`dev/README.md`](../dev/README.md) for the contributor harness overview and the
[`justfile`](../justfile) for the canonical setup recipe.

## Declaration inventory

VaultSpec maintains exactly four declaration files for three packages. Each dependency
specifies a minimum version without a maximum version, so its installed version can
change when the lockfile is updated.

| Package             | Declaration file                                       | Declared surface                                                                               | Real-fidelity coverage                                                                                                  |
| ------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `phart>=0.5.0`      | [`phart/__init__.pyi`](phart/__init__.pyi)             | `ASCIIRenderer`, its graph member, constructor options, and `render() -> str`                  | Constructs a genuine renderer with a real directed graph, checks graph identity, and verifies nonempty label rendering. |
| `radon>=6.0.1`      | [`radon/complexity.pyi`](radon/complexity.pyi)         | `ComplexityBlock`, `cc_rank`, and `cc_visit`                                                   | Checks genuine function and class blocks, reads their attributes, and verifies grade strings.                           |
| `radon>=6.0.1`      | [`radon/metrics.pyi`](radon/metrics.pyi)               | `mi_visit -> float` and `mi_rank -> str`                                                       | Invokes the real functions.                                                                                             |
| `ruamel.yaml>=0.18` | [`ruamel/yaml/__init__.pyi`](ruamel/yaml/__init__.pyi) | `YAMLError`, `YAML`, `preserve_quotes`, `width`, the constructor, `indent`, `load`, and `dump` | Uses actual load and dump operations, quote preservation, and the exception subclass.                                   |

The [fidelity tests](../dev/guards/test_typings_fidelity.py) do not independently
exercise every optional argument and therefore do not provide exhaustive API validation.

## Authoring rules

- Declarations must reflect observed behavior in the installed runtime for the consumed
  API, not exhaustive upstream coverage.
- Declare only the surfaces owned code calls. When adding an upstream call, widen the
  declaration and add matching genuine-runtime fidelity coverage in the same change; do
  not use ignore comments.
- A local `.pyi` file shadows the entire upstream module; symbols do not merge. Verify
  import and re-export resolution so a narrow declaration does not silently remove
  symbols.
- Reject generics and return contracts that observed runtime behavior does not support.
  A clean static check cannot establish `.pyi` fidelity.
- Stable owned return contracts are allowed when an adapter validates or normalizes real
  untyped results.
- Tests must use genuine installed libraries without test doubles and assert coarse,
  stable invariants instead of volatile exact metrics or layout.
- Do not claim coverage of every optional argument or the full upstream API.

## NetworkX runtime boundary

The repository does not own NetworkX `.pyi` overrides. NetworkX 3.6 graph classes lack
runtime `__class_getitem__`, so typeshed-only forms such as `Graph[T]` and `DiGraph[T]`
must not become repository-owned runtime types.

The canonical adapter,
[`networkx_runtime.py`](../src/vaultspec_core/graph/networkx_runtime.py), localizes
`NetworkXGraph = Any` and owns graph construction and operations with problematic
untyped returns. It:

- Creates real directed graphs.
- Validates that node-link dictionaries have string keys.
- Validates reconstructed and ego results as real directed graphs.
- Accepts non-boolean numeric density values and normalizes them to `float`.
- Runtime-checks actual `DiGraph` instances.

Keep runtime-boundary validation in the adapter. Other NetworkX algorithm calls may
remain in their owning modules.

[`test_networkx_runtime.py`](../src/vaultspec_core/graph/tests/test_networkx_runtime.py)
exercises real graph mutation, node-link round-trips, ego radius, and density. Keep
NetworkX behavior in unit tests, not in `.pyi` fidelity tests.

Verify the boundary with
`uv run --no-sync pytest -q src/vaultspec_core/graph/tests/test_networkx_runtime.py`,
`just lint type-strict`, and `just test unit`. Use the focused fidelity command above
for `.pyi` declaration fidelity. `just test repo` includes that coverage in the broader
repository-health guard lane; it is not the NetworkX boundary gate.

## References

### Repository

- [Third-party declarations: phart](phart/__init__.pyi) — renderer surface.
- [Third-party declarations: radon complexity](radon/complexity.pyi) — complexity API.
- [Third-party declarations: radon metrics](radon/metrics.pyi) — maintainability API.
- [Third-party declarations: ruamel.yaml](ruamel/yaml/__init__.pyi) — round-trip YAML
  API.
- [Declaration fidelity tests](../dev/guards/test_typings_fidelity.py) — real-package
  contract checks.
- [NetworkX runtime adapter](../src/vaultspec_core/graph/networkx_runtime.py) —
  validated untyped boundary.
- [NetworkX runtime adapter tests](../src/vaultspec_core/graph/tests/test_networkx_runtime.py)
  — real-runtime behavior.
- [Project configuration](../pyproject.toml) — dependency bounds and type-checker
  policy.
- [Setup recipes](../justfile) — bootstrap and verification commands.
- [Development harness](../dev/README.md) — tool and guard organization.
- [VaultSpec Core issue tracker](https://github.com/nevenincs/vaultspec-core/issues)

### Upstream documentation

- [BasedPyright configuration](https://docs.basedpyright.com/latest/configuration/config-files/)
- [BasedPyright type stubs](https://docs.basedpyright.com/v1.28.0/usage/type-stubs/)
- [phart package](https://pypi.org/project/phart/)
- [radon API](https://radon.readthedocs.io/en/stable/api.html)
- [ruamel.yaml API](https://yaml.dev/doc/ruamel.yaml/api/)
- [NetworkX reference](https://networkx.org/documentation/stable/reference/index.html)
