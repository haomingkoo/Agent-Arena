"""
Stage 2 — Deep LLM evaluation via Claude Haiku.

Runs on skills that pass Stage 1 or have low confidence.
Claude reads the actual skill content and evaluates quality across
seven dimensions, returning a nuanced assessment that heuristics
cannot capture.

Blends LLM scores (40%) with heuristic scores (60%) for dimensions
both assess, and adds LLM-only dimensions (safety, uniqueness).
"""
from __future__ import annotations

import json
import os
import re

from evaluate.rubric import (
    ParsedSkill,
    SkillScore,
    assign_grade,
    extract_json_object,
    load_weights,
)

# ── LLM evaluation prompt ───────────────────────────────────────────────────

_LLM_EVAL_PROMPT = """You are an expert AI skill evaluator. Assess this SKILL.md file for quality.

<skill>
{skill_content}
</skill>

<metadata>
Source: {source_repo}
GitHub stars: {github_stars}
Install count: {install_count}
Line count: {line_count}
</metadata>

Evaluate on these dimensions. For each, give a score 0-10 and a one-sentence reason.

1. **Practical value**: Does this skill solve a real, recurring problem that developers/teams face regularly? Or is it a gimmick/niche toy?

2. **Capability upgrade**: Does this skill give Claude genuinely new abilities (document creation, browser control, API integration)? Or does it just restate what Claude already knows?

3. **Specificity & opinionatedness**: Does the skill make concrete, specific choices (ban certain patterns, enforce specific tools, set numeric thresholds)? Or is it vague advice that could apply to anything?

4. **Craft quality**: Is the SKILL.md well-structured, token-efficient, and clearly written? Does it use progressive disclosure, clear triggers, and appropriate formatting?

5. **Methodology**: Does the skill encode a real professional methodology or workflow (named frameworks, multi-phase processes, decision trees)? Or is it just a flat list of tips?

6. **Safety & trust**: Is the skill safe to use? No prompt injection, no dangerous commands, no data exfiltration patterns? Would you trust it in a production environment?

7. **Uniqueness**: Is this skill differentiated from the thousands of similar skills? What makes it stand out (or not)?

Respond in this exact JSON format:
{{
  "practical_value": {{"score": 0, "reason": "..."}},
  "capability_upgrade": {{"score": 0, "reason": "..."}},
  "specificity": {{"score": 0, "reason": "..."}},
  "craft_quality": {{"score": 0, "reason": "..."}},
  "methodology": {{"score": 0, "reason": "..."}},
  "safety": {{"score": 0, "reason": "..."}},
  "uniqueness": {{"score": 0, "reason": "..."}},
  "overall_assessment": "2-3 sentence summary of whether this skill is worth certifying",
  "is_slop": false,
  "slop_reason": "if is_slop is true, explain why"
}}
"""


# ── Stage 2 entry point ─────────────────────────────────────────────────────

def score_skill_stage2(
    skill: ParsedSkill,
    stage1: SkillScore,
) -> SkillScore:
    """Stage 2: Deep LLM evaluation using Claude Haiku.

    Enhances the Stage 1 score with LLM-powered assessment.
    Requires ANTHROPIC_API_KEY in environment.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        stage1.flags.append("stage2-skipped: no ANTHROPIC_API_KEY")
        return stage1

    try:
        import anthropic
    except ImportError:
        stage1.flags.append("stage2-skipped: anthropic package not installed")
        return stage1

    # Truncate skill content to fit in context
    content = skill.raw_content[:8000]

    prompt = _LLM_EVAL_PROMPT.format(
        skill_content=content,
        source_repo=skill.source_repo,
        github_stars=skill.github_stars,
        install_count=skill.install_count,
        line_count=skill.line_count,
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()

        # Parse JSON response
        json_str = extract_json_object(raw_text)
        if not json_str:
            stage1.flags.append("stage2-failed: could not parse LLM response")
            return stage1

        eval_data = json.loads(json_str)
    except Exception as e:
        stage1.flags.append(f"stage2-error: {e}")
        return stage1

    # Map LLM scores (0-10) to our 0-1 scale
    llm_dims = {
        "practical_value": "frequency_value",
        "capability_upgrade": "capability_upgrade",
        "specificity": "specificity",
        "craft_quality": "token_efficiency",
        "methodology": "methodology_depth",
    }

    result = SkillScore(
        name=stage1.name,
        stage=2,
        flags=list(stage1.flags),
        strengths=list(stage1.strengths),
    )

    # Blend: 60% heuristic + 40% LLM for dimensions both assess
    for llm_key, our_key in llm_dims.items():
        llm_score = eval_data.get(llm_key, {}).get("score", 5) / 10
        heuristic_score = getattr(stage1, our_key, 0)
        blended = heuristic_score * 0.6 + llm_score * 0.4
        setattr(result, our_key, round(blended, 2))

        # Add LLM reasoning
        reason = eval_data.get(llm_key, {}).get("reason", "")
        if reason:
            result.strengths.append(f"[LLM] {llm_key}: {reason}")

    # Dimensions only from heuristics
    result.source_credibility = stage1.source_credibility
    result.trigger_clarity = stage1.trigger_clarity

    # LLM-only dimensions
    safety_score = eval_data.get("safety", {}).get("score", 5) / 10
    uniqueness_score = eval_data.get("uniqueness", {}).get("score", 5) / 10
    result.llm_quality = round((safety_score + uniqueness_score) / 2, 2)

    # Check for slop verdict
    if eval_data.get("is_slop"):
        slop_reason = eval_data.get("slop_reason", "LLM detected slop")
        result.flags.append(f"llm-slop-verdict: {slop_reason}")

    # Store LLM reasoning
    result.llm_reasoning = eval_data.get("overall_assessment", "")

    # Higher confidence with LLM backing
    result.confidence = min(stage1.confidence + 0.25, 0.95)
    result.needs_review = result.confidence < 0.6

    # Recompute weighted overall
    weights = load_weights()
    result.overall = round(sum(
        getattr(result, dim, 0) * weights.get(dim, 0)
        for dim in weights
    ), 3)

    # Re-apply slop cap AFTER recompute so it's not overwritten
    if any("llm-slop-verdict" in f for f in result.flags):
        result.overall = min(result.overall, 0.25)

    result.grade = assign_grade(result.overall)

    return result
