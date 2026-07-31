"""Define and maintain the ``body_hash`` content fingerprint.

The ``modified:`` recency stamp is CLI-owned, but the permitted hand-edit
surface is body prose, so a document can change without any verb stamping
it. The modified-stamp-provenance ADR settles what evidence that drift is
derived from: a content fingerprint carried in the document's own
frontmatter, never the file's mtime. This module is the single home of
that fingerprint - its canonical definition, its canonical serialized
form, and the in-place writer every stamping code path calls.

**The body, exactly.** The fingerprint covers the body and nothing else.
Frontmatter is CLI-owned and re-attested by the very write that changes
it, so including it would be self-referential; body-only aligns the
fingerprint with the one surface a human is allowed to touch. The body is
derived from the document's full text by four deterministic steps, in
order:

1. A single leading UTF-8 BOM (``U+FEFF``) is dropped, matching
   :func:`~vaultspec_core.vaultcore.parser.parse_vault_metadata`. A BOM is
   an encoding artifact of how the file was saved, not content.
2. Every ``\\r\\n`` and every lone ``\\r`` becomes ``\\n``. Line endings
   are a checkout artifact: ``core.autocrlf`` rewrites them on clone and
   on checkout, exactly the class of corpus-wide event that disqualified
   mtime as evidence. A fingerprint that moved with the newline
   convention would reintroduce that failure in a new costume.
3. Everything up to and including the closing ``---`` fence of the leading
   frontmatter block is removed. Text with no frontmatter fence is its own
   body in full.
4. Leading and trailing whitespace is stripped. The number of blank lines
   between the fence and the first heading, and the presence or absence of
   a final newline, are formatting noise that markdown hygiene and editors
   churn independently of authorship.

The result is encoded UTF-8 and hashed with SHA-256. The serialized field
value is the lowercase hex digest behind an explicit ``sha256:`` prefix,
so the algorithm is named in the document rather than inferred from digest
length.

**Machine-filled.** ``body_hash`` is written only by code - scaffold time
(:func:`~vaultspec_core.vaultcore.hydration._inject_body_hash`), every
mutating verb (:func:`~vaultspec_core.vaultcore.models.refresh_modified_stamp`),
and the modified-stamp checker's own fix
(:func:`~vaultspec_core.vaultcore.checks.modified_stamp.write_stamp`). It
follows the project's snake_case convention for machine-filled fields and
must never be hand-authored: a hand-written value is an assertion about
content the author did not compute, which is the only way this field can
lie.

**Silence, not suspicion.** A document carrying no ``body_hash`` makes no
claim about its body, so it earns no staleness finding - the precedent set
by the body-schema attestation decision. Corpora predating the field, and
third-party vaults, stay quiet until a migration seeds them or a mutating
verb touches them.

See Also:
    :mod:`vaultspec_core.vaultcore.body_schema` for the ledger-carried
    digest that attests legacy body *structure*, a deliberate human act
    rather than a side effect of every mutation.
"""

from __future__ import annotations

import hashlib
import re

__all__ = [
    "BODY_HASH_FIELD",
    "BODY_HASH_PREFIX",
    "body_digest",
    "canonical_body",
    "document_body_digest",
    "is_canonical_digest",
    "set_body_hash",
    "strip_frontmatter",
]

#: Frontmatter key holding the fingerprint. Machine-filled, snake_case.
BODY_HASH_FIELD = "body_hash"

#: Algorithm prefix on every serialized digest, so a future algorithm
#: change is a readable format change rather than a silent reinterpretation
#: of an unlabelled hex string.
BODY_HASH_PREFIX = "sha256:"

#: Canonical serialized form: the prefix followed by 64 lowercase hex
#: characters. Anything else is not a fingerprint this module wrote.
_CANONICAL_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Leading frontmatter fence, tolerating a BOM and LF/CRLF/CR endings.
#: Group 2 is the frontmatter block including the trailing EOL of its last
#: line; the match ends after the closing fence's own EOL, so the body is
#: whatever follows the match.
_FENCE_RE = re.compile(
    r"^(﻿?)---[ \t]*(?:\r\n|\r|\n)(.*?(?:\r\n|\r|\n))---[ \t]*(?:\r\n|\r|\n|\Z)",
    re.DOTALL,
)

#: Frontmatter ``body_hash:`` line, capturing indentation so an indented
#: key is rewritten in place rather than duplicated.
_BODY_HASH_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)body_hash:.*$")

#: Insertion anchors, in canonical field order: the fingerprint lands
#: directly after ``body_schema:`` when present, else after ``modified:``,
#: else after ``date:``. A document with none of the three has no canonical
#: schema position and is left alone.
_ANCHOR_PATTERNS = (
    re.compile(r"^(?P<indent>[ \t]*)body_schema:.*$"),
    re.compile(r"^(?P<indent>[ \t]*)modified:.*$"),
    re.compile(r"^(?P<indent>[ \t]*)date:.*$"),
)


