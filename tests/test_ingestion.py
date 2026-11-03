from pathlib import Path

from agent.ingestion import parse_transcript

TEST1 = Path(__file__).resolve().parents[1] / "baselines" / "b0_rules" / "examples" / "test1.txt"


def test_parses_eleven_utterances_from_test1():
    utterances = parse_transcript(TEST1.read_text(encoding="utf-8"))
    assert len(utterances) == 11
    assert [u.id for u in utterances] == [f"u{i}" for i in range(1, 12)]


def test_skips_header_line_with_no_colon():
    utterances = parse_transcript(TEST1.read_text(encoding="utf-8"))
    assert all("Weekly Product Sync" not in u.raw for u in utterances)


def test_first_and_last_utterance_content():
    utterances = parse_transcript(TEST1.read_text(encoding="utf-8"))
    assert utterances[0].speaker == "Priya"
    assert utterances[0].text.startswith("Thanks everyone")
    assert utterances[-1].speaker == "Priya"
    assert "Meeting adjourned" in utterances[-1].text


def test_blank_lines_are_skipped():
    text = "Priya: hello\n\n\nMarcus: world\n"
    utterances = parse_transcript(text)
    assert len(utterances) == 2
    assert utterances[1].id == "u2"


def test_evidence_context_preserves_full_turns_and_deduplicates_windows():
    from agent.ingestion import evidence_context

    utterances = parse_transcript("A: Before.\nB: I will write an email. Include the budget.\nC: Include the deadline too.\nD: After.")
    context = evidence_context(utterances, ["u2", "u3", "u2", "missing"], window=1)
    assert [u["id"] for u in context] == ["u1", "u2", "u3", "u4"]
    assert context[1]["text"] == "I will write an email. Include the budget."
    assert context[2]["speaker"] == "C"
    assert evidence_context(utterances, ["missing"]) == []
