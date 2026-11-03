"""Inspect the existing one-person demo card; never create a card or call an LLM.

Default: read-only. --correct-due updates ONLY the supplied card's deadline,
after checking that all other expected demo fields match. Run only with the
owner's permission to use this checkout's .env and connected Trello account.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.tools.live_trello import (  # noqa: E402
    GET_CARD_SLUG, TRELLO_CARD_FIELDS, TRELLO_TOOLKIT_VERSION,
    _normalize_card, trello_due_timestamp,
)

EXPECTED_TITLE = "Prepare the capstone demo slides"
EXPECTED_DUE = "2026-11-06"
EXPECTED_DESCRIPTION = "Arjun Ranjan will prepare the capstone demo slides by November 6, 2026."


def verify_existing(client, user_id, card_id, list_id, member_id, correct_due=False):
    expected = {"title": EXPECTED_TITLE, "due": EXPECTED_DUE, "member_ids": [member_id],
                "list_id": list_id, "description": EXPECTED_DESCRIPTION}

    def read():
        response = client.tools.execute(
            slug=GET_CARD_SLUG, arguments={"idCard": card_id, "fields": TRELLO_CARD_FIELDS},
            user_id=user_id, version=TRELLO_TOOLKIT_VERSION,
        )
        if not response.get("successful"):
            raise RuntimeError("Card read failed; no further action taken")
        raw = response.get("data") or {}
        card = raw.get("card") if isinstance(raw.get("card"), dict) else raw
        if card.get("id") != card_id:
            raise RuntimeError("Read-back card ID did not match the requested card")
        normalized = _normalize_card(raw, None, "", "")
        actual = {"title": normalized["title"], "due": normalized["due"],
                  "member_ids": card.get("idMembers"), "list_id": normalized["list_id"],
                  "description": normalized["description"]}
        return card, actual

    card, before = read()
    mismatches = {key: {"expected": value, "actual": before[key]}
                  for key, value in expected.items() if before[key] != value}
    updated = False
    if correct_due and mismatches:
        if set(mismatches) != {"due"}:
            raise RuntimeError("Other demo fields differ; refusing to change the deadline")
        response = client.tools.execute(
            slug="TRELLO_UPDATE_CARDS_BY_ID_CARD",
            arguments={"idCard": card_id, "due": trello_due_timestamp(EXPECTED_DUE)},
            user_id=user_id, version=TRELLO_TOOLKIT_VERSION,
        )
        if not response.get("successful"):
            raise RuntimeError("Deadline update failed; inspect the existing card before retrying")
        updated = True
        card, actual = read()
    else:
        actual = before
    return {"card_id": card_id, "url": card.get("url"), "timezone": "America/Phoenix",
            "deadline_convention": "17:00 local time for date-only tasks",
            "deadline_updated": updated, "before": before, "actual": actual,
            "mismatches": {key: {"expected": value, "actual": actual[key]}
                           for key, value in expected.items() if actual[key] != value},
            "verified": actual == expected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card-id", required=True)
    parser.add_argument("--correct-due", action="store_true",
                        help="Update only the existing demo card's due date, then read back")
    args = parser.parse_args()

    from dotenv import dotenv_values
    from composio import Composio

    config = dotenv_values(ROOT / ".env", interpolate=False)
    if not config.get("COMPOSIO_API_KEY") or not config.get("TRELLO_LIST_ID"):
        raise SystemExit("COMPOSIO_API_KEY and TRELLO_LIST_ID must be configured locally")
    roster = json.loads((ROOT / "data/demo/arjun_trello/roster.json").read_text())
    try:
        result = verify_existing(
            Composio(api_key=config["COMPOSIO_API_KEY"]),
            config.get("COMPOSIO_USER_ID") or "meeting-action-router", args.card_id,
            config["TRELLO_LIST_ID"], roster[0]["trello_member_id"], args.correct_due,
        )
    except Exception as exc:
        # Provider errors can contain keys; never print raw exceptions.
        raise SystemExit(f"Verification stopped ({type(exc).__name__}); no card creation was attempted") from None
    path = ROOT / "runs/trello_existing_card_verification.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"Verification evidence: {path}")
    if not result["verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
