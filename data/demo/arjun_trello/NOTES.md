# One-person Trello smoke test

Meeting date: 2026-11-03. Expected: one Trello task for preparing the capstone demo slides, owned by Arjun Ranjan, due 2026-11-06.

This fixture is for a manual integration smoke test, outside the evaluation splits. The member ID was supplied by the user from a successful authenticated Trello identity lookup. The email is intentionally empty: this fixture is for Trello only, not Calendar or Gmail.

The supplied demo board's To Do list ID is `6ae9cbc8d83a099c8d68e19e`. Configure it locally as TRELLO_LIST_ID; no environment files are changed by adding these fixtures.

Review the proposed owner, date, and destination before approving a live action. Provider authentication and schema checks alone do not verify live create/read-back behavior.

The fixture now uses one explicit named commitment. The first live attempt's two-sentence wording produced an extra candidate whose pronoun-only quote failed grounding. This remains a recorded extraction/grounding limitation. The approved action was blocked locally by Composio's missing-version check before card creation; the Trello adapter now pins release `20261007_01` for create and read-back.

Use a fresh meeting ID for the next attempt (for example `arjun-trello-demo-02`): escalated ledger entries from the first attempt are terminal and skipped on rerun.

Once a card exists, do not use a fresh meeting ID to troubleshoot read-back: that can create another card. Run `python scripts/verify_trello_demo.py --card-id <existing-id>` for read-only verification. Adding `--correct-due` updates only that card's deadline, and only if its title, description, list, and member IDs already match this fixture. It does not change the original run report or ledger.

The live demo uses America/Phoenix and 17:00 local time as an explicit convention for date-only Trello deadlines. LiveTrello accepts a different timezone_name in its constructor. Read-back compares the date in that timezone. Midnight UTC on November 6 is November 5 in Phoenix, so merely truncating a UTC timestamp would wrongly verify the date shown to the user.

The demo-03 card was created successfully, but the default Composio read-back returned only its ID. The adapter now requests the exact card fields it verifies instead of relying on that default. Subsequent verification of the existing card corrected its deadline and returned zero mismatches; the original failed report remains unchanged.

The separate checklist fixture transcript_full_run.txt then passed the complete agent path as arjun-trello-full-01: Verified: 1, Escalated: 0, Tool calls used: 1 ($0.000501). Repeating that same meeting ID with its persisted ledger reported one completed action skipped and zero execution calls ($0.000122 for extraction). This checks an unchanged one-action meeting's skip behavior, not general crash/lost-response safety.
