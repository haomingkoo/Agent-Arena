"""
Stage 1 — Fast heuristic skill scoring (no API calls).

Runs on every skill. Produces a preliminary score + confidence level.
Flags uncertain cases for Stage 2 LLM evaluation.

Scoring dimensions:
  - frequency_value: does it solve a common problem?
  - capability_upgrade: does it give Claude new abilities?
  - specificity: is it concrete and opinionated?
  - token_efficiency: is it concise and well-structured?
  - source_credibility: is the author trusted?
  - trigger_clarity: does it define clear activation triggers?
  - methodology_depth: does it encode a real methodology?
"""
from __future__ import annotations

import re

from evaluate.rubric import (
    CAPABILITY_INDICATORS,
    GENERIC_PHRASES,
    HIGH_FREQUENCY_DOMAINS,
    TRUSTED_ORGS,
    ParsedSkill,
    SkillScore,
    assign_grade,
    load_weights,
)


# ── Dimension scorers ───────────────────────────────────────────────────────
# Each returns (score, confidence, flags, strengths).

def _score_frequency(text_lower: str) -> tuple[float, float, list[str], list[str]]:
    """Score + confidence for frequency value."""
    domain_hits = sum(1 for d in HIGH_FREQUENCY_DOMAINS if d in text_lower)
    if domain_hits >= 3:
        return 1.0, 0.9, [], ["solves high-frequency problem"]
    elif domain_hits >= 2:
        return 0.8, 0.8, [], []
    elif domain_hits >= 1:
        return 0.5, 0.6, [], []
    else:
        # Low confidence — might be a novel domain we don't recognize
        return 0.2, 0.4, ["low-frequency: may be too niche (or novel domain we don't recognize)"], []


def _score_capability(text_lower: str, skill: ParsedSkill) -> tuple[float, float, list[str], list[str]]:
    """Score + confidence for capability upgrade."""
    capability_hits = sum(1 for c in CAPABILITY_INDICATORS if c in text_lower)
    has_tools = len(skill.allowed_tools) > 0
    generic_hits = sum(1 for g in GENERIC_PHRASES if g in text_lower)

    flags, strengths = [], []

    if has_tools and capability_hits >= 3:
        score, conf = 1.0, 0.9
        strengths.append(f"real capability: {len(skill.allowed_tools)} tool(s) + {capability_hits} action indicators")
    elif has_tools or capability_hits >= 3:
        score, conf = 0.8, 0.7
    elif capability_hits >= 1:
        score, conf = 0.5, 0.5
    else:
        score, conf = 0.2, 0.4
        flags.append("low-upgrade: may just be generic advice (or novel capability we don't recognize)")

    if generic_hits >= 3:
        score = max(0, score - 0.4)
        conf = min(conf + 0.2, 1.0)  # MORE confident it's slop
        flags.append(f"slop-detected: {generic_hits} generic phrases found")
    elif generic_hits >= 2:
        score = max(0, score - 0.2)
        flags.append(f"generic-phrases: {generic_hits} slop indicators")

    return score, conf, flags, strengths


def _score_specificity(instructions: str, text_lower: str) -> tuple[float, float, list[str], list[str]]:
    """Score + confidence for specificity."""
    flags, strengths = [], []

    specific_rules = len(re.findall(
        r"(?:must|should|always|never|do not|don't|require|ensure)\s+\w+",
        text_lower,
    ))
    code_blocks = len(re.findall(r"```", instructions))
    numbered_items = len(re.findall(r"^\s*\d+\.\s+", instructions, re.MULTILINE))
    bullet_items = len(re.findall(r"^\s*[-*]\s+", instructions, re.MULTILINE))
    structured_items = numbered_items + bullet_items

    # Concrete numbers, percentages, measurements
    concrete_values = len(re.findall(
        r"\b\d+(?:\.\d+)?(?:\s*(?:%|px|rem|em|ms|s|mb|gb|kb|tokens?|lines?|chars?))\b",
        text_lower,
    ))
    # Named tools, libraries, frameworks
    named_tools = len(re.findall(
        r"\b(?:react|next\.?js|vue|angular|tailwind|docker|postgres|redis|"
        r"webpack|vite|eslint|prettier|jest|vitest|playwright|cypress|"
        r"semgrep|codeql|owasp|wcag|aria)\b",
        text_lower,
    ))

    score = 0.0
    score += min(specific_rules / 5, 1.0) * 0.25
    score += min(code_blocks / 4, 1.0) * 0.20
    score += min(structured_items / 10, 1.0) * 0.20
    score += min(concrete_values / 3, 1.0) * 0.20
    score += min(named_tools / 3, 1.0) * 0.15
    score = round(min(score, 1.0), 2)

    # Confidence based on signal strength
    total_signals = specific_rules + code_blocks + structured_items + concrete_values + named_tools
    if total_signals >= 15:
        conf = 0.9
        strengths.append(f"highly specific: {specific_rules} rules, {code_blocks} code blocks, {named_tools} named tools")
    elif total_signals >= 8:
        conf = 0.7
    elif total_signals >= 3:
        conf = 0.5
    else:
        conf = 0.3  # very uncertain
        flags.append("vague: lacks concrete rules, examples, or tool references")

    return score, conf, flags, strengths


