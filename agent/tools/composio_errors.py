"""
agent/tools/composio_errors.py
---------------------------------
Composio's tools.execute() returns {"successful": bool, "error":
Optional[str], "data": dict} rather than raising typed exceptions per
HTTP status code the way agent/tools/mock_backend.py does -- this maps
that result into the SAME exception types (agent/tools/errors.py), so
agent/verifier.py's retry/escalate logic works unchanged against a
live backend.

This is pattern-matching on the error STRING (Composio doesn't expose
a clean status code at this layer), which is inherently best-effort --
an unrecognized error raises the generic ToolError base class, which
agent/verifier.py's `except Exception` catches as "escalate" (the safe
default when a failure can't be confidently classified), never a
silent success and never a blind retry.
"""

from __future__ import annotations

from agent.tools.errors import (
    ExpiredAuthError,
    InvalidArgumentError,
    RateLimitError,
    ServiceUnavailableError,
    ToolError,
    ToolTimeoutError,
)

_PATTERNS: list[tuple[tuple[str, ...], type[ToolError]]] = [
    (("429", "rate limit", "too many requests"), RateLimitError),
    (("503", "502", "500", "server error", "service unavailable", "internal error"), ServiceUnavailableError),
    (("timeout", "timed out"), ToolTimeoutError),
    (
        ("401", "unauthorized", "token expired", "invalid credentials", "re-authenticate", "connection expired"),
        ExpiredAuthError,
    ),
    (("400", "invalid", "bad request", "validation"), InvalidArgumentError),
]


def raise_for_composio_result(action_slug: str, result: dict) -> dict:
    """Returns result["data"] on success; raises the best-matching
    typed error on failure."""
    if result.get("successful"):
        return result.get("data") or {}

    message = result.get("error") or f"{action_slug} failed with no error message"
    lowered = message.lower()
    for keywords, exc_type in _PATTERNS:
        if any(k in lowered for k in keywords):
            raise exc_type(f"{action_slug}: {message}")
    raise ToolError(f"{action_slug}: {message} (unclassified -- treated as escalate, not retried)")
