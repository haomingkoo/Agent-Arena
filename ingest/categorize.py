"""
Auto-categorization of skills into tournament categories.

Two-stage approach:
  Stage 1: Rule-based keyword matching (no API calls, instant)
  Stage 2: LLM classification via Claude Haiku (for ambiguous cases)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from evaluate.rubric import ParsedSkill, extract_json_object

# ── Category definitions ───────────────────────────────────────────────────

CATEGORIES: dict[str, dict] = {
    "code-review": {
        "display": "Code Review",
        "keywords": {
            "review", "pr", "pull request", "diff", "lint",
            "code quality", "code review", "reviewer", "linting",
        },
    },
    "testing": {
        "display": "Testing",
        "keywords": {
            "test", "tdd", "jest", "vitest", "pytest", "coverage",
            "assertion", "spec", "testing", "unit test", "integration test",
            "test-driven", "e2e", "end-to-end",
        },
    },
    "frontend": {
        "display": "Frontend",
        "keywords": {
            "react", "vue", "angular", "css", "tailwind", "ui",
            "component", "jsx", "tsx", "frontend", "next.js", "nuxt",
            "svelte", "html", "dom", "responsive",
        },
    },
    "backend": {
        "display": "Backend",
        "keywords": {
            "api", "rest", "graphql", "fastapi", "express", "endpoint",
            "server", "middleware", "backend", "flask", "django", "route",
            "controller", "microservice",
        },
    },
    "devops": {
        "display": "DevOps",
        "keywords": {
            "docker", "ci/cd", "deploy", "kubernetes", "terraform",
            "github actions", "pipeline", "devops", "infrastructure",
            "helm", "ansible", "cloudformation", "nixpacks",
        },
    },
    "security": {
        "display": "Security",
        "keywords": {
            "security", "owasp", "xss", "injection", "auth",
            "vulnerability", "pentest", "authentication", "authorization",
            "csrf", "encryption", "threat model",
        },
    },
    "documentation": {
        "display": "Documentation",
        "keywords": {
            "docs", "readme", "documentation", "jsdoc", "docstring",
            "changelog", "api docs", "wiki", "technical writing",
            "comment", "annotation",
        },
    },
    "database": {
        "display": "Database",
        "keywords": {
            "sql", "migration", "postgres", "mongodb", "schema", "query",
            "orm", "prisma", "database", "sqlite", "mysql", "redis",
            "index", "table", "nosql",
        },
    },
    "refactoring": {
        "display": "Refactoring",
        "keywords": {
            "refactor", "clean code", "technical debt", "extract",
            "simplify", "dry", "refactoring", "code smell",
            "decompose", "rename", "restructure",
        },
    },
    "debugging": {
        "display": "Debugging",
        "keywords": {
            "debug", "error", "stack trace", "breakpoint", "troubleshoot",
            "logging", "debugging", "exception", "bug", "crash",
            "traceback", "diagnose",
        },
    },
    "git-workflow": {
        "display": "Git Workflow",
        "keywords": {
            "git", "commit", "branch", "merge", "rebase",
            "conventional commit", "pr", "git workflow", "gitflow",
            "cherry-pick", "tag", "release",
        },
    },
    "performance": {
        "display": "Performance",
        "keywords": {
            "performance", "optimize", "cache", "profiling", "latency",
            "bundle size", "lazy load", "memoize", "benchmark",
            "throughput", "bottleneck",
        },
    },
    "accessibility": {
        "display": "Accessibility",
        "keywords": {
            "a11y", "accessibility", "wcag", "aria", "screen reader",
            "keyboard nav", "contrast", "focus indicator",
            "assistive technology",
        },
    },
    "general-coding": {
        "display": "General Coding",
        "keywords": set(),  # fallback — matches nothing specifically
    },
}

# ── LLM classification prompt ──────────────────────────────────────────────

_LLM_CLASSIFY_PROMPT = """Classify this AI skill into one of the following categories.

Categories:
- code-review: Code review, PR review, diff analysis, linting
- testing: Test writing, TDD, test frameworks, coverage
- frontend: React, Vue, Angular, CSS, UI components
- backend: API design, REST, GraphQL, server frameworks
- devops: Docker, CI/CD, deployment, infrastructure
- security: Security scanning, OWASP, auth, vulnerability detection
- documentation: Docs generation, README, API docs, changelogs
- database: SQL, migrations, schema design, ORMs
- refactoring: Code cleanup, technical debt, restructuring
- debugging: Error diagnosis, logging, troubleshooting
- git-workflow: Git operations, branching strategies, commit conventions
- performance: Optimization, caching, profiling, bundle size
- accessibility: WCAG, ARIA, screen readers, keyboard navigation
- general-coding: General-purpose coding assistance (use only if nothing else fits)

<skill>
Name: {name}
Description: {description}
Triggers: {triggers}
Instructions (first 2000 chars): {instructions}
</skill>

Respond in this exact JSON format:
{{"primary": "category-slug", "secondary": "category-slug-or-empty-string", "confidence": 0.85}}

