# Meeting Action-Item Router

An LLM agent that turns speaker-labeled meeting transcripts into real,
verified follow-up actions in Google Calendar and Trello (Gmail drafts as
a stretch goal) — built next to, and benchmarked against, a rule-based
baseline (B0) and a single-call LLM baseline (B1).

Full design doc: see the capstone prompt (not checked in here). This
README tracks **what's actually built**, not the target design — anything
not listed under "Done" is a TODO, not a claim.

## Status (build order)

- [x] **Step 1 — scaffold, B0 vendored + adapter, schema, scorer v1,
      unit tests on `test1.txt`.**
- [x] **Step 2 — mock tool backend (Calendar/Trello/Gmail-drafts fakes),
      idempotency, fault injection, unit tests.**
- [x] **Step 3 — B1 single-call LLM baseline, end to end against the
      mock tool backend.**
- [x] **Step 4 — Agent A: ledger, extractor, resolver (+ its tools),
      validator/critic, approval CLI, router, verifier, recovery,
      budget, audit log, JSON report. Run end to end on `test1.txt`.**
- [~] **Step 5 — partially done, see "Step 5" section below for exactly
      what's finished vs. still TODO.** AMI excerpts (7, within the
      5-8 target) and the gold review CLI/kappa/splits/annotation
      guide are done; synthetic transcripts are at 8 of the ~15 target
      (all required categories covered at least once, including the
      prompt-injection case) — growing this is TODO, not abandoned.
- [ ] Step 6 — eval runner + results tables
- [ ] Step 7 — live Google Calendar / Trello adapters, one live run
- [ ] Step 8 — ablations, full README, Mermaid architecture diagram

## Setup

```bash
python3.13 -m venv .venv   # repo asks for 3.11; this machine only has 3.10/3.13 —
source .venv/bin/activate  # 3.13 used instead, no 3.11-only feature is needed here.
pip install -r requirements.txt
cp .env.example .env       # then fill in OPENAI_API_KEY yourself — never in chat
```

**LLM provider: OpenAI, not Anthropic.** The spec's default was the
Anthropic API; switched to OpenAI at the user's request (no Anthropic
key available). `agent/llm.py` is a thin, provider-swappable wrapper
specifically so this doesn't touch extractor/resolver/validator code
later. Default model: `gpt-4o-mini`, temperature 0 (`agent/config.py`),
pricing verified against platform.openai.com/docs/pricing on 2026-11-02.

No paid API call has been made yet — `tests/test_llm.py` mocks the
OpenAI client entirely (no network, no key, no cost) to test
`agent/llm.py`'s parsing/cost-accounting logic.

## What's implemented so far

- `baselines/b0_rules/` — Neha's baseline (`nkashp/CSE598_Capstone`),
  vendored via `git clone` pinned at commit `3c6a693`. **Not modified.**
- `baselines/b0_adapter.py` — runs B0 on any transcript and converts its
  output into our common schema (`agent/schema.py`).
  ```bash
  python -m baselines.b0_adapter --input baselines/b0_rules/examples/test1.txt
  ```
- `agent/schema.py` — the shared `ActionItem` pydantic v2 model every
  system (B0, B1, agent A, gold) is converted into before scoring.
- `agent/ingestion.py` — parses a transcript into `Utterance`s with
  stable ids (`u1`, `u2`, ...).
- `eval/score.py` — v1 scorer: greedy evidence-overlap + task-similarity
  matching, precision/recall/F1, owner/routing accuracy on the matched
  set, **and** a raw per-prediction owner-accuracy metric (see next
  section for why there are two).
  ```bash
  python -m eval.score --predictions preds.json --gold data/gold/test1.json
  ```
- `data/gold/test1.json` + `data/gold/test1.NOTES.md` — our gold labels
  for the baseline's `test1.txt`, with per-item reasoning.
- `agent/tools/mock_backend.py` — in-memory fake Calendar, Trello, and
  Gmail-drafts for `--tools mock`. Every `create_*` is read-back-able via
  a matching `get_*`, honors idempotency keys (a repeated key returns the
  SAME object instead of creating a duplicate — the guarantee behind
  "rerunning a meeting never creates duplicates"), and supports
  deterministic fault injection (`set_fault_plan`) for 429 / 503 /
  timeout / invalid_argument / expired_token / "created but response
  lost". `agent/tools/errors.py` defines the shared exception types the
  real step-7 adapters will also raise, so the retry/escalate logic
  written in step 4 doesn't change when swapped onto live APIs.
- `agent/llm.py` + `agent/config.py` — the single interface every LLM
  call goes through (OpenAI SDK, model/temperature/pricing config).
  `LLMClient._client` is built lazily on first real call, so importing
  or constructing it needs no API key. No real/paid call has been made
  by anything in this repo yet — `tests/test_llm.py` exercises it
  entirely against a fake client.
- `agent/tool_schemas.py` — OpenAI tool-calling schemas for
  `create_calendar_event` / `create_task` / `create_email_draft`,
  shared by B1 now and by Agent A's router in step 4. Each schema adds
  two bookkeeping-only fields (`owner`, `evidence_utterance_ids`) beyond
  the spec's router signatures, stripped before any real tool call —
  disclosed design note is in the module docstring (owner/evidence
  otherwise has nowhere to live for a system with no ledger).
