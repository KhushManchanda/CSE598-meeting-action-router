from agent.config import estimate_cost_usd


def test_exact_model_name_match():
    cost = estimate_cost_usd("gpt-4o-mini", input_tokens=1_000_000, output_tokens=0)
    assert cost == 0.15


def test_dated_versioned_model_name_still_matches_via_prefix():
    # The real OpenAI API returns a dated, versioned model string even
    # when "gpt-4o-mini" was requested -- confirmed via a live smoke test.
    cost = estimate_cost_usd("gpt-4o-mini-2024-07-18", input_tokens=1_000_000, output_tokens=0)
    assert cost == 0.15


def test_longer_prefix_key_wins_over_shorter_one():
    # "gpt-4.1-mini" must not be mistaken for a dated variant of "gpt-4"
    # if a bare "gpt-4" entry existed; exercise with the two real keys we
    # have today to pin the "longest prefix wins" rule.
    cost = estimate_cost_usd("gpt-4.1-mini-2025-01-01", input_tokens=1_000_000, output_tokens=0)
    assert cost == 0.40


def test_completely_unknown_model_returns_none_not_zero():
    assert estimate_cost_usd("some-future-model", input_tokens=100, output_tokens=100) is None


def test_output_tokens_priced_separately_from_input():
    cost = estimate_cost_usd("gpt-4o-mini", input_tokens=0, output_tokens=1_000_000)
    assert cost == 0.60


def test_llm_model_falls_back_when_env_var_is_empty_string_not_just_unset(monkeypatch):
    # Regression: python-dotenv loads "LLM_MODEL=" (blank) as "" into
    # os.environ, which os.environ.get(key, default) does NOT treat as
    # missing -- found once load_dotenv() was actually wired up.
    import importlib

    import agent.config as config_module

    monkeypatch.setenv("LLM_MODEL", "")
    importlib.reload(config_module)
    assert config_module.LLM_MODEL == "gpt-4o-mini"
    monkeypatch.delenv("LLM_MODEL", raising=False)
    importlib.reload(config_module)
