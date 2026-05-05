"""Test suite for the ``vaultspec_core.plan`` package.

Exercises plan-document parsing, frontmatter validation, and identifier
handling across clean, dirty, mixed, and degraded inputs. Tests use a
deterministic randomised generator (``random.Random(seed)``) plus
explicit parameter matrices so failures are reproducible without any
external test-data dependency.
"""
