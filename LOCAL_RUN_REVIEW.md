# Local run review — November 2, 2026

This is the initial checkout inspection, preserved as historical context.
Subsequent live tests and fixes were completed on November 3; see the
README's current verification section for the latest status. In particular,
the original Composio/configuration gaps were resolved by the user, and
the current suite has 297 passing tests. Statements below about no paid
calls or live verification describe the initial inspection only.

## Verdict

The project is substantially implemented and suitable for a command-line demo with mock tools once local OpenAI configuration is approved and supplied. The rule-based B0 baseline runs now without credentials. Live Google Calendar, Trello, and Gmail operation is implemented but not verified here and has additional reliability gaps.

Cloned into `/Users/arjunranjan/Desktop/CSE598-meeting-action-router`. Created `.venv` with Python 3.11 and installed `requirements.txt`. No application source was changed. No existing environment configuration or secret values were accessed. No paid model calls or live account actions were made.

## Verified locally

- Dependency installation succeeded.
- All **271 tests passed** in 3.94 seconds. Test execution used an explicitly supplied minimal child-process environment, without inherited credentials, and disabled dotenv loading.
- B0 ran against the bundled `test1` transcript and produced seven action items.
- B0 evaluation completed across all six dev transcripts. Predictions and configuration are saved under `runs/local_inspection_b0/`; existing committed result tables were preserved.
- Fresh-directory main CLI startup reproduced `sqlite3.OperationalError: unable to open database file`.

Passing tests exercise scripted model responses and fake service clients. They do not establish that real OpenAI responses or live Composio integrations work end to end.

## What is built

| Area | Implementation |
| --- | --- |
| Interface | Python CLI; no web UI or running server |
| B0 | Rule-based extraction/routing with local tool stubs |
| B1 | Single OpenAI tool-calling request, executed against mock tools in its CLI |
| Agent A | Ingest → extract → resolve → validate/repair → human approval → execute/read back → report |
| State | SQLite action ledger, JSONL audit log, JSON report |
| Mock integrations | Calendar, Trello, Gmail drafts; injected transient/auth/argument/lost-response failures |
| Live integrations | Composio adapters plus connection and tool-schema verification scripts |
| Evaluation | Matching/scoring, split runner, ablations, repeat stability, fault table, CSV/Markdown results |
| Data | Eight synthetic transcripts, seven AMI excerpts, one legacy transcript; only legacy `test1` has reviewed gold |
| Annotation | Draft-label review CLI, annotation guide, owner-field Cohen's kappa |

## Findings relevant to running or demoing

1. **Fresh CLI startup needs a `runs` directory.** `run_agent.py` constructs `Ledger(...)` before `AuditLog(...)`; the latter creates parent directories, while `Ledger.__init__` does not. The default database path therefore fails on a fresh checkout. Workaround: run `mkdir -p runs` from the repository root before starting the agent. The tests created this directory during local verification, so it now exists in this checkout. A custom ledger path also needs its parent directory created first.

2. **Mock tools still use a real LLM.** `run_agent.py --tools mock` only replaces Calendar/Trello/Gmail with in-memory fakes. Extraction, resolution, and grounding still call OpenAI. `--auto-approve` skips item-by-item review; it does not provide an offline LLM.

3. **README status is stale.** It says live mode raises `NotImplementedError` and reports 238 tests. Current code implements live mode behind `--confirm-live`, and the current suite contains 271 passing tests. Claims in the README about prior paid runs were not independently reproduced here.

4. **Live service mappings are unverified.** The adapters explicitly disclose guessed/unverified Composio action schemas and response normalization. Run the supplied schema checker before a real-account demo, then validate actual create/read-back behavior on test accounts. The connection script does not call `load_dotenv()`, unlike the main CLI and schema checker; merely filling a `.env` file will not make that script consume it.

5. **Some recovery claims exceed the implementation.** Read-back calls in `execute_with_recovery` sit outside its create-call exception handling, so a read-back exception can terminate a run. The verifier returns `needs_resolver_repair` for invalid arguments, but the orchestrator escalates it instead of invoking another resolver repair. The budget counts create attempts, excludes resolver lookups/read-backs, and retries can exceed the remaining budget.

