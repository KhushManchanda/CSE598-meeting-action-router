#!/usr/bin/env python3
"""
scripts/composio_connect.py
------------------------------
One-time, human-in-the-loop setup: connect a Google/Trello account to
this project's Composio user_id for one toolkit. Opens a consent URL
that YOU must visit and approve in a browser; this script just prints
the URL and blocks until Composio reports the connection active (or
times out).

Usage:
    python scripts/composio_connect.py --toolkit GOOGLECALENDAR
    python scripts/composio_connect.py --toolkit GMAIL
    python scripts/composio_connect.py --toolkit TRELLO

Run once per toolkit, ever (per COMPOSIO_USER_ID) -- nothing in the
rest of this project calls toolkits.authorize() automatically.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from agent.tools.composio_client import get_client, get_user_id  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect a Composio-managed account for one toolkit.")
    parser.add_argument("--toolkit", required=True, choices=["GOOGLECALENDAR", "GMAIL", "TRELLO"])
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    client = get_client()
    user_id = get_user_id()

    print(f"Requesting a connection for toolkit={args.toolkit!r}, user_id={user_id!r}...")
    connection_request = client.toolkits.authorize(user_id=user_id, toolkit=args.toolkit)

    if connection_request.redirect_url:
        print(f"\nOpen this URL and approve access:\n\n  {connection_request.redirect_url}\n")
    print(f"Waiting up to {args.timeout:.0f}s for you to complete it...")

    connected_account = connection_request.wait_for_connection(timeout=args.timeout)
    print(f"Connected. status={connected_account.status!r} id={connected_account.id!r}")


if __name__ == "__main__":
    main()
