"""Tests for dev-repo protection guard.

Issue #88: drop the ``VAULTSPEC_ALLOW_DEV_WRITES`` environment variable
override and gate dev-mode operation on an explicit ``--dev`` flag
plumbed through :func:`guard_dev_repo`.  These tests pin both the
removal of the env-var bypass and the new ``dev=`` parameter contract.
"""

import os
import subprocess
import sys
import textwrap

import pytest

from vaultspec_core.core.guards import (
    DevRepoProtectionError,
    _cached_is_dev_repo,
    guard_dev_repo,
    is_dev_repo,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the LRU cache between tests."""
    _cached_is_dev_repo.cache_clear()
    yield
    _cached_is_dev_repo.cache_clear()


# is_dev_repo ----------------------------------------------------------


def _materialise_source_layout(root):
    """Create the minimum on-disk shape that makes :func:`is_dev_repo` fire."""
    pyproject = root / "pyproject.toml"
    pyproject.write_text('[project]\nname = "vaultspec-core"\n', encoding="utf-8")
    pkg = root / "src" / "vaultspec_core"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    return root


def test_detects_dev_repo_with_matching_pyproject(tmp_path):
    """pyproject ``name`` AND ``src/vaultspec_core/__init__.py`` -> detected."""
    _materialise_source_layout(tmp_path)
    assert is_dev_repo(tmp_path) is True


def test_pyproject_name_alone_is_not_enough(tmp_path):
    """A spoofed pyproject.toml without the source layout is not the dev repo.

    Hardened detection (issue #88): a consumer project that ships a
    pyproject.toml declaring ``name = "vaultspec-core"`` (e.g. a stale
    fork, a copied template, an attacker-crafted file) must not trigger
    the guard.  The corroborating source-layout signal pins us to the
    actual source bearer.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "vaultspec-core"\n', encoding="utf-8")
    # No `src/vaultspec_core/__init__.py` -> not detected.
    assert is_dev_repo(tmp_path) is False


def test_source_layout_alone_is_not_enough(tmp_path):
    """Source layout without a matching pyproject is not the dev repo."""
    pkg = tmp_path / "src" / "vaultspec_core"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    # No pyproject.toml at root -> not detected.
    assert is_dev_repo(tmp_path) is False


def test_ignores_dir_without_pyproject(tmp_path):
    """A directory without pyproject.toml is not the dev repo."""
    assert is_dev_repo(tmp_path) is False


def test_ignores_different_project_name(tmp_path):
    """A pyproject.toml with a different project name is not the dev repo."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "my-cool-project"\n', encoding="utf-8")
    assert is_dev_repo(tmp_path) is False


def test_ignores_malformed_pyproject(tmp_path):
    """A malformed pyproject.toml does not cause a crash."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("this is not valid toml {{{{", encoding="utf-8")
    assert is_dev_repo(tmp_path) is False


def test_ignores_pyproject_without_project_table(tmp_path):
    """A pyproject.toml with no [project] table is not the dev repo."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[build-system]\nrequires = ["hatchling"]\n', encoding="utf-8")
    assert is_dev_repo(tmp_path) is False


# guard_dev_repo (default behaviour, no --dev) ------------------------


def test_guard_raises_on_dev_repo(tmp_path):
    """Without ``dev=True``, guard_dev_repo refuses to mutate the source repo."""
    _materialise_source_layout(tmp_path)
    with pytest.raises(DevRepoProtectionError, match="source repository"):
        guard_dev_repo(tmp_path)


def test_guard_passes_on_normal_dir_without_dev(tmp_path):
    """guard_dev_repo does not raise for a normal project directory."""
    guard_dev_repo(tmp_path)


# guard_dev_repo (--dev flag plumbed through) -------------------------


def test_dev_flag_authorises_source_repo_writes(tmp_path):
    """``dev=True`` allows the operation to proceed in the source repo."""
    _materialise_source_layout(tmp_path)
    # Must not raise.
    guard_dev_repo(tmp_path, dev=True)


def test_dev_flag_in_non_source_repo_raises(tmp_path):
    """``dev=True`` outside the source repo is a misuse and surfaces loudly.

    The flag is the explicit "yes I'm working on the source repo"
    signal.  Passing it in a context where it cannot apply must not be
    a silent no-op; the user's intent is unmet and they should know.
    """
    with pytest.raises(DevRepoProtectionError, match="not a vaultspec-core source"):
        guard_dev_repo(tmp_path, dev=True)


def test_dev_flag_keyword_only_in_signature() -> None:
    """``dev`` is a keyword-only parameter in :func:`guard_dev_repo`.

    Inspect the signature directly rather than calling positionally,
    because static type checkers refuse positional misuse before the
    runtime ``TypeError`` ever fires.
    """
    import inspect

    sig = inspect.signature(guard_dev_repo)
    assert sig.parameters["dev"].kind is inspect.Parameter.KEYWORD_ONLY


# Env-var bypass removed (issue #88) ----------------------------------


def test_env_var_no_longer_bypasses_guard(tmp_path):
    """``VAULTSPEC_ALLOW_DEV_WRITES`` must NOT bypass the guard.

    The env-var override was the original "yes really" mechanism.  It
    was too coarse: it converted the guard into a global no-op for any
    process that inherited the variable, including the install/sync
    logic that wrote the consumer-style gitignore block in the source
    repo (the root cause of issue #88).  The fix removes the env var
    entirely and gates everything on the explicit ``dev=`` parameter.
    """
    _materialise_source_layout(tmp_path)

    script = textwrap.dedent(
        """
        import sys
        from pathlib import Path

        from vaultspec_core.core.guards import DevRepoProtectionError, guard_dev_repo

        try:
            guard_dev_repo(Path(sys.argv[1]))
        except DevRepoProtectionError:
            print("blocked")
        else:
            raise AssertionError("env var bypassed guard_dev_repo")
        """
    )
    for val in ("1", "true", "yes", "True", "YES"):
        env = {**os.environ, "VAULTSPEC_ALLOW_DEV_WRITES": val}
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert result.returncode == 0, (
            f"guard env-var contract failed for {val!r}: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert result.stdout.strip() == "blocked"


def test_guards_module_does_not_reference_env_var() -> None:
    """The env-var name must not appear anywhere in the guards module.

    A residual ``os.environ.get("VAULTSPEC_ALLOW_DEV_WRITES")`` would
    quietly resurrect the bypass; this regression test catches that.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "guards.py"
    text = src.read_text(encoding="utf-8")
    assert "VAULTSPEC_ALLOW_DEV_WRITES" not in text
    # ``os.environ`` should not be needed at all in the guard module
    # after the bypass is removed.
    assert "os.environ" not in text
