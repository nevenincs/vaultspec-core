"""Meta-contracts for the test suite itself."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.repo]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Every tree that carries committed test code. The library's suites cohabit
#: with the modules they exercise under ``src``; the development instruments
#: and these guards live under ``dev``; the documentation-asset renderers keep
#: their suite beside the output they write, under ``docs/_render``. Naming the
#: trees rather than each cohabiting ``tests`` package inside them is
#: deliberate: a suite added beside a new module is covered by existing,
#: instead of by someone remembering to extend a list.
TEST_ROOTS = (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "dev",
    PROJECT_ROOT / "docs" / "_render",
)


def _test_files() -> list[Path]:
    files: list[Path] = []
    for root in TEST_ROOTS:
        files.extend(root.rglob("test_*.py"))
        files.extend(root.rglob("conftest.py"))
    found = sorted(set(files))
    # An empty corpus passes every meta-contract in this file. `rglob` reports
    # a missing root the same way it reports an empty one, so a renamed tree
    # in TEST_ROOTS would silence these guards rather than fail them.
    assert found, f"no test files found under any of {TEST_ROOTS}"
    return found


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def test_tests_do_not_use_doubles_or_runtime_patching() -> None:
    offenders: list[str] = []
    forbidden_imports = {
        "unittest.mock",
        "mock",
        "pytest_mock",
    }
    forbidden_names = {
        "monkeypatch",
        "mocker",
        "Mock",
        "MagicMock",
        "AsyncMock",
        "patch",
    }
    forbidden_calls = {
        "pytest.skip",
        "pytest.xfail",
        "pytest.importorskip",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "pytest.mark.skipif",
        "patch",
        "patch.object",
    }

    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_imports:
                        offenders.append(f"{_rel(path)}:{node.lineno}: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_imports:
                    offenders.append(f"{_rel(path)}:{node.lineno}: {node.module}")
            elif isinstance(node, ast.arg) and node.arg in forbidden_names:
                offenders.append(f"{_rel(path)}:{node.lineno}: fixture arg {node.arg}")
            elif isinstance(node, ast.Name) and node.id in forbidden_names:
                offenders.append(f"{_rel(path)}:{node.lineno}: name {node.id}")
            elif isinstance(node, ast.Call):
                call_name = _call_name(node.func)
                if call_name in forbidden_calls:
                    offenders.append(f"{_rel(path)}:{node.lineno}: call {call_name}")
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                lowered = node.name.lower()
                if "fake" in lowered or "stub" in lowered:
                    offenders.append(f"{_rel(path)}:{node.lineno}: {node.name}")

    assert not offenders, (
        "Tests must exercise real code paths without mocks, fakes, stubs, "
        "monkeypatching, skips, or xfails:\n  - " + "\n  - ".join(offenders)
    )


def test_json_mode_tests_do_not_mask_stdout_prefixes() -> None:
    offenders: list[str] = []
    prefix_masking_methods = {"find", "index", "split", "partition"}

    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in prefix_masking_methods:
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and first_arg.value == "{":
                offenders.append(f"{_rel(path)}:{node.lineno}: {node.func.attr}('{{')")

    assert not offenders, (
        "JSON-mode tests must parse the whole stdout payload so human prefixes "
        "cannot be hidden:\n  - " + "\n  - ".join(offenders)
    )


#: The guard trees whose corpora are derived rather than named. A guard in
#: `dev/guards/` asserts a repository-wide invariant, so it discovers its own
#: subject by globbing - which is the whole exposure: `Path.glob` and
#: `Path.rglob` report a missing directory and an empty one identically, and
#: neither raises.
_GUARD_DIR = PROJECT_ROOT / "dev" / "guards"

#: The call names that derive a corpus from the filesystem.
_CORPUS_CALLS = ("glob", "rglob", "iterdir")


def _guard_modules() -> list[Path]:
    """Every Python module under ``dev/guards/``.

    A helper rather than a `.rglob` inside the test, because that is the rule
    this file enforces: a corpus derived where nothing asserts it exists is a
    corpus that can vanish silently.
    """
    modules = sorted(_GUARD_DIR.rglob("*.py"))
    assert modules, f"no guard modules found under {_GUARD_DIR}"
    return modules


def _asserts_within(node: ast.AST) -> bool:
    """Whether *node* contains an ``assert`` statement anywhere inside it."""
    return any(isinstance(child, ast.Assert) for child in ast.walk(node))


def _derives_a_corpus(node: ast.AST) -> bool:
    """Whether *node* builds a file corpus by globbing the filesystem."""
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr in _CORPUS_CALLS
        ):
            return True
    return False


def test_every_globbed_guard_corpus_asserts_it_found_something() -> None:
    """A guard that globs must prove its corpus is non-empty.

    Every guard in ``dev/guards/`` reports by collecting offenders and
    asserting the collection is empty. That shape inverts when the corpus is
    empty: no files, no offenders, a pass. And an empty corpus is not
    hypothetical - it is what a renamed directory produces, silently, because
    ``Path.glob`` treats "missing" and "empty" the same way and raises for
    neither.

    Measured on 2026-09-05: with ``.vaultspec/templates/`` moved aside, all
    three guards in ``test_template_annotations.py`` passed. They had been
    validating nothing that any change to that path would have revealed.

    The rule is therefore two-sided. A helper that derives a corpus states
    what it expects to find, and a test never derives one itself - it asks a
    helper. Exempting tests from the first half is what let this guard glob
    `dev/guards/` and pass on 2026-09-05 with that directory renamed away:
    it collected offenders from an empty corpus and, correctly, found none.
    """
    offenders: list[str] = []

    for path in _guard_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        # Module level counts as one scope: a corpus built into a module
        # constant is checked by an assert beside it, not inside a function.
        module_body = [n for n in tree.body if not isinstance(n, ast.FunctionDef)]
        if any(_derives_a_corpus(n) for n in module_body) and not any(
            _asserts_within(n) for n in module_body
        ):
            offenders.append(f"{_rel(path)}: module level")

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not _derives_a_corpus(node):
                continue
            # A test may not derive its own corpus, even when it does assert.
            # Exempting tests is what let this very guard glob `dev/guards/`
            # and pass with the directory renamed away: it collected offenders
            # from nothing and found none. Derivation belongs in a helper,
            # where the rule above applies to it.
            if node.name.startswith("test_"):
                offenders.append(
                    f"{_rel(path)}:{node.lineno}: {node.name} (derives its own corpus)"
                )
            elif not _asserts_within(node):
                offenders.append(f"{_rel(path)}:{node.lineno}: {node.name}")

    assert not offenders, (
        "these derive a file corpus by globbing without proving it is "
        "non-empty, so a renamed directory retires the guard instead of "
        f"failing it: {offenders}"
    )
