# Architecture — Meeting Action-Item Router (Agent A)

One ReAct-style tool-using agent with a separate validator/critic, per
meeting. No multi-agent setup. This diagram reflects the actual
pipeline in `agent/orchestrator.py` as of 2026-11-03 — see that
module's docstring for the exact spec language each box implements.

```mermaid
flowchart TD
    T["Transcript + meeting date<br/>+ roster"] --> ING["Ingestion<br/>(agent/ingestion.py)<br/>parse into Utterances: u1, u2, ..."]

    ING --> EXT["Extractor (LLM, 1 call)<br/>(agent/extractor.py)<br/>propose candidates with<br/>evidence_quote + evidence_utterance_ids"]

    EXT -->|"per candidate"| RES["Resolver (LLM + tools, ReAct loop)<br/>(agent/resolver.py)<br/>lookup_participant / resolve_date / get_context<br/>→ finalize_resolution"]

    RES --> VAL{"Validator / critic<br/>(agent/validator.py)<br/>schema + due-date + roster membership<br/>+ verbatim evidence + LLM grounding check"}

    VAL -->|"failed, attempts remain"| REP1["Repair: re-resolve with<br/>validator's errors as feedback<br/>(max 2 attempts)"]
    REP1 --> RES
    VAL -->|"failed, attempts exhausted"| ESC1["Escalate to manual review"]
    VAL -->|"passed"| APR

    APR{"Human approval<br/>(agent/approval_cli.py)<br/>approve / edit / reject<br/>(--auto-approve for batch runs, logged)"}

    APR -->|"reject"| REJ["Rejected<br/>(no write, ever)"]
    APR -->|"edit"| REVAL["Re-validate the edit<br/>(no re-approval needed after this)"]
    REVAL -->|"failed"| ESC2["Escalate"]
    REVAL -->|"passed"| EXEC
    APR -->|"approve"| EXEC

    EXEC["Router<br/>(agent/router.py)<br/>build real tool args<br/>idempotency_key = hash(meeting_id, action_id)"]

    EXEC --> VER{"Verifier<br/>(agent/verifier.py)<br/>call tool → read object back → compare"}

    VER -->|"transient error<br/>(429/503/timeout/lost-response)"| RETRY["Retry same idempotency_key<br/>w/ backoff, max 3 attempts"]
    RETRY --> VER
    VER -->|"invalid argument"| REP2["Execution repair: re-resolve<br/>with the execution error as feedback,<br/>re-validate, retry<br/>(max 2 attempts, no re-approval)"]
    REP2 --> VER
    VER -->|"expired auth / unknown error /<br/>repair attempts exhausted"| ESC3["Escalate to manual review"]
    VER -->|"verified: read-back matches"| OK["Verified"]

    OK --> OUT
    ESC1 --> OUT
    ESC2 --> OUT
    ESC3 --> OUT
    REJ --> OUT

    OUT["Ledger (SQLite)<br/>(agent/ledger.py)<br/>proposed→resolved→validated→approved→<br/>executed→verified|escalated|rejected"]
    OUT --> REPORT["JSON report + JSONL audit log<br/>(agent/audit.py, agent/orchestrator.py)"]

    EXEC -.->|"--tools mock"| MOCK["In-memory fakes<br/>(agent/tools/mock_backend.py)<br/>fault injection, idempotency"]
    EXEC -.->|"--tools live --confirm-live"| LIVE["Composio-connected<br/>Calendar / Trello / Gmail<br/>(agent/tools/live_*.py)"]

    style ESC1 fill:#5a3a1a,stroke:#d08030,color:#f0e0c0
    style ESC2 fill:#5a3a1a,stroke:#d08030,color:#f0e0c0
    style ESC3 fill:#5a3a1a,stroke:#d08030,color:#f0e0c0
    style REJ fill:#5a1a1a,stroke:#d04040,color:#f0d0d0
    style OK fill:#1a4a2a,stroke:#40b060,color:#d0f0d8
```

## Ablation flags (on `run_meeting(...)`, used by `eval/run_eval.py`)

- **A-noval** (`enable_validator=False`): skips the Validator box
  entirely — no deterministic checks, no grounding check, no repair
  loop. The resolver's raw output becomes the action item unchecked.
- **A-norec** (`enable_recovery=False`): skips the Verifier's
  read-back and retry — one attempt, trust success blindly, escalate
  immediately on any exception.

## Comparison systems (not pictured above — see `baselines/`)

- **B0**: Neha's rule-based baseline (`baselines/b0_rules/`, vendored
  unmodified). Regex keyword matching, owner = speaker always, no
  dates, no validation, no retry.
- **B1**: one single tool-calling LLM request over the whole
  transcript + roster (`baselines/b1_single_call.py`), same tool
  schemas as Agent A, each tool call executed once against the same
  backends — no validator, no approval, no read-back, no retry.

## State and safety properties worth calling out

- **Idempotency**: every write is tagged
  `hash(meeting_id, action_id)`. The same key on a retry either
  creates the object once or recovers the one already committed —
  never a duplicate, even for a "created but response lost" fault.
- **Rerun safety**: a persisted ledger lets a second run of the same
  meeting skip any action that already reached a terminal state
  (verified/escalated/rejected) instead of re-resolving/re-approving/
  re-executing it.
- **No write without approval**: every path into the Router goes
  through the Approval box first — `--auto-approve` logs that it
  skipped human review, it never skips the gate itself.
- **Prompt injection**: transcript text is data, never instructions.
  The LLM grounding check's prompt explicitly tells the model to
  report text that reads like an injected instruction as ungrounded,
  not to comply with it — and the roster-membership check plus the
  human-approval gate are independent backstops if that check ever
  fails. See `tests/test_orchestrator.py`'s prompt-injection test and
  `data/synthetic/synth_prompt_injection_06/` for the dataset case.
