import pytest

from agent.tools.composio_errors import raise_for_composio_result
from agent.tools.errors import (
    ExpiredAuthError, InvalidArgumentError, RateLimitError, ServiceUnavailableError, ToolError, ToolTimeoutError,
)


def test_successful_result_returns_data():
    data = raise_for_composio_result("SOME_SLUG", {"successful": True, "data": {"id": "evt_1"}, "error": None})
    assert data == {"id": "evt_1"}


def test_successful_with_missing_data_returns_empty_dict():
    data = raise_for_composio_result("SOME_SLUG", {"successful": True, "data": None, "error": None})
    assert data == {}


@pytest.mark.parametrize(
    "error_message,expected_exc",
    [
        ("429 Too Many Requests", RateLimitError),
        ("Rate limit exceeded, slow down", RateLimitError),
        ("503 Service Unavailable", ServiceUnavailableError),
        ("Internal server error occurred", ServiceUnavailableError),
        ("Request timed out after 30s", ToolTimeoutError),
        ("401 Unauthorized: token expired", ExpiredAuthError),
        ("Connection expired, please re-authenticate", ExpiredAuthError),
        ("400 Bad Request: invalid parameter 'due'", InvalidArgumentError),
    ],
)
def test_error_messages_map_to_expected_exception_type(error_message, expected_exc):
    with pytest.raises(expected_exc):
        raise_for_composio_result("SOME_SLUG", {"successful": False, "data": {}, "error": error_message})


def test_unrecognized_error_raises_generic_tool_error_not_silently():
    with pytest.raises(ToolError):
        raise_for_composio_result("SOME_SLUG", {"successful": False, "data": {}, "error": "something weird happened"})


def test_missing_error_message_still_raises_with_a_message():
    with pytest.raises(ToolError, match="SOME_SLUG"):
        raise_for_composio_result("SOME_SLUG", {"successful": False, "data": {}, "error": None})
