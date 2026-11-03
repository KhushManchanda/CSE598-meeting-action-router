import pytest

from agent.participants import Roster

PARTICIPANTS = [
    {"name": "Marcus", "aliases": ["Marc"], "email": "marcus@example.com", "trello_member_id": "member_marcus"},
    {"name": "Priya", "aliases": [], "email": "priya@example.com", "trello_member_id": "member_priya"},
]


def test_lookup_by_exact_name():
    roster = Roster(PARTICIPANTS)
    assert roster.lookup("Marcus")["email"] == "marcus@example.com"


def test_lookup_is_case_insensitive():
    roster = Roster(PARTICIPANTS)
    assert roster.lookup("marcus")["email"] == "marcus@example.com"
    assert roster.lookup("PRIYA")["email"] == "priya@example.com"


def test_lookup_by_alias():
    roster = Roster(PARTICIPANTS)
    assert roster.lookup("Marc")["name"] == "Marcus"


def test_lookup_not_found_returns_none_not_an_exception():
    roster = Roster(PARTICIPANTS)
    assert roster.lookup("Nobody") is None


def test_from_file(tmp_path):
    import json

    path = tmp_path / "roster.json"
    path.write_text(json.dumps(PARTICIPANTS))
    roster = Roster.from_file(path)
    assert roster.lookup("Priya")["trello_member_id"] == "member_priya"


def test_all_returns_every_participant():
    roster = Roster(PARTICIPANTS)
    assert len(roster.all()) == 2
