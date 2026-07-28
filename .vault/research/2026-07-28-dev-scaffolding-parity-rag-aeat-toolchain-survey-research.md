---
tags:
  - '#research'
  - '#dev-scaffolding-parity'
date: '2026-07-28'
modified: '2026-07-28'
body_schema: 'body-v1'
related: []
---

# `dev-scaffolding-parity` research: `rag aeat toolchain survey`

Two sibling repositories enforce a quality bar this one does not, and the
question was which of their dimensions transfer here and at what thresholds.
The evidence picture: every dimension transfers except two that cannot run and
one that encodes a convention this package does not hold, and none of them can
land at the siblings' own values because this tree measures well outside them.

## Findings

### The sibling toolchains differ in packaging, not in dimension

Both siblings gate the same dimensions. The semantic-search sibling declares
them in `pyproject.toml` and invokes each from a development harness recipe.
The larger application sibling adds a first-party `dev/` Python package holding
custom audit implementations, committed baselines, and a red/amber health
verdict, plus architectural-boundary contracts and a custom pattern-scanner
rule set. The dimension list is otherwise the same, so the packaging choice is
independent of which checks run.

Dimensions surveyed and their disposition here:

| Dimension                  | Tool                                   | Transfers              |
| -------------------------- | -------------------------------------- | ---------------------- |
| Cognitive complexity       | `complexipy@6.2`                       | yes, gating            |
| Cyclomatic complexity      | ruff `C901`                            | yes, gating            |
| Function-size limits       | ruff `PLR0911/0912/0913/0915`          | yes, gating            |
| Module length, class shape | `pylint@4.0` `C0302 R0902 R0904 R0916` | yes, gating            |
| Strict typing              | `basedpyright@1.39`                    | yes, advisory          |
| Dead code                  | `vulture@2.16`                         | yes, advisory          |
| Security posture           | `bandit@1.9.4`                         | yes, advisory          |
| Dependency drift           | `deptry@0.25.1`                        | yes, advisory          |
| Cyclomatic rank ceilings   | `xenon`, `radon` CLI                   | no, cannot run         |
| Import convention          | scoped grep gate                       | no, no such convention |

### Two dimensions cannot run in this repository at all

`xenon` and `radon` both discover configuration by feeding every `[tool.*]`
table of `pyproject.toml` into a `%`-interpolating `configparser`. This
repository's `[tool.pytest.ini_options]` sets `log_cli_format` to
`%(asctime)s [%(levelname)8s] %(name)s: %(message)s`, which raises an
interpolation error before either tool inspects a single file. `radon` is still
usable through its Python API, which performs no configuration discovery, and
that is how the aggregate report reaches it. The cognitive-complexity and ruff
`C901` dimensions cover the overlapping signal, so nothing is lost by dropping
the two CLIs.

### The import-convention gate encodes a convention this package does not hold

The semantic-search sibling forbids absolute intra-package imports and gates on
it. This package is mixed: 1274 `from vaultspec_core.` absolute imports against
941 relative ones. Neither direction is a majority large enough to call it the
existing convention, so adopting either gate would be a rename campaign across
roughly a thousand sites justified by a lint flag. Ruff's `TID252` is the rule
that would enforce the relative-import direction and is disabled for the same
reason.

### Both siblings carry a latent ignore-pattern defect

Both declare their test-tree exclusion as a TOML basic string,
`".*[\\/]tests[\\/].*"`. TOML basic-string escape processing turns `\\` into a
single backslash, so the regex the tool receives is `.*[\/]tests[\/].*`, whose
character class `[\/]` contains only a forward slash - the backslash is read as
an escape of `/`, not as a member. On Windows the pattern therefore never
matches, and the test tree the exclusion names silently enters the gate. This
was observed directly here: before the fix, `pylint` reported four test modules
including a 47-public-method test factory that would have set the class-shape
baseline. The TOML literal-string form `'.*[\\/]tests[\\/].*'` passes both
separators through and matches on either platform.

### This tree measures far outside the sibling thresholds

Census taken 2026-07-28 against `src/vaultspec_core`, production only, 172
modules. The right column is the sibling's own worst production value or the
tool default, for scale.