def canonical_body(body: str) -> str:
    """Return the canonical form of an already-extracted body.

    Applies the normalization half of the module docstring's definition -
    BOM removal, newline normalization, outer-whitespace stripping - to a
    body the caller has already separated from its frontmatter, such as
    the one carried in a
    :data:`~vaultspec_core.vaultcore.checks._base.VaultSnapshot` entry.
    Deliberately does no fence removal, so a body whose own first line is
    a ``---`` thematic break is hashed whole rather than half-eaten.

    Args:
        body: Document body text, without frontmatter.

    Returns:
        The canonical body string that :func:`body_digest` hashes.
    """
    if body.startswith("﻿"):
        body = body[1:]
    return body.replace("\r\n", "\n").replace("\r", "\n").strip()


def body_digest(body: str) -> str:
    """Return the fingerprint of an already-extracted body.

    Encoded with ``surrogateescape`` because the edit pipeline reads
    documents with that handler so undecodable legacy bytes (a lone C1
    byte in a hand-migrated document, say) survive a round trip as lone
    surrogates. Strict encoding would raise on exactly those documents,
    turning a preserved byte into a crash; the handler restores the
    original byte, so the fingerprint covers what the file actually holds.
    Text with no surrogates encodes identically either way.

    Args:
        body: Document body text, without frontmatter. Normalized through
            :func:`canonical_body` before hashing, so callers may pass the
            body exactly as their parser handed it over.

    Returns:
        ``"sha256:"`` followed by the lowercase hex SHA-256 digest of the
        canonical body's UTF-8 encoding.
    """
    encoded = canonical_body(body).encode("utf-8", "surrogateescape")
    return BODY_HASH_PREFIX + hashlib.sha256(encoded).hexdigest()


def strip_frontmatter(text: str) -> str:
    """Return everything after the leading frontmatter fence of *text*.

    Args:
        text: Full document text, including any YAML frontmatter.

    Returns:
        The document body. Text with no leading frontmatter fence is its
        own body in full.
    """
    if text.startswith("﻿"):
        text = text[1:]
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    fence = _FENCE_RE.match(normalized)
    return normalized if fence is None else normalized[fence.end() :]


def document_body_digest(text: str) -> str:
    """Return the fingerprint of a full document text's body.

    The composition of :func:`strip_frontmatter` and :func:`body_digest`,
    and the entry point for callers holding whole documents rather than
    parsed bodies.

    Args:
        text: Full document text, including any YAML frontmatter.

    Returns:
        The canonical serialized digest of the document's body.
    """
    return body_digest(strip_frontmatter(text))


def is_canonical_digest(value: str | None) -> bool:
    """Return whether *value* is a digest this module could have written.

    A value failing this test - an empty field, a bare hex string, a
    truncated digest, a hand-typed note - is not evidence about the body
    and is treated exactly like an absent attestation.

    Args:
        value: Raw ``body_hash`` frontmatter value, or ``None``.

    Returns:
        ``True`` when *value* is the canonical ``sha256:<64 hex>`` form.
    """
    return value is not None and _CANONICAL_DIGEST_RE.match(value) is not None


def set_body_hash(text: str, digest: str | None = None) -> str:
    """Write the ``body_hash`` field into *text*'s frontmatter.

    Preserves every other byte, including the source LF/CRLF/CR convention
    and a leading BOM. An existing ``body_hash:`` line is rewritten in
    place, keeping its indentation; otherwise the field is inserted
    directly after the first of ``body_schema:``, ``modified:``, or
    ``date:`` that the frontmatter carries, which is its canonical schema
    position. Text with no frontmatter fence, or frontmatter carrying none
    of the three anchors, is returned unchanged: there is nowhere
    canonical to put the field, and the document simply keeps making no
    claim about its body.

    Args:
        text: Full document text, including any YAML frontmatter.
        digest: Digest to write. Defaults to the fingerprint of *text*'s
            own body, which is what every stamping path wants; callers
            pass an explicit value only when re-attesting text they are
            about to write in a different shape.

    Returns:
        The document text carrying the field, or the input unchanged when
        no canonical anchor exists.
    """
    from .rename_ops import split_keepends

    fence = _FENCE_RE.match(text)
    if fence is None:
        return text

    value = digest if digest is not None else document_body_digest(text)
    block_start = fence.start(2)
    block_end = fence.end(2)
    pairs = split_keepends(text[block_start:block_end])
    canonical = f"'{value}'"

    for pair in pairs:
        existing = _BODY_HASH_LINE_RE.match(pair[0])
        if existing is not None:
            pair[0] = f"{existing.group('indent')}{BODY_HASH_FIELD}: {canonical}"
            return _rejoin(text, pairs, block_start, block_end)

    for anchor in _ANCHOR_PATTERNS:
        for idx, pair in enumerate(pairs):
            match = anchor.match(pair[0])
            if match is None:
                continue
            indent = match.group("indent")
            pairs.insert(
                idx + 1,
                [f"{indent}{BODY_HASH_FIELD}: {canonical}", pair[1] or "\n"],
            )
            return _rejoin(text, pairs, block_start, block_end)

    return text


def _rejoin(text: str, pairs: list[list[str]], block_start: int, block_end: int) -> str:
    """Splice edited frontmatter *pairs* back into the full document text."""
    block = "".join(content + ending for content, ending in pairs)
    return text[:block_start] + block + text[block_end:]
