import pytest

from scripts.verify_trello_demo import EXPECTED_DESCRIPTION, verify_existing


class FakeClient:
    def __init__(self, title="Prepare the capstone demo slides"):
        self.tools = self
        self.calls = []
        self.card = {"id": "card_demo", "name": title, "desc": EXPECTED_DESCRIPTION,
                     "idMembers": ["member_demo"], "idList": "list_demo",
                     "due": "2026-11-06T00:00:00.000Z", "url": "https://trello.com/c/demo"}

    def execute(self, slug, arguments, user_id, version):
        self.calls.append((slug, arguments))
        assert version == "20261007_01"
        if slug == "TRELLO_UPDATE_CARDS_BY_ID_CARD":
            assert arguments == {"idCard": "card_demo", "due": "2026-11-06T17:00:00-07:00"}
            self.card["due"] = "2026-11-07T00:00:00.000Z"
        else:
            assert slug == "TRELLO_GET_CARDS_BY_ID_CARD"
            assert arguments["fields"] == "name,desc,idList,idMembers,due,url"
        return {"successful": True, "data": dict(self.card)}


def test_read_only_verification_detects_real_local_date_mismatch():
    client = FakeClient()
    result = verify_existing(client, "user", "card_demo", "list_demo", "member_demo")
    assert not result["verified"]
    assert result["mismatches"] == {"due": {"expected": "2026-11-06", "actual": "2026-11-05"}}
    assert len(client.calls) == 1


def test_correct_existing_deadline_and_readback_without_creating_card():
    client = FakeClient()
    result = verify_existing(client, "user", "card_demo", "list_demo", "member_demo", True)
    assert result["verified"]
    assert result["deadline_updated"]
    assert [call[0] for call in client.calls] == ["TRELLO_GET_CARDS_BY_ID_CARD",
            "TRELLO_UPDATE_CARDS_BY_ID_CARD", "TRELLO_GET_CARDS_BY_ID_CARD"]
    # A repeated correction is a read-only check, not another write.
    result = verify_existing(client, "user", "card_demo", "list_demo", "member_demo", True)
    assert result["verified"] and not result["deadline_updated"]


def test_refuses_update_if_other_fields_differ():
    client = FakeClient(title="Some other task")
    with pytest.raises(RuntimeError, match="Other demo fields differ"):
        verify_existing(client, "user", "card_demo", "list_demo", "member_demo", True)
    assert len(client.calls) == 1
