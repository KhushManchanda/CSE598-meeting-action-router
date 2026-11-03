"""Read-only local .env checks; never prints keys or account credentials.

Run only with the owner's permission to read this checkout's .env.
--network checks provider authentication, connection metadata, and tool schemas.
It performs no generation requests and executes no integration actions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
VARIABLES = ("OPENAI_API_KEY", "LLM_MODEL", "COMPOSIO_API_KEY", "COMPOSIO_USER_ID", "TRELLO_LIST_ID")
EXPECTED_ARGS = {
    "GOOGLECALENDAR_CREATE_EVENT": {"summary", "start_datetime", "end_datetime", "attendees", "description"},
    "GOOGLECALENDAR_EVENTS_GET": {"event_id"},
    "GMAIL_CREATE_EMAIL_DRAFT": {"recipient_email", "subject", "body", "cc"},
    "GMAIL_GET_DRAFT": {"draft_id"},
    "TRELLO_ADD_CARDS": {"idList", "name", "desc", "due", "idMembers"},
    "TRELLO_GET_CARDS_BY_ID_CARD": {"idCard"},
}


def safe_error(exc: Exception) -> dict:
    # Provider messages can contain credentials. Return only bounded metadata.
    return {"error_type": type(exc).__name__, "http_status": getattr(exc, "status_code", None)}


def check(network: bool = False) -> dict:
    config = dotenv_values(ROOT / ".env", interpolate=False)
    result = {"variables": {name: bool(config.get(name)) for name in VARIABLES}}
    result["env_gitignored"] = __import__("subprocess").run(
        ["/usr/bin/git", "check-ignore", "-q", ".env"], cwd=ROOT,
        capture_output=True,
    ).returncode == 0
    if not network:
        return result

    import httpx

    key = config.get("OPENAI_API_KEY")
    if key:
        try:
            with httpx.Client(timeout=20, trust_env=False) as client:
                response = client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
                status = response.status_code
                models = response.json().get("data", []) if status == 200 else []
                model = config.get("LLM_MODEL") or "gpt-4o-mini"
                result["openai"] = {"http_status": status, "authenticated": status == 200,
                                    "configured_model_listed": any(m.get("id") == model for m in models)}
        except Exception as exc:
            result["openai"] = safe_error(exc)
    key = config.get("COMPOSIO_API_KEY")
    if key:
        from composio import Composio

        client = Composio(api_key=key)
        user_id = config.get("COMPOSIO_USER_ID") or "meeting-action-router"
        try:
            page = client.connected_accounts.list(user_ids=[user_id])
            # Do not serialize account objects: they may include auth state.
            connections = [{"toolkit": item.toolkit.slug, "status": item.status} for item in page.items]
            result["composio"] = {"authenticated": True, "connections": connections,
                                  "using_default_user_id": not bool(config.get("COMPOSIO_USER_ID"))}
        except Exception as exc:
            result["composio"] = safe_error(exc)
        schemas = {}
        for slug, expected in EXPECTED_ARGS.items():
            try:
                tool = client.tools.get_raw_composio_tool_by_slug(slug)
                schema = getattr(tool, "input_parameters", None) or getattr(tool, "parameters", None) or {}
                properties = schema.get("properties", {})
                required = set(schema.get("required", []))
                schemas[slug] = {"unknown_sent_parameters": sorted(expected - set(properties)),
                                 "required_not_sent": sorted(required - expected),
                                 "required_parameters": sorted(required)}
            except Exception as exc:
                schemas[slug] = safe_error(exc)
        result["tool_schemas"] = schemas
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.network), indent=2))