| Dimension               | Worst here            | Count over tool default | Sibling worst |
| ----------------------- | --------------------- | ----------------------- | ------------- |
| Cognitive complexity    | 253                   | 177 over 15             | 20            |
| Cyclomatic complexity   | 84                    | 191 over 10             | not measured  |
| Statements per function | 214                   | -                       | not measured  |
| Branches per function   | 63                    | -                       | not measured  |
| Arguments per function  | 20                    | -                       | not measured  |
| Module length           | 2782                  | 12 over 1000            | 2955          |
| Instance attributes     | 21                    | -                       | 28            |
| Strict-typing errors    | 8242 across 348 files | -                       | 0             |

Distribution for the two dimensions where the shape matters most. Cognitive
complexity: 57 functions over 30, 76 over 25, 109 over 20, 134 over 18, 166
over 16, 177 over 15. Module length: 3 modules over 2000, 7 over 1500, 8 over
1200, 12 over 1000, 35 over 500. The longest production module is
`src/vaultspec_core/cli/spec_cmd.py` at 2782 lines.

The strict-typing volume is concentrated in five rules -
`reportUnknownMemberType` 2362, `reportUnknownArgumentType` 1756,
`reportUnknownVariableType` 1374, `reportUnknownParameterType` 1269,
`reportMissingParameterType` 1189 - which together are 91% of the total and are
all annotation debt rather than defects. The remaining tail includes 10
`reportPossiblyUnboundVariable` and 2 `reportAttributeAccessIssue`, which are
the only entries that can denote real bugs.

### The advisory dimensions are nearly clean

`vulture` reports 2 findings, both `__exit__` protocol-fixed parameter names at
`src/vaultspec_core/vaultcore/rename_engine.py:188`, and neither is dead.
`deptry` reports 17, of which 4 are runtime declarations for a transport stack
no first-party module imports and 13 are a legacy `[project.optional-dependencies]`
dev extra duplicating the PEP 735 dev group. `bandit` reports 40, of which 38
are LOW and dominated by this project's deliberate subprocess design.

Neither non-LOW finding was a defect, and both are instructive about how the
scanner reads code rather than about this code:

- The B506 "unsafe yaml load" at `src/vaultspec_core/vaultcore/parser.py:73`
  was a FALSE POSITIVE. The loader was already `yaml.CSafeLoader`, falling back
  to `yaml.SafeLoader`; both derive from `yaml.constructor.SafeConstructor`,
  which is exactly what refuses the `!!python/object` tags that would
  instantiate arbitrary objects out of frontmatter. The module bound it to a
  private alias `_SafeLoader`, and bandit's B506 check matches on the loader
  NAME at the call site, so the alias defeated recognition. Dropping the alias
  resolved the finding without changing a single semantic - the safety became
  visible to the scanner instead of being suppressed from it. This is the
  preferred shape of a false-positive resolution here: no `# nosec`, no config
  skip, just code that states its own safety.
- The B108 insecure-temp-path finding was in `hooks/tests/`, which the scan
  should never have measured. See the scoping defect below.

The `bandit` invocation excluded `src/vaultspec_core/tests` by path, which does
not cover nested test trees such as `src/vaultspec_core/hooks/tests/`. Three
findings, including that B108, came from test code the exclusion named but
never reached. A `*/tests/*` glob covers every depth and drops all three.

### Not investigated

The larger sibling's architectural-boundary contracts and custom
pattern-scanner rules were surveyed but not costed for adoption here; both
require declaring a layer model this package has not defined. Duplication
scanning was not measured. Whether the four transport dependencies are
deliberate version floors or removable cruft was referred to a separate
investigation rather than settled here.

## Sources

- `pyproject.toml` (this repository), `[tool.pytest.ini_options]` `log_cli_format`
- `src/vaultspec_core/cli/spec_cmd.py`
- `src/vaultspec_core/vaultcore/rename_engine.py:188`
- `src/vaultspec_core/vaultcore/parser.py:73`
- `complexipy@6.2`, `pylint@4.0`, `basedpyright@1.39.9`, `vulture@2.16`,
  `bandit@1.9.4`, `deptry@0.25.1`, `radon@6.0.1`, `xenon@0.9.3`
- TOML v1.0.0 basic-string escape rules, https://toml.io/en/v1.0.0#string
- Census figures produced by `tools/health_report.py --census` in this
  repository on 2026-07-28.
