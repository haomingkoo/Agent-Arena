"""
JD → Role Blueprint → Tournament Task pipeline.

Reads real JD postings from the database, uses an LLM to extract structured
responsibilities/tools/seniority signals, builds a role blueprint, then
generates tournament-ready work-sample tasks with realistic code scenarios
at different difficulty levels mapped to seniority.

This is the correct order:
  1. Ingest JDs from ATS sources
  2. Extract responsibilities from JD content (LLM-assisted)
  3. Build a role blueprint
  4. Generate tournament tasks from the blueprint (LLM-generated code scenarios)
  5. THEN run tournaments with market-grounded tasks

Difficulty mapping by seniority:
  - easy       → junior-level (0-2 yrs): straightforward, single-concept tasks
  - medium     → mid-level (3-5 yrs): multi-step, requires tradeoff reasoning
  - hard       → senior-level (6-8 yrs): system-level, requires architecture judgment
  - adversarial → staff+ (9+ yrs): ambiguous requirements, conflicting constraints
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from store.db import (
    get_jd_corpus_stats,
    get_latest_corpus_version,
    list_jd_postings,
)


@dataclass
class RoleBlueprint:
    """Structured summary of a role extracted from JD corpus."""

    field: str
    role: str
    corpus_version: str
    posting_count: int
    company_count: int

    common_responsibilities: list[str] = field(default_factory=list)
    common_tools: list[str] = field(default_factory=list)
    common_deliverables: list[str] = field(default_factory=list)
    common_failure_modes: list[str] = field(default_factory=list)
    qualification_signals: list[str] = field(default_factory=list)
    seniority_levels: list[dict] = field(default_factory=list)


@dataclass
class GeneratedTask:
    """A tournament task generated from a role blueprint."""

    id: str
    name: str
    responsibility: str
    difficulty: str            # easy | medium | hard | adversarial
    seniority_target: str      # junior | mid | senior | staff
    task_bucket: str           # anchor | rotating | holdout
    input_prompt: str
    input_context: str
    acceptance_criteria: list[str]
    source_jd_companies: list[str]
    stack: str = ""


# ── LLM-Assisted Extraction ────────────────────────────────────────


_BLUEPRINT_EXTRACTION_PROMPT = """\
You are analyzing real job descriptions for the role: {role_display}.
Field: {field}

Below are {count} job postings from {companies} different companies.
Extract a structured role blueprint.

JD CONTENT:
{jd_content}

Return a JSON object with exactly these keys:
{{
  "responsibilities": [
    // Top 15 core responsibilities that appear across multiple JDs.
    // Each must be an action-oriented verb phrase (e.g., "Review pull requests for security vulnerabilities")
    // Exclude qualification requirements ("5+ years experience") and company perks
  ],
  "tools": [
    // Programming languages, frameworks, platforms, and tools mentioned across JDs
  ],
  "deliverables": [
    // Concrete outputs this role produces (e.g., "security audit reports", "code review feedback", "incident postmortems")
  ],
  "failure_modes": [
    // Common ways this role can fail (e.g., "missing critical vulnerabilities in review", "false positives causing alert fatigue")
  ],
  "seniority_levels": [
    {{
      "level": "junior",
      "years": "0-2",
      "typical_tasks": ["simple, single-focus tasks from the responsibilities list"],
      "complexity": "Single concept, clear requirements, one right answer"
    }},
    {{
      "level": "mid",
      "years": "3-5",
      "typical_tasks": ["moderate multi-step tasks requiring judgment"],
      "complexity": "Multiple concerns, requires tradeoff reasoning"
    }},
    {{
      "level": "senior",
      "years": "6-8",
      "typical_tasks": ["system-level tasks requiring architecture judgment"],
      "complexity": "Cross-system impact, mentoring component, ambiguity"
    }},
    {{
      "level": "staff",
      "years": "9+",
      "typical_tasks": ["org-level impact, conflicting constraints"],
      "complexity": "Ambiguous requirements, political tradeoffs, long-term strategy"
    }}
  ]
}}

Only return valid JSON. No markdown fences. No commentary."""


_TASK_GENERATION_PROMPT = """\
You are generating a realistic work-sample benchmark task for evaluating AI agents
in the role: {role_display}.

This task must test the following responsibility from real job descriptions:
  "{responsibility}"

Difficulty: {difficulty} (targeting {seniority_target}-level, {years} years experience)
Complexity guidance: {complexity}
Common tools for this role: {tools}

