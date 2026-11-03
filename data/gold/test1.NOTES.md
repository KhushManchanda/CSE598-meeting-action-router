# Gold labeling notes — data/gold/test1.json

Meeting date: **2026-09-02** (Wednesday). Transcript:
`baselines/b0_rules/examples/test1.txt` (vendored, unmodified).

This file records the reasoning behind each gold item, in particular the
calls that are not mechanical (cross-turn delegation resolution). Keep
this file next to the gold JSON so Arjun/Khush/future-us can see *why*
a label is what it is, not just what it is.

## Item-by-item

- **G1** (`u3`, "Marcus will schedule a demo..."): owner named in-sentence
  (Marcus), unambiguous. `due`: "next week" has no specific day — left
  `null` rather than guessing; a good agent should ask for clarification
  or flag low-confidence rather than pick an arbitrary weekday.
- **G2** (`u5`, "Jordan needs to send an email..."): owner named
  in-sentence (Jordan), unambiguous. No date mentioned.
- **G3** (`u6`+`u7`): `u6` is Marcus raising it with no named owner
  ("someone should follow up"); `u7` is Priya claiming it one turn later
  ("I'll handle that one. Priya will email the legal team..."). These two
  utterances describe **one** action item — true owner is Priya, resolved
  via the very next turn. Evidence spans both utterances.
- **G4** (`u8`): owner named in-sentence (Jordan) and matches speaker. No
  resolvable absolute date ("once the pipeline is fixed" is conditional,
  not a date).
- **G5** (`u9`+`u10`): same cross-turn pattern as G3 — `u9` is Priya's
  unassigned "we must write release notes before Friday's launch"; `u10`
  is Marcus claiming the drafting specifically. True owner Marcus,
  resolved one turn later. `due` resolved from "before Friday's launch"
  relative to the 2026-09-02 (Wed) meeting date -> the same week's
  Friday, **2026-09-04**. ("Before Friday" could arguably mean
  2026-09-03; we chose the launch day itself as the deadline anchor —
  flagging this as a judgment call, not a certainty.)
- **G6** (`u10` only): "...and create a task to track review" is a
  *second*, distinct action item merged into the same line as G5 by both
  the speaker and by B0's single-item-per-line extractor. No distinct
  reviewer is named, so owner defaults to Marcus (the person committing
  to create the tracking task). Same due-date reasoning as G5.

## Why this gives 3/7 owner accuracy on B0, not the README's "4/7 (57.1%)"

B0's baseline README (`baselines/b0_rules/README.md`, section 7) reports
owner accuracy as 4 of 7 **raw extracted items** correct, calling out
items 1, 2, and 6 (in B0's own 1-indexed output order) as mis-attributed.

Applying **one consistent rule** — "true owner is whoever is explicitly
named as the doer, resolving across turns when a vague commitment
('someone', 'we') is claimed by a named person in a nearby turn" — to
*every* item gives a different count. The README's own claim is
internally inconsistent by this rule: it treats B0's raw-item **6**
(`u9`, "we must write release notes...") as mis-attributed by resolving
it against the *next* turn (`u10`, Marcus claiming it) — but does not
apply that same cross-turn resolution to raw-item **3** (`u6`, "someone
should follow up with legal..."), which is resolved the exact same way
one turn later (`u7`, Priya claiming it). Scored consistently, B0's
raw-item 3 is *also* wrong (true owner Priya, B0 says Marcus), which
drops the count to **3 of 7 (42.9%)**, not 4 of 7.

We are keeping our own, consistently-applied gold (3/7) as the real
gold for this project rather than quietly matching the README's number,
per the project's "never fabricate results — say so if something
differs" rule. `tests/test_score.py` has a separate, clearly-labeled
sanity-check test against a literal transcription of the README's
claimed 4/7 interpretation, to prove the *scorer's arithmetic* is
correct — it is not treated as gold.
