from agent.tools.idempotency_store import IdempotencyStore


def test_get_missing_key_returns_none(tmp_path):
    store = IdempotencyStore(tmp_path / "store.json")
    assert store.get("missing") is None


def test_set_then_get_round_trips(tmp_path):
    store = IdempotencyStore(tmp_path / "store.json")
    store.set("idem-1", "evt_123")
    assert store.get("idem-1") == "evt_123"


def test_persists_across_instances(tmp_path):
    path = tmp_path / "store.json"
    store1 = IdempotencyStore(path)
    store1.set("idem-1", "evt_123")

    store2 = IdempotencyStore(path)
    assert store2.get("idem-1") == "evt_123"


def test_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "store.json"
    store = IdempotencyStore(path)
    store.set("idem-1", "evt_1")
    assert path.exists()
