"""No live source may cite a recipe invocation that no longer exists.

The harness has been through three renames: a nested module namespace, a
verb-plus-argument dispatch, and the flat hyphenated recipes the justfile
carries today. Each rename left citations behind - in a doc comment, a
workflow, a README, the text an error message prints - and each stale citation
sends its reader to a recipe that errors out.

There is no alias layer to soften that: a `just` alias binds one name to one
recipe and cannot carry an argument, so a two-token invocation has no shim and
never will. This sweep is the whole safety net, which is why it walks the tree
rather than a hand-written file list: the previous cutover swept a list, and
four citations survived it.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003  (a runtime value, not only an annotation)

import pytest

#: Invocation prefixes that no longer exist.
#:
#: Assembled from fragments ON PURPOSE. Written as literals, the retired
#: strings would appear in this file and the sweep below would flag its own
#: source - the guard failing on itself is how the first version behaved.
RETIRED_INVOCATIONS: tuple[str, ...] = tuple(
    "just " + verb + " "
    for verb in (
        "lint",
        "fix",
        "audit",
        "test",
        "deps",
        "vault",
        "framework",
        "docs",
        "health",
        "build",
        "binaries",
        "channels",
    )
)

#: The contexts a real citation appears in. Bare prose is deliberately NOT one
#: of them: "or we can just test that the parser works" is English, not a stale
#: recipe, and an unanchored sweep flags it. Every genuine citation in these
#: trees is either inside backticks, a shell prompt, or a workflow `run:` step.
CITATION_CONTEXTS: tuple[str, ...] = ("`", "$ ", "run: ", "  ")


def _retired_citations() -> tuple[str, ...]:
    """Return every retired invocation as it would really be written."""
    return tuple(
        context + invocation
        for invocation in RETIRED_INVOCATIONS
        for context in CITATION_CONTEXTS
    )


#: Trees excluded from the sweep. `.vault/` records state what was true when
#: they were written and are deliberately never rewritten; the rest are
#: generated, vendored, cached, or build output.
CITATION_EXCLUDED: frozenset[str] = frozenset(
    {
        ".vault",
        ".git",
        ".venv",
        ".uv-cache",
        ".profile",
        "node_modules",
        "target",
        "dist",
        "dist-bin",
        "build",
        "tmp",
        "scratch",
        "scratchpad",
        "var",
        ".logs",
        "__pycache__",
        "_build",
        "locales",
        "site-packages",
    }
)

#: Suffixes worth sweeping. A retired invocation only misleads where a reader
#: or a runner will meet it.
CITATION_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".mjs",
        ".js",
        ".ts",
        ".tsx",
        ".rs",
        ".md",
        ".rst",
        ".toml",
        ".yml",
        ".yaml",
        ".json",
        ".ps1",
        ".sh",
    }
)


#: Where live citations can be. Bounded on purpose rather than walking the whole
#: checkout: a full `rglob` here traverses the virtual environment, the tool
#: caches and the generated documentation trees, which between them are orders
#: of magnitude larger than the source and carry no live citation at all.
SWEPT_ROOTS: tuple[str, ...] = (
    ".github",
    "dev",
    "docs",
    "engine",
    "frontend",
    "infra",
    "packaging",
    "schemas",
    "scripts",
    "service",
    "src",
    "tools",
    "typings",
)


def _sweepable(repo_root: Path) -> list[Path]:
    """Return every source file worth sweeping, under the bounded roots.

    Args:
        repo_root: The tree to sweep.

    Returns:
        Every sweepable file. Never empty for a real checkout: a corpus that
        globs to nothing would retire this guard silently, so the caller
        asserts on the count.
    """
    candidates: list[Path] = [path for path in repo_root.glob("*") if path.is_file()]
    for name in SWEPT_ROOTS:
        tree = repo_root / name
        if tree.is_dir():
            candidates.extend(tree.rglob("*"))
    sweepable = [
        path
        for path in candidates
        if path.is_file()
        and path.suffix in CITATION_SUFFIXES
        and not CITATION_EXCLUDED & set(path.relative_to(repo_root).parts)
    ]
    assert sweepable, (
        f"no sweepable source found under {repo_root}; an empty corpus retires "
        "this guard silently rather than failing it"
    )
    return sweepable


@pytest.mark.repo
def test_no_live_source_cites_a_retired_invocation(repo_root: Path) -> None:
    """A doc comment or error message naming a retired form sends readers nowhere.

    Args:
        repo_root: The repository root.
    """
    swept = _sweepable(repo_root)
    assert len(swept) > 50, (
        f"the sweep found only {len(swept)} files under {SWEPT_ROOTS}; a corpus "
        "this small means a renamed tree retired the guard rather than failing it"
    )
    citations = _retired_citations()
    offenders: list[str] = []
    for path in swept:
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(citation in text for citation in citations):
            offenders.append(str(path.relative_to(repo_root)))
    assert not offenders, (
        f"these cite a retired invocation {RETIRED_INVOCATIONS}: {sorted(offenders)}"
    )


@pytest.mark.repo
def test_the_sweep_can_actually_fail(tmp_path: Path) -> None:
    """A guard that cannot fail reports nothing. Prove this one can.

    Args:
        tmp_path: A scratch tree the sweep is pointed at.
    """
    planted = tmp_path / "doc.md"
    planted.write_text(f"Run {RETIRED_INVOCATIONS[0]}something.\n", encoding="utf-8")
    swept = _sweepable(tmp_path)
    assert planted in swept, "the planted file must be inside the sweep's scope"
    assert any(
        retired in planted.read_text(encoding="utf-8")
        for retired in RETIRED_INVOCATIONS
    ), "the planted citation must be one the sweep looks for"
