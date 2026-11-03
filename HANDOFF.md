# Project handoff and Milestone 2 next steps

Updated November 3, 2026. Start here and with README.md's current verification
section; the older build logs describe historical checkpoints.

## Current checkpoint

- Branch: `master`. Previous backend integration checkpoint: `0565c96`.
- Implemented: CLI, B0 rules baseline, B1 single-call baseline, full agent,
  evaluation harness, mock tools, and Composio live adapters.
- New local Streamlit UI: transcript setup, participant editing, source
  evidence beside approve/edit/reject controls, verification results, JSON
  downloads, saved UI history, historical evaluation, manual connection checks.
- Automated suite: 314 passing tests with fake model/service clients. These
  do not establish real-model accuracy or live UI integration success.
- No hosting or public deployment is configured; the UI is a local app.

## Start and understand the app

Use Python 3.11+ from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_ui.py
```

Open http://127.0.0.1:8501. The launcher binds to localhost, disables
telemetry and Streamlit secrets-file loading, and skips its credential prompt.
Startup does not load the project's `.env`.

Start with **Offline walkthrough**: scripted proposals for one fixed
fictional meeting, real downstream validation/approval/ledger, mock tools.
It tests the workflow, not extraction accuracy. **OpenAI + mock tools**
processes actual input with paid model requests and simulated integrations.
**OpenAI + live tools** uses connected accounts. API modes require explicit
in-app configuration consent; live mode also requires account-use confirmation.
Every action pauses for review. Gmail creates drafts only.

Pipeline: ingestion -> extraction -> owner/date resolution -> validation
and bounded repair -> human review -> execution/read-back -> verification
or escalation. SQLite holds action state; JSONL holds the trace.

UI artifacts live in `runs/ui/<unique-id>/`. History is read-only; it cannot
resume disconnected approvals. Unanswered review stops after 30 minutes.
Stopping prevents subsequent model calls/approvals; an in-flight request
may finish. New UI runs have new IDs and can repeat earlier remote actions.

## Verification evidence and limits

| Area | Observed evidence | Still needed |
| --- | --- | --- |
| Trello CLI | Full run created/verified a task; same meeting/ledger rerun skipped it with zero execution calls | Broader attribution and live UI acceptance |
| Calendar CLI | Event created; original run escalated on response parsing. Separate read-only check after fix verified ID, title, start/end, attendee | Fresh full run through current UI |
| Gmail CLI | Initial draft created/read back but content was generic. Revised real-model/mock run produced requested agenda | Live write of revised content through UI |
| UI browser walkthrough | Edited Trello task verified, Calendar rejected, Gmail verified, using scripted model/mock tools | Real-model/mock and approved live UI tests |
| Evaluation | Historical pilot scores for reviewed `test1` only | Reviewed synthetic/AMI labels and fresh two-dataset comparisons |

The operator already connected Gmail, Calendar, and Trello in Composio.
Do not reconnect accounts reflexively. Auth configs and active connections
are different; the configured user ID must select the intended connections.

## Next work in order

### 1. Complete UI acceptance testing

Run OpenAI + mock tools first. Inspect owner, date, destination, evidence,
and actual Gmail subject/body; exercise editing and rejection. Then have
the operator approve test-account Trello, Calendar, and Gmail actions in
the UI. Compare reports against actual objects and preserve evidence locally.
If creation succeeds but verification fails, inspect the existing object
before starting a fresh run. Do not label it fully verified merely because
the object exists remotely.

Completion: documented current-UI real-model/mock and live outcomes with
correct fields and read-back statuses. No live UI acceptance is claimed yet.

### 2. Record the stakeholder walkthrough and get feedback

Arjun wants a full end-to-end video for Neha Kashyap. A new prototype
follow-up has not yet been completed. Prepare one clear demo, rehearse it,
then record. A suggested length is 6-8 minutes, not a course requirement.

1. Explain the manual meeting-to-task problem and expected outcome.
2. Show transcript, meeting date, and real test-account roster.
3. Start a real-model run; show proposals and source evidence.
4. Edit a proposal and reject a proposal; explain validation/approval.
5. Approve Calendar, Trello, and Gmail draft actions.
6. Inspect actual objects, verification results, and report/history.
7. Explain limitations and invite feedback on the workflow.

Clearly identify simulated versus live segments. Keep keys and credential
screens out of the recording. Recording/sharing are not completed at this
checkpoint. Do not invent a video URL or send it without explicit instruction.

Ask Neha whether it addresses her workflow, whether owner/date/destination
review is clear, what blocks adoption, and which final deliverables/success
criteria she wants. Share the video, arrange a brief follow-up conversation,
and record date, participants, notes, and **Feedback -> Team response -> Next
action**. The template asks for a stakeholder meeting; do not assume a video
alone satisfies that requirement.

### 3. Make preliminary evaluation defensible

- Data contains eight synthetic transcripts and seven AMI excerpts. Only
  `data/gold/test1.json` is currently reviewed. Do not silently promote drafts.
- Arjun and Khush should review a pilot from both datasets using
  `data/ANNOTATION_GUIDE.md` and `scripts/review_gold.py`. Record sample/action
  counts and disagreements. Three synthetic plus three AMI excerpts is a
  suggested starting pilot, not a rubric minimum.
- Preserve `data/splits.json`; never tune prompts or thresholds on held-out
  test examples. Human-review AMI role/alias assumptions and retain ambiguity.
- Check scoring before paid runs: zero precision/recall currently produces
  null F1; empty reviewed gold is treated as unscored. Inspect the greedy
  evidence/text matching heuristic on representative examples.
- Separate extracted/resolved quality from execution success: the current
  A evaluator emits only verified actions, while B1 emits predictions
  separately. Correct or explain the difference, particularly for correctly
  escalated ambiguous actions, before interpreting comparisons.
- Compare B0, B1, and A on the same reviewed examples from both datasets
  with mock tools. Record model, temperature, prompt hashes, budgets, sample
  counts, precision/recall/F1, owner/routing accuracy, relevant argument
  accuracy, cost, and latency. Label unavailable measurements explicitly.
- B1/A use paid requests. Do not run paid experiments or access configuration
  without the operator's authorization. Mock success is not live reliability.
- Add ablations/repeats as time permits. Preserve historical results before
  replacing tables; old prompt scores are not current-version measurements.

Milestone 2 permits a clearly identified pilot and does not require beating
every baseline. The larger Milestone 1 held-out-data target remains final
project work unless a scope change is documented.

### 4. Assemble the report

The supplied Milestone 2 template specifies 5-10 pages:

| Section | Points | Evidence needed |
| --- | --- | --- |
| Stakeholder follow-up and deliverables | 10 | Dated notes, feedback/responses, agreed scope |
| Implemented system | 25 | Updated architecture, mechanisms/state/tools, changes since Milestone 1 |
| Preliminary evaluation | 30 | Agent plus two baselines on two datasets; conditions, tables, analysis |
| Actual-run demo/case study | 15 | Readable screenshots, input, decisions, tools, final result |
| Failure analysis/limitations | 10 | Trace-backed actual failure, diagnosis, fix and verification |
| Remaining work | 10 | Priorities, owners, completion evidence; required versus optional |
| Repository/team contributions | Listed separately | Accessible URL, branch/commit, setup, actual contributions and links |

Actual failure cases already observed: Trello UTC deadline display shift,
Calendar successful creation followed by read-back parsing failure, and
Gmail's initially generic body. Preserve original evidence; distinguish a
separate corrective check from a fresh successful end-to-end run.

The milestone source documents were supplied outside this repository;
consult the originals for exact wording. Document actual contributions;
suggested ownership is not completed work. The deadline and remaining task
assignments are not confirmed in this checkpoint.

### 5. Freeze the submission

After acceptance/evaluation/report work, run tests, review the diff, push
the submission checkpoint, record its exact commit, check grader access,
and rehearse the demo with a clearly labeled offline fallback. Keep runtime
artifacts and secrets out of version control.

## Important implementation limits

- Calendar uses a fixed 10:00 start/30-minute duration; transcript-specific
  time/duration extraction is not implemented. Trello date-only deadlines
  use 17:00. Default timezone: America/Phoenix.
- Live duplicate prevention is best effort after ambiguous writes/lost
  responses. Extraction-position IDs assume stable candidate ordering.
- The budget counts creation attempts, excluding resolver/read-back calls;
  retry sequences can exceed the remaining attempt budget.
- Invalid-argument outcomes do not guarantee another resolver-repair loop;
  describe actual escalation rather than the original design promise.
- Session state does not provide production multi-user reliability or a
  general crash recovery guarantee.
- Passing tests/one-person smoke tests do not establish accuracy targets,
  broad integration reliability, or stakeholder acceptance.

## Contributor rules and source map

Follow AGENTS.md and the operator's configuration restrictions. Never read,
search, source, modify, commit, or push `.env` or credential files without
applicable explicit permission. `.env.example` is a placeholder reference.
Preserve existing functionality; avoid unrelated removals/refactors.

Relevant entry points: `streamlit_app.py`, `run_ui.py`, `ui/runtime.py`,
`ui/demo.py`, `agent/orchestrator.py`, `agent/tools/live_*.py`,
`eval/run_eval.py`, `eval/score.py`, `tests/test_ui_runtime.py`, and
`tests/test_streamlit_app.py`.