def _score_efficiency(skill: ParsedSkill, text_lower: str) -> tuple[float, float, list[str], list[str]]:
    """Score + confidence for token efficiency."""
    flags, strengths = [], []

    # Value density: meaningful content per line
    empty_lines = sum(1 for line in skill.instructions.split("\n") if not line.strip())
    content_lines = skill.line_count - empty_lines
    content_ratio = content_lines / max(skill.line_count, 1)

    if skill.line_count <= 100:
        score = 1.0
        strengths.append(f"concise: {skill.line_count} lines (~{skill.token_estimate} tokens)")
    elif skill.line_count <= 150:
        score = 0.8
    elif skill.line_count <= 300:
        score = 0.5
    elif skill.line_count <= 500:
        score = 0.3
        flags.append(f"heavy: {skill.line_count} lines (~{skill.token_estimate} tokens)")
    else:
        score = 0.1
        flags.append(f"bloated: {skill.line_count} lines (~{skill.token_estimate} tokens)")

    # Penalty for low content density
    if content_ratio < 0.5 and skill.line_count > 50:
        score = max(0, score - 0.15)
        flags.append(f"sparse: {empty_lines} empty lines out of {skill.line_count}")

    # Bonus for progressive disclosure
    if re.search(r"progressive|tier|load.+when|only.+relevant|conditionally", text_lower):
        score = min(score + 0.15, 1.0)
        strengths.append("uses progressive disclosure")

    return score, 0.9, flags, strengths  # high confidence — line count is objective


def _score_credibility(skill: ParsedSkill) -> tuple[float, float, list[str], list[str]]:
    """Score + confidence for source credibility."""
    flags, strengths = [], []
    repo_lower = skill.source_repo.lower()
    repo_owner = repo_lower.split("/")[0] if "/" in repo_lower else repo_lower

    if repo_owner in TRUSTED_ORGS:
        score = 1.0
        strengths.append(f"trusted source: {repo_owner}")
    elif skill.github_stars >= 10000:
        score = 0.9
        strengths.append(f"high stars: {skill.github_stars:,}")
    elif skill.github_stars >= 1000:
        score = 0.7
    elif skill.github_stars >= 100:
        score = 0.5
    elif skill.github_stars >= 10:
        score = 0.3
    else:
        score = 0.1
        flags.append("unknown-source: unverified author, low/no stars")

    if skill.install_count >= 100000:
        score = min(score + 0.2, 1.0)
        strengths.append(f"proven adoption: {skill.install_count:,} installs")
    elif skill.install_count >= 10000:
        score = min(score + 0.1, 1.0)

    # Confidence: install counts are strong signal, stars moderate, nothing = low
    if skill.install_count > 0:
        conf = 0.9
    elif skill.github_stars > 0:
        conf = 0.7
    else:
        conf = 0.3  # we really don't know

    return score, conf, flags, strengths


def _score_triggers(skill: ParsedSkill, text_lower: str) -> tuple[float, float, list[str], list[str]]:
    """Score + confidence for trigger clarity."""
    flags, strengths = [], []

    if skill.triggers:
        avg_trigger_len = sum(len(t) for t in skill.triggers) / len(skill.triggers)
        if avg_trigger_len >= 30:
            score = 1.0
            strengths.append(f"clear triggers: {len(skill.triggers)} specific activation conditions")
        elif avg_trigger_len >= 15:
            score = 0.8
        else:
            score = 0.6
        conf = 0.9
    elif re.search(r"(when|trigger|activat|use this skill|invoke|fires when)", text_lower):
        score, conf = 0.5, 0.5
    else:
        score, conf = 0.1, 0.6
        flags.append("no-triggers: unclear when this skill should activate")

    return score, conf, flags, strengths


