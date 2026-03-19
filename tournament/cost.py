"""
Cost estimation and tracking for tournament runs.

Tracks API spend per tournament so we can set budgets and
detect runaway costs before they get expensive.
"""
from __future__ import annotations

import os

# Pricing as of March 2026 (USD per million tokens)
PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {
        "input_per_mtok": 1.00,
        "output_per_mtok": 5.00,
    },
    "gemini-2.5-flash": {
        "input_per_mtok": 0.15,
        "output_per_mtok": 0.60,
    },
}

# Average token counts per call, measured from real benchmark runs
AVG_EXEC_INPUT_TOKENS = 2500
AVG_EXEC_OUTPUT_TOKENS = 3000
AVG_JUDGE_INPUT_TOKENS = 4000
AVG_JUDGE_OUTPUT_TOKENS = 1500

EXEC_MODEL = "claude-haiku-4-5-20251001"
JUDGE_MODEL = "gemini-2.5-flash"


def _qwen_env_pricing() -> dict[str, float] | None:
    """Load optional Qwen pricing from env in USD per million tokens."""
    input_price = os.environ.get("QWEN_INPUT_PER_MTOK")
    output_price = os.environ.get("QWEN_OUTPUT_PER_MTOK")
    if input_price is None or output_price is None:
        return None
    try:
        return {
            "input_per_mtok": float(input_price),
            "output_per_mtok": float(output_price),
        }
    except ValueError:
        return None


def estimate_cost(
    num_skills: int,
    num_tasks: int = 5,
    runs_per_task: int = 1,
) -> dict:
    """Estimate tournament cost before running.

    Each skill runs every task (runs_per_task times). Each run involves:
      1. One execution call (EXEC_MODEL)
      2. One judge call (JUDGE_MODEL)

    Plus one baseline run per task (cached, but counted for first run).

    Returns:
        Dict with itemized cost breakdown and total.
    """
    total_skill_runs = num_skills * num_tasks * runs_per_task
    total_baseline_runs = num_tasks  # one per task (cached across skills)

    exec_pricing = PRICING[EXEC_MODEL]
    judge_pricing = PRICING[JUDGE_MODEL]

    # Execution cost (skill runs + baselines)
    total_exec_calls = total_skill_runs + total_baseline_runs
    exec_input_cost = (
        total_exec_calls * AVG_EXEC_INPUT_TOKENS
        * exec_pricing["input_per_mtok"] / 1_000_000
    )
    exec_output_cost = (
        total_exec_calls * AVG_EXEC_OUTPUT_TOKENS
        * exec_pricing["output_per_mtok"] / 1_000_000
    )

    # Judge cost (same number of calls — one judge per execution)
    judge_input_cost = (
        total_exec_calls * AVG_JUDGE_INPUT_TOKENS
        * judge_pricing["input_per_mtok"] / 1_000_000
    )
    judge_output_cost = (
        total_exec_calls * AVG_JUDGE_OUTPUT_TOKENS
        * judge_pricing["output_per_mtok"] / 1_000_000
    )

    total = exec_input_cost + exec_output_cost + judge_input_cost + judge_output_cost

    return {
        "num_skills": num_skills,
        "num_tasks": num_tasks,
        "runs_per_task": runs_per_task,
        "total_api_calls": total_exec_calls * 2,  # exec + judge
        "exec_model": EXEC_MODEL,
        "judge_model": JUDGE_MODEL,
        "exec_cost_usd": round(exec_input_cost + exec_output_cost, 4),
        "judge_cost_usd": round(judge_input_cost + judge_output_cost, 4),
        "total_cost_usd": round(total, 4),
    }


def compute_actual_cost(
    input_tokens: int,
    output_tokens: int,
    model: str,
) -> float:
    """Compute actual cost from token counts for a single API call.

    Args:
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.
        model: Model identifier (must exist in PRICING).

    Returns:
        Cost in USD. Returns 0.0 if model is unknown.
    """
    pricing = PRICING.get(model)
    if pricing is None and model.startswith("qwen"):
        pricing = _qwen_env_pricing()
    if not pricing:
        return 0.0
    input_cost = input_tokens * pricing["input_per_mtok"] / 1_000_000
    output_cost = output_tokens * pricing["output_per_mtok"] / 1_000_000
    return round(input_cost + output_cost, 6)
