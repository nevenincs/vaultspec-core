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
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ._base import CheckDiagnostic, CheckResult, Severity

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from pathlib import Path

    from ...graph.models import EncodingIssue
    from ._base import VaultSnapshot

__all__ = ["DOCUMENT_CHECK_NAMES", "check_staged_documents"]

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


def _ingest(
    documents: Iterable[Path],
) -> tuple[dict[Path, tuple[str, bool]], list[EncodingIssue]]:
    """Read each document once, the way the graph's ingress read does.

    Returns:
        The ``(normalised text, source_had_crlf)`` map for every document that
        decoded, and the read or decode failures for the rest.
    """
    from ...graph.models import EncodingIssue

    raw_texts: dict[Path, tuple[str, bool]] = {}
    issues: list[EncodingIssue] = []
    for path in documents:
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            issues.append(EncodingIssue(path, "read", str(exc), None))
            continue
        try:
            decoded = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            issues.append(EncodingIssue(path, "decode", exc.reason, exc.start))
            continue
        crlf = "\r\n" in decoded
        raw_texts[path] = (decoded.replace("\r\n", "\n").replace("\r", "\n"), crlf)
    return raw_texts, issues


class _LinkIndex:
    """Resolve wiki-link targets the way the vault graph does, from names alone.

    A bare stem resolves when any document has it. A ``type/stem`` reference
    resolves only when the stem is shared by several documents, because that
    is the only case in which the graph keys a document by its qualified name.
    A target found under ``_archive/`` resolves too, as the graph does not flag
    archived targets as dangling.
    """

    def __init__(self, root_dir: Path) -> None:
        from ...config import get_config
        from ..scanner import doc_type_resolver, scan_vault

        by_stem: dict[str, list[Path]] = defaultdict(list)
        for path in scan_vault(root_dir):
            by_stem[path.stem].append(path)
        resolve_type = doc_type_resolver(root_dir)
        self._stems = frozenset(by_stem)
        self._qualified = frozenset(
            f"{doc_type.value if (doc_type := resolve_type(path)) else 'unknown'}"
            f"/{stem}"
            for stem, stem_paths in by_stem.items()
            if len(stem_paths) > 1
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
    root_dir: Path, raw_texts: Mapping[Path, tuple[str, bool]]
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
    index = _LinkIndex(root_dir)
    for path, (text, _crlf) in raw_texts.items():
        frontmatter, body = parse_frontmatter(text)
        related = frontmatter.get("related", [])
        targets = set(extract_wiki_links(body))
        if isinstance(related, list):
            targets.update(extract_related_links(related))
        rel_path = path.relative_to(root_dir)
        for target in sorted(t for t in targets if not index.resolves(t)):
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


def _document_checkers(
    root_dir: Path,
    snapshot: VaultSnapshot,
    raw_texts: Mapping[Path, tuple[str, bool]],
) -> list[Callable[[], CheckResult]]:
    from .adr_status import check_adr_status
    from .annotations import check_annotations
    from .body_links import check_body_links
    from .body_sections import check_body_sections
    from .frontmatter import check_frontmatter
    from .links import check_links
    from .markdown import check_markdown
    from .modified_stamp import check_modified_stamp
    from .placeholders import check_placeholders
    from .structure import check_structure

    return [
        lambda: check_structure(root_dir, snapshot=snapshot),
        lambda: check_frontmatter(root_dir, snapshot=snapshot),
        lambda: check_annotations(root_dir, raw_texts=raw_texts),
        lambda: check_markdown(root_dir, raw_texts=raw_texts),
        lambda: check_links(root_dir, snapshot=snapshot),
        lambda: _check_dangling(root_dir, raw_texts),
        lambda: check_body_links(root_dir, snapshot=snapshot),
        lambda: check_placeholders(root_dir, snapshot=snapshot),
        lambda: check_body_sections(root_dir, snapshot=snapshot),
        lambda: check_adr_status(root_dir, snapshot=snapshot),
        lambda: check_modified_stamp(root_dir, snapshot=snapshot),
    ]


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
    from ..parser import parse_vault_metadata
    from .encoding import encoding_issue_result

    root_dir = root_dir.resolve()
    documents = _staged_documents(root_dir, paths)
    raw_texts, issues = _ingest(documents)
    snapshot: VaultSnapshot = {
        path: parse_vault_metadata(text) for path, (text, _crlf) in raw_texts.items()
    }
    # The graph keeps a node for a document it could not read, with empty
    # metadata, so the combined pass reports its missing frontmatter as well
    # as the encoding failure. Matching that keeps both passes in agreement.
    for issue in issues:
        snapshot[issue.path] = parse_vault_metadata("")

    results = [run() for run in _document_checkers(root_dir, snapshot, raw_texts)]
    results.append(encoding_issue_result(root_dir, issues))

    checked = {path.relative_to(root_dir) for path in documents}
    for result in results:
        result.diagnostics = [d for d in result.diagnostics if d.path in checked]
    return results
