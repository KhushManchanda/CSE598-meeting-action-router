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

## Gold-labeling judgment calls (reviewed — see data/gold/ and data/ANNOTATION_GUIDE.md)

Several PM wrap-up utterances assign tasks like "look and feel design,
user interface design, product evaluation" to "you each" / "you two"
**without** naming which role does which. We did **not** guess: any
owner that isn't explicitly stated (by role title, or resolved below)
is left `owner: null` with `category: "ambiguous_escalate"` —
consistent with this project's "don't guess, escalate" policy (see
`data/gold/test1.NOTES.md` for the same principle applied to B0).

Where a first name is used (Nathan/Ron/Florent/Baba/David Jordan),
resolving it to a role needed one of two kinds of argument — and only
one kind survived review as something we're willing to call "not a
guess":

- **Pure elimination** (kept, treated as resolved): the transcript
  itself, combined with the known closed set of 4 roles, forces a
  unique answer with no appeal to outside knowledge. `ami_is1003b_closing`'s
  "Florent" (u65-66) is this case: in the same utterance (u60), PM has
  already explicitly named the Industrial Designer and the User
  Interface Designer for their own tasks; PM (the speaker) isn't
  addressing themselves; that leaves exactly one role (Marketing
  Expert) for exactly one remaining name. Added "Florent" as a roster
  alias for Marketing Expert and set
  `ami_is1003b_closing-gold-3`'s owner accordingly.
- **Content-based convention** (rejected, left unresolved): matching a
  name to a role via what the TASK CONTENT typically implies (e.g.
  "look and feel" sounds like Industrial-Designer work, by general
  convention in this AMI scenario family) is reasoning from outside
  the transcript, not from it — exactly the kind of guess this
  project's "don't guess" policy exists to prevent. Two cases were
  originally drafted this way and were corrected on review:
  - `ami_es2009c_closing`'s "Nathan"/"Ron" (u57-59): originally guessed
    as Industrial Designer / User Interface Designer by task-content
    convention, with roster.json aliases added to match. The aliases
    created a real, found inconsistency: a system correctly using our
    own `lookup_participant` tool would have resolved "Nathan" and been
    scored WRONG against a gold that said `owner: null`. Fixed by
    removing both aliases from `ami_es2009c_closing/roster.json`;
    `owner: null` / `category: "pronoun_or_alias"` stands, now
    consistent with what the roster can actually resolve.
  - `ami_is1003c_closing`'s "Baba"/"David Jordan" (u48, u61): two names
    need mapping to 2 of 3 remaining roles (ID/UI/ME), which is not a
    forced 1:1 elimination the way Florent's single name/single role
    case was — matching them specifically to {ID, UI} (the pair that
    usually builds the clay prototype in this scenario) is the same
    convention-based guess as Nathan/Ron. `owner: null` stands.

This distinction — internal logical necessity vs. external convention,
however plausible — is the dividing line used throughout review.

This item (one person, one task, two possible names, unknown order) is
also a real example of a genuinely **multi-owner** action that our
single-`owner`-string schema can't cleanly represent — worth noting as
a found limitation, not papered over.
