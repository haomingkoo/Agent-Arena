"""
Insights — discover patterns in certified skills.

Analyzes the certified skills database to find:
- What dimensions correlate with adoption?
- What do Gold skills have in common?
- What patterns predict failure?
"""
from __future__ import annotations

from store.db import get_feedback_entries, list_skills


def analyze_quality_patterns() -> dict:
    """Compare Gold vs Bronze vs Uncertified to find distinguishing patterns."""
    gold = list_skills(cert_tier="gold", limit=1000)
    silver = list_skills(cert_tier="silver", limit=1000)
    bronze = list_skills(cert_tier="bronze", limit=1000)

    dims = [
        "frequency_value", "capability_upgrade", "specificity",
        "token_efficiency", "source_credibility", "trigger_clarity",
        "methodology_depth", "llm_quality",
    ]

    result = {}
    for tier_name, skills in [("gold", gold), ("silver", silver), ("bronze", bronze)]:
        if not skills:
            result[tier_name] = {"count": 0, "avg_dimensions": {}}
            continue
        avgs = {}
        for dim in dims:
            values = [getattr(s, dim, 0) for s in skills]
            avgs[dim] = round(sum(values) / len(values), 3) if values else 0
        result[tier_name] = {
            "count": len(skills),
            "avg_dimensions": avgs,
            "avg_line_count": round(sum(s.line_count for s in skills) / len(skills), 1),
            "avg_tokens": round(sum(s.token_estimate for s in skills) / len(skills), 1),
        }

    # What dimensions most differentiate Gold from Bronze?
    gold_count = result.get("gold", {}).get("count", 0)
    bronze_count = result.get("bronze", {}).get("count", 0)
    if gold_count > 0 and bronze_count > 0:
        diffs = {}
        for dim in dims:
            gold_avg = result["gold"]["avg_dimensions"].get(dim, 0)
            bronze_avg = result["bronze"]["avg_dimensions"].get(dim, 0)
            diffs[dim] = round(gold_avg - bronze_avg, 3)
        # Sort by biggest difference
        result["gold_vs_bronze_diffs"] = dict(
            sorted(diffs.items(), key=lambda x: -abs(x[1]))
        )

    return result


def print_insights() -> None:
    """Print human-readable insights about skill quality patterns."""
    patterns = analyze_quality_patterns()

    print("\n" + "=" * 60)
    print("  Skill Quality Insights")
    print("=" * 60)

    for tier in ["gold", "silver", "bronze"]:
        data = patterns.get(tier, {})
        count = data.get("count", 0)
        if count == 0:
            print(f"\n  {tier.upper()}: no skills yet")
            continue
        print(f"\n  {tier.upper()} ({count} skills):")
        print(f"    Avg lines: {data.get('avg_line_count', 0)}")
        print(f"    Avg tokens: {data.get('avg_tokens', 0)}")
        for dim, val in data.get("avg_dimensions", {}).items():
            filled = int(val * 20)
            empty = 20 - filled
            bar = "|" * filled + "." * empty
            print(f"    {dim:<22} {bar} {val:.2f}")

    diffs = patterns.get("gold_vs_bronze_diffs", {})
    if diffs:
        print(f"\n  What separates Gold from Bronze:")
        for dim, diff in diffs.items():
            direction = "+" if diff > 0 else "-"
            print(f"    {direction} {dim}: {diff:+.3f}")

    print(f"\n{'=' * 60}")