6. **Duplicate prevention is best effort for live accounts.** Action IDs depend on extraction position; a changed LLM ordering can align a previous ledger entry with a different task. Live adapters save the remote ID only after receiving a successful create response. A server-side create followed by a lost response can therefore duplicate on retry. Mock lost-response tests do not prove live deduplication.

7. **Calendar scheduling is simplified.** The router uses a fixed 10:00 start and 30-minute duration, with naive timestamps; transcript times/timezones are not modeled. The weekday resolver uses the nearest occurrence on or after the meeting date even when wording says “next”. These conventions matter for realistic demo transcripts.

8. **Most datasets cannot yet produce reviewed accuracy scores.** Fifteen draft-gold files await human review. Evaluation still generates predictions for them but skips scoring. Zero-valued precision/recall can also lead to `f1=None` in the current scorer, and empty gold lists are treated as unscored; these need attention before interpreting aggregate evaluation results.

9. **Run from the repository root.** Input paths, default outputs, and several script paths are relative. Use a unique `--meeting-id` for each independent demonstration: terminal ledger states, including rejection/escalation, are skipped on later runs using the same meeting ID and ledger.

10. **Dependencies are not pinned.** The current requirements installed and the tests passed here, but future installations may resolve different versions. Live SDK compatibility remains unproven by the fake-client tests.

## Run the verified offline baseline

```bash
cd /Users/arjunranjan/Desktop/CSE598-meeting-action-router
.venv/bin/python -m baselines.b0_adapter \
  --input baselines/b0_rules/examples/test1.txt
```

This prints common-schema JSON and performs no external writes. B0 deliberately has attribution and duplicate-extraction limitations; it is a comparison baseline.

## Main agent demo, after configuration is approved

```bash
cd /Users/arjunranjan/Desktop/CSE598-meeting-action-router
mkdir -p runs
.venv/bin/python run_agent.py \
  --input baselines/b0_rules/examples/test1.txt \
  --roster data/rosters/test1_roster.json \
  --meeting-date 2026-09-02 \
  --meeting-id demo-test1-01 \
  --tools mock
```

This uses paid OpenAI requests and interactive approval, then writes `runs/demo-test1-01_report.json`, `runs/demo-test1-01_audit.jsonl`, and `runs/demo-test1-01_ledger.sqlite3`. Tools remain simulated. This real-model demo has **not** been executed during this review.

## Configuration requiring explicit permission

No configuration changes have been made. For a local mock-tools demo:

- Required variable: `OPENAI_API_KEY`, for OpenAI extraction, resolution, and grounding requests.
- Optional variable: `LLM_MODEL`, to select the model; current code defaults to `gpt-4o-mini`.
- Affected environment: this local Desktop checkout only; no preview, staging, or production environment.
- Proposed file change, only after approval: create a gitignored `/Users/arjunranjan/Desktop/CSE598-meeting-action-router/.env` containing `OPENAI_API_KEY=<value entered privately by you>` and optionally `LLM_MODEL=gpt-4o-mini`. Do not paste the key in chat. An existing configuration must not be read or overwritten without separate explicit approval.
- Proposed run after approval: the mock-tools command above, loading local configuration without displaying credential values.

Live mode additionally needs `COMPOSIO_API_KEY` (service authentication), `COMPOSIO_USER_ID` (connected-account identity; a default exists), and `TRELLO_LIST_ID` (destination list), plus connected Google/Trello accounts and real roster identities. This requires a separate configuration and account-action approval scope.

## Using your demo transcripts

Supply the transcript paths and meeting dates. The parser expects UTF-8 text with one turn per line:

```text
Arjun: Khush will prepare the demo slides by Friday.
Khush: I'll email Arjun the agenda tomorrow.
```

Each demo also needs a roster JSON array. A mock roster can use documented fictional placeholder identities:

```json
[
  {"name": "Arjun", "aliases": [], "email": "arjun@example.com", "trello_member_id": "member_arjun"},
  {"name": "Khush", "aliases": [], "email": "khush@example.com", "trello_member_id": "member_khush"}
]
```

Speaker labels, aliases, and mentioned recipients should match the roster. PDF, DOCX, timestamped VTT/SRT, or other transcript formats may need conversion before using the existing CLI.
