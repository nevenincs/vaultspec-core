"""Runtime fidelity smoke tests for the hand-written stubs in ``typings/``.

``phart``, ``radon``, and ``ruamel.yaml`` ship no usable inline types, so
``typings/`` carries hand-written ``.pyi`` stubs asserting each package's
shape (see ``typings/phart/__init__.pyi``, ``typings/radon/complexity.pyi``,
``typings/radon/metrics.pyi``, and ``typings/ruamel/yaml/__init__.pyi``).

``networkx`` is there for a different reason. It is not untyped - typeshed
ships stubs for it and basedpyright bundles them - but several of the
functions this project calls are declared upstream without return
annotations, so their results degrade to ``Unknown`` and contaminate every
value computed from them. ``typings/networkx/`` restates exactly those
four (``typings/networkx/readwrite/json_graph/node_link.pyi``,
``typings/networkx/generators/ego.pyi``, and
``typings/networkx/classes/function.pyi``). The drift risk is the same or
worse: a stub that shadows a *typed* upstream module also shadows any
correction upstream makes to it.

A ``.pyi`` file is erased at runtime: basedpyright checks it, but the
interpreter never imports it. Every one of these packages is pinned with an
open lower bound (``radon>=6.0.1``, ``phart>=0.5.0``, ``ruamel.yaml>=0.18``,
``networkx>=3.6``), so a routine ``uv sync --upgrade`` can move the
installed version silently. If that upgrade changes the real API, the stub
keeps asserting the old fiction, the type checker keeps reporting green,
and the first symptom is an ``AttributeError`` in production. No type gate
can ever catch that failure mode, by construction.

These tests call the exact surface each stub declares against trivial real
input and assert the shape the stub promises: that the return is the
declared type, and that the attributes the stub declares actually exist on
the real returned objects. If one of these packages drifts out from under
its stub, this file - not basedpyright - is what turns that into a test
failure instead of a runtime surprise.

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
from typing import cast

import networkx as nx
import pytest
from networkx.classes.function import density
from networkx.readwrite import json_graph
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


def _triangle_with_a_tail() -> nx.DiGraph[str]:
    """Return a small directed graph with a node outside the 1-hop ego set.

    ``a -> b -> c`` plus ``c -> d``: dense enough for ``density`` to return a
    fraction strictly between 0 and 1, and deep enough that a radius-1 ego
    graph around ``a`` provably excludes ``d``.
    """
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_edge("a", "b", kind="body")
    graph.add_edge("b", "c", kind="related")
    graph.add_edge("c", "d", kind="both")
    return graph


class TestNetworkxNodeLinkTypings:
    """Pins ``typings/networkx/readwrite/json_graph/node_link.pyi``."""

    def test_node_link_data_returns_a_dict_keyed_by_the_requested_edges_name(
        self,
    ) -> None:
        """The declared ``dict[str, Any]`` return must really be a ``dict``.

        ``edges="edges"`` is passed explicitly at every call site because
        networkx changed the default wire key from ``"links"`` (<=3.5) to
        ``"edges"`` (>=3.6); the keyword must therefore keep being honoured,
        not merely accepted.
        """
        data = json_graph.node_link_data(_triangle_with_a_tail(), edges="edges")
        assert isinstance(data, dict)
        assert "nodes" in data
        assert "edges" in data
        assert "links" not in data

    def test_node_link_graph_round_trips_back_to_a_directed_graph(self) -> None:
        """The declared ``nx.DiGraph[str]`` return must really be a ``DiGraph``.

        Round-trips the exact keyword set
        :meth:`~vaultspec_core.graph.api.VaultGraph._load_from_cache` uses,
        and asserts the edge attributes survive, since the graph cache
        reconstructs its whole edge payload through this call.
        """
        original = _triangle_with_a_tail()
        data = json_graph.node_link_data(original, edges="edges")

        restored = json_graph.node_link_graph(
            data,
            directed=True,
            multigraph=False,
            edges="edges",
        )
        assert isinstance(restored, nx.DiGraph)
        assert set(restored.nodes()) == set(original.nodes())
        assert set(restored.edges()) == set(original.edges())
        assert restored.edges["a", "b"]["kind"] == "body"

    def test_the_package_re_exports_the_shadowed_leaf_module(self) -> None:
        """``json_graph.node_link_data`` must stay the ``node_link`` one.

        The declaration shadows the leaf module ``networkx.readwrite.
        json_graph.node_link``, but production code calls through the alias
        ``json_graph.node_link_data``. That alias only carries the stub's
        declaration while the package keeps re-exporting the leaf module's
        function; if upstream ever re-homes it, the type checker would keep
        reporting the stub's signature for a different callable.
        """
        from networkx.readwrite.json_graph import node_link

        # Reached through ``cast("object", ...)`` because the submodule
        # attribute resolves to typeshed's unannotated declaration, not to the
        # stub: typeshed's ``json_graph/__init__.pyi`` re-exports the leaf
        # module's names with an absolute import (which does route through
        # ``stubPath``), while the ``node_link`` submodule attribute itself
        # resolves inside the typeshed package. That asymmetry is the whole
        # reason this assertion is worth making.
        assert cast("object", node_link.node_link_data) is json_graph.node_link_data
        assert cast("object", node_link.node_link_graph) is json_graph.node_link_graph


class TestNetworkxEgoGraphTypings:
    """Pins the surface declared in ``typings/networkx/generators/ego.pyi``."""

    def test_ego_graph_returns_a_graph_scoped_to_the_radius(self) -> None:
        """The declared ``nx.DiGraph[str]`` return must really be a ``DiGraph``.

        ``radius`` and ``undirected`` are the two keywords
        :meth:`~vaultspec_core.graph.api.VaultGraph.ego_subgraph` passes, so
        both are exercised, and the returned node set is checked to prove
        ``radius`` still bounds the traversal rather than being ignored.
        """
        ego = nx.ego_graph(_triangle_with_a_tail(), "a", radius=1, undirected=True)
        assert isinstance(ego, nx.DiGraph)
        assert set(ego.nodes()) == {"a", "b"}

    def test_ego_graph_is_re_exported_on_the_networkx_namespace(self) -> None:
        """``nx.ego_graph`` must stay the ``networkx.generators.ego`` one."""
        from networkx.generators import ego

        assert nx.ego_graph is ego.ego_graph


class TestNetworkxDensityTypings:
    """Pins the surface declared in ``typings/networkx/classes/function.pyi``."""

    def test_density_returns_a_float(self) -> None:
        """The declared ``float`` return must really be a ``float``.

        ``GraphMetrics.density`` is typed ``float`` and is fed straight from
        this call, so an ``int`` (which the empty-graph and complete-graph
        edge cases could plausibly produce) would be a real divergence.
        """
        value = density(_triangle_with_a_tail())
        assert isinstance(value, float)
        assert 0.0 < value < 1.0

    def test_density_is_importable_from_its_defining_module(self) -> None:
        """``density`` must stay in ``networkx.classes.function``.

        The stub only applies on that import path (typeshed re-exports the
        module into the ``networkx`` namespace with a relative import that
        never reaches ``stubPath``), and
        :mod:`vaultspec_core.graph.api` imports it from there for exactly
        that reason. If upstream re-homed the function, the import would
        break at runtime while the shadowing stub kept type-checking green.
        """
        # ``nx.density`` needs ``cast("object", ...)`` for the very reason
        # stated above: it is typeshed's unannotated re-export, and only the
        # ``density`` imported from the defining module carries the stub.
        assert cast("object", nx.density) is density
