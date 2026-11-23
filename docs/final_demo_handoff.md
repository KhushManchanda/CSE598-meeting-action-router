# Group 30 final demo handoff

Poster upload is due November 23 at 2:00 PM Arizona time. Submit one portrait
24 × 36-inch PDF as `Group30_Poster.pdf`. The in-person poster session is
December 2. Both team members attend. The teammate handoff ZIP contains
`Group30_Poster_ASU.pdf`, `Group30_Poster_Editorial.pdf`, and editable source.
Rename the selected copy to `Group30_Poster.pdf` for submission. Use this file
to track the remaining implementation behind the product workflow shown on
either poster.

## Milestone 2 evidence

- Reference commit: [e54e61a](https://github.com/KhushManchanda/CSE598-meeting-action-router/commit/e54e61a).
- The Streamlit UI already supports transcript setup, an editable review
  queue, a per-run ledger, saved reports, and an offline walkthrough.
- Live CLI smoke tests verified Trello card creation and Gmail draft
  creation. Calendar creation succeeded, followed by a separate read-back
  after the response parser was fixed. Revised Gmail content was tested
  with mock tools. See the [README](../README.md) for the evidence.
- The evaluation covers 16 transcripts and 51 distinct reference actions.
  Agent A matched 9/23 synthetic actions and 4/22 AMI actions. These are
  verified-output scores. Analyze escalation and extraction separately.

## Work before the final demo

| Priority | Proposed owner | Done when |
| --- | --- | --- |
| Approved Trello view | Khush | One view gathers approved Trello actions from saved UI runs. It distinguishes verified cards from unresolved actions and links to a live card when one exists. Try it with at least two runs. |
| Approval after execution repair | Khush | A repair that changes owner, recipient, date, destination, title, body, or other material arguments returns to review. Unchanged transient retries can reuse approval. Exercise both cases with mock failure injection. |
| Live UI acceptance | Arjun | On connected test accounts, approve and read back one assigned Trello card, one Calendar event with its attendee, and one Gmail draft with the approved recipient and body. Reject a fourth proposal and confirm it caused no write. Save redacted screenshots and the run report. |
| Label review and evaluation | Arjun and Khush | Independently review ambiguous labels and aliases. Run B0, B1, and Agent A on identical saved examples. Archive config, predictions, and scoring. Track extraction misses, correct escalations, and unsupported guesses separately. Use new examples for held-out evaluation if tuning against existing AMI cases. |
| Rehearsal and submission evidence | Arjun and Khush | Rehearse the live flow and its offline fallback, verify grader access, and record the final commit. Confirm the approved-card view answers Neha's request. |

Suggested schedule: implement and test the first two items by November 27,
finish live acceptance and benchmark checks by November 30, and rehearse on
December 1. If a verified demo path fails, switch to the labeled offline
walkthrough and show saved live evidence.

## Demo sequence

Launch `python run_ui.py` from the repository root. Show the transcript,
meeting date, and roster. Inspect the evidence for a proposal, edit one
action, reject another, and approve test-account writes. Show the remote
objects and the report. End with the approved Trello view and explain one
case where the agent escalated because it could not verify the result.

The target stays scoped to text transcripts and reviewer-approved Calendar
events, assigned Trello cards, and Gmail drafts. Human review, tool read-back,
and visible follow-up are part of the demo acceptance criteria.
