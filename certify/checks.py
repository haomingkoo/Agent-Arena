"""
Certification checks — Bronze / Silver / Gold tier requirements.

Each tier has specific, binary pass/fail checks with recorded reasons.
Bronze is "Not Slop", Silver is "Verified Quality", Gold is "Production Ready".
Each tier builds on the previous — you can't get Silver without Bronze.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from evaluate.rubric import GENERIC_PHRASES, ParsedSkill, SkillScore
from evaluate.safety import scan_text


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class Check:
    """A single certification check — pass/fail with reason."""
    name: str
    description: str
    passed: bool = False
    reason: str = ""
    required: bool = True  # required vs recommended


@dataclass
class CertificationResult:
    """Full certification audit for a skill."""
    skill_name: str
    source_url: str
    tier: str = "UNCERTIFIED"
    bronze_checks: list[Check] = field(default_factory=list)
    silver_checks: list[Check] = field(default_factory=list)
    gold_checks: list[Check] = field(default_factory=list)
    bronze_passed: bool = False
    silver_passed: bool = False
    gold_passed: bool = False
    score: SkillScore | None = None
    certified_at: str = ""
    expires_at: str = ""          # certifications expire — skills must be re-evaluated
    certification_id: str = ""

    def summary(self) -> str:
        lines = [
            f"{'='*60}",
            f"  WH-CERT Audit: {self.skill_name}",
            f"  Tier: {self.tier}",
            f"{'='*60}",
        ]

        for tier_name, checks, passed in [
            ("BRONZE — Not Slop", self.bronze_checks, self.bronze_passed),
            ("SILVER — Verified Quality", self.silver_checks, self.silver_passed),
            ("GOLD — Production Ready", self.gold_checks, self.gold_passed),
        ]:
            status = "PASSED" if passed else "FAILED"
            lines.append(f"\n  [{status}] {tier_name}")
            for c in checks:
                icon = "PASS" if c.passed else "FAIL"
                req = "" if c.required else " (recommended)"
                lines.append(f"    [{icon}] {c.name}{req}")
                if c.reason:
                    lines.append(f"           {c.reason}")

        lines.append(f"\n{'='*60}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "source_url": self.source_url,
            "tier": self.tier,
            "bronze_passed": self.bronze_passed,
            "silver_passed": self.silver_passed,
            "gold_passed": self.gold_passed,
            "bronze_checks": [
                {"name": c.name, "passed": c.passed, "reason": c.reason, "required": c.required}
                for c in self.bronze_checks
            ],
            "silver_checks": [
                {"name": c.name, "passed": c.passed, "reason": c.reason, "required": c.required}
                for c in self.silver_checks
            ],
            "gold_checks": [
                {"name": c.name, "passed": c.passed, "reason": c.reason, "required": c.required}
                for c in self.gold_checks
            ],
            "certified_at": self.certified_at,
            "expires_at": self.expires_at,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  BRONZE — "Not Slop" (basic quality bar)
# ══════════════════════════════════════════════════════════════════════════════

def _run_bronze(skill: ParsedSkill, score: SkillScore) -> list[Check]:
    """Bronze checks: is this skill worth anyone's time?"""
    checks = []

    # B1: Has a name and description
    checks.append(Check(
        name="B1: Identity",
        description="Skill has a clear name and description",
        passed=bool(skill.name.strip()) and bool(skill.description.strip()) and len(skill.description) >= 15,
        reason=f"name='{skill.name}', description={len(skill.description)} chars"
            if skill.name else "missing name or description",
    ))

    # B2: Not empty / too short
    checks.append(Check(
        name="B2: Substance",
        description="Skill has meaningful content (>20 lines of instructions)",
        passed=skill.line_count >= 20 and len(skill.instructions) >= 200,
        reason=f"{skill.line_count} lines, {len(skill.instructions)} chars of instructions",
    ))

    # B3: Not bloated (under 500 lines)
    checks.append(Check(
        name="B3: Efficiency",
        description="Skill is not bloated (<500 lines, <2000 tokens)",
        passed=skill.line_count <= 500 and skill.token_estimate <= 2000,
        reason=f"{skill.line_count} lines, ~{skill.token_estimate} tokens",
    ))

    # B4: Has structure (headings, lists, or code blocks)
    headings = len(re.findall(r"^#{1,3}\s+", skill.instructions, re.MULTILINE))
    lists = len(re.findall(r"^\s*[-*\d]+[.)]\s+", skill.instructions, re.MULTILINE))
    code_blocks = len(re.findall(r"```", skill.instructions))
    total_structure = headings + lists + code_blocks
    checks.append(Check(
        name="B4: Structure",
        description="Skill uses headings, lists, or code blocks",
        passed=total_structure >= 3,
        reason=f"{headings} headings, {lists} list items, {code_blocks} code blocks",
    ))

    # B5: No slop phrases (max 1 allowed)
    text_lower = f"{skill.name} {skill.description} {skill.instructions}".lower()
    slop_count = sum(1 for g in GENERIC_PHRASES if g in text_lower)
    checks.append(Check(
        name="B5: Anti-Slop",
        description="Contains fewer than 2 generic/filler phrases",
        passed=slop_count < 2,
        reason=f"{slop_count} generic phrases detected" if slop_count else "clean",
    ))

    # B6: Has YAML frontmatter with required fields
    has_frontmatter = skill.raw_content.strip().startswith("---")
    has_name_field = bool(skill.name)
    has_desc_field = bool(skill.description)
    checks.append(Check(
        name="B6: Frontmatter",
        description="Has YAML frontmatter with name and description",
        passed=has_frontmatter and has_name_field and has_desc_field,
        reason="valid frontmatter" if has_frontmatter else "missing frontmatter",
    ))

    # B7: Specificity score >= 0.3
    checks.append(Check(
        name="B7: Specificity",
        description="Contains concrete rules, numbers, or tool references (score >= 0.3)",
        passed=score.specificity >= 0.3,
        reason=f"specificity score: {score.specificity:.2f}",
    ))

    # B8: Has triggers or clear activation context
    checks.append(Check(
        name="B8: Activation",
        description="Specifies when the skill should activate",
        passed=score.trigger_clarity >= 0.4,
        reason=f"{len(skill.triggers)} triggers defined" if skill.triggers else "no explicit triggers",
    ))

    return checks


