import pytest

from agent.schema import ActionItem
from eval.kappa import cohens_kappa, kappa_on_owner_field


def test_perfect_agreement_is_kappa_one():
    assert cohens_kappa(["Marcus", "Priya", "Jordan"], ["Marcus", "Priya", "Jordan"]) == pytest.approx(1.0)


def test_total_disagreement_with_balanced_labels_is_kappa_zero_or_below():
    # classic worked example: two raters, systematic disagreement
    kappa = cohens_kappa(["A", "A", "B", "B"], ["B", "B", "A", "A"])
    assert kappa <= 0.0


def test_partial_agreement_is_between_zero_and_one():
    kappa = cohens_kappa(["Marcus", "Priya", "Jordan", "Marcus"], ["Marcus", "Priya", "Priya", "Marcus"])
    assert 0.0 < kappa < 1.0


def test_none_values_are_valid_labels():
    kappa = cohens_kappa(["Marcus", None, "Priya"], ["Marcus", None, "Priya"])
    assert kappa == pytest.approx(1.0)


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        cohens_kappa(["Marcus"], ["Marcus", "Priya"])


def test_empty_lists_raise():
    with pytest.raises(ValueError):
        cohens_kappa([], [])


def test_single_shared_category_full_agreement_is_one():
    assert cohens_kappa(["Marcus", "Marcus"], ["Marcus", "Marcus"]) == 1.0


def test_single_shared_category_disagreement_is_zero_not_a_division_error():
    assert cohens_kappa(["Marcus", "Marcus"], ["Marcus", "Priya"]) == 0.0


def _item(item_id, owner):
    return ActionItem(id=item_id, transcript_id="t", task="x", owner=owner)


def test_kappa_on_owner_field_matches_by_id_over_shared_subset():
    items_a = [_item("g1", "Marcus"), _item("g2", "Priya"), _item("g3", "Jordan")]
    items_b = [_item("g1", "Marcus"), _item("g2", "Priya"), _item("g4", "Nobody")]  # g4 not shared, g3 missing
    kappa = kappa_on_owner_field(items_a, items_b)
    assert kappa == pytest.approx(1.0)  # only g1,g2 are shared and both agree


def test_kappa_on_owner_field_raises_with_no_shared_ids():
    items_a = [_item("g1", "Marcus")]
    items_b = [_item("g2", "Priya")]
    with pytest.raises(ValueError):
        kappa_on_owner_field(items_a, items_b)
