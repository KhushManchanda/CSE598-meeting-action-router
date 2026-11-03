"""
eval/kappa.py
---------------
Cohen's kappa between two independent gold-label sets for the same
transcript(s), on the `owner` field. Spec: "Support Cohen's kappa if
we both label a shared subset."

Items are matched by `id` -- this measures agreement between two
HUMAN labelers who each drafted/reviewed the same items, not
prediction-vs-gold scoring (that's eval/score.py, which matches by
evidence overlap since a system's predictions won't share gold's ids).
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from agent.schema import ActionItem


def cohens_kappa(labels_a: list[Optional[str]], labels_b: list[Optional[str]]) -> float:
    """Standard two-rater Cohen's kappa over parallel label lists (same
    item, same order). Returns 1.0 for perfect agreement; handles the
    degenerate case where both raters only ever use one label (no
    disagreement is even possible) by returning 1.0 if they agree on
    every item, 0.0 otherwise, rather than dividing by zero."""
    if len(labels_a) != len(labels_b):
        raise ValueError("labels_a and labels_b must be the same length (one shared, item-matched subset)")
    n = len(labels_a)
    if n == 0:
        raise ValueError("cannot compute kappa over zero items")

    po = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n

    count_a, count_b = Counter(labels_a), Counter(labels_b)
    categories = set(count_a) | set(count_b)
    pe = sum((count_a[c] / n) * (count_b[c] / n) for c in categories)

    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


def kappa_on_owner_field(items_a: list[ActionItem], items_b: list[ActionItem]) -> float:
    """Computes cohens_kappa on the `owner` field over whichever item
    ids appear in BOTH lists (the "shared subset" the spec refers to)."""
    by_id_a = {item.id: item for item in items_a}
    by_id_b = {item.id: item for item in items_b}
    shared_ids = sorted(set(by_id_a) & set(by_id_b))
    if not shared_ids:
        raise ValueError("no shared item ids between the two label sets -- nothing to compare")

    labels_a = [by_id_a[i].owner for i in shared_ids]
    labels_b = [by_id_b[i].owner for i in shared_ids]
    return cohens_kappa(labels_a, labels_b)
