# AMI Meeting Corpus excerpts — source, license, and labeling notes

## Source

**AMI Meeting Corpus**, manual annotations v1.6.2.
- Official site: https://groups.inf.ed.ac.uk/ami/corpus/
- Download used: https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip
  (22MB, released 2017-04-10)
- **License: Creative Commons Attribution 4.0 International (CC BY 4.0)**,
  as stated on the official site.

The full 22MB annotation archive is **not** vendored into this repo —
only our 7 curated excerpts (derived, attributed extracts) are checked
in under `data/ami/`. `scripts/build_ami_excerpts.py` regenerates them
(and can produce more) from a fresh download of the archive above.

## What these excerpts are

AMI's "scenario" meetings (series `ES20xx`, `IS10xx`, `TS30xx`) are
role-played: four participants are assigned the roles **Project
Manager (PM)**, **Industrial Designer (ID)**, **User Interface
Designer (UI)**, and **Marketing Expert (ME)** for a fictional
remote-control design task, across a 4-meeting series (a/b/c/d). The
PM/ID/UI/ME → speaker-letter mapping is itself AMI's own public
metadata (`corpusResources/meetings.xml`), not something we guessed or
invented. We use the role title as each person's roster "name" (e.g.
`"Project Manager"`) rather than inventing a personal name, since the
role is the one stable, documented identity AMI assigns.

We picked 7 excerpts (target was "5 to 8") by scanning full meeting
transcripts for action-item cue density and selecting the closing
segment of each, where the Project Manager wraps up and assigns
individual/paired follow-up work for before the next meeting — see
`scripts/build_ami_excerpts.py`'s `EXCERPTS` list for the exact
(meeting, utterance range) picked.

| excerpt_id | source meeting | utterances | meeting_date |
|---|---|---|---|
| ami_es2008c_closing | ES2008c | 46 | 2005-02-04 |
| ami_es2009c_closing | ES2009c | 65 | 2005-02-14 |
| ami_es2011c_closing | ES2011c | 62 | 2005-02-18 |
| ami_is1003b_closing | IS1003b | 74 | 2004-11-19 |
| ami_is1003c_closing | IS1003c | 74 | 2004-11-19 |
| ami_ts3003b_closing | TS3003b | 45 | 2004-10-11 |
| ami_ts3005b_closing | TS3005b | 45 | 2004-10-13 |

## Fidelity: we reconstruct, we do not edit

Transcript text is reconstructed exactly as AMI's own transcribers
wrote it (fillers, disfluencies, false starts included) — we do not
clean up, paraphrase, or correct it. "Never make up AMI content" cuts
both ways: we also don't redact or alter it.

**Known consequence**: in 4 of the 7 excerpts, a participant is
addressed by an actual first name instead of their role title —
`ami_es2009c_closing` ("Nathan", "Ron"), `ami_is1003b_closing`
("Florent", "David Jordan"), `ami_is1003c_closing` ("Baba", "David
Jordan"). This is how AMI recorded and transcribed these sessions; we
are surfacing it, not introducing it. If this is a concern for wider
distribution, these are the 4 files to redact — ask and we will.

## Gold-labeling judgment calls (gold_draft/, pending review)

Several PM wrap-up utterances assign tasks like "look and feel design,
user interface design, product evaluation" to "you each" / "you two"
**without** naming which role does which. We did **not** guess: any
owner that isn't explicitly stated (by role title, or by a first name
we could confidently map) is left `owner: null` with
`category: "ambiguous_escalate"` — consistent with this project's
"don't guess, escalate" policy (see `data/gold/test1.NOTES.md` for the
same principle applied to B0).

Where a first name is used (Nathan/Ron/Florent/Baba/David Jordan), we
did not confidently map it to a role either — those are tagged
`category: "pronoun_or_alias"` with `owner: null`, since resolving them
requires either audio/video (not available to us) or an elimination
argument from the roles already assigned elsewhere in the same
utterance (not a certainty). Reviewers with more context should feel
free to fill in a confident owner during gold review — that's what
`gold_draft/` → `gold/` review is for.

Content-based (not certain) guesses, left out of the JSON itself but
recorded here for whoever reviews these:
- `ami_es2009c_closing`: "Nathan" is plausibly the Industrial Designer
  (assigned "basic look and feel"), "Ron" plausibly the User Interface
  Designer (assigned menu/layout work) — **our** roster.json for this
  excerpt adds these as aliases under that guess; revisit on review.
- `ami_is1003b_closing`: "Florent" is plausibly the Marketing Expert,
  by elimination (ID and UI are explicitly assigned elsewhere in the
  same utterance, PM is the speaker, leaving ME as the only
  unaccounted-for role).
- `ami_is1003c_closing`: "Baba" and "David Jordan" are plausibly the
  Industrial Designer and User Interface Designer (the usual pair
  assigned the clay-prototype task in this scenario), in unknown order.

This item (one person, one task, two possible names, unknown order) is
also a real example of a genuinely **multi-owner** action that our
single-`owner`-string schema can't cleanly represent — worth noting as
a found limitation, not papered over.
