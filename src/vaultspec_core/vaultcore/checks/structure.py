"""Check vault directory structure and filename conventions.

Wraps VaultConstants.validate_vault_structure() and validate_filename()
which exist but were never wired to a CLI command.  With ``--fix``,
renames files that have wrong suffixes or missing date prefixes, and
updates incoming ``[[wiki-link]]`` references in the ``related:``
frontmatter of other documents so the rename does not leave dangling
links behind.
"""

from __future__ import annotations

import logging
import re
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..models import vault_today
from ..parser import split_frontmatter
from ..rename_ops import rename_document_path as _rename_document_path
from ..rename_ops import rewrite_incoming_refs as _rewrite_incoming_refs
from ..rename_ops import split_keepends
from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    VaultSnapshot,
    is_generated_index,
)

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from pathlib import Path

__all__ = ["check_structure", "ensure_index_directory_tag"]

logger = logging.getLogger(__name__)


def _fix_filename(
    doc_path: Path, root_dir: Path, result: CheckResult
) -> tuple[list[tuple[str, str]], Path]:
    """Attempt to fix filename issues: wrong suffix, missing date prefix.

    Returns a two-tuple of ``(renames, final_path)`` where *renames* is
    the list of ``(old_stem, new_stem)`` tuples for every successful
    rename performed on *doc_path* (zero, one, or two renames per call)
    and *final_path* is the on-disk path after those renames land
    (or the input *doc_path* if nothing was renamed).  The caller needs
    *final_path* to re-validate the renamed file, because local
    rebinding inside this function does not propagate to the caller's
    variable.

    The returned *renames* list drives a follow-up
    :func:`_rewrite_incoming_refs` pass so incoming ``[[wiki-link]]``
    references stay in sync with the new filenames.
    """
    from ..models import DocType
    from ..scanner import get_doc_type

    doc_type = get_doc_type(doc_path, root_dir)
    if not doc_type:
        return [], doc_path

    fix = _FilenameFix(doc_path, root_dir, result)
    filename = doc_path.name
    expected_suffix = f"-{doc_type.value}.md"
    if doc_type == DocType.EXEC:
        needs_rename = f"-{DocType.EXEC.value}" not in filename
    else:
        needs_rename = not filename.endswith(expected_suffix)

    if needs_rename:
        match = re.match(
            r"^(\d{4}-\d{2}-\d{2}-.+?)(?:-(?:adr|audit|"
            r"exec|plan|reference|research).*)?\.md$",
            filename,
        )
        if match and not fix.rename(
            f"{match.group(1)}{expected_suffix}", conflict="target already exists"
        ):
            return fix.renames, fix.doc_path

    if not re.match(r"^\d{4}-\d{2}-\d{2}-", fix.doc_path.name):
        # The vault's single canonical clock (UTC), so the backfilled
        # prefix agrees with every other vault document date regardless
        # of the runner's local timezone. See `vault_today` for why.
        fix.rename(
            f"{vault_today().isoformat()}-{fix.doc_path.name}",
            conflict="target already exists",
        )

    lowercase_filename = fix.doc_path.name.lower()
    if fix.doc_path.name != lowercase_filename:
        fix.rename(lowercase_filename, conflict="target exists", warn=False)

    fix.flush()
    return fix.renames, fix.doc_path


@dataclass
class _FilenameFix:
    """One document's filename repairs, applied in sequence.

    Tracks the path as each rename lands, the ``(old_stem, new_stem)`` pairs
    performed, and the INFO messages for them, which are reported against
    the document's final path.
    """

    doc_path: Path
    root_dir: Path
    result: CheckResult
    renames: list[tuple[str, str]] = field(default_factory=list)
    fixed_messages: list[str] = field(default_factory=list)

    def flush(self) -> None:
        """Report the pending fixed messages against the current path."""
        fixed_rel = self.doc_path.relative_to(self.root_dir)
        for message in self.fixed_messages:
            self.result.diagnostics.append(
                CheckDiagnostic(
                    path=fixed_rel,
                    message=message,
                    severity=Severity.INFO,
                )
            )
        self.fixed_messages.clear()

    def rename(self, new_filename: str, *, conflict: str, warn: bool = True) -> bool:
        """Rename the document to *new_filename*, or report why it could not."""
        new_path = self.doc_path.parent / new_filename
        old_filename = self.doc_path.name
        if _rename_document_path(self.doc_path, new_path):
            self.result.fixed_count += 1
            self.renames.append((self.doc_path.stem, new_path.stem))
            self.doc_path = new_path
            self.fixed_messages.append(f"Fixed: renamed to {new_filename}")
            logger.info("Renamed %s -> %s", old_filename, new_filename)
            return True
        if warn:
            logger.warning("Cannot rename %s: target exists", old_filename)
        self.flush()
        self.result.diagnostics.append(
            CheckDiagnostic(
                path=self.doc_path.relative_to(self.root_dir),
                message=f"Cannot rename to {new_filename}: {conflict}",
                severity=Severity.ERROR,
            )
        )
        return False


