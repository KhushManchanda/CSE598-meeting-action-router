Meeting date 2026-10-05 is a Monday.

- G1 due: "by Thursday" from Monday -> 2026-10-08.
- G3 due: "before our next sync" has no specific day -> left null
  deliberately (don't guess); category=relative_date to test that the
  resolver correctly refuses to resolve this rather than picking an
  arbitrary date.
- G4 due: "Friday morning" from Monday -> 2026-10-09 (time-of-day
  "morning" is not modeled, only the date).
- NOT a gold item (non_action): u6, "we should probably look into
  switching the CI runner at some point" -- a vague suggestion with no
  commitment or owner ("at some point"), and Dana explicitly says
  "Noted, not urgent." A good system should NOT extract this as an
  action item.
