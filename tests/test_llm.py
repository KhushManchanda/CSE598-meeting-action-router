"""
Tests for agent/llm.py. These NEVER touch the real OpenAI API — the SDK
client is replaced with a fake that returns a canned response shaped
like the real SDK's, so no network call, no API key, and no cost is
incurred by running the test suite.
"""

from types import SimpleNamespace

from agent.llm import LLMClient


class _FakeToolCall:
    def __init__(self, id_, name, arguments):
        self.id = id_
        self.function = SimpleNamespace(name=name, arguments=arguments)


def _fake_response(content=None, tool_calls=None, model="gpt-4o-mini", prompt_tokens=100, completion_tokens=20):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        model=model,
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class _FakeOpenAIClient:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


def test_complete_parses_plain_text_response_and_computes_cost():
    client = LLMClient(model="gpt-4o-mini")
    client._client = _FakeOpenAIClient(_fake_response(content="hello"))

    result = client.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.content == "hello"
    assert result.tool_calls == []
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    # 100 * 0.15/1e6 + 20 * 0.60/1e6
    assert result.cost_usd is not None
    assert round(result.cost_usd, 8) == round((100 * 0.15 + 20 * 0.60) / 1_000_000, 8)


def test_complete_parses_tool_calls():
    tool_calls = [_FakeToolCall("call_1", "lookup_participant", '{"name": "Marcus"}')]
    client = LLMClient(model="gpt-4o-mini")
    client._client = _FakeOpenAIClient(_fake_response(content=None, tool_calls=tool_calls))

    result = client.complete(messages=[{"role": "user", "content": "hi"}], tools=[{"type": "function"}])

    assert result.content is None
    assert result.tool_calls == [{"id": "call_1", "name": "lookup_participant", "arguments": '{"name": "Marcus"}'}]


def test_unknown_model_gives_none_cost_not_a_fabricated_zero():
    client = LLMClient(model="some-future-model")
    client._client = _FakeOpenAIClient(_fake_response(model="some-future-model"))

    result = client.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.cost_usd is None


def test_complete_passes_temperature_and_model_through():
    fake = _FakeOpenAIClient(_fake_response(content="ok"))
    client = LLMClient(model="gpt-4o-mini", temperature=0.0)
    client._client = fake

    client.complete(messages=[{"role": "user", "content": "hi"}])

    assert fake.last_kwargs["model"] == "gpt-4o-mini"
    assert fake.last_kwargs["temperature"] == 0.0


def test_constructing_client_does_not_require_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Must not raise even with no key set -- the real SDK client is only
    # built lazily inside complete(), not here.
    LLMClient(model="gpt-4o-mini")