- `baselines/b1_single_call.py` — one tool-calling LLM request over the
  full transcript + roster + meeting date; every tool call it makes is
  executed once against the mock backend; no validator, no approval, no
  read-back, no retry, matching the spec's B1 definition exactly.
  `data/rosters/test1_roster.json` is a placeholder roster for the
  fictional `test1.txt` transcript (made up for this test fixture, not
  representing anyone real).
  ```bash
  python -m baselines.b1_single_call --input baselines/b0_rules/examples/test1.txt \
      --roster data/rosters/test1_roster.json --meeting-date 2026-09-02
  ```
- **Agent A** (step 4), one module per pipeline stage:
  - `agent/ledger.py` — SQLite state machine (`proposed → resolved →
    validated → approved → executed → verified | escalated | rejected`),
    persisted to a file by default so a rerun can detect an action_id
    that already reached a terminal state and skip it entirely — the
    orchestrator-level half of "never duplicate on rerun" (the other
    half is the mock backend's idempotency-key dedup from step 2).
  - `agent/extractor.py` — one forced structured-output call proposing
    candidates, each with `evidence_quote` + `evidence_utterance_ids`.
  - `agent/participants.py`, `agent/dates.py` — the resolver's
    deterministic `lookup_participant`/`resolve_date` tool backends.
    `resolve_date` deliberately returns `None` (not a guess) for bare,
    dayless phrases like "next week" — same policy as our own gold
    labeling (`data/gold/test1.NOTES.md`).
  - `agent/resolver.py` — the ReAct tool-calling loop
    (`lookup_participant` / `resolve_date` / `get_context` →
    `finalize_resolution`), with a `repair_feedback` hook the
    orchestrator uses to retry with the validator's actual errors
    instead of blindly repeating the same call.
  - `agent/validator.py` — deterministic checks (schema, due-on/after-
    meeting-date, roster membership, verbatim evidence, calendar events
    require a resolved day) **plus** an LLM grounding check ("does the
    evidence actually support this action and owner?"). This grounding
    check is the project's main prompt-injection defense — its test
    explicitly assumes the extractor/resolver already complied with an
    injected instruction, to prove the roster check and approval gate
    hold regardless (`tests/test_orchestrator.py::test_prompt_injection_in_transcript_never_produces_an_unauthorized_write`).
  - `agent/router.py` / `agent/verifier.py` — maps a validated item onto
    the real tool call (idempotency key = `hash(meeting_id, action_id)`),
    then reads it back and compares; retries transient errors (429/503/
    timeout/lost-response) up to 3× with backoff on the *same* key,
    routes invalid-argument back to the resolver, escalates expired-auth.
  - `agent/approval_cli.py` — approve/edit/reject per item, `--auto-approve`
    for batch runs (clearly logged either way); unrecognized input
    defaults to reject, never to a silent approve.
  - `agent/orchestrator.py` — wires all of the above per candidate, with
    a 2-repair-attempt loop before escalating, a 40-tool-call budget
    (escalates whatever's left once hit), and `agent/audit.py`'s JSONL
    log of every model call / tool call / decision with tokens, cost,
    and latency. `run_agent.py` is the CLI (`--tools mock|live`,
    `--auto-approve`); `--tools live` raises `NotImplementedError` for
    now rather than silently acting like mock — that's step 7.
- `tests/` — 199 unit tests, all passing (`pytest -q`). Every stage's
  tests run against a fake/scripted LLM client (deterministic, no
  cost); only the manual CLI runs noted below have made real API calls.

## Step 5 — data, gold labels, review tooling

**AMI Meeting Corpus excerpts — done, 7 of the 5-8 target.**
Source: AMI's own manual-annotations download (CC BY 4.0) — full
provenance, license, and license-compliance notes in
`data/ami/ATTRIBUTION.md`. We do **not** vendor the 22MB annotation
archive; `scripts/build_ami_excerpts.py` regenerates our 7 excerpts
(or more) from a fresh download. Each excerpt is a real PM wrap-up
segment (picked by scanning for action-cue density) where follow-up
work gets assigned — genuinely messy real speech, which is exactly the
texture our clean synthetic transcripts don't have. Speaker→role
(PM/ID/UI/ME) mapping comes from AMI's own public metadata, not a
guess. `data/ami/ATTRIBUTION.md` also discloses every judgment call
made drafting gold for these (several PM assignments don't name who
does what — left `owner: null` / `category: "ambiguous_escalate"`
rather than guessed) and flags that 4 of the 7 excerpts contain a real
participant's first name spoken mid-conversation (AMI's own
transcription, not something we added).

**Synthetic transcripts — 8 of the ~15 target, TODO to grow further.**
`data/synthetic/<id>/{transcript.txt,roster.json,meta.json,NOTES.md}`
+ `data/gold_draft/<id>.json`. Every required category
(`agent/schema.py:ALLOWED_CATEGORIES`) is exercised at least once,
including the required prompt-injection transcript
(`synth_prompt_injection_06` — see its `NOTES.md` for why that line
must produce zero action items). Honest gap: spec's target was "start
with about 15... grow to 20+"; 8 is a real start, not the full target
— said plainly rather than rounded up.

**Gold review workflow — done.** `data/ANNOTATION_GUIDE.md` defines
the category vocabulary and the draft→review process.
`scripts/review_gold.py` steps through `gold_draft/` items one at a
time (accept/fix/skip), writing only reviewed items into `gold/` —
**nothing has been auto-promoted**; every draft above is still
sitting in `gold_draft/` pending an actual human review pass (ideally
by whichever of Arjun/Khush didn't write that draft). `eval/kappa.py`
computes Cohen's kappa on the owner field over a shared, id-matched
subset, for whenever both of you label independently before
reconciling. `data/splits.json` assigns `test1` + 5 synthetic
transcripts to `dev`, everything else (3 synthetic + all 7 AMI) to
held-out `test` — per the annotation guide, test-split transcripts are
never to be tuned against.

**Schema change**: `agent/schema.py:ActionItem` gained an optional
`category` field (gold-only; predictions never set it), validated
against `ALLOWED_CATEGORIES`, to carry the category tags the spec asks
for.

## B1 vs B0 vs Agent A, on `test1.txt` (our gold, `data/gold/test1.json`)

One real run each (`python -m baselines.b1_single_call ...` / `python run_agent.py --auto-approve ...`), scored against our gold with `eval/score.py`:

| | owner accuracy | routing accuracy | precision | recall |
|---|---|---|---|---|
| B0 (rules) | 42.9% (3/7) | — | — | — |
| B1 (single-call LLM, gpt-4o-mini) | **100%** (5/5) | **100%** | **100%** | 83.3% (5/6) |
| Agent A (gpt-4o-mini, auto-approve) | **100%** (5/5) | 80% (4/5) | **100%** | 83.3% (5/6) |

B1 also correctly resolved the cross-turn delegation ("someone should
follow up with legal..." → Priya claims it next turn) as a **single**
action item, instead of reproducing B0's duplicate-prediction bug. Its
one miss: it merged "draft release notes" and "create a task to track
review" into one Trello task (arguably reasonable — the transcript line
itself merges them the same way), which our v1 matcher counts as hitting
gold item 6 but missing gold item 5.

**Agent A's real run surfaced two honest findings, not hidden here:**
- **A routing bug**: it filed "schedule a demo with the design team" as
  an `email_draft` instead of a `calendar_event` — the resolver chose
  the wrong tool. Owner and evidence were still correct; this is a
  genuine quality miss worth fixing, not a scoring artifact.
- **Two items were escalated, not executed**, both for the same reason:
  the extractor split "Marcus will draft the release notes" into two
  separate candidates sharing the same evidence utterance `u10`
  ("draft the release notes" and "create a task to track review"), and
  for a *third*, related candidate built from `u9` alone ("we must
  write release notes..."), the LLM grounding check correctly noticed
  that `u9`'s evidence quote *on its own* doesn't name Marcus as owner
  — it only becomes clear from `u10`, the next turn. The grounding
  check only looks at the evidence quote text, not the full transcript
  context, so it's stricter here than a human (or our own
  cross-turn-resolved gold) would be. That's a deliberate safety
  trade-off (escalate on real ambiguity rather than guess), but it
  costs recall — exactly the "validator on vs. off" comparison the
  A-noval ablation (step 8) is meant to quantify, not something to
  patch away now.

Small sample (one transcript, one real run per system) — not a claim
any of this holds at scale; step 6's eval runner is where that gets
tested properly across the full dataset with repeats. Total real API
cost across every B1/Agent-A run so far: well under $0.01.

## B0's owner accuracy on `test1.txt`: 3/7 (42.9%), not 4/7 (57.1%)

B0's own README claims it gets the owner right on 4 of 7 extracted items.
Reproducing that *exact* number required inheriting an inconsistency: the
README resolves one vague, unnamed commitment ("we must write release
notes...") against the next turn where someone explicitly claims it, but
does **not** apply that same cross-turn resolution to a structurally
identical case two lines earlier ("someone should follow up with
legal..."). Applied consistently, B0 is actually wrong on **3** items,
not 2 — owner accuracy **42.9%**, not 57.1%.

- `tests/test_score.py::test_owner_accuracy_raw_on_our_gold` — the real
  number (3/7), against our own gold (`data/gold/test1.json`).
- `tests/test_score.py::test_owner_accuracy_raw_matches_readme_claim_on_reference_fixture`
  — a sanity check that the *scorer's arithmetic* reproduces the README's
  claimed 4/7 exactly, against a literal transcription of that claim
  (`tests/fixtures/b0_readme_reference_owners.json`), **not** treated as
  gold. Both are documented in `data/gold/test1.NOTES.md`.

This is disclosed, not hidden, per the project's "never fabricate /
always say when something scores differently than expected" rule.

## Running tests

```bash
source .venv/bin/activate
pytest -q
```
