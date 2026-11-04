# Eval Results

## Dataset: ami

| system | n scored | precision | recall | F1 | owner acc (matched) | routing acc |
|---|---|---|---|---|---|---|
| a | 7 | 50.0% | 15.5% | 33.9% | 100.0% | 100.0% |
| a_norec | 7 | 60.0% | 15.5% | 31.3% | 66.7% | 100.0% |
| a_noval | 7 | 71.4% | 78.6% | 70.1% | 60.7% | 78.6% |
| b0 | 7 | 32.1% | 45.2% | 28.7% | 25.0% | 58.3% |
| b1 | 7 | 89.3% | 71.4% | 72.4% | 42.9% | 100.0% |


## Dataset: synthetic

| system | n scored | precision | recall | F1 | owner acc (matched) | routing acc |
|---|---|---|---|---|---|---|
| a | 8 | 100.0% | 38.5% | 66.5% | 100.0% | 83.3% |
| a_norec | 8 | 100.0% | 41.7% | 62.7% | 100.0% | 85.7% |
| a_noval | 8 | 100.0% | 82.3% | 89.0% | 93.8% | 89.6% |
| b0 | 8 | 88.1% | 54.2% | 67.2% | 14.3% | 71.4% |
| b1 | 8 | 100.0% | 81.2% | 88.9% | 87.5% | 70.8% |


## Dataset: test1

| system | n scored | precision | recall | F1 | owner acc (matched) | routing acc |
|---|---|---|---|---|---|---|
| a | 3 | 100.0% | 94.4% | 97.0% | 100.0% | 82.2% |
| a_norec | 3 | 100.0% | 100.0% | 100.0% | 100.0% | 83.3% |
| a_noval | 3 | 83.3% | 83.3% | 83.3% | 100.0% | 100.0% |
| b0 | 3 | 85.7% | 100.0% | 92.3% | 50.0% | 100.0% |
| b1 | 3 | 100.0% | 83.3% | 90.9% | 100.0% | 100.0% |


## Per-category breakdown (owner accuracy, matched items, all systems/transcripts with reviewed gold)

| category | owner accuracy | n matched items |
|---|---|---|
| absolute_date | 100.0% | 4 |
| ambiguous_escalate | 5.0% | 20 |
| baseline | 96.3% | 27 |
| multi_turn_delegation | 60.0% | 5 |
| multiple_actions_one_line | 90.9% | 11 |
| pronoun_or_alias | 63.2% | 19 |
| relative_date | 100.0% | 4 |
| speaker_differs_from_owner | 87.5% | 24 |
| uncategorized | 89.2% | 83 |


## Stability (repeated runs)

| transcript_id | system | n runs | mean F1 | stdev F1 |
|---|---|---|---|---|
| test1 | a | 3 | 97.0% | 0.0429 |
| test1 | a_norec | 3 | 100.0% | 0.0000 |
| test1 | a_noval | 3 | 83.3% | 0.0000 |
| test1 | b0 | 3 | 92.3% | 0.0000 |
| test1 | b1 | 3 | 90.9% | 0.0000 |


## Worst errors per system (lowest F1, reviewed gold only)

**a**:
- `ami_is1003c_closing` (run 0): F1=0.0%, precision=0.0%, recall=0.0%
- `ami_ts3005b_closing` (run 0): F1=0.0%, precision=0.0%, recall=0.0%
- `synth_vendor_call_05` (run 0): F1=50.0%, precision=100.0%, recall=33.3%
**a_norec**:
- `ami_is1003c_closing` (run 0): F1=0.0%, precision=0.0%, recall=0.0%
- `ami_ts3005b_closing` (run 0): F1=0.0%, precision=0.0%, recall=0.0%
- `synth_design_review_03` (run 0): F1=40.0%, precision=100.0%, recall=25.0%
**a_noval**:
- `ami_es2011c_closing` (run 0): F1=33.3%, precision=50.0%, recall=25.0%
- `ami_is1003c_closing` (run 0): F1=50.0%, precision=33.3%, recall=100.0%
- `synth_standup_04` (run 0): F1=66.7%, precision=100.0%, recall=50.0%
**b0**:
- `ami_es2011c_closing` (run 0): F1=0.0%, precision=0.0%, recall=0.0%
- `ami_ts3005b_closing` (run 0): F1=18.2%, precision=11.1%, recall=50.0%
- `ami_es2009c_closing` (run 0): F1=25.0%, precision=25.0%, recall=25.0%
**b1**:
- `ami_is1003c_closing` (run 0): F1=40.0%, precision=25.0%, recall=100.0%
- `ami_es2009c_closing` (run 0): F1=66.7%, precision=100.0%, recall=50.0%
- `ami_es2011c_closing` (run 0): F1=66.7%, precision=100.0%, recall=50.0%


## Fault injection (agent/verifier.py's recovery, exercised directly)

| fault | A (full recovery) | A-norec / B1-style (single attempt, no retry) |
|---|---|---|
| 429 | verified (2 attempt(s)) | FAILED, no retry (RateLimitError); object committed server-side: False |
| 503 | verified (2 attempt(s)) | FAILED, no retry (ServiceUnavailableError); object committed server-side: False |
| timeout | verified (2 attempt(s)) | FAILED, no retry (ToolTimeoutError); object committed server-side: False |
| lost_response | verified (2 attempt(s)) | FAILED, no retry (ResponseLostError); object committed server-side: True |
| invalid_argument | needs_resolver_repair (1 attempt(s)) | FAILED, no retry (InvalidArgumentError); object committed server-side: False |
| expired_token | escalate (1 attempt(s)) | FAILED, no retry (ExpiredAuthError); object committed server-side: False |
