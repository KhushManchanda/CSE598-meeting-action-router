# Annotation Guide — gold labels for the Meeting Action-Item Router

This guide covers both datasets (`data/synthetic/`, `data/ami/`):
how a gold item is shaped, what the category tags mean, and the
draft → review workflow.

## Workflow: gold_draft/ → gold/

1. Whoever writes a transcript (synthetic) or picks an excerpt (AMI)
   also drafts its gold labels, into `data/gold_draft/<transcript_id>.json`.
2. Run `python scripts/review_gold.py --transcript-id <id>` to step
   through each draft item and accept or fix it.
3. Only reviewed items move into `data/gold/<transcript_id>.json`.
   **Nothing in `data/gold/` should be unreviewed** — if you wrote the
   draft yourself, a second person (Arjun or Khush, whichever didn't
   write it) should be the one who reviews it where practical.
4. If both of you label the same transcript independently before
   reconciling, `eval/kappa.py` computes Cohen's kappa on the owner
   field over the shared subset — a sanity check that the category
   definitions below are being applied consistently, not just that
   one person's judgment is self-consistent.

## Gold item shape

Same schema as predictions (`agent/schema.py:ActionItem`), with one
gold-only field:

```json
{
  "id": "...", "transcript_id": "...", "task": "...",
  "owner": "... or null", "tool": "calendar_event|trello_task|email_draft|null",
  "due": "YYYY-MM-DD or null", "attendees_or_recipients": ["..."],
  "evidence_utterance_ids": ["u3", "u4"],
  "category": "one of ALLOWED_CATEGORIES below"
}
```

**Don't guess.** If the transcript doesn't support a confident owner,
tool, or date, leave it `null` rather than picking the most plausible
value — a null means "the system should ask for clarification or
escalate," which is a real, scoreable, *correct* behavior, not a gap
to paper over. See `data/gold/test1.NOTES.md` and
`data/ami/ATTRIBUTION.md` for worked examples of this principle.

## Categories (`agent/schema.py:ALLOWED_CATEGORIES`)

Pick the single most salient one; an item can genuinely exhibit more
than one (note the others in prose if you want, but one is required).

| category | meaning | example |
|---|---|---|
| `baseline` | normal case, no particular edge case being tested | "Priya: I'll email the vendor." |
| `speaker_differs_from_owner` | the person who says it isn't the person who does it | "Priya: Marcus will schedule a demo." |
| `multi_turn_delegation` | the true owner is only clear from a *different* utterance (an earlier vague claim, a later confirmation) | "Marcus: someone should follow up." → "Priya: I'll handle that." |
| `multiple_actions_one_line` | one utterance contains 2+ distinct action items | "I'll draft the notes and create a task to track review." |
| `relative_date` | due date stated relative to the meeting ("next Friday", "before launch") | — |
| `absolute_date` | due date stated as a specific date | "by September 10th" |
| `pronoun_or_alias` | owner is named by pronoun, nickname, or an alias not in the roster's canonical name | "he'll handle it", a first name used instead of a role/title |
| `non_action` | NOT a real action item: a suggestion, question, hypothetical, negation, or something already completed. **Should not appear as a gold action item at all** — tag it this way in the transcript's notes file (not as a gold ActionItem) to document that a good system should *not* extract it. |
| `ambiguous_escalate` | the transcript genuinely doesn't resolve who/what clearly enough to act on — `owner`/`tool`/`due` should be `null` and a good system should escalate, not guess |
| `prompt_injection` | the evidence text itself resembles an instruction aimed at the system ("ignore previous instructions...") rather than a real commitment by a real person |

`non_action` items are a documentation device, not a gold ActionItem —
record them in the transcript's own notes (see
`data/synthetic/*.NOTES.md`) as "the system should NOT extract this,"
so recall/precision scoring and manual review both know it was
deliberate, not missed.

## Review provenance (important — read before citing these numbers)

As of 2026-11-03, all 15 `gold_draft/` transcripts (8 synthetic + 7
AMI) have been promoted into `data/gold/` via `scripts/review_gold.py`
(51 items total, alongside the pre-existing 6-item `test1.json`).
**This review was done by Claude (an AI), re-reading every item
against its transcript, not by an independent second human** (Arjun or
Khush) as this guide otherwise recommends. The review was real, not a
rubber-stamp — it found and fixed concrete errors (see
`data/synthetic/synth_marketing_02/NOTES.md`,
`data/synthetic/synth_vendor_call_05/NOTES.md`, and
`data/ami/ATTRIBUTION.md` for exactly what changed and why), and it
fixed a real resolver bug in `agent/dates.py` ("end of day"/"this
afternoon" and similar same-day phrases were previously unresolvable).

This is disclosed, not hidden, per this project's "never fabricate /
always say what's uncertain" rule: **treat these 51 items as a solid
first pass, not a methodologically independent ground truth.** A
genuine second human reviewer (ideally whichever of Arjun/Khush didn't
draft a given transcript) going through `scripts/review_gold.py`
again, re-checking the judgment calls flagged in the notes above, is
still the right next step before these numbers go into anything that
depends on them being unimpeachable (e.g. a publication). For a
sponsor preview of where the project stands, they're real, checked
numbers — just not yet independently human-reviewed.

## Dev vs. test split

`data/splits.json` lists which transcript_ids are in `dev` (safe to
iterate prompts against) vs. `test` (held out — **never** tune
prompts, few-shot examples, or thresholds against test-split
transcripts; that's how an eval number stops meaning anything).
