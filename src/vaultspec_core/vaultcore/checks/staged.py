"""Run the document-scoped vault checks over a named set of documents.

The commit gate checks what a commit stages, not the whole corpus. Every
checker admitted here judges a document from that document alone, so running
it over a subset gives the same findings for those documents as the combined
pass (:func:`~vaultspec_core.vaultcore.checks.run_all_checks`) gives. Findings
that belong to the vault rather than to a document - orphans, feature coverage,
cross-feature references, rename integrity, foreign files - are properties of
the corpus and stay with the combined pass.

Link targets are resolved against a listing of document names, never a parse
of the corpus, so the cost is the size of the staged set plus one directory
walk.

:func:`gate_staged_documents` adds attribution: it checks each document's
committed version the same way and blocks only on error-level findings the
commit introduces, so an author never answers for a defect they inherited.
"""

from __future__ import annotations

import logging
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from ._base import CheckDiagnostic, CheckResult, Severity

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from pathlib import Path

    from ...graph.models import EncodingIssue
    from ._base import VaultSnapshot

logger = logging.getLogger(__name__)

__all__ = [
    "DOCUMENT_CHECK_NAMES",
    "StagedGateOutcome",
    "check_staged_documents",
    "gate_staged_documents",
]

#: The checkers the staged pass runs, by their ``check_name``. Each one reads
#: only the document it reports on (plus workspace-global attestation data),
#: which is what makes a subset run agree with the combined pass.
DOCUMENT_CHECK_NAMES: tuple[str, ...] = (
    "structure",
    "frontmatter",
    "annotations",
    "markdown",
    "links",
    "dangling",
    "body-links",
    "placeholders",
    "body-sections",
    "adr-status",
    "modified-stamp",
    "encoding",
)


def _staged_documents(root_dir: Path, paths: Iterable[Path | str]) -> list[Path]:
    """Return the vault corpus documents among *paths*, as absolute paths.

    Paths outside the docs directory, non-markdown files, deleted files and
    documents in non-corpus subtrees (editor state, archive, trash) are
    dropped: none of them is a vault document the commit adds or changes.
    """
    from ...config import get_config
    from ..exclusions import is_excluded_vault_path

    docs_dir = (root_dir / get_config().docs_dir).resolve()
    selected: dict[Path, None] = {}
    for raw in paths:
        path = root_dir / raw
        if path.suffix != ".md" or not path.is_file():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(docs_dir):
            continue
        if is_excluded_vault_path(resolved.relative_to(docs_dir)):
            continue
        selected[resolved] = None
    return sorted(selected)


def _decode(
    sources: Mapping[Path, bytes | OSError],
) -> tuple[dict[Path, tuple[str, bool]], list[EncodingIssue]]:
    """Decode each document's bytes the way the graph's ingress read does.

    Args:
        sources: Each document's raw bytes, or the error reading them raised.

    Returns:
        The ``(normalised text, source_had_crlf)`` map for every document that
        decoded, and the read or decode failures for the rest.
    """
    from ...graph.models import EncodingIssue

    raw_texts: dict[Path, tuple[str, bool]] = {}
    issues: list[EncodingIssue] = []
    for path, raw in sources.items():
        if isinstance(raw, OSError):
            issues.append(EncodingIssue(path, "read", str(raw), None))
            continue
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            issues.append(EncodingIssue(path, "decode", exc.reason, exc.start))
            continue
        crlf = "\r\n" in decoded
        raw_texts[path] = (decoded.replace("\r\n", "\n").replace("\r", "\n"), crlf)
    return raw_texts, issues


def _read_working_tree(documents: Iterable[Path]) -> dict[Path, bytes | OSError]:
    sources: dict[Path, bytes | OSError] = {}
    for path in documents:
        try:
            sources[path] = path.read_bytes()
        except OSError as exc:
            sources[path] = exc
    return sources


