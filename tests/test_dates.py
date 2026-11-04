from agent.dates import resolve_date

MEETING_DATE = "2026-09-02"  # Wednesday


def test_bare_next_week_is_ambiguous_returns_none():
    assert resolve_date("next week", MEETING_DATE) is None


def test_this_week_soon_later_are_ambiguous():
    for expr in ["this week", "soon", "later", "eventually"]:
        assert resolve_date(expr, MEETING_DATE) is None


def test_weekday_name_resolves_to_nearest_upcoming_occurrence():
    assert resolve_date("Friday", MEETING_DATE) == "2026-09-04"
    assert resolve_date("before Friday's launch", MEETING_DATE) == "2026-09-04"
    assert resolve_date("next Friday", MEETING_DATE) == "2026-09-04"
    assert resolve_date("Monday", MEETING_DATE) == "2026-09-07"


def test_weekday_same_as_meeting_day_resolves_to_meeting_date_itself():
    # 2026-09-02 is itself a Wednesday.
    assert resolve_date("Wednesday", MEETING_DATE) == "2026-09-02"


def test_tomorrow_and_relative_offsets():
    assert resolve_date("tomorrow", MEETING_DATE) == "2026-09-03"
    assert resolve_date("in 3 days", MEETING_DATE) == "2026-09-05"


def test_absolute_iso_date_passthrough():
    assert resolve_date("2026-09-10", MEETING_DATE) == "2026-09-10"


def test_empty_expression_returns_none():
    assert resolve_date("", MEETING_DATE) is None
    assert resolve_date("   ", MEETING_DATE) is None


def test_never_returns_a_date_before_the_meeting_date():
    # "last Friday" is before the meeting date; must not resolve to a past date.
    result = resolve_date("last Friday", MEETING_DATE)
    if result is not None:
        from datetime import date
        assert date.fromisoformat(result) >= date.fromisoformat(MEETING_DATE)


def test_end_of_day_resolves_to_the_meeting_date():
    # Found while reviewing gold labels for sponsor review: a common
    # real phrase ("before end of day") was previously unresolvable.
    assert resolve_date("end of day", MEETING_DATE) == MEETING_DATE
    assert resolve_date("EOD", MEETING_DATE) == MEETING_DATE
    assert resolve_date("by end of the day", MEETING_DATE) == MEETING_DATE
    assert resolve_date("before end of day", MEETING_DATE) == MEETING_DATE


def test_other_same_day_phrasings_resolve_to_the_meeting_date():
    for expr in ["this afternoon", "this morning", "this evening", "tonight", "later today"]:
        assert resolve_date(expr, MEETING_DATE) == MEETING_DATE
