import importlib


def test_default_trello_list_id_falls_back_when_env_var_is_empty_string(monkeypatch):
    import agent.tool_schemas as tool_schemas_module

    monkeypatch.setenv("TRELLO_LIST_ID", "")
    importlib.reload(tool_schemas_module)
    assert tool_schemas_module.DEFAULT_TRELLO_LIST_ID == "list_todo"
    monkeypatch.delenv("TRELLO_LIST_ID", raising=False)
    importlib.reload(tool_schemas_module)


def test_default_trello_list_id_uses_env_var_when_set(monkeypatch):
    import agent.tool_schemas as tool_schemas_module

    monkeypatch.setenv("TRELLO_LIST_ID", "list_abc123")
    importlib.reload(tool_schemas_module)
    assert tool_schemas_module.DEFAULT_TRELLO_LIST_ID == "list_abc123"
    monkeypatch.delenv("TRELLO_LIST_ID", raising=False)
    importlib.reload(tool_schemas_module)
