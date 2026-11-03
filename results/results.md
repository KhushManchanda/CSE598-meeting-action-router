# Eval Results

## Dataset: synthetic

_No reviewed gold yet for dataset `synthetic` -- predictions were generated and saved (see runs/<timestamp>/predictions/), but nothing to score. See `data/gold_draft/` and `scripts/review_gold.py`._


## Dataset: test1

| system | n scored | precision | recall | F1 | owner acc (matched) | routing acc |
|---|---|---|---|---|---|---|
| a | 3 | 100.0% | 88.9% | 93.9% | 100.0% | 94.4% |
| a_norec | 3 | 100.0% | 94.4% | 97.0% | 100.0% | 88.9% |
| a_noval | 3 | 83.3% | 83.3% | 83.3% | 100.0% | 100.0% |
| b0 | 3 | 85.7% | 100.0% | 92.3% | 50.0% | 100.0% |
| b1 | 3 | 100.0% | 83.3% | 90.9% | 100.0% | 100.0% |


## Per-category breakdown (owner accuracy, matched items, all systems/transcripts with reviewed gold)

| category | owner accuracy | n matched items |
|---|---|---|
| uncategorized | 88.9% | 81 |


## Stability (repeated runs)

| transcript_id | system | n runs | mean F1 | stdev F1 |
|---|---|---|---|---|
| test1 | a | 3 | 93.9% | 0.0429 |
| test1 | a_norec | 3 | 97.0% | 0.0429 |
| test1 | a_noval | 3 | 83.3% | 0.0000 |
| test1 | b0 | 3 | 92.3% | 0.0000 |
| test1 | b1 | 3 | 90.9% | 0.0000 |


## Worst errors per system (lowest F1, reviewed gold only)

**a**:
- `test1` (run 0): F1=90.9%, precision=100.0%, recall=83.3%
- `test1` (run 2): F1=90.9%, precision=100.0%, recall=83.3%
- `test1` (run 1): F1=100.0%, precision=100.0%, recall=100.0%
**a_norec**:
- `test1` (run 2): F1=90.9%, precision=100.0%, recall=83.3%
- `test1` (run 0): F1=100.0%, precision=100.0%, recall=100.0%
- `test1` (run 1): F1=100.0%, precision=100.0%, recall=100.0%
**a_noval**:
- `test1` (run 0): F1=83.3%, precision=83.3%, recall=83.3%
- `test1` (run 1): F1=83.3%, precision=83.3%, recall=83.3%
- `test1` (run 2): F1=83.3%, precision=83.3%, recall=83.3%
**b0**:
- `test1` (run 0): F1=92.3%, precision=85.7%, recall=100.0%
- `test1` (run 1): F1=92.3%, precision=85.7%, recall=100.0%
- `test1` (run 2): F1=92.3%, precision=85.7%, recall=100.0%
**b1**:
- `test1` (run 0): F1=90.9%, precision=100.0%, recall=83.3%
- `test1` (run 1): F1=90.9%, precision=100.0%, recall=83.3%
- `test1` (run 2): F1=90.9%, precision=100.0%, recall=83.3%


## Fault injection (agent/verifier.py's recovery, exercised directly)

| fault | A (full recovery) | A-norec / B1-style (single attempt, no retry) |
|---|---|---|
| 429 | verified (2 attempt(s)) | FAILED, no retry (RateLimitError); object committed server-side: False |
| 503 | verified (2 attempt(s)) | FAILED, no retry (ServiceUnavailableError); object committed server-side: False |
| timeout | verified (2 attempt(s)) | FAILED, no retry (ToolTimeoutError); object committed server-side: False |
| lost_response | verified (2 attempt(s)) | FAILED, no retry (ResponseLostError); object committed server-side: True |
| invalid_argument | needs_resolver_repair (1 attempt(s)) | FAILED, no retry (InvalidArgumentError); object committed server-side: False |
| expired_token | escalate (1 attempt(s)) | FAILED, no retry (ExpiredAuthError); object committed server-side: False |
