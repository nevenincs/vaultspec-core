"""Meta-contracts for the test suite itself."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOTS = (
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "src" / "vaultspec_core",
)


def _test_files() -> list[Path]:
    files: list[Path] = []
    for root in TEST_ROOTS:
        files.extend(root.rglob("test_*.py"))
        files.extend(root.rglob("conftest.py"))
    return sorted(set(files))


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
