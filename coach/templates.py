"""Coaching prompt templates."""
from __future__ import annotations

COACHING_PROMPT = """You are a senior AI skill coach. A skill competed in the {category} tournament and ranked #{rank} out of {total}.

<skill_content>
{skill_content}
</skill_content>

<tournament_context>
Category: {category}
This skill's avg score: {skill_score:.3f}
Top 3 avg score: {top_score:.3f}
Bottom 3 avg score: {bottom_score:.3f}
Baseline (no skill): {baseline_score:.3f}
</tournament_context>

<winner_patterns>
Top-performing skills in this category share these traits:
{winner_patterns}
</winner_patterns>

<this_skill_weaknesses>
Weakest tasks for this skill:
{weak_tasks}

Dimension gaps vs top 3:
{dimension_gaps}

Structural comparison:
{structural_comparison}
</this_skill_weaknesses>

Generate 3-5 specific, actionable coaching recommendations. For each:
1. What you observed that's holding this skill back
2. Exactly what to change (specific enough to make the edit)
3. A brief example of the improved version

Respond in JSON:
{{
  "recommendations": [
    {{
      "priority": 1,
      "area": "specificity|methodology|structure|triggers|safety|token_efficiency|other",
      "observation": "what's wrong",
      "recommendation": "what to do",
      "example": "show the fix",
      "estimated_impact": "high|medium|low"
    }}
  ],
  "summary": "One sentence overall assessment"
}}"""
