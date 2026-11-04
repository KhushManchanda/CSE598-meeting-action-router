# Stakeholder walkthrough — script and talking points

Draft prep material for the ~6-8 minute video for Neha (HANDOFF.md,
"Record the stakeholder walkthrough"). **Nobody has recorded this
yet** — this is a script to rehearse from, not a transcript of
something that happened. Fill in the bracketed choices, rehearse once
dry, then record. Keep API keys and any credential/consent screens out
of frame.

Pick ONE of you to narrate; the other can drive the keyboard if that's
easier live, or skip that split and have one person do both.

---

## 0. Before you hit record

- Decide: Streamlit UI (`python run_ui.py`, more visual) or CLI
  (`run_agent.py`, more direct/faster to narrate)? The steps below work
  for either; UI-specific notes are in brackets.
- Pick a transcript. Recommended: **`data/synthetic/synth_eng_sync_01/`**
  — short (9 lines), real reviewed gold, and exercises
  speaker-differs-from-owner (the core pitch) without the AMI excerpts'
  messier real speech, which is harder to follow live. Swap in
  `baselines/b0_rules/examples/test1.txt` if you'd rather use the
  original capstone example instead.
- Decide live-tools or mock-tools for the actual write. Live needs a
  connected Composio account and `--confirm-live`; it's higher-stakes
  to demo live (something can go wrong on camera) but more convincing.
  Mock is safer to rehearse with first.
- Have `data/gold/<transcript_id>.json` open in a second window so you
  can show "here's what a human labeled this as" as a point of
  comparison if Neha asks how you know the system is right.

## 1. The problem (30-45s)

Say, in your own words, roughly:

> "After a meeting, someone has to go back through the transcript,
> figure out who actually owns each follow-up, work out real dates
> from things like 'next Friday', and manually create the calendar
> event, Trello card, or email. That's slow and error-prone, and the
> errors are specifically things like crediting the wrong person
> because they weren't the one who said it out loud."

Show the raw transcript file in a text editor for 5-10 seconds — let
Neha see it's genuinely unstructured speaker-labeled text, not a
clean form.

## 2. Transcript, meeting date, roster (30s)

Show:
- The transcript file (`data/synthetic/synth_eng_sync_01/transcript.txt`
  or your chosen one).
- The meeting date (`meta.json`).
- The roster (`roster.json`) — point out it's name + aliases + email +
  Trello member id, and that this is how the system turns "Chef" or
  "Sunny" into a real person later.

> "This roster is how we resolve nicknames and ambiguous references —
> you'll see that come up in a minute."

## 3. Start a real run, show proposals + evidence (60-90s)

CLI:
```bash
python run_agent.py --input data/synthetic/synth_eng_sync_01/transcript.txt \
  --roster data/synthetic/synth_eng_sync_01/roster.json \
  --meeting-date 2026-10-05 --meeting-id neha-demo-01 --tools mock
```
[UI: pick "OpenAI + mock tools", select or upload the transcript, fill
in the meeting date, click run.]

When the first proposal appears, pause and narrate what's on screen:
owner, due date, which tool (Calendar/Trello/Gmail), and — this is the
part worth dwelling on — **the evidence**: the exact transcript lines
backing this claim. Point out specifically:

> "Dana says 'Omar will deploy the auth service to staging by
> Thursday' — Dana is the speaker, but Omar is the actual owner. The
> system got that right, and you can see exactly which line it's
> citing as proof, not just taking our word for it."

## 4. Edit one, reject one (45-60s)

Pick an item and edit a field live (e.g. correct a due date or
owner) — narrate that an edit goes back through validation before
it's allowed through. Reject a different item (e.g. a genuinely
ambiguous one) and explain:

> "This one got flagged because the transcript doesn't actually say
> who's doing it — rather than guess, it's asking a human. That's a
> deliberate design choice: wrong guesses are worse than asking."

## 5. Approve Calendar / Trello / Gmail actions (60-90s)

Approve the remaining items one at a time. For each, name which real
tool it's about to touch and what "verified" means:

> "It's not just creating this — it reads the object back afterward
> and checks the title, date, and attendees match what was intended,
> before it tells you it succeeded."

If using live tools: show the actual Google Calendar / Trello board /
Gmail drafts folder in a browser tab right after, so Neha sees the
real object, not just a JSON blob claiming success.

## 6. Report, history, limitations (45-60s)

Show the JSON report / run history view. Then say plainly, in your own
words — don't skip this part, it's the credible part of the demo:

> "A few things this doesn't do yet: it schedules every calendar event
> at a fixed 10am slot since we don't extract meeting times from the
> transcript; Gmail only creates drafts, it never sends; and our
> evaluation so far covers [N] reviewed example meetings, not a large
> dataset — that's AI-reviewed so far, not yet independently checked by
> a second person on our team."

(Fill in N from the actual eval run once you have it — see
`results/results.md` / this project's Milestone 2 report for the
current number.)

## 7. Ask for feedback (30-45s)

Close with actual questions, not just "let us know what you think":

- "Does this match how you'd actually want to review these before
  they go out?"
- "Is the owner/date/destination information enough, or is something
  missing before you'd trust it unsupervised?"
- "What would block you from using this day to day?"
- "What would you consider the right final deliverable here?"

---

## After recording

Per HANDOFF.md: don't invent or share a video URL without being asked.
Record the actual stakeholder meeting notes separately — date,
participants, what Neha said, and **Feedback → Team response → Next
action** for each point she raises. A video alone does not satisfy the
"stakeholder meeting" requirement; the follow-up conversation does.