Generate a JSON object with exactly these keys:
{{
  "name": "Short descriptive name (under 60 chars)",
  "input_prompt": "Clear task instruction telling the agent what to do. Be specific about what output is expected.",
  "input_context": "Realistic code snippet, log excerpt, config file, or scenario that the agent must work with. This should be 20-60 lines of actual code or data — not a description. Make it realistic and contain the specific issue the agent needs to address.",
  "acceptance_criteria": [
    // 5-7 specific, measurable criteria for judging the response.
    // Each criterion should be independently verifiable.
    // At least 2 criteria should test for common mistakes at this seniority level.
  ],
  "stack": "e.g. python/fastapi, javascript/react, go/kubernetes"
}}

Rules:
- The input_context MUST contain actual code, logs, configs, or data — not just a description
- The task must require DOING the work, not just describing what should be done
- {difficulty_rules}
- Do not include the answer in the context
- Make the scenario realistic enough that an expert would recognize it as a real work situation

Only return valid JSON. No markdown fences."""


_DIFFICULTY_RULES = {
    "easy": "Single clear issue. One right approach. Junior engineer should handle this with basic knowledge.",
    "medium": "Multiple concerns interacting. Requires understanding tradeoffs. Mid-level engineer needs to weigh options.",
    "hard": "System-level impact. Cross-cutting concerns. Requires architecture judgment and experience with failure modes.",
    "adversarial": "Ambiguous requirements. Conflicting constraints. Red herrings present. Requires staff-level judgment to identify what actually matters.",
}

_SENIORITY_MAP = {
    "easy": ("junior", "0-2"),
    "medium": ("mid", "3-5"),
    "hard": ("senior", "6-8"),
    "adversarial": ("staff", "9+"),
}


def _call_gemini(prompt: str) -> str:
    """Call Gemini for structured extraction/generation."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY required for JD extraction")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=16384,
            response_mime_type="application/json",
        ),
    )
    return response.text.strip()


# ── Blueprint Extraction ────────────────────────────────────────────


def extract_role_blueprint(
    field: str,
    role: str,
    use_llm: bool = True,
) -> RoleBlueprint:
    """Extract a role blueprint from JD postings using LLM analysis."""
    postings = list_jd_postings(field=field, role=role, limit=200)
    stats = get_jd_corpus_stats(field, role)
    latest = get_latest_corpus_version(field, role)

    if not postings:
        return RoleBlueprint(
            field=field, role=role, corpus_version="",
            posting_count=0, company_count=0,
        )

    # Build JD content block (truncate to fit in context)
    jd_blocks: list[str] = []
    total_chars = 0
    companies: set[str] = set()
    for p in postings:
        content = p.get("content", "")
        company = p.get("company_name", "unknown")
        title = p.get("title", "")
        companies.add(company)

        block = f"--- {company}: {title} ---\n{content[:3000]}"
        if total_chars + len(block) > 40000:
            break
        jd_blocks.append(block)
        total_chars += len(block)

    jd_content = "\n\n".join(jd_blocks)
    role_display = role.replace("-", " ").replace("agent", "").strip()

    if not use_llm:
        return _extract_blueprint_regex(field, role, postings, stats, latest)

    prompt = _BLUEPRINT_EXTRACTION_PROMPT.format(
        role_display=role_display,
        field=field,
        count=len(postings),
        companies=len(companies),
        jd_content=jd_content,
    )

    raw = _call_gemini(prompt)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        from evaluate.rubric import extract_json_object, repair_truncated_json
        json_str = extract_json_object(raw) or repair_truncated_json(raw)
        if not json_str:
            print("  WARNING: LLM returned unparseable blueprint, falling back to regex")
            return _extract_blueprint_regex(field, role, postings, stats, latest)
        data = json.loads(json_str)

    return RoleBlueprint(
        field=field,
        role=role,
        corpus_version=latest["version_label"] if latest else "",
        posting_count=stats["total"],
        company_count=stats["companies"],
        common_responsibilities=data.get("responsibilities", [])[:20],
        common_tools=data.get("tools", [])[:20],
        common_deliverables=data.get("deliverables", [])[:10],
        common_failure_modes=data.get("failure_modes", [])[:10],
        seniority_levels=data.get("seniority_levels", []),
    )


