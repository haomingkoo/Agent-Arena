"""
Coaching recommender — generates improvement recommendations for skills.

Pipeline:
1. Extract performance patterns (top vs bottom)
2. Score the target skill with heuristics
3. Identify dimension gaps
4. Call LLM to generate specific coaching
5. Persist to DB
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from coach.analyzer import PerformancePattern, _detect_content_patterns
from coach.templates import COACHING_PROMPT
from evaluate.heuristic import score_skill_stage1
from evaluate.rubric import ParsedSkill, SkillScore, extract_json_object
from store.db import add_coaching


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class CoachingItem:
    """A single coaching recommendation."""

    priority: int
    area: str
    observation: str
    recommendation: str
    example: str
    estimated_impact: str  # high | medium | low


@dataclass
class CoachingResult:
    """Complete coaching output for a skill."""

    skill_id: str
    skill_name: str
    category: str
    tournament_week: str
    current_rank: int
    recommendations: list[CoachingItem] = field(default_factory=list)
    summary: str = ""


# ── Dimension names and labels ────────────────────────────────────────────

_DIMENSION_LABELS = {
    "frequency_value": "Frequency Value",
    "capability_upgrade": "Capability Upgrade",
    "specificity": "Specificity",
    "token_efficiency": "Token Efficiency",
    "source_credibility": "Source Credibility",
    "trigger_clarity": "Trigger Clarity",
    "methodology_depth": "Methodology Depth",
}


# ── Prompt formatting helpers ─────────────────────────────────────────────


def _format_winner_patterns(patterns: PerformancePattern) -> str:
    """Format top performer patterns into a readable string for the prompt."""
    lines: list[str] = []

    if patterns.top_patterns:
        for p in patterns.top_patterns:
            lines.append(f"- {p}")
    else:
        lines.append("- No significant distinguishing patterns detected")

    # Add structural insight
    if patterns.avg_lines_top > 0:
        lines.append(
            f"- Avg length: top {patterns.avg_lines_top:.0f} lines "
            f"vs bottom {patterns.avg_lines_bottom:.0f} lines"
        )
    if patterns.avg_tokens_top > 0:
        lines.append(
            f"- Avg tokens: top {patterns.avg_tokens_top:.0f} "
            f"vs bottom {patterns.avg_tokens_bottom:.0f}"
        )

    return "\n".join(lines)


def _format_dimension_gaps(
    skill_score: SkillScore,
    patterns: PerformancePattern,
) -> str:
    """Format dimension gaps between this skill and top performers."""
    lines: list[str] = []

    # Sort by gap magnitude (largest gap = biggest opportunity)
    sorted_dims = sorted(
        patterns.dimension_gaps.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for dim, gap in sorted_dims:
        if gap <= 0.05:
            continue  # skip negligible gaps
        skill_val = getattr(skill_score, dim, 0.0)
        label = _DIMENSION_LABELS.get(dim, dim)
        lines.append(
            f"- {label}: this skill {skill_val:.2f}, "
            f"gap vs top: -{gap:.2f}"
        )

    if not lines:
        lines.append("- No significant dimension gaps detected")

    return "\n".join(lines)


def _format_weak_tasks(weak_tasks: list[dict]) -> str:
    """Format weakest tasks into a readable list."""
    if not weak_tasks:
        return "- No task-level data available"

    lines: list[str] = []
    for task in weak_tasks[:5]:
        task_id = task.get("task_id", "unknown")
        score = task.get("score", 0.0)
        verdict = task.get("verdict", "unknown")
        lines.append(f"- {task_id}: score={score:.2f}, verdict={verdict}")
    return "\n".join(lines)


def _format_structural_comparison(
    skill: ParsedSkill,
    patterns: PerformancePattern,
) -> str:
    """Format structural comparison between this skill and the groups."""
    lines: list[str] = [
        f"- This skill: {skill.line_count} lines, ~{skill.token_estimate} tokens",
        f"- Top avg: {patterns.avg_lines_top:.0f} lines, ~{patterns.avg_tokens_top:.0f} tokens",
        f"- Bottom avg: {patterns.avg_lines_bottom:.0f} lines, ~{patterns.avg_tokens_bottom:.0f} tokens",
    ]

    content_patterns = _detect_content_patterns(skill)
    present = [k for k, v in content_patterns.items() if v > 0]
    absent = [k for k, v in content_patterns.items() if v == 0]

    if present:
        lines.append(f"- Has: {', '.join(present)}")
    if absent:
        lines.append(f"- Missing: {', '.join(absent)}")

    return "\n".join(lines)


# ── LLM coaching generation ──────────────────────────────────────────────


def _call_llm_coaching(prompt: str) -> dict | None:
    """Call Claude Haiku to generate coaching recommendations.

    Returns parsed JSON dict or None on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()

        json_str = extract_json_object(raw_text)
        if not json_str:
            return None

        return json.loads(json_str)
    except Exception:
        return None


