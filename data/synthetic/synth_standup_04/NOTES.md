Meeting date 2026-10-15 (Thursday).

- G1 due: "by Monday" from Thursday -> 2026-10-19.
- G2: addressed to "everyone" -- no single owner. Our schema's single
  `owner` string can't represent "all three participants," so this is
  deliberately left owner=null / ambiguous_escalate, even though the
  due date ("end of day" -> same-day, 2026-10-15) IS resolvable. A
  found schema limitation, documented rather than forced into a guess
  (e.g. picking "Robin" just because he happens to reply "Will do").

NOT gold items (non_action), four distinct patterns in one transcript:
- u2: "I already pushed the hotfix... yesterday, it's live" --
  COMPLETED past action, not a future commitment.
- u3: "maybe we should eventually add more E2E tests, just an idea for
  later" -- SUGGESTION, vague, no commitment.
- u4: "If we had more time, I'd love to refactor... but that's not
  happening this sprint" -- HYPOTHETICAL, explicitly negated.
- u5: "No, I don't think we need to touch the payment service right
  now" -- explicit NEGATION.
