from agent.tools.composio_client import DEFAULT_USER_ID, get_user_id


def test_get_user_id_falls_back_when_env_var_is_empty_string_not_just_unset(monkeypatch):
    monkeypatch.setenv("COMPOSIO_USER_ID", "")
    assert get_user_id() == DEFAULT_USER_ID


def test_get_user_id_uses_env_var_when_set(monkeypatch):
    monkeypatch.setenv("COMPOSIO_USER_ID", "arjun-test")
    assert get_user_id() == "arjun-test"


def test_get_user_id_falls_back_when_unset(monkeypatch):
    monkeypatch.delenv("COMPOSIO_USER_ID", raising=False)
    assert get_user_id() == DEFAULT_USER_ID