def _extract_blueprint_regex(
    field: str, role: str, postings: list[dict],
    stats: dict, latest: dict | None,
) -> RoleBlueprint:
    """Regex-only fallback for blueprint extraction (no LLM)."""
    action_words = {
        "design", "build", "develop", "implement", "create", "review",
        "analyze", "debug", "test", "maintain", "collaborate", "lead",
        "architect", "identify", "investigate", "monitor", "improve",
        "automate", "deploy", "manage", "evaluate", "assess", "ensure",
        "write", "research", "perform", "conduct", "define", "establish",
        "respond", "triage", "remediate", "secure", "audit", "inspect",
    }
    known_tools = [
        "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++",
        "Kubernetes", "Docker", "AWS", "GCP", "Azure", "Terraform",
        "PostgreSQL", "Redis", "Kafka", "GraphQL", "REST", "CI/CD",
        "SAST", "DAST", "Semgrep", "SonarQube", "OWASP",
    ]

    all_resp: dict[str, list[str]] = {}
    all_tools: dict[str, int] = {}

    for p in postings:
        content = p.get("content", "")
        company = p.get("company_name", "unknown")

        bullets = re.findall(r"[-•*]\s+(.{15,})", content)
        for b in bullets:
            b = b.strip()
            if any(b.lower().startswith(w) for w in action_words):
                key = b.lower().rstrip(".,;:")
                if key not in all_resp:
                    all_resp[key] = []
                if company not in all_resp[key]:
                    all_resp[key].append(company)

        for t in known_tools:
            if t.lower() in content.lower():
                all_tools[t] = all_tools.get(t, 0) + 1

    sorted_resp = sorted(all_resp.items(), key=lambda x: len(x[1]), reverse=True)
    sorted_tools = sorted(all_tools.items(), key=lambda x: x[1], reverse=True)

    return RoleBlueprint(
        field=field, role=role,
        corpus_version=latest["version_label"] if latest else "",
        posting_count=stats["total"],
        company_count=stats["companies"],
        common_responsibilities=[r for r, _ in sorted_resp[:20]],
        common_tools=[t for t, _ in sorted_tools[:15]],
    )


# ── LLM Task Generation ────────────────────────────────────────────


def generate_task_with_llm(
    responsibility: str,
    role: str,
    difficulty: str,
    tools: list[str],
    task_id: str,
    task_bucket: str,
) -> GeneratedTask:
    """Use LLM to generate a realistic work-sample task with code context."""
    seniority_target, years = _SENIORITY_MAP.get(difficulty, ("mid", "3-5"))
    role_display = role.replace("-", " ").replace("agent", "").strip()
    difficulty_rules = _DIFFICULTY_RULES.get(difficulty, "")

    prompt = _TASK_GENERATION_PROMPT.format(
        role_display=role_display,
        responsibility=responsibility,
        difficulty=difficulty,
        seniority_target=seniority_target,
        years=years,
        complexity=_SENIORITY_MAP.get(difficulty, ("mid", ""))[0],
        tools=", ".join(tools[:8]),
        difficulty_rules=difficulty_rules,
    )

    raw = _call_gemini(prompt)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        from evaluate.rubric import extract_json_object, repair_truncated_json
        json_str = extract_json_object(raw) or repair_truncated_json(raw)
        if not json_str:
            raise ValueError(f"LLM returned unparseable task for: {responsibility[:50]}")
        data = json.loads(json_str)

    return GeneratedTask(
        id=task_id,
        name=data.get("name", responsibility[:60]),
        responsibility=responsibility,
        difficulty=difficulty,
        seniority_target=seniority_target,
        task_bucket=task_bucket,
        input_prompt=data.get("input_prompt", ""),
        input_context=data.get("input_context", ""),
        acceptance_criteria=data.get("acceptance_criteria", []),
        source_jd_companies=[],
        stack=data.get("stack", ""),
    )


def generate_tasks_from_blueprint(
    blueprint: RoleBlueprint,
    max_tasks: int = 10,
    use_llm: bool = True,
) -> list[GeneratedTask]:
    """Generate tournament tasks from a role blueprint.

    Distributes tasks across difficulty levels mapped to seniority:
      - 2 easy (junior): anchor tasks for baseline comparison
      - 3 medium (mid): core rotating tasks
      - 2 hard (senior): rotating tasks requiring experience
      - 1 adversarial (staff): holdout for anti-gaming
      - 2 medium holdouts: internal validation
    """
    if not blueprint.common_responsibilities:
        return []

    # Task distribution: bucket + difficulty
    task_slots = [
        ("anchor",   "easy"),
        ("anchor",   "medium"),
        ("rotating", "medium"),
        ("rotating", "medium"),
        ("rotating", "hard"),
        ("rotating", "hard"),
        ("rotating", "easy"),
        ("holdout",  "medium"),
        ("holdout",  "adversarial"),
        ("holdout",  "medium"),
    ]

    responsibilities = blueprint.common_responsibilities[:max_tasks]
    role_slug = blueprint.role.replace("-", "_")
    tasks: list[GeneratedTask] = []

    for i, resp in enumerate(responsibilities):
        if i >= len(task_slots):
            break

        bucket, difficulty = task_slots[i]
        task_id = f"jd-{role_slug}-{i+1:02d}"

        if use_llm:
            try:
                task = generate_task_with_llm(
                    responsibility=resp,
                    role=blueprint.role,
                    difficulty=difficulty,
                    tools=blueprint.common_tools,
                    task_id=task_id,
                    task_bucket=bucket,
                )
                tasks.append(task)
                print(f"    [{bucket}/{difficulty}] {task.name[:65]}")
            except Exception as e:
                print(f"    ERROR generating task for '{resp[:40]}': {e}")
        else:
            seniority, years = _SENIORITY_MAP.get(difficulty, ("mid", "3-5"))
            tasks.append(GeneratedTask(
                id=task_id,
                name=f"Work sample: {resp[:60]}",
                responsibility=resp,
                difficulty=difficulty,
                seniority_target=seniority,
                task_bucket=bucket,
                input_prompt=f"Perform this task: {resp}",
                input_context="",
                acceptance_criteria=[f"Demonstrates: {resp}"],
                source_jd_companies=[],
            ))

    return tasks


