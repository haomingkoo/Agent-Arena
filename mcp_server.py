"""
AgentArena MCP Server — exposes skill scoring, safety scanning,
leaderboard, and skill store queries as MCP tools.

Run with:
    python mcp_server.py
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from evaluate.heuristic import score_skill_stage1
from evaluate.rubric import parse_skill_md
from evaluate.safety import scan_text
from evaluate.sandbox import get_leaderboard_data
from store.db import get_stats, init_db, search_skills

mcp = FastMCP("agentarena")


@mcp.tool(
    description=(
        "Score a SKILL.md file using Stage 1 heuristic evaluation. "
        "Returns an overall score (0-1), letter grade (S/A/B/C/D/F), "
        "confidence level, per-dimension breakdown, flags, and strengths. "
        "No API key required — runs entirely offline."
    ),
)
def score(skill_md_content: str) -> str:
    """Parse and score SKILL.md content with fast heuristic evaluation."""
    parsed = parse_skill_md(skill_md_content)
    result = score_skill_stage1(parsed)
    return json.dumps(result.to_dict(), indent=2)


@mcp.tool(
    description=(
        "Scan text for safety threats: prompt injection, data exfiltration, "
        "malicious code execution, and social engineering patterns. "
        "Returns a list of detected threats (empty list means safe). "
        "No API key required — runs entirely offline."
    ),
)
def scan(text: str) -> str:
    """Scan text content for safety threats."""
    threats = scan_text(text)
    return json.dumps({"threats": threats, "safe": len(threats) == 0}, indent=2)


@mcp.tool(
    description=(
        "Get the current AgentArena leaderboard showing benchmark results "
        "for evaluated skills. Returns skill names, scores, pass rates, "
        "upgrade over baseline, and token usage — sorted by upgrade then score."
    ),
)
def leaderboard() -> str:
    """Return the current benchmark leaderboard data."""
    data = get_leaderboard_data()
    if not data:
        return json.dumps({"message": "No benchmark results yet.", "entries": []})
    return json.dumps({"entries": data}, indent=2)


@mcp.tool(
    description=(
        "Look up a skill by name in the certified skills database. "
        "Returns certification tier, scores, dimensions, flags, "
        "community votes, and source information."
    ),
)
def skill_detail(skill_name: str) -> str:
    """Search for a skill by name and return its full details."""
    init_db()
    results = search_skills(skill_name, limit=5)
    if not results:
        return json.dumps({"error": f"No skill found matching '{skill_name}'"})

    # Return the top match with full details
    top = results[0]
    detail = top.model_dump()
    # Remove bulky raw content from the response
    detail.pop("raw_content", None)
    detail.pop("instructions", None)

    # Include all matches if there are multiple
    if len(results) > 1:
        detail["other_matches"] = [
            {"name": s.name, "overall_score": s.overall_score, "cert_tier": s.cert_tier.value}
            for s in results[1:]
        ]

    return json.dumps(detail, indent=2, default=str)


@mcp.tool(
    description=(
        "Get aggregate statistics from the AgentArena skill store: "
        "total skills, certification tier counts (gold/silver/bronze/uncertified), "
        "average score, and average confidence."
    ),
)
def stats() -> str:
    """Return aggregate stats from the skill store."""
    init_db()
    data = get_stats()
    return json.dumps(data, indent=2)


if __name__ == "__main__":
    mcp.run()
