---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6d5353fe5e5d2202e90b1794feb4dc26553375697bbbee813d071c075463aad9'
step_id: 'S17'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Suppress model docstrings and auto-derived titles in generated schemas

## Scope

- `src/vaultspec_core/mcp_server/results.py`

## Description

- Introduce a result-model base that keeps class docstrings and derived titles out of generated schemas.
- Move twenty-five result models onto it.

## Outcome

The schema generator lifts a model's docstring into its description, so a Google-style docstring - attributes block and markup included - was re-sent to the model on every turn of every conversation. Output schemas were 26,785 of 43,919 characters of the tool surface, and not one of those descriptions sat on a leaf field: each described its fields in prose the model then had to re-associate by name. Maximum bytes, least usable position.

Derived titles went for the same reason: the generator title-cases the property name, carrying nothing the key does not already say.

The full surface fell from 41,346 characters to 18,745, and the read-only surface from 20,192 to 9,194.

## Notes

Deliberate field descriptions survive - those are written for the model rather than for a maintainer. The docstrings stay in the source, where the maintainer needs them.
