"""
Evaluation rubric — scoring weights, constants, and data classes.

Shared definitions used across the two-stage skill quality evaluation:
  - Stage 1 (heuristic.py): fast regex/structure scoring, no API calls
  - Stage 2 (llm_judge.py): deep LLM evaluation via Claude Haiku

Also provides the ParsedSkill parser for SKILL.md files and a learning
loop that persists / loads weight adjustments over time.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Weight configuration (learned over time) ────────────────────────────────

DEFAULT_WEIGHTS = {
    "frequency_value": 0.10,
    "capability_upgrade": 0.20,
    "specificity": 0.20,
    "token_efficiency": 0.10,
    "source_credibility": 0.10,
    "trigger_clarity": 0.10,
    "methodology_depth": 0.10,
    "llm_quality": 0.10,       # Stage 2: LLM assessment
}

WEIGHTS_PATH = Path("data/skill_weights.json")


def load_weights() -> dict[str, float]:
    """Load learned weights, or use defaults."""
    if WEIGHTS_PATH.exists():
        with open(WEIGHTS_PATH) as f:
            return json.load(f)
    return DEFAULT_WEIGHTS.copy()


def save_weights(weights: dict[str, float]) -> None:
    """Persist updated weights."""
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WEIGHTS_PATH, "w") as f:
        json.dump(weights, f, indent=2)


# ── High-frequency problem domains ──────────────────────────────────────────

HIGH_FREQUENCY_DOMAINS = {
    "code review", "testing", "tdd", "test-driven", "debugging",
    "frontend", "design", "ui", "ux", "css", "react", "next.js",
    "documentation", "docs", "readme", "api", "rest", "graphql",
    "deployment", "deploy", "ci/cd", "docker", "kubernetes",
    "security", "auth", "authentication", "git", "commit",
    "database", "sql", "migration", "refactor", "performance",
    "accessibility", "a11y", "seo", "monitoring", "logging",
    "email", "pdf", "spreadsheet", "document", "marketing",
    "data pipeline", "analytics", "video", "image",
}

# ── Capability upgrade indicators ────────────────────────────────────────────

CAPABILITY_INDICATORS = {
    "create", "generate", "build", "produce", "render", "export",
    "browser", "headless", "puppeteer", "playwright", "selenium",
    "api call", "http request", "webhook", "scrape", "crawl",
    "pdf", "docx", "xlsx", "pptx", "csv", "svg", "png",
    "video", "audio", "animation",
    "execute", "run command", "shell", "terminal", "sandbox",
    "database", "query", "migration",
}

# ── Slop indicators ─────────────────────────────────────────────────────────

GENERIC_PHRASES = {
    "write better code", "improve your", "best practices for everything",
    "be helpful", "be concise", "think step by step",
    "you are an expert", "you are a helpful", "act as a",
    "comprehensive guide", "ultimate guide", "complete guide",
    "always ensure", "make sure to", "remember to always",
}

# ── Trusted sources ─────────────────────────────────────────────────────────

TRUSTED_ORGS = {
    "anthropic", "anthropics", "vercel", "vercel-labs",
    "trail-of-bits", "trailofbits", "remotion",
    "composio", "composiohq", "firecrawl",
    "snyk", "pulumi", "obra", "superpowers",
    "microsoft", "google", "aws", "cloudflare",
    "figma", "notion", "atlassian", "sentry", "ramp",
    "langchain", "langgraph",
}


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class SkillScore:
    """Complete quality assessment for a skill."""
    name: str
    overall: float = 0.0
    confidence: float = 0.0       # 0-1: how sure are we about this score?
    frequency_value: float = 0.0
    capability_upgrade: float = 0.0
    specificity: float = 0.0
    token_efficiency: float = 0.0
    source_credibility: float = 0.0
    trigger_clarity: float = 0.0
    methodology_depth: float = 0.0
    llm_quality: float = 0.0     # Stage 2: LLM assessment
    flags: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    needs_review: bool = False    # route to human when uncertain
    llm_reasoning: str = ""       # Stage 2: why the LLM scored it this way
    grade: str = ""               # S / A / B / C / D / F
    stage: int = 1                # 1 = heuristic only, 2 = LLM-enhanced

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "overall": self.overall,
            "confidence": self.confidence,
            "grade": self.grade,
            "stage": self.stage,
            "needs_review": self.needs_review,
            "dimensions": {
                "frequency_value": self.frequency_value,
                "capability_upgrade": self.capability_upgrade,
                "specificity": self.specificity,
                "token_efficiency": self.token_efficiency,
                "source_credibility": self.source_credibility,
                "trigger_clarity": self.trigger_clarity,
                "methodology_depth": self.methodology_depth,
                "llm_quality": self.llm_quality,
            },
            "flags": self.flags,
            "strengths": self.strengths,
            "llm_reasoning": self.llm_reasoning,
        }


@dataclass
class ParsedSkill:
    """Parsed SKILL.md content."""
    name: str = ""
    description: str = ""
    instructions: str = ""
    triggers: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    source_repo: str = ""
    source_url: str = ""
    github_stars: int = 0
    install_count: int = 0
    line_count: int = 0
    token_estimate: int = 0
    raw_content: str = ""


# ── Parsing ─────────────────────────────────────────────────────────────────

def parse_skill_md(
    content: str,
    source_repo: str = "",
    source_url: str = "",
) -> ParsedSkill:
    """Parse a SKILL.md file into structured data."""
    skill = ParsedSkill(
        raw_content=content,
        source_repo=source_repo,
        source_url=source_url,
    )

    lines = content.strip().split("\n")
    skill.line_count = len(lines)
    skill.token_estimate = len(content) // 4

    # Parse YAML frontmatter
    if lines and lines[0].strip() == "---":
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx > 0:
            frontmatter = "\n".join(lines[1:end_idx])
            body = "\n".join(lines[end_idx + 1:])

            for line in frontmatter.split("\n"):
                line = line.strip()
                if line.startswith("name:"):
                    skill.name = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("description:"):
                    skill.description = line.split(":", 1)[1].strip().strip('"\'')

            trigger_match = re.search(
                r"triggers?:\s*\n((?:\s+-\s+.+\n?)+)", frontmatter
            )
            if trigger_match:
                for t in re.findall(r"-\s+(.+)", trigger_match.group(1)):
                    skill.triggers.append(t.strip().strip('"\''))

            tools_match = re.search(
                r"allowed[-_]tools?:\s*\n((?:\s+-\s+.+\n?)+)", frontmatter
            )
            if tools_match:
                for t in re.findall(r"-\s+(.+)", tools_match.group(1)):
                    skill.allowed_tools.append(t.strip().strip('"\''))

            skill.instructions = body.strip()
        else:
            skill.instructions = content
    else:
        skill.instructions = content

    if not skill.name:
        heading = re.search(r"^#\s+(.+)", content, re.MULTILINE)
        if heading:
            skill.name = heading.group(1).strip()

    return skill


# ── JSON extraction (brace-depth counting) ─────────────────────────────────


def extract_json_object(text: str) -> str | None:
    """Extract the first top-level JSON object from text using brace counting.

    Unlike a greedy regex, this correctly handles nested braces and stops
    at the matching closing brace rather than greedily consuming everything.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def repair_truncated_json(text: str) -> str | None:
    """Attempt to repair truncated JSON by closing unclosed braces/brackets.

    Handles the common case where a judge model hits its output token limit
    and produces a valid-prefix JSON that just stops mid-way.

    Returns a repaired JSON string or None if no JSON start was found.
    """
    start = text.find("{")
    if start == -1:
        return None

    # Track the nesting stack
    stack: list[str] = []
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()

    if not stack:
        # Already complete — shouldn't reach here, but return the text
        return extract_json_object(text)

    # Truncate to the last complete value boundary
    # Remove trailing partial strings/values before closing
    fragment = text[start:]

    # If we're mid-string, close the string first
    if in_string:
        fragment += '..."'

    # Remove any trailing comma or partial key
    import re
    fragment = re.sub(r',\s*"[^"]*$', "", fragment)  # partial key
    fragment = re.sub(r',\s*$', "", fragment)          # trailing comma

    # Close all open braces/brackets
    fragment += "".join(reversed(stack))

    return fragment


# ── Grade assignment ────────────────────────────────────────────────────────

def assign_grade(overall: float) -> str:
    """Map a 0-1 overall score to a letter grade."""
    if overall >= 0.85:
        return "S"
    elif overall >= 0.70:
        return "A"
    elif overall >= 0.55:
        return "B"
    elif overall >= 0.40:
        return "C"
    elif overall >= 0.25:
        return "D"
    return "F"
