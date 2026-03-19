"""
Pattern analyzer — extracts what top-performing skills do differently.

Uses Positive Deviance methodology: find uncommon but successful behaviors
in the top performers, compare against the bottom performers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from evaluate.rubric import ParsedSkill, SkillScore


# ── Content pattern detectors ──────────────────────────────────────────────

def _count_code_blocks(text: str) -> int:
    """Count fenced code blocks (``` pairs)."""
    return len(re.findall(r"```", text)) // 2


def _count_numbered_steps(text: str) -> int:
    """Count numbered list items (1. 2. 3. patterns)."""
    return len(re.findall(r"^\s*\d+\.\s+", text, re.MULTILINE))


def _has_decision_trees(text: str) -> bool:
    """Check for conditional/decision logic in instruction context."""
    text_lower = text.lower()
    patterns = [
        r"\bif\b.*\bthen\b",
        r"\bwhen\b.*\bdo\b",
        r"\bdepending on\b",
        r"\bbased on the\b",
        r"\bchoose between\b",
        r"\bif the .+ is\b",
        r"\bwhen .+ are\b",
    ]
    return any(re.search(p, text_lower) for p in patterns)


def _has_output_format(text: str) -> bool:
    """Check for explicit output format specification."""
    text_lower = text.lower()
    indicators = [
        "output format",
        "respond with",
        "return format",
        "response format",
        "output as",
        "format your response",
        "respond in",
        "return a json",
        "return json",
        "output:",
    ]
    return any(ind in text_lower for ind in indicators)


def _has_error_handling(text: str) -> bool:
    """Check for error/edge-case handling guidance."""
    text_lower = text.lower()
    indicators = [
        "error",
        "fail",
        "edge case",
        "handle",
        "fallback",
        "exception",
        "graceful",
        "invalid input",
        "unexpected",
        "recover",
    ]
    # Require at least 2 distinct indicators to reduce false positives
    hits = sum(1 for ind in indicators if ind in text_lower)
    return hits >= 2


def _has_methodology(text: str) -> bool:
    """Check for named frameworks or multi-phase processes."""
    text_lower = text.lower()
    return bool(re.search(
        r"(red.green.refactor|owasp|semgrep|codeql|"
        r"brainstorm.*spec.*plan|review.*merge|"
        r"arrange.*act.*assert|given.*when.*then|"
        r"plan.*implement.*test|dry.*kiss.*yagni|"
        r"agile|scrum|kanban|tdd|bdd|ddd|"
        r"phase\s*\d|stage\s*\d|step\s*\d)",
        text_lower,
    ))


def _detect_content_patterns(skill: ParsedSkill) -> dict[str, float]:
    """Detect concrete content patterns in a skill. Returns pattern name -> count or 0/1."""
    text = skill.instructions or skill.raw_content
    return {
        "code_blocks": float(_count_code_blocks(text)),
        "numbered_steps": float(_count_numbered_steps(text)),
        "decision_trees": 1.0 if _has_decision_trees(text) else 0.0,
        "output_format": 1.0 if _has_output_format(text) else 0.0,
        "error_handling": 1.0 if _has_error_handling(text) else 0.0,
        "methodology": 1.0 if _has_methodology(text) else 0.0,
        "tools_specified": float(len(skill.allowed_tools)),
        "triggers_defined": float(len(skill.triggers)),
    }


# ── Performance pattern data class ────────────────────────────────────────


@dataclass
class PerformancePattern:
    """What distinguishes winners from losers in a tournament."""

    category: str
    week: str
    top_count: int = 0
    bottom_count: int = 0
    # Structural differences
    avg_lines_top: float = 0.0
    avg_lines_bottom: float = 0.0
    avg_tokens_top: float = 0.0
    avg_tokens_bottom: float = 0.0
    # Score dimension differences (from heuristic scoring)
    dimension_gaps: dict[str, float] = field(default_factory=dict)
    # Content patterns
    top_patterns: list[str] = field(default_factory=list)
    bottom_patterns: list[str] = field(default_factory=list)
    # Task-level insights
    hardest_tasks: list[str] = field(default_factory=list)
    easiest_tasks: list[str] = field(default_factory=list)


# ── Structural analysis ───────────────────────────────────────────────────


def _avg(values: list[float]) -> float:
    """Safe average that returns 0 for empty lists."""
    return sum(values) / len(values) if values else 0.0


def _compute_structural(
    skills: list[ParsedSkill],
) -> tuple[float, float, int, int]:
    """Return (avg_lines, avg_tokens, heading_count, section_count)."""
    if not skills:
        return 0.0, 0.0, 0, 0

    lines = [float(s.line_count) for s in skills]
    tokens = [float(s.token_estimate) for s in skills]
    avg_lines = _avg(lines)
    avg_tokens = _avg(tokens)

    total_headings = 0
    total_sections = 0
    for s in skills:
        text = s.instructions or s.raw_content
        total_headings += len(re.findall(r"^#{1,6}\s+", text, re.MULTILINE))
        total_sections += len(re.findall(r"^#{2,3}\s+", text, re.MULTILINE))

    return avg_lines, avg_tokens, total_headings, total_sections


# ── Dimension gap analysis ────────────────────────────────────────────────

_DIMENSION_NAMES = [
    "frequency_value",
    "capability_upgrade",
    "specificity",
    "token_efficiency",
    "source_credibility",
    "trigger_clarity",
    "methodology_depth",
]


def _compute_dimension_gaps(
    top_scores: list[SkillScore],
    bottom_scores: list[SkillScore],
) -> dict[str, float]:
    """
    Compute the gap (top avg - bottom avg) for each scoring dimension.

    Positive values mean top performers score higher on that dimension.
    The larger the gap, the more that dimension distinguishes winners.
    """
    gaps: dict[str, float] = {}
    for dim in _DIMENSION_NAMES:
        top_vals = [getattr(s, dim, 0.0) for s in top_scores]
        bottom_vals = [getattr(s, dim, 0.0) for s in bottom_scores]
        top_avg = _avg(top_vals)
        bottom_avg = _avg(bottom_vals)
        gaps[dim] = round(top_avg - bottom_avg, 3)
    return gaps


# ── Content pattern aggregation ───────────────────────────────────────────


def _aggregate_patterns(skills: list[ParsedSkill]) -> dict[str, float]:
    """Compute average content pattern scores across a group of skills."""
    if not skills:
        return {}

    totals: dict[str, float] = {}
    for skill in skills:
        patterns = _detect_content_patterns(skill)
        for key, val in patterns.items():
            totals[key] = totals.get(key, 0.0) + val

    return {k: round(v / len(skills), 2) for k, v in totals.items()}


def _patterns_to_labels(
    avg_patterns: dict[str, float],
    threshold: float = 0.5,
) -> list[str]:
    """Convert average pattern scores to human-readable labels."""
    labels = []
    label_map = {
        "code_blocks": "code examples",
        "numbered_steps": "numbered steps",
        "decision_trees": "decision trees / conditional logic",
        "output_format": "explicit output format",
        "error_handling": "error handling guidance",
        "methodology": "named methodology / framework",
        "tools_specified": "allowed tools specified",
        "triggers_defined": "triggers defined",
    }
    for key, avg_val in avg_patterns.items():
        label = label_map.get(key, key)
        if avg_val >= threshold:
            labels.append(f"{label} (avg {avg_val:.1f})")
    return labels


# ── Main extraction function ──────────────────────────────────────────────


def extract_patterns(
    top_skills: list[ParsedSkill],
    bottom_skills: list[ParsedSkill],
    top_scores: list[SkillScore],
    bottom_scores: list[SkillScore],
    category: str,
    week: str,
) -> PerformancePattern:
    """
    Compare top N vs bottom N performers.

    Analyzes three axes:
    1. Structural: line count, token count, headings, sections
    2. Dimensional: which heuristic dimensions differ most
    3. Content: concrete patterns (code blocks, steps, decision trees, etc.)
    """
    pattern = PerformancePattern(
        category=category,
        week=week,
        top_count=len(top_skills),
        bottom_count=len(bottom_skills),
    )

    # 1. Structural analysis
    top_lines, top_tokens, _, _ = _compute_structural(top_skills)
    bottom_lines, bottom_tokens, _, _ = _compute_structural(bottom_skills)
    pattern.avg_lines_top = round(top_lines, 1)
    pattern.avg_lines_bottom = round(bottom_lines, 1)
    pattern.avg_tokens_top = round(top_tokens, 1)
    pattern.avg_tokens_bottom = round(bottom_tokens, 1)

    # 2. Dimension gap analysis
    pattern.dimension_gaps = _compute_dimension_gaps(top_scores, bottom_scores)

    # 3. Content pattern analysis
    top_avg_patterns = _aggregate_patterns(top_skills)
    bottom_avg_patterns = _aggregate_patterns(bottom_skills)

    # Identify patterns that top performers have significantly more of
    for key in top_avg_patterns:
        top_val = top_avg_patterns.get(key, 0.0)
        bottom_val = bottom_avg_patterns.get(key, 0.0)
        if top_val > bottom_val + 0.3:
            pattern.top_patterns.append(
                f"{key}: top avg {top_val:.1f} vs bottom avg {bottom_val:.1f}"
            )
        elif bottom_val > top_val + 0.3:
            pattern.bottom_patterns.append(
                f"{key}: bottom avg {bottom_val:.1f} vs top avg {top_val:.1f}"
            )

    # Add human-readable labels for top performer patterns
    top_labels = _patterns_to_labels(top_avg_patterns)
    if top_labels:
        pattern.top_patterns.extend(
            [f"common in top: {label}" for label in top_labels]
        )

    return pattern
