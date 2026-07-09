"""The metric families, each a pure function over a ``CallRecord`` iterable.

Every metric consumes the normalized record stream and, where relevant, joins
it against the declared-capability denominator parsed from the generated
markers in the CLI reference.
"""

from __future__ import annotations
