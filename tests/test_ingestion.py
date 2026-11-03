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
