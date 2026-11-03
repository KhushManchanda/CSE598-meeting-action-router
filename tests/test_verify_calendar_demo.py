import pytest

from scripts.verify_calendar_demo import verify_existing


@pytest.mark.parametrize("end,expected_verified", [("2026-11-08T17:30:00Z", True),
                                                  ("2026-11-08T18:30:00Z", False)])
def test_existing_event_read_only_verification(end, expected_verified):
    class Client:
        def __init__(self):
            self.tools = self
            self.calls = 0

        def execute(self, slug, arguments, user_id, version):
            self.calls += 1
            assert slug == "GOOGLECALENDAR_EVENTS_GET"
            assert arguments == {"event_id": "existing_event", "calendar_id": "primary",
                                 "time_zone": "America/Phoenix"}
            assert version == "20261010_00"
            return {"successful": True, "data": {"response_data": {
                "id": "existing_event", "summary": "Schedule a capstone demo rehearsal",
                "start": {"dateTime": "2026-11-08T17:00:00Z"},
                "end": {"dateTime": end}, "attendees": [{"email": "self@example.com"}],
                "description": "Displayed for manual review",
            }}}

    client = Client()
    result = verify_existing(client, "test-user", "existing_event", "self@example.com")
    assert result["verified"] is expected_verified
    assert client.calls == 1
    assert result["actual"]["start"] == "2026-11-08T10:00:00"
    if not expected_verified:
        assert "end" in result["mismatches"]
