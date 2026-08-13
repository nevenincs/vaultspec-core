"""Generate and update feature index documents.

A feature index is a living ``<feature>.index.md`` file under
``<docs_dir>/<index_dir>/`` that makes the implicit feature-tag binding
explicit in the document graph. It lists all documents sharing a feature
tag and links to them via ``related:`` frontmatter.
"""

from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from .models import vault_today

if TYPE_CHECKING:
    from pathlib import Path

    from ..graph.api import DocNode

logger = logging.getLogger(__name__)

__all__ = [
    "FeatureIndexResult",
    "feature_index_lock_target",
    "generate_feature_index",
    "generate_feature_index_result",
]


@dataclass(frozen=True)
class FeatureIndexResult:
    """Outcome of one canonical feature-index regeneration."""

    path: Path
    changed: bool


def feature_index_lock_target(docs_dir: Path, feature: str) -> Path:
    """Return the ignored per-feature sentinel used by index writers."""
    return docs_dir / "data" / "index" / feature


def _render_index(
    feature: str,
    nodes: list[DocNode],
    *,
    created: str,
    modified: str,
) -> str:
    """Render one canonical generated feature index."""
    from .body_hash import set_body_hash
    from .body_schema import CURRENT_BODY_SCHEMA

    related_links = sorted(
        f"[[{node.name}]]"
        for node in nodes
        if node.path and not node.name.endswith(".index")
    )
    by_type: dict[str, list[DocNode]] = {}
    for node in nodes:
        if node.path and not node.name.endswith(".index"):
            key = node.doc_type.value if node.doc_type else "unknown"
            by_type.setdefault(key, []).append(node)

    body_lines: list[str] = []
    for type_name in sorted(by_type):
        body_lines.extend((f"### {type_name}", ""))
        for node in sorted(by_type[type_name], key=lambda n: (n.date or "", n.name)):
            body_lines.append(f"- `{node.name}` - {node.title or node.name}")
        body_lines.append("")
    document_list = "\n".join(body_lines).rstrip()
    related_block = (
        "related:\n" + "\n".join(f"  - '{link}'" for link in related_links)
        if related_links
        else "related: []"
    )
    content = (
        "---\n"
        "generated: true\n"
        "tags:\n"
        "  - '#index'\n"
        f"  - '#{feature}'\n"
        f"date: '{created}'\n"
        f"modified: '{modified}'\n"
        f"body_schema: '{CURRENT_BODY_SCHEMA}'\n"
        f"{related_block}\n"
        "---\n\n"
        f"# `{feature}` feature index\n\n"
        f"Auto-generated index of all documents tagged with `#{feature}`.\n\n"
        "## Documents\n\n"
        f"{document_list}\n"
    )
    return set_body_hash(content)


def generate_feature_index_result(
    root_dir: Path,
    feature: str,
    *,
    nodes: list[DocNode] | None = None,
    date_str: str | None = None,
    dry_run: bool = False,
) -> FeatureIndexResult:
    """Create or update a feature index file for *feature*.

    The index file lives at ``<docs_dir>/<index_dir>/<feature>.index.md``
    and contains a ``related:`` field linking to every document tagged
    with the feature, plus a body listing documents grouped by type. The
    rendered frontmatter carries the standard two-tag shape
    (``#index`` directory tag plus ``#<feature>`` feature tag), the
    ``generated: true`` marker, a stable creation ``date:``, a ``modified:``
    stamp refreshed only when canonical generated content changes,
    and a ``body_hash:`` fingerprint of the rendered body, so the index
    reconciles cleanly against the modified-stamp checker like every other
    CLI-created document.

    Args:
        root_dir: Project root directory.
        feature: Feature name (without ``#`` prefix).
        nodes: Explicit nodes for isolated callers and tests. Production callers
            omit this so membership is refreshed under the index lock.
        date_str: Override date for the index. Defaults to today.
        dry_run: Compute whether the canonical index would change without writing.

    Returns:
        Typed path and physical-change outcome.
    """
    from ..config import get_config
    from ..core.helpers import advisory_lock, atomic_write
    from .models import normalize_date
    from .parser import parse_frontmatter

    cfg = get_config()
    docs_dir = root_dir / cfg.docs_dir
    index_dir = docs_dir / cfg.index_dir
    index_path = index_dir / f"{feature}.index.md"
    today = date_str or vault_today().isoformat()
    lock_target = feature_index_lock_target(docs_dir, feature)
    if not dry_run:
        lock_target.parent.mkdir(parents=True, exist_ok=True)
    lock = nullcontext() if dry_run else advisory_lock(lock_target)
    with lock:
        if not dry_run:
            index_dir.mkdir(parents=True, exist_ok=True)
        if nodes is None:
            from ..graph import VaultGraph

            nodes = VaultGraph(root_dir, use_cache=False).get_feature_nodes(feature)
        if not nodes:
            logger.info("No documents found for feature index: %s", feature)
            return FeatureIndexResult(index_path, changed=False)

        existing: str | None = None
        created = today
        modified = today
        if index_path.exists():
            existing = index_path.read_text(encoding="utf-8")
            parsed, _ = parse_frontmatter(existing)
            raw = cast("object", parsed)
            if isinstance(raw, dict):
                metadata = cast("dict[str, Any]", raw)
                created = normalize_date(metadata.get("date")) or today
                modified = normalize_date(metadata.get("modified")) or created

        unchanged = _render_index(feature, nodes, created=created, modified=modified)
        if existing == unchanged:
            logger.info("Feature index body already current: %s", index_path)
            return FeatureIndexResult(index_path, changed=False)

        content = _render_index(feature, nodes, created=created, modified=today)
        if not dry_run:
            atomic_write(index_path, content)
            logger.info("Generated feature index: %s", index_path)
        return FeatureIndexResult(index_path, changed=True)


def generate_feature_index(
    root_dir: Path,
    feature: str,
    *,
    nodes: list[DocNode] | None = None,
    date_str: str | None = None,
) -> Path:
    """Compatibility entry point returning the generated index path."""
    return generate_feature_index_result(
        root_dir, feature, nodes=nodes, date_str=date_str
    ).path
