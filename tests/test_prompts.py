import pytest

from agent.prompts import load_prompt, prompt_hash


def test_load_prompt_returns_nonempty_text():
    text = load_prompt("extractor_v1")
    assert len(text) > 0
    assert "propose_action_items" in text


def test_load_prompt_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist_v99")


def test_prompt_hash_is_stable_and_deterministic():
    h1 = prompt_hash("extractor_v1")
    h2 = prompt_hash("extractor_v1")
    assert h1 == h2
    assert len(h1) == 12


def test_different_prompts_have_different_hashes():
    assert prompt_hash("extractor_v1") != prompt_hash("resolver_v1")


def test_all_four_production_prompts_load():
    for name in ["extractor_v1", "resolver_v1", "validator_grounding_v1", "b1_single_call_v1"]:
        assert len(load_prompt(name)) > 0


def test_active_email_drafting_prompts_load_separately_from_historical_versions():
    from agent.resolver import PROMPT_NAME
    from agent.validator import GROUNDING_PROMPT_NAME

    assert PROMPT_NAME == "resolver_v2"
    assert GROUNDING_PROMPT_NAME == "validator_grounding_v2"
    assert prompt_hash(PROMPT_NAME) != prompt_hash("resolver_v1")
    assert prompt_hash(GROUNDING_PROMPT_NAME) != prompt_hash("validator_grounding_v1")
