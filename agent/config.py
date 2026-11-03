"""
agent/config.py
-----------------
Central model/provider config and the price table used to compute
per-call dollar cost for the audit log (spec requirement: "Log tokens
and compute cost from a price table in config").

Provider note: the spec's default was the Anthropic API. Switched to
OpenAI at the user's explicit request (no Anthropic key available) —
agent/llm.py is written as a provider-swappable interface specifically
so this kind of swap doesn't touch extractor/resolver/validator code.

Pricing verified against https://platform.openai.com/docs/pricing on
2026-11-02 — re-check before trusting this for real budget decisions if
much time has passed.
"""

from __future__ import annotations

import os
from typing import Optional

LLM_PROVIDER = "openai"
LLM_MODEL = os.environ.get("LLM_MODEL") or "gpt-4o-mini"  # `or`, not .get's default: treat "" same as unset
LLM_TEMPERATURE = 0.0

# USD per 1,000,000 tokens, standard (non-batch) pricing.
PRICE_TABLE_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
}


def _lookup_price(model: str) -> Optional[dict[str, float]]:
    """Exact match first; otherwise the longest price-table key that the
    model name starts with. The OpenAI API returns a dated, versioned
    model string (e.g. "gpt-4o-mini-2024-07-18") even when you requested
    the bare alias ("gpt-4o-mini") — confirmed via a live smoke-test call
    on 2026-11-02 — so an exact-only lookup silently returns None (and
    the audit log would wrongly show cost as "unknown") on every real
    call."""
    if model in PRICE_TABLE_PER_MILLION_TOKENS:
        return PRICE_TABLE_PER_MILLION_TOKENS[model]
    prefix_matches = [key for key in PRICE_TABLE_PER_MILLION_TOKENS if model.startswith(key + "-")]
    if not prefix_matches:
        return None
    best_key = max(prefix_matches, key=len)
    return PRICE_TABLE_PER_MILLION_TOKENS[best_key]


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Returns None (rather than guessing) if `model` has no price-table
    entry (exact or dated-version prefix match) — callers should log
    that as "cost unknown", not fabricate $0."""
    prices = _lookup_price(model)
    if prices is None:
        return None
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