# ══════════════════════════════════════════════════════════════════════════════
#  SILVER — "Verified Quality" (deep evaluation)
# ══════════════════════════════════════════════════════════════════════════════

def _run_silver(skill: ParsedSkill, score: SkillScore) -> list[Check]:
    """Silver checks: is this skill genuinely good?"""
    checks = []

    # S1: Capability upgrade — adds real ability, not just advice
    checks.append(Check(
        name="S1: Capability Upgrade",
        description="Skill adds genuine new abilities (tools, outputs, integrations)",
        passed=score.capability_upgrade >= 0.5,
        reason=f"capability score: {score.capability_upgrade:.2f}",
    ))

    # S2: Methodology — encodes real professional process
    checks.append(Check(
        name="S2: Methodology",
        description="Encodes a structured professional methodology or workflow",
        passed=score.methodology_depth >= 0.3,
        reason=f"methodology score: {score.methodology_depth:.2f}",
    ))

    # S3: LLM evaluation passed (if available)
    if score.stage >= 2 and score.llm_reasoning:
        is_slop = "slop" in " ".join(score.flags).lower()
        checks.append(Check(
            name="S3: LLM Assessment",
            description="Passed deep LLM quality evaluation",
            passed=score.llm_quality >= 0.5 and not is_slop,
            reason=score.llm_reasoning[:200],
        ))
    else:
        checks.append(Check(
            name="S3: LLM Assessment",
            description="Passed deep LLM quality evaluation",
            passed=False,
            reason="Stage 2 LLM evaluation not run — required for Silver",
        ))

    # S4: Safety — no dangerous patterns
    combined_text = "\n".join([
        skill.name,
        skill.description or "",
        skill.instructions,
    ])
    threats = scan_text(combined_text)
    checks.append(Check(
        name="S4: Safety Scan",
        description="No prompt injection, exfiltration, or malicious patterns",
        passed=len(threats) == 0,
        reason="clean" if not threats else f"threats: {', '.join(threats[:3])}",
    ))

    # S5: Scorer confidence >= 60%
    checks.append(Check(
        name="S5: Confidence",
        description="Scorer has >= 60% confidence in the assessment",
        passed=score.confidence >= 0.6,
        reason=f"confidence: {score.confidence:.0%}",
    ))

    # S6: Overall score >= 0.55 (B grade or above)
    checks.append(Check(
        name="S6: Overall Quality",
        description="Overall quality score >= 0.55 (B grade minimum)",
        passed=score.overall >= 0.55,
        reason=f"overall: {score.overall:.3f} (grade {score.grade})",
    ))

    # S7: Not a duplicate of a higher-rated certified skill (recommended)
    checks.append(Check(
        name="S7: Uniqueness",
        description="Not a near-duplicate of an already-certified skill",
        passed=True,  # TODO: implement dedup against certified skills DB
        reason="dedup check not yet implemented",
        required=False,
    ))

    return checks


