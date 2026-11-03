# One-person Google integration tests

Meeting date: 2026-11-03. The user supplied arjunranjanwork@gmail.com as the connected account and intended recipient/attendee for both tests. These are separate manual smoke tests, outside evaluation splits.

- calendar.txt: one calendar event on 2026-11-08. The existing router defaults to 10:00 for 30 minutes; no arbitrary transcript time is claimed to be parsed. Confirm the adapter's timezone handling before live execution.
- gmail.txt: one email draft addressed only to the user. No sending is requested or permitted by this test.

Before live writes, run scripts/inspect_google_tools.py locally to inspect the four tools' pinned schemas. Pinning versions and passing fake-client tests do not establish live create/read-back behavior. Use per-item human approval. Once an object exists, inspect it instead of changing meeting IDs to retry creation.

The user returned schemas for Google Calendar `20261010_00` and Gmail `20261029_00`. Calendar now sends an explicit America/Phoenix timezone, disables Meet creation and update notifications, and uses the primary calendar. The demo slot is November 8, 2026, 10:00–10:30 Phoenix time. Event read-back converts offset timestamps into that same local representation for comparison.

Gmail now uses extra_recipients for additional To addresses, disables automatic signatures, and reads raw MIME to compare the saved recipient, decoded subject, and body. Authored body text is HTML-escaped rather than interpreted as markup. No send tools are used. The first live draft test was pending when these mappings were introduced; subsequent results are recorded below.

If read-back raises an error after creation, the verifier preserves the returned object ID and escalates without retrying creation. Escalation reports now include returned objects and field mismatches to help diagnose live failures without another create call.

The initial Gmail live run created and verified a draft, but its body merely described the task of writing an email. That proves transport fidelity, not content quality. Resolver v2 now receives the full cited source turns and nearby context, and asks for a recipient-facing subject and body. Grounding v2 also reviews the drafted content against that context. The CLI shows the body before approval; editing another field preserves that body. Historical v1 prompts and prior evidence are preserved, and new eval runs hash the active prompt versions.

Before another live draft, preview model-generated content with `--tools mock` and a distinct meeting ID (for example `arjun-gmail-content-preview-01`). Mock tools still make paid model requests but create no Gmail objects. Accept the content only if it actually presents the rehearsal agenda: review the transcript, demonstrate the approval step, and inspect verified tool outputs. It must not invent dates, links, attachments, or completed work. Offline regression tests cover source availability, critic inputs, approval preview, and body preservation; they do not establish real-model content quality by themselves.

Observed results, November 3: Calendar creation succeeded but the original run escalated because the event ID was nested in response_data. The adapter was fixed, and separate read-only verification returned zero mismatches for ID, title, start, end, and attendee. Description was displayed for review, not independently scored. The initial Gmail agent run returned Verified: 1 with no escalations. After v2 drafting changes, the real-model/mock-tools content preview also returned Verified: 1 and included all three agenda points. Its cost was $0.000693. The user deleted the earlier generic live draft; this preview created no replacement in Gmail.
