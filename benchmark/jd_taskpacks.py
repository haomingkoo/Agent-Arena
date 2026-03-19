"""
JD-backed task pack loader.

Loads tournament tasks generated from the JD extraction pipeline
(ingest/jd/extract.py) and converts them into BenchmarkJob objects
for use in tournaments.

These replace hand-authored task packs with market-grounded tasks
derived from real job descriptions.

Task packs are versioned:
  - v1: hand-authored (legacy, kept for comparison)
  - v2: JD-generated via LLM from real ATS postings
"""
from __future__ import annotations

import json
from pathlib import Path

from evaluate.sandbox import BenchmarkJob

_DATA_DIR = Path("data")


def load_jd_tasks(role: str) -> list[BenchmarkJob]:
    """Load JD-generated tasks from the saved JSON file.

    Args:
        role: The role slug (e.g., "code-review-agent", "software-engineer-agent")

    Returns:
        List of BenchmarkJob objects ready for tournament use.
    """
    path = _DATA_DIR / f"jd_generated_tasks_{role}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No JD-generated tasks found at {path}. "
            f"Run: python ingest/jd/extract.py <field> {role}"
        )

    with open(path) as f:
        data = json.load(f)

    tasks: list[BenchmarkJob] = []
    for t in data.get("tasks", []):
        tasks.append(BenchmarkJob(
            id=t["id"],
            name=t["name"],
            category=t.get("responsibility", "")[:50],
            skill_domain=role,
            task_bucket=t.get("task_bucket", "rotating"),
            difficulty=t.get("difficulty", "medium"),
            input_prompt=t["input_prompt"],
            input_context=t["input_context"],
            acceptance_criteria=t["acceptance_criteria"],
            risk_level="medium",
            stack=t.get("stack", "python"),
            test_set="agent-pack-v2",
        ))

    return tasks


def get_jd_task_metadata(role: str) -> dict:
    """Get metadata about the JD-generated tasks (blueprint info)."""
    path = _DATA_DIR / f"jd_generated_tasks_{role}.json"
    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    blueprint = data.get("blueprint", {})
    return {
        "corpus_version": blueprint.get("corpus_version", ""),
        "posting_count": blueprint.get("posting_count", 0),
        "company_count": blueprint.get("company_count", 0),
        "responsibilities_count": len(blueprint.get("responsibilities", [])),
        "tools": blueprint.get("tools", []),
        "task_count": len(data.get("tasks", [])),
        "seniority_levels": blueprint.get("seniority_levels", []),
    }