def _read_committed(
    root_dir: Path, documents: Iterable[Path], ref: str
) -> dict[Path, bytes | OSError]:
    """Read each document's blob at *ref* from the object database.

    One ``git cat-file --batch`` call serves every document. A document absent
    at *ref* (new, or renamed in this commit) is left out, as is everything
    when *root_dir* is not a repository or *ref* does not resolve (a first
    commit has no ``HEAD``).
    """
    documents = list(documents)
    if not documents:
        return {}
    names = [path.relative_to(root_dir).as_posix() for path in documents]
    request = "".join(f"{ref}:{name}\n" for name in names).encode()
    try:
        completed = subprocess.run(
            ["git", "-C", str(root_dir), "cat-file", "--batch"],
            input=request,
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        logger.debug("No committed baseline for the staged documents: %s", exc)
        return {}

    out = completed.stdout
    committed: dict[Path, bytes | OSError] = {}
    cursor = 0
    for path in documents:
        header_end = out.find(b"\n", cursor)
        if header_end < 0:
            break
        header = out[cursor:header_end].split()
        cursor = header_end + 1
        if header and header[-1] == b"missing":
            continue
        if len(header) != 3 or not header[2].isdigit():
            # An answer this parser does not understand leaves no way to find
            # where the next one starts, so the remaining documents simply
            # have no baseline - every error in them counts - rather than
            # being matched against bytes from someone else's object.
            break
        size = int(header[2])
        if header[1] == b"blob":
            committed[path] = out[cursor : cursor + size]
        # Every object's payload is skipped, not only a blob's: a path that is
        # a tree at the baseline still prints its contents.
        cursor += size + 1
    return committed


class _LinkIndex:
    """Resolve wiki-link targets the way the vault graph does, from names alone.

    A bare stem resolves when any document has it. A ``type/stem`` reference
    resolves only when the stem is shared by several documents, because that
    is the only case in which the graph keys a document by its qualified name.
    A target found under ``_archive/`` resolves too, as the graph does not flag
    archived targets as dangling.
    """

    def __init__(self, root_dir: Path) -> None:
        import os
        from pathlib import Path

        from ...config import get_config
        from ..exclusions import EXCLUDED_VAULT_DIR_NAMES
        from ..scanner import doc_type_resolver

        # The same walk and exclusions as ``scan_vault``, but collecting bare
        # strings: building and sorting a ``Path`` per document is most of that
        # function's cost on a large vault, and only colliding stems ever need
        # one here.
        docs_dir = root_dir / get_config().docs_dir
        dirs_by_stem: dict[str, list[str]] = defaultdict(list)
        for dirpath, dirnames, filenames in os.walk(docs_dir):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_VAULT_DIR_NAMES]
            for name in filenames:
                if name.endswith(".md"):
                    dirs_by_stem[name[:-3]].append(dirpath)
        by_stem: dict[str, list[Path]] = {
            stem: [Path(d, f"{stem}.md") for d in dirs]
            for stem, dirs in dirs_by_stem.items()
            if len(dirs) > 1
        }
        resolve_type = doc_type_resolver(root_dir)
        self._stems = frozenset(dirs_by_stem)
        self._qualified = frozenset(
            f"{doc_type.value if (doc_type := resolve_type(path)) else 'unknown'}"
            f"/{stem}"
            for stem, stem_paths in by_stem.items()
            for path in stem_paths
        )
        self._archive_dir = root_dir / get_config().docs_dir / "_archive"

    def resolves(self, target: str) -> bool:
        if target in self._stems or target in self._qualified:
            return True
        if not self._archive_dir.exists():
            return False
        normalized = target.replace("\\", "/")
        if "/" in normalized:
            return (self._archive_dir / f"{normalized}.md").exists()
        return any(self._archive_dir.rglob(f"{normalized}.md"))


def _check_dangling(
    root_dir: Path,
    raw_texts: Mapping[Path, tuple[str, bool]],
    index: Callable[[], _LinkIndex],
) -> CheckResult:
    """Report wiki-links from *raw_texts* documents that resolve to nothing.

    Mirrors the combined pass's ``dangling`` check: both ``related:`` entries
    and body wiki-links count, and each finding carries the same wording.
    """
    from ..links import extract_related_links, extract_wiki_links
    from ..parser import parse_frontmatter

    result = CheckResult(check_name="dangling", supports_fix=True)
    if not raw_texts:
        return result
    links = index()
    for path, (text, _crlf) in raw_texts.items():
        frontmatter, body = parse_frontmatter(text)
        related = frontmatter.get("related", [])
        targets = set(extract_wiki_links(body))
        if isinstance(related, list):
            # Frontmatter is untyped data; the extractor skips malformed entries.
            targets.update(extract_related_links(cast("list[str]", related)))
        rel_path = path.relative_to(root_dir)
        for target in sorted(t for t in targets if not links.resolves(t)):
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=f"Dangling wiki-link: [[{target}]] does not exist",
                    severity=Severity.ERROR,
                    fixable=True,
                    fix_description=f"Remove [[{target}]] from related:",
                )
            )
    return result


