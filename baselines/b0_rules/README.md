# Meeting Action-Item Router (Capstone Baseline)

An agentic system that reads a raw meeting transcript, extracts the action
items mentioned in it, and **routes each one to the right tool** —
`schedule_event`, `send_email`, or `create_task` — then executes that tool
and reports back what it did.

This repository contains the **baseline** version of the system, submitted
for the capstone proposal. See `agent.py` for the extract → decide → act
loop, and `tools.py` for the (simulated) external tools it can call.

## 1. Dependencies

None beyond the Python standard library. No external packages, no API
keys, no network access are required to run the baseline.

- Python 3.9+ (tested on Python 3.12.3)

```bash
# Optional: create a virtual environment
python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

# No packages to install — the baseline only uses the standard library.
# requirements.txt is included for completeness / future phases.
pip install -r requirements.txt
```

## 2. Required API keys / environment variables

**None.** The baseline's `schedule_event`, `send_email`, and `create_task`
tools in `tools.py` are local stubs that simulate what a real Calendar
API / Email API / Task Tracker API would return, so the whole pipeline
runs offline with zero credentials and zero cost.

(A future phase will add an LLM-based extraction/routing step using the
Claude API, which will require an `ANTHROPIC_API_KEY` environment
variable — see Section 7 of the proposal / "Next steps" below.)

## 3. Exact command to run the baseline

```bash
python run_baseline.py --input examples/test1.txt
```

This is the only command needed. It prints the extracted action items,
their routed tool, and each tool's confirmation message to the terminal.

## 4. Where the input is

The sample transcript lives at `examples/test1.txt` — an 11-line
excerpt of a fictional weekly product sync with 7 action items embedded
in it.

To test on your own transcript, put any `.txt` file anywhere and point
`--input` at it, e.g.:

```bash
python run_baseline.py --input path/to/your_transcript.txt
```

Expected transcript format: one line per speaker turn, formatted as
`Speaker Name: sentence.` Lines without a colon are still scanned, but
the "owner" of the resulting action item is reported as `Unassigned`.

## 5. Where the output appears

- **Console**: a numbered, human-readable list of each action item, its
  owner, the tool it was routed to, and that tool's confirmation string,
  followed by a total count.
- **File**: a machine-readable JSON version is written next to the input
  file, e.g. `examples/test1_output.json`, containing the same
  information as a list of objects.

## 6. Known setup limitations

- The action-item extractor is **rule-based** (regex keyword matching on
  modal verbs like "will", "should", "needs to"), not an LLM. It will
  miss action items phrased unusually and will occasionally flag a
  non-action sentence that happens to contain a matched keyword.
- **Owner attribution** currently defaults to the *speaker of the line*,
  not necessarily the person named in the sentence. For example, if
  Priya says "Marcus will schedule a demo," the baseline currently
  attributes the resulting task to Priya (the speaker), not Marcus (the
  actual owner). This is a known, observed failure mode — see the test
  case output below and Section 7 of the proposal for the planned fix.
- Tool execution is simulated locally; nothing is actually written to a
  real calendar, inbox, or task tracker.

## 7. Test case

Input: `examples/test1.txt` (included in this repo).

Run:
```bash
python run_baseline.py --input examples/test1.txt
```

Actual output: see `baseline_run_screenshot.png` in this repo, and the
raw text in `run_output.txt` / structured data in
`examples/test1_output.json`.

The baseline correctly detected all 7 action items in the transcript and
routed 3 to `schedule_event`/`send_email` correctly by keyword, and 3 to
`create_task` as a sensible default. It also revealed the owner-attribution
limitation described above (item 1, 2, and 6 were mis-attributed to the
speaker rather than the named owner) — useful, concrete evidence for
what the next iteration needs to fix.

## Repository contents

```
agent.py           # core extract -> decide -> act agent loop
tools.py           # simulated schedule_event / send_email / create_task tools
run_baseline.py    # CLI entry point
requirements.txt   # dependencies (empty for now; future phases will add anthropic SDK)
examples/test1.txt # sample meeting transcript test case
run_output.txt      # captured console output from the test case run
baseline_run_screenshot.png  # screenshot of a successful run
```

## Next steps

See Section 7 of the capstone proposal for the full plan. In short: the
rule-based extractor/router in `agent.py` will be replaced with an
LLM tool-calling call to the Claude API (model routing decided by the
LLM instead of keyword rules), which should fix the owner-attribution
bug and generalize to transcripts with less rigid formatting.
