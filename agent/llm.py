"""
agent/llm.py
-------------
Single interface every LLM call in this project goes through — swapping
providers or models later should mean editing only this file, not the
extractor/resolver/validator that call it. Provider: OpenAI (see
agent/config.py for why this differs from the spec's Anthropic default),
via the official `openai` SDK.

No network call happens at import time, and constructing an LLMClient
does not require OPENAI_API_KEY either — the actual SDK client is built
lazily on the first real `.complete()` call, so this module is safe to
import (and unit-test against a fake client) with no key configured.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.config import LLM_MODEL, LLM_TEMPERATURE, estimate_cost_usd


@dataclass
class LLMCallResult:
    """Everything step 4's audit log needs for one model call: content,
    any tool calls the model made, token counts, latency, and cost."""

    content: Optional[str]
    tool_calls: list[dict] = field(default_factory=list)  # [{"id","name","arguments"}]
    model: str = LLM_MODEL
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float = 0.0
    cost_usd: Optional[float] = None
    raw_response: Any = None


class LLMClient:
    """Wraps one OpenAI chat-completion call. Pass `tools` (OpenAI
    tool-schema list) for tool-calling (resolver, B1); pass
    `response_format` instead for a plain structured-output call
    (extractor)."""

    def __init__(self, model: str = LLM_MODEL, temperature: float = LLM_TEMPERATURE):
        self.model = model
        self.temperature = temperature
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI  # imported lazily: a missing

            self._client = OpenAI()  # OPENAI_API_KEY only breaks at call time, not import time
        return self._client

    def complete(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[Any] = None,
        response_format: Optional[dict] = None,
    ) -> LLMCallResult:
        client = self._get_client()
        start = time.monotonic()
        kwargs: dict[str, Any] = {"model": self.model, "temperature": self.temperature, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if response_format:
            kwargs["response_format"] = response_format

        response = client.chat.completions.create(**kwargs)
        latency = time.monotonic() - start
        return self._to_result(response, latency)

    @staticmethod
    def _to_result(response: Any, latency: float) -> LLMCallResult:
        choice = response.choices[0]
        raw_tool_calls = choice.message.tool_calls or []
        tool_calls = [
            {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments} for tc in raw_tool_calls
        ]

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        return LLMCallResult(
            content=choice.message.content,
            tool_calls=tool_calls,
            model=response.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_seconds=latency,
            cost_usd=estimate_cost_usd(response.model, input_tokens, output_tokens),
            raw_response=response,
        )