_INDEX_TAG = "#index"

# Match a YAML block-sequence tag entry and capture the tag value
# (with or without surrounding quotes). Anchored to the line start so
# stray free-text occurrences in the body never match. The trailing
# ``\s*$`` is intentional - tags entries that carry inline comments
# would not validate under the project's frontmatter rules.
_TAG_ENTRY_RE = re.compile(r"""^\s*-\s*['"]?(#[\w-]+)['"]?\s*$""")


def ensure_index_directory_tag(content: str) -> tuple[str, bool]:
    """Insert ``#index`` into the YAML ``tags:`` block if missing.

    Args:
        content: Full file content (frontmatter plus body).

    Returns:
        A two-tuple ``(new_content, changed)`` where *changed* indicates
        whether the content needed rewriting. The function only mutates
        the YAML block sequence under ``tags:`` and leaves the rest of
        the file unchanged.
    """
    split = split_frontmatter(content)
    if split.yaml_block is None:
        return content, False
    yaml = content[split.yaml_start : split.yaml_end]
    lines = [text + ending for text, ending in split_keepends(yaml)]
    in_tags = False
    insert_idx: int | None = None
    has_index_tag = False
    tag_indent: str = "  "

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("tags:"):
            in_tags = True
            continue

        if in_tags:
            if line.startswith((" ", "\t", "-")):
                # Match an existing list entry to capture indent style
                # and detect the index tag.
                bullet = line.lstrip()
                if bullet.startswith("-"):
                    tag_indent = line[: len(line) - len(bullet)]
                    # Compare the captured tag value exactly so a
                    # tag like ``#index-notes`` does not falsely
                    # signal that the directory tag ``#index`` is
                    # already present.
                    tag_match = _TAG_ENTRY_RE.match(line)
                    if tag_match and tag_match.group(1) == _INDEX_TAG:
                        has_index_tag = True
                continue
            # End of tags block: plant before this non-tag line.
            in_tags = False
            insert_idx = idx
    if in_tags and insert_idx is None:
        # The tags block runs to the closing fence: plant before the fence.
        insert_idx = len(lines)

    if has_index_tag:
        return content, False
    if insert_idx is None:
        # Either no frontmatter or no tags: leave content alone, caller
        # will surface an ERROR diagnostic.
        return content, False

    # Preserve the source file's newline convention. Mixed CRLF/LF
    # inside one file is what we want to avoid - if the document is
    # CRLF, the inserted tag line must end with \r\n, otherwise the
    # frontmatter ends up with one stray \n line in a sea of \r\n.
    newline = "\r\n" if "\r\n" in content else "\n"
    new_line = f"{tag_indent}- '{_INDEX_TAG}'{newline}"
    new_lines = [*lines[:insert_idx], new_line, *lines[insert_idx:]]
    return (
        content[: split.yaml_start] + "".join(new_lines) + content[split.yaml_end :],
        True,
    )


def _detect_legacy_root_indexes(
    root_dir: Path,
    snapshot: VaultSnapshot,
    result: CheckResult,
) -> None:
    """Warn about misplaced feature index files without mutating.

    Walks *snapshot* for ``*.index.md`` files whose parent directory is
    not the canonical ``<docs_dir>/<index_dir>/`` subfolder and emits
    one warning per file pointing the operator at
    ``vaultspec-core migrations run``. Mutation lives in the migration
    registry (see :mod:`vaultspec_core.migrations`), which no longer runs
    lazily on every vault command: since issue #443 it is reached only by a
    caller that asked to converge or that is about to write to a location
    the schema decides. So this checker stays read-only, and reporting the
    drift is the whole of its job - the operator, not a passing read,
    decides when the file moves.

    Reading from the pre-built snapshot rather than a fresh
    :func:`pathlib.Path.rglob` walk avoids a redundant filesystem scan
    inside ``vault check all``, which already has the full document tree
    in memory.

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed
            data. The detection only consults the keys, not the parsed
            metadata, so any well-formed snapshot is acceptable.
        result: :class:`CheckResult` to accumulate diagnostics into.
    """
    from ...config import get_config

    cfg = get_config()
    docs_dir = root_dir / cfg.docs_dir
    if not docs_dir.is_dir():
        return

    index_dir = docs_dir / cfg.index_dir
    legacy_files = sorted(
        path
        for path in snapshot
        if path.name.endswith(".index.md") and path.parent != index_dir
    )
    if not legacy_files:
        return

    for legacy in legacy_files:
        rel = legacy.relative_to(root_dir)
        is_root_level = legacy.parent == docs_dir
        misplacement_label = (
            f"{cfg.docs_dir}/ root"
            if is_root_level
            else str(legacy.parent.relative_to(root_dir)).replace("\\", "/")
        )
        result.diagnostics.append(
            CheckDiagnostic(
                path=rel,
                message=(
                    f"Misplaced feature index at {misplacement_label}: "
                    f"'{legacy.name}'. Pending schema migration to "
                    f"{cfg.docs_dir}/{cfg.index_dir}/."
                ),
                severity=Severity.WARNING,
                fixable=False,
                fix_description=(
                    "Run 'vaultspec-core migrations run' to apply the "
                    "registered schema migration."
                ),
            )
        )