def _score_methodology(skill: ParsedSkill, text_lower: str) -> tuple[float, float, list[str], list[str]]:
    """Score + confidence for methodology depth."""
    flags, strengths = [], []
    instructions = skill.instructions

    phase_patterns = len(re.findall(
        r"(phase|stage|step)\s*\d|#{2,3}\s*(phase|stage|step)",
        text_lower,
    ))
    checklist_items = len(re.findall(
        r"^\s*-\s*\[[\sx]\]", instructions, re.MULTILINE
    ))
    structured_items = len(re.findall(
        r"^\s*(?:\d+\.|-|\*)\s+", instructions, re.MULTILINE
    ))
    has_todo = "todo" in text_lower or "checklist" in text_lower
    has_named_methodology = bool(re.search(
        r"(red.green.refactor|owasp|semgrep|codeql|audit|"
        r"brainstorm.*spec.*plan|review.*merge|"
        r"arrange.*act.*assert|given.*when.*then|"
        r"plan.*implement.*test|dry.*kiss.*yagni|"
        r"agile|scrum|kanban|tdd|bdd|ddd)",
        text_lower,
    ))

    # Check for decision trees / conditional logic
    has_decision_logic = bool(re.search(
        r"(if .+ then|when .+ do|depending on|based on the|choose between)",
        text_lower,
    ))

    depth = 0.0
    if has_named_methodology:
        depth += 0.4
        strengths.append("encodes named methodology")
    if has_decision_logic:
        depth += 0.2
        strengths.append("includes decision logic")
    if phase_patterns >= 2:
        depth += 0.2
    elif phase_patterns >= 1:
        depth += 0.1
    if checklist_items >= 3 or has_todo:
        depth += 0.15
    if structured_items >= 8:
        depth += 0.1

    score = round(min(depth, 1.0), 2)

    # Confidence: named methodology = high, some structure = medium, nothing = low
    if has_named_methodology:
        conf = 0.8
    elif phase_patterns >= 1 or structured_items >= 5:
        conf = 0.6
    else:
        conf = 0.3  # might have implicit methodology we can't detect
        flags.append("shallow: no detected methodology (LLM review recommended)")

    return score, conf, flags, strengths


# ── Stage 1 entry point ─────────────────────────────────────────────────────

def score_skill_stage1(skill: ParsedSkill) -> SkillScore:
    """Stage 1: Fast heuristic scoring. No API calls."""
    result = SkillScore(name=skill.name or "unknown", stage=1)
    text_lower = f"{skill.name} {skill.description} {skill.instructions}".lower()

    # Score each dimension
    dim_results = {
        "frequency_value": _score_frequency(text_lower),
        "capability_upgrade": _score_capability(text_lower, skill),
        "specificity": _score_specificity(skill.instructions, text_lower),
        "token_efficiency": _score_efficiency(skill, text_lower),
        "source_credibility": _score_credibility(skill),
        "trigger_clarity": _score_triggers(skill, text_lower),
        "methodology_depth": _score_methodology(skill, text_lower),
    }

    confidences = []
    for dim_name, (score, conf, flags, strengths) in dim_results.items():
        setattr(result, dim_name, score)
        confidences.append(conf)
        result.flags.extend(flags)
        result.strengths.extend(strengths)

    # Overall confidence is the average, pulled down by lowest dimension
    avg_conf = sum(confidences) / len(confidences)
    min_conf = min(confidences)
    result.confidence = round(avg_conf * 0.7 + min_conf * 0.3, 2)

    # Flag for human review if confidence is low
    if result.confidence < 0.5:
        result.needs_review = True
        result.flags.append(
            f"low-confidence ({result.confidence:.0%}): "
            "heuristics uncertain, LLM evaluation recommended"
        )

    # Compute weighted overall
    weights = load_weights()
    result.overall = round(sum(
        getattr(result, dim, 0) * weights.get(dim, 0)
        for dim in weights
    ), 3)

    # Grade
    result.grade = assign_grade(result.overall)

    return result
