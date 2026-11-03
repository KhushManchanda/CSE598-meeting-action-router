import pytest

from eval.dataset import load_bundle, load_gold, load_split


def test_load_bundle_legacy_test1():
    bundle = load_bundle("test1")
    assert bundle.dataset == "test1"
    assert bundle.meeting_date == "2026-09-02"
    assert "Marcus" in bundle.transcript_text
    assert any(p["name"] == "Priya" for p in bundle.roster)


def test_load_bundle_synthetic():
    bundle = load_bundle("synth_eng_sync_01")
    assert bundle.dataset == "synthetic"
    assert bundle.meeting_date == "2026-10-05"
    assert any(p["name"] == "Dana" for p in bundle.roster)


def test_load_bundle_ami():
    bundle = load_bundle("ami_es2008c_closing")
    assert bundle.dataset == "ami"
    assert any(p["name"] == "Project Manager" for p in bundle.roster)


def test_load_bundle_unknown_id_raises():
    with pytest.raises(FileNotFoundError):
        load_bundle("definitely_not_a_real_transcript_id")


def test_load_gold_returns_items_when_reviewed():
    gold = load_gold("test1")
    assert gold is not None
    assert len(gold) == 6


def test_load_gold_returns_none_when_not_yet_reviewed():
    # synth_eng_sync_01 only has a gold_draft, nothing in data/gold/ yet.
    assert load_gold("synth_eng_sync_01") is None


def test_load_split_dev_and_test():
    dev = load_split("dev")
    test = load_split("test")
    assert "test1" in dev
    assert len(dev) == 6
    assert len(test) == 10
    assert set(dev).isdisjoint(set(test))