def check_structure(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    fix: bool = False,
) -> CheckResult:
    """Check vault directory structure and filename conventions.

    Detects unsupported subdirectories in ``.vault/``, files placed directly
    in the ``.vault/`` root, filenames deviating from the
    ``YYYY-MM-DD-<feature>-<type>.md`` convention, and misplaced feature
    index files (any ``<feature>.index.md`` outside the configured
    ``index/`` subfolder). With ``fix=True``, renames mis-suffixed files
    and inserts missing date prefixes.

    Misplaced feature indexes are surfaced as warnings only; the
    actual relocation lives in the schema migration registry
    (:mod:`vaultspec_core.migrations`) which runs lazily on every
    ``vaultspec-core vault ...`` command and explicitly via
    ``vaultspec-core migrations run``.

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed data.
        fix: When ``True``, performs auto-renames and frontmatter
            rewrites.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"structure"``.
    """
    from ..models import VaultConstants

    result = CheckResult(check_name="structure", supports_fix=True)
    all_renames: list[tuple[str, str]] = []

    for msg in VaultConstants.validate_vault_structure(root_dir):
        # The detection helper below emits one actionable per-file
        # WARNING for each misplaced index. The aggregate validator
        # also produces a pathless message for root-level index files;
        # drop those so operators see exactly one diagnostic per offence
        # rather than two messages saying the same thing.
        if "Legacy feature index" in msg:
            continue
        result.diagnostics.append(
            CheckDiagnostic(
                path=None,
                message=msg,
                severity=Severity.ERROR,
            )
        )

    # Migration mutation lives in the registry; the checker only
    # surfaces pending-migration warnings irrespective of --fix.
    _detect_legacy_root_indexes(root_dir, snapshot, result)

    # Serialise the whole mutating cascade (the ``--fix`` file renames in
    # ``_fix_filename`` plus the follow-up ``related:`` ref-rewrite) against the
    # other docs-domain mutators (``rename_feature``, ``vault rename``) on the
    # single docs sentinel. The lock is acquired only on a fix run; read-only
    # passes (``fix=False``) take no lock. ``advisory_lock`` no-ops when
    # ``.vault/data`` is absent and this path never creates it, so the lock is a
    # no-op in un-provisioned trees and a real serialiser wherever ``data/``
    # exists.
    from ...config import get_config
    from ...core.helpers import advisory_lock
    from ..rename_engine import docs_lock_target
    from ..scanner import doc_type_resolver

    docs_dir = root_dir / get_config().docs_dir
    cascade_lock: AbstractContextManager[object] = (
        advisory_lock(docs_lock_target(docs_dir)) if fix else nullcontext()
    )

    resolve_doc_type = doc_type_resolver(root_dir)
    with cascade_lock:
        for doc_path in snapshot:
            # Skip generated index files (non-standard naming convention)
            if is_generated_index(doc_path):
                continue

            doc_type = resolve_doc_type(doc_path)
            errors = VaultConstants.validate_filename(doc_path.name, doc_type)

            if errors and fix:
                renames, final_path = _fix_filename(doc_path, root_dir, result)
                all_renames.extend(renames)
                # ``final_path`` tracks the on-disk location after any
                # renames performed by ``_fix_filename``; the original
                # ``doc_path`` reference is stale after a successful rename
                # and would cause the post-fix validation to be skipped.
                if final_path.exists():
                    remaining = VaultConstants.validate_filename(
                        final_path.name, doc_type
                    )
                    for msg in remaining:
                        result.diagnostics.append(
                            CheckDiagnostic(
                                path=final_path.relative_to(root_dir),
                                message=msg,
                                severity=Severity.ERROR,
                            )
                        )
            else:
                for msg in errors:
                    result.diagnostics.append(
                        CheckDiagnostic(
                            path=doc_path.relative_to(root_dir),
                            message=msg,
                            severity=Severity.ERROR,
                            fixable=True,
                        )
                    )

        if fix and all_renames:
            _rewrite_incoming_refs(root_dir, all_renames, result)

    return result