Rules:
- primary is required, must be one of the slugs above
- secondary is optional (empty string if none), must differ from primary
- confidence is 0-1, how sure you are about the primary category"""


# ── Data class ─────────────────────────────────────────────────────────────

@dataclass
class CategoryAssignment:
    """Result of categorizing a skill."""
    primary_category: str
    secondary_category: str  # empty string if none
    confidence: float        # 0-1
    method: str              # "rule" | "llm"


# ── Rule-based categorization (Stage 1) ────────────────────────────────────

def _build_searchable_text(skill: ParsedSkill) -> str:
    """Combine all relevant skill fields into a single lowercased string."""
    parts = [
        skill.name,
        skill.description,
        skill.instructions,
        " ".join(skill.triggers),
    ]
    return " ".join(parts).lower()


def _score_categories(text: str) -> list[tuple[str, float]]:
    """Score each category by keyword match ratio. Returns sorted descending."""
    scores: list[tuple[str, float]] = []
    for slug, cat_def in CATEGORIES.items():
        keywords = cat_def["keywords"]
        if not keywords:
            continue
        matches = sum(1 for kw in keywords if kw in text)
        ratio = matches / len(keywords)
        scores.append((slug, ratio))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _categorize_rule(skill: ParsedSkill) -> CategoryAssignment | None:
    """Stage 1: Rule-based keyword matching.

    Returns a CategoryAssignment if confident enough, or None to signal
    that LLM fallback is needed.
    """
    text = _build_searchable_text(skill)
    scores = _score_categories(text)

    if not scores:
        return None

    top_slug, top_score = scores[0]
    second_slug, second_score = scores[1] if len(scores) > 1 else ("", 0.0)

    # Ambiguous: top score too low or top two too close
    if top_score <= 0.3:
        return None
    if len(scores) > 1 and (top_score - second_score) < 0.05:
        return None

    # Confident rule-based assignment
    secondary = second_slug if second_score > 0.15 else ""
    confidence = min(top_score, 1.0)

    return CategoryAssignment(
        primary_category=top_slug,
        secondary_category=secondary,
        confidence=round(confidence, 2),
        method="rule",
    )


# ── LLM-based categorization (Stage 2) ────────────────────────────────────

def _categorize_llm(skill: ParsedSkill) -> CategoryAssignment:
    """Stage 2: LLM classification via Claude Haiku.

    Falls back to 'general-coding' if LLM is unavailable or fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return CategoryAssignment(
            primary_category="general-coding",
            secondary_category="",
            confidence=0.1,
            method="rule",
        )

    try:
        import anthropic
    except ImportError:
        return CategoryAssignment(
            primary_category="general-coding",
            secondary_category="",
            confidence=0.1,
            method="rule",
        )

    prompt = _LLM_CLASSIFY_PROMPT.format(
        name=skill.name,
        description=skill.description,
        triggers=", ".join(skill.triggers) if skill.triggers else "(none)",
        instructions=skill.instructions[:2000],
    )

    valid_slugs = set(CATEGORIES.keys())

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()

        json_str = extract_json_object(raw_text)
        if not json_str:
            return CategoryAssignment(
                primary_category="general-coding",
                secondary_category="",
                confidence=0.1,
                method="llm",
            )

        data = json.loads(json_str)
        primary = data.get("primary", "general-coding")
        secondary = data.get("secondary", "")
        confidence = float(data.get("confidence", 0.5))

        # Validate slugs
        if primary not in valid_slugs:
            primary = "general-coding"
            confidence = 0.1
        if secondary and secondary not in valid_slugs:
            secondary = ""
        if secondary == primary:
            secondary = ""

        return CategoryAssignment(
            primary_category=primary,
            secondary_category=secondary,
            confidence=round(min(max(confidence, 0.0), 1.0), 2),
            method="llm",
        )
    except Exception:
        return CategoryAssignment(
            primary_category="general-coding",
            secondary_category="",
            confidence=0.1,
            method="llm",
        )


# ── Public API ─────────────────────────────────────────────────────────────

def categorize_skill(skill: ParsedSkill) -> CategoryAssignment:
    """Categorize a single skill.

    Stage 1: Count keyword matches across skill.name, skill.description,
    skill.instructions, and skill.triggers.

    Score each category by: matches / total_keywords_in_category.
    Pick top 2 categories.

    If top category score > 0.3, use it (method="rule").
    If top category score <= 0.3 or top two are within 0.05 of each other,
    fall back to LLM (method="llm").

    Stage 2 (LLM): Send skill content to Claude Haiku with a structured prompt
    asking it to classify into one of the 14 categories. Parse JSON response.
    Only called when Stage 1 is ambiguous.
    """
    result = _categorize_rule(skill)
    if result is not None:
        return result
    return _categorize_llm(skill)


def categorize_batch(skills: list[ParsedSkill]) -> list[CategoryAssignment]:
    """Categorize multiple skills. Uses rule-based for most, LLM for ambiguous."""
    return [categorize_skill(skill) for skill in skills]