# ── Rule-based fallback coaching ─────────────────────────────────────────


def _rule_based_coaching(
    skill: ParsedSkill,
    score: SkillScore,
    patterns: PerformancePattern,
) -> list[CoachingItem]:
    """
    Fallback coaching without LLM. Based on heuristic dimension gaps.

    Checks each dimension against thresholds and the top performers.
    Generates specific, actionable recommendations for the weakest areas.
    """
    items: list[CoachingItem] = []
    priority = 1

    content_patterns = _detect_content_patterns(skill)

    # Check specificity
    if score.specificity < 0.5:
        items.append(CoachingItem(
            priority=priority,
            area="specificity",
            observation=(
                f"Specificity score is {score.specificity:.2f} (below 0.50 threshold). "
                "The skill lacks concrete rules, numeric thresholds, or named tools."
            ),
            recommendation=(
                "Add specific numeric thresholds, named tools, and concrete patterns. "
                "Replace vague instructions like 'write good tests' with "
                "'ensure >80% branch coverage using vitest, fail if any test >200ms'."
            ),
            example=(
                "Before: 'Write clean, well-tested code'\n"
                "After: 'Enforce max 30 lines per function. "
                "Use vitest for unit tests with >80% branch coverage. "
                "Fail CI if any single test exceeds 200ms.'"
            ),
            estimated_impact="high",
        ))
        priority += 1

    # Check methodology depth
    if score.methodology_depth < 0.5:
        items.append(CoachingItem(
            priority=priority,
            area="methodology",
            observation=(
                f"Methodology depth is {score.methodology_depth:.2f} (below 0.50 threshold). "
                "No named framework, multi-step process, or decision tree detected."
            ),
            recommendation=(
                "Add a named framework or multi-phase process. Structure instructions "
                "as phases (Phase 1: Analyze, Phase 2: Plan, Phase 3: Implement) with "
                "decision points between them."
            ),
            example=(
                "Before: 'Review the code and fix issues'\n"
                "After: 'Phase 1 - Static Analysis: Run eslint + semgrep. "
                "Phase 2 - Logic Review: Trace data flow, check edge cases. "
                "Phase 3 - Fix: If severity >= high, fix inline. "
                "If low, add TODO with issue link.'"
            ),
            estimated_impact="high",
        ))
        priority += 1

    # Check trigger clarity
    if score.trigger_clarity < 0.5:
        items.append(CoachingItem(
            priority=priority,
            area="triggers",
            observation=(
                f"Trigger clarity is {score.trigger_clarity:.2f} (below 0.50 threshold). "
                "No explicit trigger conditions found in frontmatter or body."
            ),
            recommendation=(
                "Add explicit trigger conditions in YAML frontmatter. "
                "Define when this skill should activate with specific patterns."
            ),
            example=(
                "Add to frontmatter:\n"
                "triggers:\n"
                '  - "when the user asks to review a pull request"\n'
                '  - "when reviewing code changes or diffs"\n'
                '  - "when the user mentions code quality or linting"'
            ),
            estimated_impact="medium",
        ))
        priority += 1

    # Check token efficiency
    if score.token_efficiency < 0.5:
        items.append(CoachingItem(
            priority=priority,
            area="token_efficiency",
            observation=(
                f"Token efficiency is {score.token_efficiency:.2f} (below 0.50 threshold). "
                f"Skill is {skill.line_count} lines (~{skill.token_estimate} tokens). "
                "Top performers average "
                f"{patterns.avg_lines_top:.0f} lines."
            ),
            recommendation=(
                "Reduce verbosity by removing filler phrases. Use progressive disclosure: "
                "put essential rules first, advanced/conditional rules in later sections. "
                "Remove duplicate instructions."
            ),
            example=(
                "Before: 'You should always make sure to carefully consider...'\n"
                "After: 'Always: [rule]. Never: [rule].'\n\n"
                "Use tiered sections:\n"
                "## Core Rules (always loaded)\n"
                "## Advanced (load when relevant)\n"
                "## Edge Cases (load on demand)"
            ),
            estimated_impact="medium",
        ))
        priority += 1

    # Check for missing code examples
    if content_patterns.get("code_blocks", 0) == 0:
        items.append(CoachingItem(
            priority=priority,
            area="specificity",
            observation=(
                "No code examples found. Top-performing skills typically include "
                "code blocks showing expected input/output format."
            ),
            recommendation=(
                "Add code examples showing expected output format. Include at least "
                "one 'before' and 'after' example, or a template of the expected response."
            ),
            example=(
                "Add a section like:\n"
                "## Output Format\n"
                "```json\n"
                '{"assessment": "...", "issues": [...], "fixed_code": "..."}\n'
                "```"
            ),
            estimated_impact="medium",
        ))
        priority += 1

    # Check for missing error handling guidance
    if content_patterns.get("error_handling", 0) == 0:
        items.append(CoachingItem(
            priority=priority,
            area="other",
            observation=(
                "No error handling or edge case guidance found. "
                "Skills that address failure modes score higher in tournaments."
            ),
            recommendation=(
                "Add a section on edge cases and error handling. "
                "Specify what to do when inputs are malformed, files are missing, "
                "or the task is ambiguous."
            ),
            example=(
                "Add a section like:\n"
                "## Edge Cases\n"
                "- If the input file is empty, return an error message "
                "explaining what's needed\n"
                "- If the code has syntax errors, fix them before proceeding "
                "with the review\n"
                "- If the task is ambiguous, ask one clarifying question "
                "before starting"
            ),
            estimated_impact="low",
        ))
        priority += 1

    # Cap at 5 recommendations
    return items[:5]


