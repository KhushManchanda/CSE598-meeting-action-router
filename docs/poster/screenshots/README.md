# Sponsor UI screenshot walkthrough

Captured November 3, 2026, from the actual running local Streamlit app.
Run: ui-3ffbb9d36678. These are unedited browser screenshots.

IMPORTANT: This set uses Offline walkthrough: scripted model responses,
fictional participants, and simulated tool writes. It demonstrates the
implemented UI and downstream approval/verification workflow. It does not
demonstrate real-model extraction accuracy or live account operations.
No local credentials were read and no external objects were created.

Suggested introduction to Neha:

> These screenshots show our current review interface using a fictional
> demonstration meeting and simulated tools. You can see the transcript,
> source evidence, action review controls, draft content, and final statuses.
> Please let us know whether this workflow addresses your needs, what is
> missing or confusing, and which outcomes we should prioritize for the
> final version. Our separate CLI smoke tests have exercised live tools;
> these particular images are an offline UI demonstration.

## Captions

1. **01_meeting_setup.jpg**: The organizer supplies a speaker-labeled
   transcript and meeting date. Offline mode is explicitly indicated.
   The participant roster is available farther down the setup form.
2. **02_action_evidence.jpg**: A proposed task displays its owner,
   destination, due date, and description beside cited source evidence.
   The organizer can inspect or edit fields before approval.
3. **03_approval_controls.jpg**: Approve/reject controls gate execution.
   The task title was edited to "Prepare the reviewed deployment checklist"
   before approval; the resulting title is visible in images 5 and 6.
4. **04_gmail_draft_review.jpg**: The email recipient and agenda body can
   be reviewed alongside the source commitment before creating a mock draft.
   Gmail integration is draft-only; this screenshot contains fictional data.
5. **05_final_results.jpg**: The completed run records two verified mock
   actions and one rejected Calendar proposal. The rejected action was not
   executed. A JSON report is available for download.
6. **06_verified_mock_task.jpg**: Expanding the verified task exposes the
   mock object's final title, assignee, due date, list, and description.
   This is a simulated object, not a card from a live Trello board.

The Calendar proposal was deliberately rejected to demonstrate user control;
it was not rejected because a defect was detected. The offline grounding
responses are scripted and should not be presented as independent evidence
that the edited content was semantically correct.
