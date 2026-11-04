"""
eval/score.py
---------------
Scores a system's predicted ActionItems against gold for one transcript.

Two distinct owner-accuracy numbers are reported on purpose, because they
answer different questions:

  owner_accuracy_raw
      For every PREDICTED item, find any gold item it evidence-overlaps
      with and compare owners. Denominator = number of predictions.
      This is a simple "per output row, is the owner field right?" count
      — the same style of measurement B0's own README uses when it says
      "the baseline gets the owner right on only 4 of 7 items". It does
      NOT deduplicate: if two predictions both describe the same gold
      item (a duplicate-prediction bug), both are scored independently.

  owner_accuracy_matched
      Computed only over the formal one-to-one MATCHED set produced by
      match_predictions_to_gold() below. A duplicate prediction that
      loses its gold item to a competing prediction is excluded here
      (it shows up as an unmatched extra instead, hurting precision).

v1 scope note: matching combines evidence-utterance overlap with a task
text-similarity tiebreak (difflib), greedily, highest-score-first. This
is a deliberately simple first version for step 1 (reproducing B0's
behavior end-to-end); category-aware matching, routing accuracy on
non-owner fields, and fault-injection/behavior metrics come in step 6
(eval/run_eval.py) once B1/agent-A exist to compare against.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from agent.schema import ActionItem

# Below this combined match score, a (prediction, gold) pair is not
# considered a match at all (prediction counts as an unmatched extra).
_MATCH_THRESHOLD = 0.2
_EVIDENCE_WEIGHT = 0.7
_TASK_SIM_WEIGHT = 0.3


def load_items(path: str | Path) -> list[ActionItem]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ActionItem(**row) for row in data]


def _normalize(s: Optional[str]) -> Optional[str]:
    return s.strip().lower() if isinstance(s, str) else s


def _evidence_overlap(a: ActionItem, b: ActionItem) -> float:
    """Jaccard overlap of evidence_utterance_ids. 0.0 if either side is empty."""
    set_a, set_b = set(a.evidence_utterance_ids), set(b.evidence_utterance_ids)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _task_similarity(a: ActionItem, b: ActionItem) -> float:
    return SequenceMatcher(None, a.task.lower(), b.task.lower()).ratio()


def _match_score(pred: ActionItem, gold: ActionItem) -> float:
    return _EVIDENCE_WEIGHT * _evidence_overlap(pred, gold) + _TASK_SIM_WEIGHT * _task_similarity(pred, gold)


@dataclass
class MatchResult:
    pred: ActionItem
    gold: Optional[ActionItem]  # None if pred is an unmatched "extra"
    score: float


def match_predictions_to_gold(predictions: list[ActionItem], gold: list[ActionItem]) -> list[MatchResult]:
    """Greedy one-to-one matching, highest-scoring pairs claimed first.

    Documented rule: for every (prediction, gold) pair, compute
    0.7 * evidence_jaccard_overlap + 0.3 * task_text_similarity. Sort all
    pairs scoring >= _MATCH_THRESHOLD descending; walk the list claiming
    each prediction's best still-available gold item. Predictions left
    over are "extras" (hurt precision); gold items left over are
    "misses" (hurt recall).
    """
    candidates = []
    for pred in predictions:
        for g in gold:
            s = _match_score(pred, g)
            if s >= _MATCH_THRESHOLD:
                candidates.append((s, pred, g))
    candidates.sort(key=lambda c: c[0], reverse=True)

    matched_pred_ids: set[str] = set()
    claimed_gold_ids: set[str] = set()
    results: list[MatchResult] = []

    for score, pred, g in candidates:
        if pred.id in matched_pred_ids or g.id in claimed_gold_ids:
            continue
        matched_pred_ids.add(pred.id)
        claimed_gold_ids.add(g.id)
        results.append(MatchResult(pred=pred, gold=g, score=score))

    for pred in predictions:
        if pred.id not in matched_pred_ids:
            results.append(MatchResult(pred=pred, gold=None, score=0.0))

    return results


def owner_accuracy_raw(predictions: list[ActionItem], gold: list[ActionItem]) -> dict:
    """Per-prediction owner accuracy via ANY evidence overlap with gold
    (many-to-one allowed — duplicates are each scored, not deduplicated).
    See module docstring for why this exists alongside the matched metric.
    """
    per_item = []
    correct = 0
    for pred in predictions:
        overlapping = [g for g in gold if _evidence_overlap(pred, g) > 0]
        true_owner = overlapping[0].owner if overlapping else None
        is_correct = bool(overlapping) and _normalize(pred.owner) == _normalize(true_owner)
        correct += int(is_correct)
        per_item.append(
            {
                "prediction_id": pred.id,
                "predicted_owner": pred.owner,
                "true_owner": true_owner,
                "correct": is_correct,
                "had_gold_overlap": bool(overlapping),
            }
        )
    n = len(predictions)
    return {"accuracy": (correct / n) if n else None, "correct": correct, "total": n, "per_item": per_item}


def score(predictions: list[ActionItem], gold: list[ActionItem]) -> dict:
    """Full v1 scoring: matched-pair precision/recall/F1 + owner/routing
    accuracy on the matched set, plus the raw owner-accuracy metric."""
    matches = match_predictions_to_gold(predictions, gold)
    matched = [m for m in matches if m.gold is not None]
    extras = [m for m in matches if m.gold is None]  # unmatched predictions
    matched_gold_ids = {m.gold.id for m in matched}
    missed_gold = [g for g in gold if g.id not in matched_gold_ids]  # unmatched gold

    tp, fp, fn = len(matched), len(extras), len(missed_gold)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    # `if precision and recall` is wrong here: 0.0 is a legitimate value
    # (tp=0 with fp>0 or fn>0, a real failure) but is falsy in Python, so
    # that check silently turned a real 0% F1 into a missing "None" --
    # found while preparing results for sponsor review. None is reserved
    # for precision/recall themselves being undefined (no predictions
    # and no gold at all); the 0+0 case is the standard F1 convention
    # (harmonic mean of 0 and anything is 0, not undefined).
    if precision is None or recall is None:
        f1 = None
    elif precision == 0.0 and recall == 0.0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    owner_correct = sum(1 for m in matched if _normalize(m.pred.owner) == _normalize(m.gold.owner))
    tool_correct = sum(1 for m in matched if _normalize(m.pred.tool) == _normalize(m.gold.tool))

    return {
        "n_predictions": len(predictions),
        "n_gold": len(gold),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "owner_accuracy_matched": (owner_correct / tp) if tp else None,
        "routing_accuracy_matched": (tool_correct / tp) if tp else None,
        "owner_accuracy_raw": owner_accuracy_raw(predictions, gold),
        "extras": [m.pred.id for m in extras],
        "missed_gold": [g.id for g in missed_gold],
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Score predictions (common-schema JSON) against gold JSON.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--gold", required=True)
    args = parser.parse_args()

    preds = load_items(args.predictions)
    golds = load_items(args.gold)
    print(json.dumps(score(preds, golds), indent=2))
