"""Tests binding core's advisory rag floor to a single declaration.

Two duties, both of which currently exist nowhere and are the cheapest honest
version of maintaining a constraint about a package core does not depend on:

1. The floor is declared once. A second version literal is how the existing
   ``>=0.3.8`` dev pin drifted a full minor release behind rag without anything
   noticing - nothing consumed it, so nothing could notice.
2. Core never writes a ``minimum_version`` onto a distribution entry it does
   not own. That map's floor is an input to the owning package's own skew gate,
   so writing one there would be actuation, not advice.

See ``.vault/adr/2026-08-26-rag-search-exposure-adr.md``.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from vaultspec_core.core.diagnosis.collectors_companion import (
    RAG_DISTRIBUTION_NAME,
    RAG_MINIMUM_VERSION,
)
from vaultspec_core.core.workspace_mode import CORE_DISTRIBUTION_NAME

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_SRC = _REPO_ROOT / "src"


def _dev_group() -> list[str]:
    """Return the PEP 735 ``dev`` dependency-group entries."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    groups = data.get("dependency-groups", {})
    return list(groups.get("dev", []))


class TestSingleDeclaration:
    def test_dev_group_pin_matches_the_constant(self):
        """The dev pin and the constant are one decision, not two."""
        pins = [p for p in _dev_group() if p.startswith(RAG_DISTRIBUTION_NAME)]
        assert len(pins) == 1, f"expected exactly one rag pin, got {pins}"
        assert f">={RAG_MINIMUM_VERSION}" in pins[0], (
            f"dev pin {pins[0]!r} disagrees with RAG_MINIMUM_VERSION "
            f"{RAG_MINIMUM_VERSION!r}; the floor is one decision and must be "
            f"changed in one place"
        )

    def test_rag_is_never_a_runtime_dependency(self):
        """Core declares no runtime or published-extra dependency on rag."""
        data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
        project = data["project"]
        runtime = project.get("dependencies", [])
        assert not any(RAG_DISTRIBUTION_NAME in dep for dep in runtime)
        for extra_deps in project.get("optional-dependencies", {}).values():
            assert not any(RAG_DISTRIBUTION_NAME in dep for dep in extra_deps)

    def test_constant_is_the_only_rag_version_literal_in_src(self):
        """No second hardcoded rag version anywhere under ``src``.

        The constant's own module is exempt - it is the declaration - as is
        this test, which must name the version to check it.
        """
        pattern = re.compile(
            re.escape(RAG_DISTRIBUTION_NAME) + r"[^\n]{0,20}?\d+\.\d+\.\d+"
        )
        offenders: list[str] = []
        for path in _SRC.rglob("*.py"):
            if path.name in ("collectors_companion.py", Path(__file__).name):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(text):
                offenders.append(str(path.relative_to(_REPO_ROOT)))
        assert not offenders, f"second rag version literal found in: {offenders}"


class TestNoForeignFloorWrites:
    """Core must not write a floor onto a distribution it does not own."""

    def test_no_core_call_site_writes_a_foreign_floor(self):
        """No core call site passes a non-core package with a floor.

        Checked over core's real source rather than by patching the writer,
        because the property is static: it is about which call sites exist,
        not about what one probe run happens to do. rag writes its own entry
        through this same core function and reads its floor back into its own
        skew gate, so a floor written there by core could make rag refuse its
        own invocation.
        """
        offenders: list[str] = []
        for path in (_REPO_ROOT / "src").rglob("*.py"):
            if path.name.startswith("test_"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "write_package_declaration(" not in text:
                continue
            for call in re.findall(r"write_package_declaration\((.*?)\)", text, re.S):
                if "minimum_version" in call and CORE_DISTRIBUTION_NAME not in call:
                    normalized = " ".join(call.split())
                    if "RAG" in normalized or RAG_DISTRIBUTION_NAME in normalized:
                        offenders.append(f"{path.name}: {normalized[:120]}")
        assert not offenders, (
            f"core writes a minimum_version for a distribution it does not own: "
            f"{offenders}"
        )

    def test_probe_writes_nothing_at_all(self, tmp_path: Path):
        """The probe is read-only: it leaves no file behind."""
        from vaultspec_core.core.diagnosis.collectors_companion import (
            collect_companion_capability,
        )

        before = set(tmp_path.rglob("*"))
        collect_companion_capability(tmp_path)
        assert set(tmp_path.rglob("*")) == before

    def test_floor_constant_is_not_written_into_any_workspace_map(self, tmp_path: Path):
        """A full probe run must not create a workspace declaration."""
        from vaultspec_core.core.diagnosis.collectors_companion import (
            collect_companion_capability,
        )

        collect_companion_capability(tmp_path)
        assert not (tmp_path / ".vaultspec" / "workspace.json").exists()