# ══════════════════════════════════════════════════════════════════════════════
#  GOLD — "Production Ready" (proven in the real world)
# ══════════════════════════════════════════════════════════════════════════════

def _run_gold(skill: ParsedSkill, score: SkillScore) -> list[Check]:
    """Gold checks: is this skill production-proven?"""
    checks = []

    # G1: Adoption — real-world usage signal
    has_adoption = skill.install_count >= 1000 or skill.github_stars >= 100
    checks.append(Check(
        name="G1: Adoption",
        description="Proven adoption (1000+ installs or 100+ GitHub stars)",
        passed=has_adoption,
        reason=f"{skill.install_count:,} installs, {skill.github_stars:,} stars",
    ))

    # G2: Source trust — from verified org or maintainer
    checks.append(Check(
        name="G2: Trusted Source",
        description="From a verified organization or established maintainer",
        passed=score.source_credibility >= 0.5,
        reason=f"credibility: {score.source_credibility:.2f}, repo: {skill.source_repo}",
    ))

    # G3: Overall score >= 0.70 (A grade)
    checks.append(Check(
        name="G3: Excellence",
        description="Overall quality score >= 0.70 (A grade minimum)",
        passed=score.overall >= 0.70,
        reason=f"overall: {score.overall:.3f} (grade {score.grade})",
    ))

    # G4: Token efficiency — respects context window
    checks.append(Check(
        name="G4: Token Budget",
        description="Efficient with context window (<300 lines, <1200 tokens)",
        passed=skill.line_count <= 300 and skill.token_estimate <= 1200,
        reason=f"{skill.line_count} lines, ~{skill.token_estimate} tokens",
    ))

    # G5: Cross-agent compatibility (recommended — check for format compliance)
    has_standard_frontmatter = bool(skill.name) and bool(skill.description)
    has_triggers = len(skill.triggers) > 0
    checks.append(Check(
        name="G5: Cross-Agent Compatible",
        description="SKILL.md follows the open standard for cross-agent use",
        passed=has_standard_frontmatter and has_triggers,
        reason="standard frontmatter + triggers" if has_standard_frontmatter else "missing standard fields",
        required=False,
    ))

    # G6: Actively maintained (recommended)
    # We'd check last commit date, open issues, etc. — placeholder for now
    checks.append(Check(
        name="G6: Maintained",
        description="Skill repo shows signs of active maintenance",
        passed=skill.github_stars >= 50,  # proxy for now
        reason="maintenance check requires repo activity data",
        required=False,
    ))

    return checks
