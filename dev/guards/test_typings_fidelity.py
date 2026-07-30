"""Runtime fidelity smoke tests for the hand-written stubs in ``typings/``.

``phart``, ``radon``, and ``ruamel.yaml`` ship no usable inline types, so
``typings/`` carries hand-written ``.pyi`` stubs asserting each package's
shape (see ``typings/phart/__init__.pyi``, ``typings/radon/complexity.pyi``,
``typings/radon/metrics.pyi``, and ``typings/ruamel/yaml/__init__.pyi``).

A ``.pyi`` file is erased at runtime: basedpyright checks it, but the
interpreter never imports it. All three packages are pinned with open lower
bounds (``radon>=6.0.1``, ``phart>=0.5.0``, ``ruamel.yaml>=0.18``), so a
routine ``uv sync --upgrade`` can move the installed version silently. If
that upgrade changes the real API, the stub keeps asserting the old
fiction, the type checker keeps reporting green, and the first symptom is
an ``AttributeError`` in production. No type gate can ever catch that
failure mode, by construction.

These tests call the exact surface each stub declares against trivial real
input and assert the shape the stub promises: that the return is the
declared type, and that the attributes the stub declares actually exist on
the real returned objects. If one of these three packages drifts out from
under its stub, this file - not basedpyright - is what turns that into a
test failure instead of a runtime surprise.

Deliberately not asserted: exact numeric complexity/maintainability scores
or exact ASCII layout geometry. Those can legitimately shift between
library versions and would make this file a nuisance rather than a guard;
only types, attribute presence, and coarse invariants are pinned.

A note on naming. The subject here is a ``.pyi`` type stub, which is the
one thing in this repository legitimately called a "stub" - and the exact
word ``test_test_suite_quality.py`` rejects in a class or function name,
because everywhere else in a test suite it names a test double. That guard
is right and this module was the collision: nothing below stands in for a
real object, and every assertion runs against the genuine installed
library. The classes are therefore named for the ``typings/`` declarations
they pin rather than for the file extension those declarations use. Do not
rename them back to ``...Stub``; it would make a real guard read as a
false positive, which is how a guard gets weakened.
"""

from __future__ import annotations

import io
import textwrap

import networkx as nx
import pytest
from radon.complexity import cc_rank, cc_visit
from radon.metrics import mi_rank, mi_visit
from ruamel.yaml import YAML, YAMLError

pytestmark = [pytest.mark.repo]


# A top-level function plus a class with two methods, so `cc_visit` returns
# both a `Function` and a `Class` block from a single trivial source string.
_SOURCE_WITH_FUNCTION_AND_CLASS = textwrap.dedent(
    """\
    def add(a, b):
        if a > b:
            return a
        return b


    class Calculator:
        def add(self, a, b):
            if a > b:
                return a
            return b

        def sub(self, a, b):
            return a - b
    """
)


class TestRadonComplexityTypings:
    """Pins the surface declared in ``typings/radon/complexity.pyi``."""

    def test_cc_visit_returns_both_function_and_class_blocks(self) -> None:
        """``cc_visit`` must mix ``Function`` and ``Class`` blocks.

        ``complexity`` is a plain namedtuple field on ``radon.visitors.
        Function`` but a computed ``@property`` on ``radon.visitors.Class``:
        the two implementations are the most likely to drift out of sync
        silently, so the fixture source deliberately produces both kinds of
        block, not just a bare function. ``radon.visitors`` itself carries
        no local stub, so the two concrete types are told apart by runtime
        class name rather than an unstubbed ``isinstance`` import.
        """
        blocks = cc_visit(_SOURCE_WITH_FUNCTION_AND_CLASS)
        assert isinstance(blocks, list)
        block_type_names = {type(block).__name__ for block in blocks}
        assert "Function" in block_type_names
        assert "Class" in block_type_names

    def test_every_block_exposes_the_declared_attributes(self) -> None:
        """Every returned block must expose ``complexity: int`` and ``name: str``.

        ``typings/radon/complexity.pyi`` types both ``Function`` and
        ``Class`` blocks as the same ``ComplexityBlock`` shape, so both
        real objects must actually carry these two attributes regardless
        of whether the library stores or computes ``complexity``.
        """
        blocks = cc_visit(_SOURCE_WITH_FUNCTION_AND_CLASS)
        assert blocks
        for block in blocks:
            assert isinstance(block.complexity, int)
            assert isinstance(block.name, str)
            assert block.name

    def test_cc_rank_returns_a_grade_letter(self) -> None:
        blocks = cc_visit(_SOURCE_WITH_FUNCTION_AND_CLASS)
        for block in blocks:
            grade = cc_rank(block.complexity)
            assert isinstance(grade, str)
            assert grade in "ABCDEF"


class TestRadonMetricsTypings:
    """Pins the surface declared in ``typings/radon/metrics.pyi``."""

    def test_mi_visit_returns_a_float_score(self) -> None:
        score = mi_visit(_SOURCE_WITH_FUNCTION_AND_CLASS, multi=True)
        assert isinstance(score, float)

    def test_mi_rank_returns_a_grade_letter(self) -> None:
        score = mi_visit(_SOURCE_WITH_FUNCTION_AND_CLASS, multi=True)
        grade = mi_rank(score)
        assert isinstance(grade, str)
        assert grade in "ABC"


class TestPhartAsciiRendererTypings:
    """Pins the surface declared in ``typings/phart/__init__.pyi``."""

    def test_construction_and_render_shape(self) -> None:
        """A trivial two-node graph must construct and render as non-empty text."""
        from phart import ASCIIRenderer

        graph: nx.DiGraph[str] = nx.DiGraph()
        graph.add_edge("a", "b")

        renderer = ASCIIRenderer(graph)
        assert renderer.graph is graph

        rendered = renderer.render()
        assert isinstance(rendered, str)
        assert rendered.strip()
        # Coarse invariant: both node labels made it into the layout, not
        # the exact box-drawing geometry (arrows, spacing, line count).
        assert "a" in rendered
        assert "b" in rendered


class TestRuamelYamlTypings:
    """Pins the surface declared in ``typings/ruamel/yaml/__init__.pyi``."""

    def test_round_trip_preserves_quote_style(self) -> None:
        """``preserve_quotes`` plus a load/dump round trip must keep the quote.

        Mirrors :func:`vaultspec_core.core.precommit._precommit_yaml`'s real
        configuration: ``preserve_quotes``, ``width``, and ``indent`` are all
        attributes/methods the stub declares.
        """
        handler = YAML()
        handler.preserve_quotes = True
        assert handler.preserve_quotes is True
        handler.width = 4096
        handler.indent(mapping=2, sequence=2, offset=0)

        data = handler.load('greeting: "hello"\n')
        assert data is not None
        assert data["greeting"] == "hello"

        buffer = io.StringIO()
        result = handler.dump(data, buffer)
        assert result is None
        dumped = buffer.getvalue()
        assert '"hello"' in dumped

    def test_yaml_error_is_importable_and_is_an_exception(self) -> None:
        assert issubclass(YAMLError, Exception)
