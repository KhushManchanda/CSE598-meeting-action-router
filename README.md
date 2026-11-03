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
- [ ] Step 4 — Agent A (ledger, extractor, resolver, validator, approval
      CLI, router, verifier, recovery, budget, audit log)
- [ ] Step 5 — synthetic data, AMI excerpts, gold review CLI
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
- `tests/` — 77 unit tests, all passing (`pytest -q`). B1's tests run
  against a fake LLM client (deterministic, no cost); only the manual
  CLI runs above have made real (sub-cent) API calls.

## B1 vs B0 on `test1.txt` (our gold, `data/gold/test1.json`)

| | owner accuracy | routing accuracy | precision | recall |
|---|---|---|---|---|
| B0 (rules) | 42.9% (3/7) | — | — | — |
| B1 (single-call LLM, gpt-4o-mini) | **100%** (5/5) | **100%** | **100%** | 83.3% (5/6) |

B1 also correctly resolved the cross-turn delegation ("someone should
follow up with legal..." → Priya claims it next turn) as a **single**
action item, instead of reproducing B0's duplicate-prediction bug. Its
one miss: it merged "draft release notes" and "create a task to track
review" into one Trello task (arguably reasonable — the transcript line
itself merges them the same way), which our v1 matcher counts as hitting
gold item 6 but missing gold item 5. Small sample (one transcript, one
run) — not a claim this holds at scale; step 6's eval runner is where
that gets tested properly across the full dataset with repeats.

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
