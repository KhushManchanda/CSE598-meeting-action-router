"""
agent/tools/errors.py
-----------------------
Exception types shared by the mock tool backend (step 2) and, in step 7,
the real Calendar/Trello/Gmail adapters — so the router/verifier's
retry-vs-escalate logic (step 4) can be written once against these types
and never needs to know whether it's talking to the mock or the real API.
"""


class ToolError(Exception):
    """Base class for every simulated or real external-tool error."""


class RateLimitError(ToolError):
    """HTTP 429 — too many requests. Transient, retry with backoff."""


class ServiceUnavailableError(ToolError):
    """HTTP 5xx — server-side failure. Transient, retry with backoff."""


class ToolTimeoutError(ToolError):
    """Network/request timeout. Transient, retry with backoff."""


class ResponseLostError(ToolError):
    """The write actually succeeded server-side, but this call's response
    was lost before the client saw it (e.g. the connection dropped right
    after the server committed it). Transient from the caller's point of
    view: retrying with the SAME idempotency key returns the already-
    committed object instead of creating a duplicate."""


class InvalidArgumentError(ToolError):
    """The request itself was malformed. NOT retryable as-is — the spec
    routes this back to the resolver to fix the arguments, not to blind
    retry."""


class ExpiredAuthError(ToolError):
    """OAuth/API token expired or revoked. NOT retryable — the spec routes
    this to manual review (someone needs to re-authenticate)."""


# Errors where a bare retry (same request, same idempotency key) is the
# correct recovery strategy, per the spec's verifier/retry rules.
TRANSIENT_ERRORS = (RateLimitError, ServiceUnavailableError, ToolTimeoutError, ResponseLostError)