# ── Full Pipeline ───────────────────────────────────────────────────


def run_jd_to_tasks_pipeline(
    field: str,
    role: str,
    use_llm: bool = True,
    max_tasks: int = 10,
) -> dict:
    """Full pipeline: JD corpus → role blueprint → tournament tasks.

    Returns a summary dict with the blueprint and generated tasks.
    """
    print(f"\n{'='*60}")
    print(f"  JD → Tasks Pipeline: {field}/{role}")
    print(f"{'='*60}")

    print(f"\nStep 1: Extracting role blueprint from JD corpus...")
    blueprint = extract_role_blueprint(field, role, use_llm=use_llm)

    print(f"  Corpus: {blueprint.posting_count} postings, {blueprint.company_count} companies")
    print(f"  Responsibilities: {len(blueprint.common_responsibilities)}")
    print(f"  Tools: {len(blueprint.common_tools)}")
    print(f"  Deliverables: {len(blueprint.common_deliverables)}")
    print(f"  Failure modes: {len(blueprint.common_failure_modes)}")

    if not blueprint.common_responsibilities:
        print("  ERROR: No responsibilities extracted. Cannot generate tasks.")
        return {"blueprint": blueprint, "tasks": [], "error": "No responsibilities"}

    print(f"\n  Top responsibilities:")
    for i, r in enumerate(blueprint.common_responsibilities[:8], 1):
        print(f"    {i}. {r[:80]}")

    print(f"\n  Tools: {', '.join(blueprint.common_tools[:10])}")

    if blueprint.common_failure_modes:
        print(f"\n  Failure modes:")
        for fm in blueprint.common_failure_modes[:5]:
            print(f"    - {fm[:80]}")

    if blueprint.seniority_levels:
        print(f"\n  Seniority levels:")
        for sl in blueprint.seniority_levels:
            print(f"    {sl.get('level', '?')} ({sl.get('years', '?')} yrs): {sl.get('complexity', '')[:60]}")

    print(f"\nStep 2: Generating {min(max_tasks, len(blueprint.common_responsibilities))} tournament tasks...")
    tasks = generate_tasks_from_blueprint(
        blueprint, max_tasks=max_tasks, use_llm=use_llm,
    )

    print(f"\n  Generated {len(tasks)} tasks")
    for t in tasks:
        ctx_len = len(t.input_context)
        print(f"    {t.id}: [{t.task_bucket}/{t.difficulty}/{t.seniority_target}] "
              f"{t.name[:50]} ({ctx_len} chars context)")

    return {"blueprint": blueprint, "tasks": tasks}


if __name__ == "__main__":
    import sys

    field = sys.argv[1] if len(sys.argv) > 1 else "software-engineering"
    role = sys.argv[2] if len(sys.argv) > 2 else "code-review-agent"
    no_llm = "--no-llm" in sys.argv

    result = run_jd_to_tasks_pipeline(field, role, use_llm=not no_llm)

    # Save blueprint and tasks as JSON for inspection
    if result["tasks"]:
        output_path = f"data/jd_generated_tasks_{role}.json"
        output = {
            "blueprint": {
                "field": result["blueprint"].field,
                "role": result["blueprint"].role,
                "corpus_version": result["blueprint"].corpus_version,
                "posting_count": result["blueprint"].posting_count,
                "company_count": result["blueprint"].company_count,
                "responsibilities": result["blueprint"].common_responsibilities,
                "tools": result["blueprint"].common_tools,
                "deliverables": result["blueprint"].common_deliverables,
                "failure_modes": result["blueprint"].common_failure_modes,
                "seniority_levels": result["blueprint"].seniority_levels,
            },
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "responsibility": t.responsibility,
                    "difficulty": t.difficulty,
                    "seniority_target": t.seniority_target,
                    "task_bucket": t.task_bucket,
                    "input_prompt": t.input_prompt,
                    "input_context": t.input_context,
                    "acceptance_criteria": t.acceptance_criteria,
                    "stack": t.stack,
                }
                for t in result["tasks"]
            ],
        }
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n  Saved to {output_path}")
