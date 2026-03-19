"""
Learning / feedback loop — track predictions vs real-world outcomes.

Records every score as a prediction, then compares with actual outcomes
(installs, stars, deprecation, community votes) to adjust scoring weights.

Persistence: uses store/db (SQLite) instead of flat JSONL files.
"""
from __future__ import annotations

import json

from evaluate.rubric import DEFAULT_WEIGHTS, SkillScore, load_weights, save_weights
from store.db import add_feedback, get_feedback_entries, update_feedback_outcome
from store.models import FeedbackEntry


def record_prediction(
    skill_name: str,
    score: SkillScore,
    source_url: str,
) -> str:
    """Record a prediction for later comparison with outcomes.

    Returns the feedback entry ID.
    """
    entry = FeedbackEntry(
        skill_name=skill_name,
        source_url=source_url,
        predicted_grade=score.grade,
        predicted_score=score.overall,
        confidence=score.confidence,
        dimensions_json=json.dumps(score.to_dict()["dimensions"]),
    )
    return add_feedback(entry)


def record_outcome(
    skill_name: str,
    installs: int | None = None,
    stars: int | None = None,
    deprecated: bool | None = None,
    community_score: float | None = None,
) -> bool:
    """Record real-world outcome for a previously scored skill.

    Call this when we discover install counts, star changes,
    deprecation, or community votes for skills we've scored.
    """
    outcomes: dict = {}
    if installs is not None:
        outcomes["outcome_installs"] = installs
    if stars is not None:
        outcomes["outcome_stars"] = stars
    if deprecated is not None:
        outcomes["outcome_deprecated"] = 1 if deprecated else 0
    if community_score is not None:
        outcomes["outcome_community_score"] = community_score

    if not outcomes:
        return False

    return update_feedback_outcome(skill_name, **outcomes)


def learn_from_feedback() -> dict:
    """Analyze predictions vs outcomes and suggest weight adjustments.

    Returns a report of what the scorer got right/wrong and
    updated weights if enough data exists.
    """
    entries = get_feedback_entries(with_outcomes_only=True)

    if len(entries) < 10:
        return {
            "status": "insufficient data",
            "entries_with_outcomes": len(entries),
            "need": 10,
        }

    # Compute correlation between each dimension and success
    # Success = high installs or high community score
    successes = []
    for e in entries:
        installs = e.get("outcome_installs") or 0
        community = e.get("outcome_community_score") or 0
        deprecated = bool(e.get("outcome_deprecated", False))
        # Normalized success signal
        success = 0.0
        if installs >= 100000:
            success += 1.0
        elif installs >= 10000:
            success += 0.7
        elif installs >= 1000:
            success += 0.4
        if community >= 0.8:
            success += 0.5
        if deprecated:
            success -= 1.0
        successes.append(max(0, min(success, 1.0)))

    # Correlate each dimension with success
    dims = list(DEFAULT_WEIGHTS.keys())
    correlations = {}
    for dim in dims:
        dim_scores = []
        for e in entries:
            dimensions = json.loads(e.get("dimensions_json", "{}"))
            dim_scores.append(dimensions.get(dim, 0))
        if len(set(dim_scores)) <= 1:
            correlations[dim] = 0.0
            continue
        # Simple correlation: mean score of successful vs unsuccessful
        high_success = [
            d for d, s in zip(dim_scores, successes) if s >= 0.5
        ]
        low_success = [
            d for d, s in zip(dim_scores, successes) if s < 0.5
        ]
        avg_high = sum(high_success) / len(high_success) if high_success else 0
        avg_low = sum(low_success) / len(low_success) if low_success else 0
        correlations[dim] = round(avg_high - avg_low, 3)

    # Adjust weights based on correlations
    current_weights = load_weights()
    new_weights = {}
    total = 0

    for dim in dims:
        corr = correlations.get(dim, 0)
        base = current_weights.get(dim, DEFAULT_WEIGHTS.get(dim, 0.1))
        # Shift weight toward dimensions that predict success
        adjusted = base * (1 + corr * 0.3)  # conservative adjustment
        adjusted = max(0.05, adjusted)  # floor
        new_weights[dim] = adjusted
        total += adjusted

    # Normalize to sum to 1.0
    for dim in new_weights:
        new_weights[dim] = round(new_weights[dim] / total, 3)

    save_weights(new_weights)

    return {
        "status": "weights_updated",
        "entries_analyzed": len(entries),
        "correlations": correlations,
        "old_weights": current_weights,
        "new_weights": new_weights,
    }
