---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2bda8c7873cf6acc17880ca6531146f8f758b220a0eaed1dd493816e144c9234'
step_id: 'S16'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Make the batch result exception-based and cap batch input length

## Scope

- `src/vaultspec_core/mcp_server/results.py`

## Description

- Make the batch response exception-based: enumerate every failure and every warning, and summarise plain successes as counts.
- Cap the number of items a batch may carry, rejected before anything is written.

## Outcome

A batch returned one row per submitted item unconditionally, so a five-thousand-item batch cost roughly 2.4 megabytes to report success five thousand times, each row echoing data the caller had just sent.

Two hundred items now cost 3,036 bytes, and two hundred all-succeeding items cost about the same as twenty. Three failures and two warnings among them are all enumerated, adding 696 bytes.

## Notes

The counts stay exact however many rows are omitted, so the true outcome of the batch is always known. The input cap is enforced before any file is touched: an oversized batch would otherwise apply every item and then detonate the caller's context on the way back, having already made the changes.
