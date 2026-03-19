"""
Execute a single agent version against a task using its runner contract.

This module bridges the agent-native contract model with the existing
benchmark infrastructure in evaluate/sandbox.py.
"""
from __future__ import annotations

import os

from agents.contracts import RunnerContract
from evaluate.rubric import ParsedSkill
from evaluate.sandbox import BenchmarkJob, WorkSampleResult, judge_output, run_skill


def contract_to_parsed_skill(contract: RunnerContract) -> ParsedSkill:
    """Convert a RunnerContract into a ParsedSkill for the existing benchmark runner.

    This is the adapter that lets us reuse evaluate/sandbox.py without rewriting it.
    The key mapping: contract.system_instructions -> skill.raw_content

    Uses the SANITIZED system_instructions, never raw artifact content.
    The EXEC_MODEL_PROVIDER env var overrides the contract's model_provider
    so tournaments can run on alternative providers (e.g. Qwen) without
    re-normalizing every agent.
    """
    provider = os.environ.get("EXEC_MODEL_PROVIDER") or contract.model_provider
    # When provider is overridden, don't keep the old provider's model name
    if os.environ.get("EXEC_MODEL_PROVIDER") and not os.environ.get("EXEC_MODEL_NAME"):
        model_name = ""  # let sandbox.py resolve the default for this provider
    else:
        model_name = os.environ.get("EXEC_MODEL_NAME") or contract.model_name

    skill = ParsedSkill(
        name=contract.profile_name,
        description=f"{contract.field}/{contract.role}",
        instructions=contract.system_instructions,
        raw_content=contract.system_instructions,
        triggers=[],
        allowed_tools=contract.allowed_tools,
        source_repo=contract.source_url,
        source_url=contract.source_url,
    )
    skill.exec_model_provider = provider
    skill.exec_model_name = model_name
    return skill


def execute_agent_on_task(
    contract: RunnerContract,
    job: BenchmarkJob,
) -> WorkSampleResult:
    """Run one agent (via contract) against one task. Returns judged result.

    If execution succeeds, the output is judged. If the judge fails,
    the error is recorded explicitly -- no silent fallback.
    """
    skill = contract_to_parsed_skill(contract)
    result = run_skill(skill, job)
    if not result.error:
        result = judge_output(job, result)
    return result
