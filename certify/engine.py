"""
Certification engine — orchestrates tier evaluation and persistence.

Runs the full Bronze -> Silver -> Gold certification pipeline on skills,
using the two-stage scoring system (heuristic + LLM) and the tier-specific
check functions from certify.checks.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from certify.checks import (
    Check,
    CertificationResult,
    _run_bronze,
    _run_gold,
    _run_silver,
)
from evaluate.heuristic import score_skill_stage1
from evaluate.llm_judge import score_skill_stage2
from evaluate.rubric import ParsedSkill, SkillScore
from learn.feedback import record_prediction

# ── Certification tiers ─────────────────────────────────────────────────────

BRONZE = "WH-CERT-BRONZE"
SILVER = "WH-CERT-SILVER"
GOLD = "WH-CERT-GOLD"
NONE = "UNCERTIFIED"

CERT_DB_PATH = Path("data/certifications.json")


# ══════════════════════════════════════════════════════════════════════════════
#  CERTIFICATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def certify(
    skill: ParsedSkill,
    deep: bool = True,
) -> CertificationResult:
    """Run full certification audit on a skill.

    Args:
        skill: Parsed SKILL.md content
        deep: If True, run Stage 2 LLM evaluation (required for Silver+)
    """
    # Score the skill
    stage1 = score_skill_stage1(skill)
    if deep:
        score = score_skill_stage2(skill, stage1)
    else:
        score = stage1

    result = CertificationResult(
        skill_name=skill.name or "unknown",
        source_url=skill.source_url,
        tier=NONE,
        score=score,
        certified_at=datetime.utcnow().isoformat(),
    )

    # ── Run Bronze checks ─────────────────────────────────────
    result.bronze_checks = _run_bronze(skill, score)
    required_bronze = [c for c in result.bronze_checks if c.required]
    result.bronze_passed = all(c.passed for c in required_bronze)

    if not result.bronze_passed:
        result.tier = NONE
        return result

    # ── Run Silver checks ─────────────────────────────────────
    result.silver_checks = _run_silver(skill, score)
    required_silver = [c for c in result.silver_checks if c.required]
    result.silver_passed = all(c.passed for c in required_silver)

    if not result.silver_passed:
        result.tier = BRONZE
        return result

    # ── Run Gold checks ───────────────────────────────────────
    result.gold_checks = _run_gold(skill, score)
    required_gold = [c for c in result.gold_checks if c.required]
    result.gold_passed = all(c.passed for c in required_gold)

    if not result.gold_passed:
        result.tier = SILVER
        return result

    result.tier = GOLD

    # Record prediction for learning loop
    record_prediction(skill.name, score, skill.source_url)

    return result


def certify_batch(
    skills: list[ParsedSkill],
    deep: bool = False,
) -> list[CertificationResult]:
    """Certify a batch of skills. Returns results sorted by tier then score."""
    results = []
    tier_order = {GOLD: 0, SILVER: 1, BRONZE: 2, NONE: 3}

    for i, skill in enumerate(skills):
        print(f"  [{i+1}/{len(skills)}] Certifying {skill.name or 'unknown'}...")
        result = certify(skill, deep=deep)
        results.append(result)
        print(f"    -> {result.tier}")

    results.sort(key=lambda r: (
        tier_order.get(r.tier, 99),
        -(r.score.overall if r.score else 0),
    ))
    return results


# ── Persistence ───────────────────────────────────────────────────────────────

def save_certifications(results: list[CertificationResult]) -> None:
    """Persist certification results."""
    CERT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = [r.to_dict() for r in results]
    with open(CERT_DB_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Certifications saved to {CERT_DB_PATH}")


def load_certifications() -> list[dict]:
    """Load persisted certifications."""
    if not CERT_DB_PATH.exists():
        return []
    with open(CERT_DB_PATH) as f:
        return json.load(f)


def print_certification_summary(results: list[CertificationResult]) -> None:
    """Print a summary table of certifications."""
    tiers = {GOLD: 0, SILVER: 0, BRONZE: 0, NONE: 0}
    for r in results:
        tiers[r.tier] = tiers.get(r.tier, 0) + 1

    total = len(results)
    print(f"\n{'='*65}")
    print(f"  WH-CERT Certification Results -- {total} skills evaluated")
    print(f"{'='*65}")
    print(f"  GOLD   (Production Ready)  : {tiers[GOLD]:>4}  {'|' * tiers[GOLD]}")
    print(f"  SILVER (Verified Quality)  : {tiers[SILVER]:>4}  {'|' * tiers[SILVER]}")
    print(f"  BRONZE (Not Slop)          : {tiers[BRONZE]:>4}  {'|' * tiers[BRONZE]}")
    print(f"  UNCERTIFIED (Failed)       : {tiers[NONE]:>4}  {'.' * tiers[NONE]}")
    if total > 0:
        cert_rate = (total - tiers[NONE]) / total
        print(f"\n  Certification rate: {cert_rate:.0%} ({total - tiers[NONE]}/{total})")
    print(f"{'='*65}\n")

    for r in results:
        score_str = f"{r.score.overall:.2f}" if r.score else "?.??"
        conf_str = f"{r.score.confidence:.0%}" if r.score else "?"
        print(f"  [{r.tier:>15}]  {score_str}  {conf_str} conf  {r.skill_name}")