# ── Main entry point ─────────────────────────────────────────────────────


def generate_coaching(
    skill: ParsedSkill,
    skill_id: str,
    category: str,
    rank: int,
    total: int,
    skill_score: float,
    top_score: float,
    bottom_score: float,
    baseline_score: float,
    patterns: PerformancePattern,
    weak_tasks: list[dict],
    tournament_week: str = "",
) -> CoachingResult:
    """
    Generate coaching for a skill based on tournament results.

    1. Score skill with heuristics to get dimension values
    2. Format the coaching prompt with patterns and gaps
    3. Call Claude Haiku to generate recommendations
    4. Parse JSON response
    5. Persist to DB
    6. Return CoachingResult

    Falls back to rule-based coaching if no API key or LLM call fails.
    """
    # Score skill with heuristics for dimension analysis
    heuristic_score = score_skill_stage1(skill)

    result = CoachingResult(
        skill_id=skill_id,
        skill_name=skill.name or "unknown",
        category=category,
        tournament_week=tournament_week,
        current_rank=rank,
    )

    # Attempt LLM-based coaching
    llm_result = None

    prompt = COACHING_PROMPT.format(
        category=category,
        rank=rank,
        total=total,
        skill_content=(skill.raw_content or skill.instructions)[:6000],
        skill_score=skill_score,
        top_score=top_score,
        bottom_score=bottom_score,
        baseline_score=baseline_score,
        winner_patterns=_format_winner_patterns(patterns),
        weak_tasks=_format_weak_tasks(weak_tasks),
        dimension_gaps=_format_dimension_gaps(heuristic_score, patterns),
        structural_comparison=_format_structural_comparison(skill, patterns),
    )

    llm_result = _call_llm_coaching(prompt)

    if llm_result and "recommendations" in llm_result:
        # Parse LLM recommendations
        valid_areas = {
            "specificity", "methodology", "structure", "triggers",
            "safety", "token_efficiency", "other",
        }
        for rec in llm_result["recommendations"]:
            area = rec.get("area", "other")
            if area not in valid_areas:
                area = "other"
            result.recommendations.append(CoachingItem(
                priority=rec.get("priority", 0),
                area=area,
                observation=rec.get("observation", ""),
                recommendation=rec.get("recommendation", ""),
                example=rec.get("example", ""),
                estimated_impact=rec.get("estimated_impact", "medium"),
            ))
        result.summary = llm_result.get("summary", "")
    else:
        # Fallback to rule-based coaching
        result.recommendations = _rule_based_coaching(
            skill, heuristic_score, patterns,
        )
        if result.recommendations:
            weak_areas = [r.area for r in result.recommendations[:3]]
            result.summary = (
                f"Rule-based analysis identified {len(result.recommendations)} "
                f"improvement areas: {', '.join(weak_areas)}."
            )
        else:
            result.summary = "No significant weaknesses detected by heuristic analysis."

    # Persist to DB
    coaching_record = {
        "skill_id": skill_id,
        "skill_name": result.skill_name,
        "category": category,
        "tournament_week": tournament_week,
        "current_rank": rank,
        "current_rating": skill_score,
        "recommendations": [
            {
                "priority": r.priority,
                "area": r.area,
                "observation": r.observation,
                "recommendation": r.recommendation,
                "example": r.example,
                "estimated_impact": r.estimated_impact,
            }
            for r in result.recommendations
        ],
        "summary": result.summary,
        "estimated_rank_improvement": _estimate_rank_improvement(
            rank, total, len(result.recommendations),
        ),
    }
    add_coaching(coaching_record)

    return result


def _estimate_rank_improvement(
    current_rank: int,
    total: int,
    num_recommendations: int,
) -> int:
    """
    Estimate how many rank positions a skill could improve.

    Conservative heuristic: each high-priority recommendation could
    move the skill up ~1-2 positions, capped at half the remaining distance
    to first place.
    """
    if total <= 1 or current_rank <= 1:
        return 0

    max_possible = current_rank - 1
    estimated = min(num_recommendations, max_possible)
    # Cap at half the distance to first place
    capped = min(estimated, max_possible // 2 + 1)
    return max(capped, 0)
