"""
Initial field and role assignment for discovered agents.

This is intentionally heuristic. It gives discovery a scoped starting point so
we can normalize and benchmark comparable candidates, while keeping the mapping
explicit and easy to replace later.
"""
from __future__ import annotations

from dataclasses import dataclass

from evaluate.rubric import ParsedSkill
from ingest.categorize import CategoryAssignment, categorize_skill


SOFTWARE_ROLE_BY_CATEGORY: dict[str, str] = {
    "code-review": "code-review-agent",
    "testing": "test-agent",
    "frontend": "frontend-agent",
    "backend": "backend-agent",
    "devops": "devops-agent",
    "security": "security-audit-agent",
    "documentation": "documentation-agent",
    "database": "database-agent",
    "refactoring": "refactoring-agent",
    "debugging": "debugging-agent",
    "git-workflow": "git-workflow-agent",
    "performance": "performance-agent",
    "accessibility": "accessibility-agent",
    "general-coding": "software-engineer-agent",
}

SEMICONDUCTOR_KEYWORDS = {
    "rtl",
    "verilog",
    "systemverilog",
    "uvm",
    "testbench",
    "waveform",
    "assertion",
    "timing",
    "cdc",
    "simulation",
    "synopsys",
    "cadence",
    "formal verification",
    "lint",
    "sva",
    "silicon",
}

SEMICONDUCTOR_DEBUG_KEYWORDS = {
    "debug",
    "failure",
    "failing",
    "mismatch",
    "root cause",
    "assertion failure",
    "waveform",
    "simulation log",
    "testbench",
}


@dataclass
class FieldRoleAssignment:
    field: str
    role: str
    confidence: float
    method: str
    source_category: str = ""


def assign_field_role(
    skill: ParsedSkill,
    category: CategoryAssignment | None = None,
) -> FieldRoleAssignment:
    """Map a discovered candidate into an initial field and role."""

    text = _build_searchable_text(skill)
    semiconductor_hits = _count_hits(text, SEMICONDUCTOR_KEYWORDS)
    if semiconductor_hits > 0:
        role = "verification-debug-agent"
        if _count_hits(text, SEMICONDUCTOR_DEBUG_KEYWORDS) == 0:
            role = "semiconductor-agent"
        return FieldRoleAssignment(
            field="semiconductor",
            role=role,
            confidence=0.75 if semiconductor_hits >= 2 else 0.6,
            method="semiconductor-rule",
        )

    if category is None:
        category = categorize_skill(skill)
    return FieldRoleAssignment(
        field="software-engineering",
        role=SOFTWARE_ROLE_BY_CATEGORY.get(
            category.primary_category,
            "software-engineer-agent",
        ),
        confidence=max(category.confidence, 0.4),
        method=f"category-map:{category.method}",
        source_category=category.primary_category,
    )


def _build_searchable_text(skill: ParsedSkill) -> str:
    return " ".join(
        [
            skill.name,
            skill.description,
            skill.instructions,
            " ".join(skill.triggers),
        ]
    ).lower()


def _count_hits(text: str, keywords: set[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)