def _run_checks(
    root_dir: Path,
    sources: Mapping[Path, bytes | OSError],
    index: Callable[[], _LinkIndex],
) -> list[CheckResult]:
    """Run every admitted checker over *sources*, keeping their own findings."""
    from ..parser import parse_vault_metadata
    from .adr_status import check_adr_status
    from .annotations import check_annotations
    from .body_links import check_body_links
    from .body_sections import check_body_sections
    from .encoding import encoding_issue_result
    from .frontmatter import check_frontmatter
    from .links import check_links
    from .markdown import check_markdown
    from .modified_stamp import check_modified_stamp
    from .placeholders import check_placeholders
    from .structure import check_structure

    raw_texts, issues = _decode(sources)
    snapshot: VaultSnapshot = {
        path: parse_vault_metadata(text) for path, (text, _crlf) in raw_texts.items()
    }
    # The graph keeps a node for a document it could not read, with empty
    # metadata, so the combined pass reports its missing frontmatter as well
    # as the encoding failure. Matching that keeps both passes in agreement.
    for issue in issues:
        snapshot[issue.path] = parse_vault_metadata("")

    results = [
        check_structure(root_dir, snapshot=snapshot),
        check_frontmatter(root_dir, snapshot=snapshot),
        check_annotations(root_dir, raw_texts=raw_texts),
        check_markdown(root_dir, raw_texts=raw_texts),
        check_links(root_dir, snapshot=snapshot),
        _check_dangling(root_dir, raw_texts, index),
        check_body_links(root_dir, snapshot=snapshot),
        check_placeholders(root_dir, snapshot=snapshot),
        check_body_sections(root_dir, snapshot=snapshot),
        check_adr_status(root_dir, snapshot=snapshot),
        check_modified_stamp(root_dir, snapshot=snapshot),
        encoding_issue_result(root_dir, issues),
    ]

    checked = {path.relative_to(root_dir) for path in sources}
    for result in results:
        result.diagnostics = [d for d in result.diagnostics if d.path in checked]
    return results


def _cached_index(root_dir: Path) -> Callable[[], _LinkIndex]:
    built: list[_LinkIndex] = []

    def index() -> _LinkIndex:
        if not built:
            built.append(_LinkIndex(root_dir))
        return built[0]

    return index


def check_staged_documents(
    root_dir: Path, paths: Iterable[Path | str]
) -> list[CheckResult]:
    """Run the document-scoped checkers over the vault documents in *paths*.

    Never writes: every checker runs in its non-fixing mode. Each result keeps
    only the findings located in one of the checked documents, so vault-level
    observations a checker makes along the way are left to the combined pass.

    Args:
        root_dir: Project root directory.
        paths: Candidate paths, absolute or relative to *root_dir*, typically
            the files a commit stages. Anything that is not a vault corpus
            document is ignored.

    Returns:
        One :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` per
        name in :data:`DOCUMENT_CHECK_NAMES`, in that order.
    """
    root_dir = root_dir.resolve()
    documents = _staged_documents(root_dir, paths)
    return _run_checks(root_dir, _read_working_tree(documents), _cached_index(root_dir))


@dataclass(frozen=True)
class StagedGateOutcome:
    """What the commit gate found in the staged vault documents.

    Attributes:
        results: Every finding in the staged documents, per checker, in
            :data:`DOCUMENT_CHECK_NAMES` order.
        blocking: The error-level findings the commit introduces - those the
            same document's committed version does not already carry. Only
            these fail the gate.
    """

    results: list[CheckResult]
    blocking: list[tuple[str, CheckDiagnostic]]


def _finding_key(check_name: str, diagnostic: CheckDiagnostic) -> tuple[str, str, str]:
    return (check_name, str(diagnostic.path), diagnostic.message)


def gate_staged_documents(
    root_dir: Path, paths: Iterable[Path | str], *, baseline_ref: str = "HEAD"
) -> StagedGateOutcome:
    """Check the staged vault documents and decide which findings block.

    Each staged document's version at *baseline_ref* is checked by the same
    checkers, from the object database, so the gate can tell an error the
    commit introduces from one the document already had. A document with no
    version at *baseline_ref* - new, renamed, or a first commit - has nothing
    to inherit, so all of its errors block. Warnings never block.

    Args:
        root_dir: Project root directory.
        paths: Candidate paths, typically the files a commit stages.
        baseline_ref: The commit the staged documents are compared against.

    Returns:
        The findings and the subset that blocks.
    """
    root_dir = root_dir.resolve()
    documents = _staged_documents(root_dir, paths)
    index = _cached_index(root_dir)
    results = _run_checks(root_dir, _read_working_tree(documents), index)

    committed = _read_committed(root_dir, documents, baseline_ref)
    inherited = {
        _finding_key(result.check_name, diagnostic)
        for result in _run_checks(root_dir, committed, index)
        for diagnostic in result.diagnostics
    }
    blocking = [
        (result.check_name, diagnostic)
        for result in results
        for diagnostic in result.diagnostics
        if diagnostic.severity is Severity.ERROR
        and _finding_key(result.check_name, diagnostic) not in inherited
    ]
    return StagedGateOutcome(results=results, blocking=blocking)
