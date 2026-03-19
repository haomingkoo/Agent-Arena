"""
Stage 3 — Work-sample evaluation.

Runs a skill against real benchmark tasks and scores the output.
This is the part nobody else does: evaluating skills on actual work,
not just reading their prompt text.

Pipeline: load job → compose prompt → run skill → judge output → score
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from evaluate.rubric import ParsedSkill, extract_json_object, repair_truncated_json

load_dotenv()

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class BenchmarkJob:
    """A real task to test a skill against."""
    id: str
    name: str
    category: str               # feature / bugfix / testing / review / refactor / behavioral
    input_prompt: str           # what the user would ask
    input_context: str          # code, diff, or spec the skill works with
    acceptance_criteria: list[str]  # concrete pass/fail checks
    skill_domain: str = ""     # tournament category: code-review, testing, frontend, etc.
    task_bucket: str = "rotating"  # anchor | rotating | holdout
    difficulty: str = "medium"     # easy | medium | hard | adversarial
    risk_level: str = "low"     # low / medium / high
    stack: str = "python"
    good_looks_like: str = ""   # kept for documentation only — NOT sent to judge
    test_set: str = "tune"      # "tune" or "holdout" — holdout never used for tuning


@dataclass
class WorkSampleResult:
    """Result of running one skill against one job."""
    job_id: str
    skill_name: str
    # Execution
    raw_output: str = ""
    runtime_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    exec_input_tokens: int = 0
    exec_output_tokens: int = 0
    # Judgment
    passed: bool = False
    correctness: float = 0.0    # 0-1: does the output work?
    safety: float = 0.0         # 0-1: no vulnerabilities introduced?
    completeness: float = 0.0   # 0-1: all criteria met?
    quality: float = 0.0        # 0-1: how good is it beyond pass/fail?
    overall: float = 0.0        # weighted composite
    verdict: str = ""           # one-line summary
    criteria_results: list[dict] = field(default_factory=list)  # per-criterion pass/fail
    judge_reasoning: str = ""
    error: str = ""             # if execution failed
    judge_input_tokens: int = 0
    judge_output_tokens: int = 0
    judge_provider: str = ""
    exec_provider: str = ""
    exec_model: str = ""
    judge_model: str = ""
    # Full transcript for review
    exec_prompt: str = ""       # prompt sent to execution model
    judge_prompt: str = ""      # prompt sent to judge model
    judge_raw_response: str = ""  # raw judge response before parsing

    def sync_token_totals(self) -> None:
        """Keep top-level token counters aligned with execution + judging."""
        self.input_tokens = self.exec_input_tokens + self.judge_input_tokens
        self.output_tokens = self.exec_output_tokens + self.judge_output_tokens

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "skill_name": self.skill_name,
            "passed": self.passed,
            "overall": self.overall,
            "correctness": self.correctness,
            "safety": self.safety,
            "completeness": self.completeness,
            "quality": self.quality,
            "verdict": self.verdict,
            "runtime_ms": self.runtime_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "exec_input_tokens": self.exec_input_tokens,
            "exec_output_tokens": self.exec_output_tokens,
            "judge_input_tokens": self.judge_input_tokens,
            "judge_output_tokens": self.judge_output_tokens,
            "judge_provider": self.judge_provider,
            "exec_provider": self.exec_provider,
            "exec_model": self.exec_model,
            "judge_model": self.judge_model,
            "criteria_results": self.criteria_results,
            "judge_reasoning": self.judge_reasoning,
            "error": self.error,
        }

    def to_transcript(self) -> dict:
        """Full transcript including prompts and raw responses for review."""
        d = self.to_dict()
        d["exec_prompt"] = self.exec_prompt
        d["raw_output"] = self.raw_output
        d["judge_prompt"] = self.judge_prompt
        d["judge_raw_response"] = self.judge_raw_response
        return d


@dataclass
class PairedResult:
    """Result of running a skill AND baseline on the same job."""
    job_id: str
    skill_name: str
    skill_result: WorkSampleResult
    baseline_result: WorkSampleResult
    upgrade: float = 0.0  # skill_overall - baseline_overall

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "skill_name": self.skill_name,
            "upgrade": self.upgrade,
            "skill": self.skill_result.to_dict(),
            "baseline": self.baseline_result.to_dict(),
        }


@dataclass
class JudgeCallResult:
    """Raw judge response plus token accounting metadata."""
    text: str
    provider: str
    model_name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ── Baseline execution prompt (no skill loaded) ─────────────────────────────

_BASELINE_EXECUTION_PROMPT = """You are an AI coding assistant. Complete this task.

<task>
{task_prompt}
</task>

<context>
{task_context}
</context>

Complete the task. Produce working code and clear explanations.
If the task is ambiguous, unclear, or missing information, state what questions you would ask before proceeding. Do not assume what isn't specified."""

BASELINE_CACHE_PATH = Path("data/baseline_cache.json")
BASELINE_CACHE_MAX_AGE_DAYS = 7


# ── Prompts ──────────────────────────────────────────────────────────────────

_SKILL_EXECUTION_PROMPT = """You are an AI coding assistant with the following skill loaded:

<skill>
{skill_content}
</skill>

Follow the skill's instructions to complete this task.

<task>
{task_prompt}
</task>

<context>
{task_context}
</context>

Complete the task following the skill's methodology. Produce the output the skill specifies.
If the task is ambiguous, unclear, or missing information, state what questions you would ask before proceeding. Do not assume what isn't specified."""


_JUDGE_PROMPT = """You are a strict code evaluator. A coding skill was given a task and produced output. Judge the output against the acceptance criteria.

<task>
{task_prompt}
</task>

<context>
{task_context}
</context>

<skill_output>
{skill_output}
</skill_output>

<acceptance_criteria>
{criteria}
</acceptance_criteria>

For each acceptance criterion, determine if it was MET or NOT MET. Then score these dimensions (0-10):

1. **Correctness**: Would the code/output actually work? Are there logic errors, syntax errors, or incorrect assumptions?
2. **Safety**: Does the output avoid introducing vulnerabilities (SQL injection, XSS, command injection, hardcoded secrets, etc.)?
3. **Completeness**: Are all acceptance criteria addressed? Are edge cases handled?
4. **Quality**: Beyond correctness — is the code clean, well-structured, following conventions? Are explanations clear?

Respond in this exact JSON format:
{{
  "criteria_results": [
    {{"criterion": "...", "met": true, "reason": "..."}},
    {{"criterion": "...", "met": false, "reason": "..."}}
  ],
  "correctness": {{"score": 0, "reason": "..."}},
  "safety": {{"score": 0, "reason": "..."}},
  "completeness": {{"score": 0, "reason": "..."}},
  "quality": {{"score": 0, "reason": "..."}},
  "passed": false,
  "verdict": "one sentence summary"
}}"""


# ── Core functions ────────────────────────────────────────────────────────────

def _get_client():
    """Get Anthropic client. Fails explicitly if no key."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY required for work-sample evaluation")
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def _get_gemini_client():
    """Get Gemini client for cross-model judging."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "GEMINI_API_KEY is set but google-genai is not installed"
        ) from exc
    return genai.Client(api_key=api_key)


QWEN_BASE_URL = os.environ.get(
    "QWEN_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
).rstrip("/")
DEFAULT_EXEC_MODEL_PROVIDER = os.environ.get("EXEC_MODEL_PROVIDER", "anthropic")
DEFAULT_EXEC_MODEL_NAME = os.environ.get("EXEC_MODEL_NAME", "")
DEFAULT_ANTHROPIC_EXEC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_QWEN_EXEC_MODEL = os.environ.get("QWEN_EXEC_MODEL", "qwen-plus-latest")
DEFAULT_QWEN_JUDGE_MODEL = os.environ.get(
    "QWEN_JUDGE_MODEL",
    DEFAULT_QWEN_EXEC_MODEL,
)
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gemini")  # "gemini" | "anthropic" | "qwen"


def _usage_value(usage: object, *names: str) -> int:
    """Read a token count from a dict-like or attribute-style usage object."""
    for name in names:
        value = None
        if isinstance(usage, dict):
            value = usage.get(name)
        else:
            value = getattr(usage, name, None)
        if isinstance(value, int):
            return value
    return 0


def _extract_gemini_usage(response: object) -> tuple[int, int]:
    """Best-effort extraction of Gemini token counts across SDK shapes."""
    usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
    if usage is None:
        return 0, 0

    input_tokens = _usage_value(
        usage,
        "prompt_token_count",
        "input_tokens",
        "prompt_tokens",
    )
    output_tokens = _usage_value(
        usage,
        "candidates_token_count",
        "output_tokens",
        "completion_tokens",
    )
    return input_tokens, output_tokens


def _extract_openai_compatible_usage(payload: dict) -> tuple[int, int]:
    """Read prompt/completion tokens from an OpenAI-compatible payload."""
    usage = payload.get("usage", {})
    if not isinstance(usage, dict):
        return 0, 0
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    return (
        input_tokens if isinstance(input_tokens, int) else 0,
        output_tokens if isinstance(output_tokens, int) else 0,
    )


def _get_qwen_api_key() -> str:
    """Return the Qwen API key or fail closed."""
    api_key = os.environ.get("QWEN_API_KEY")
    if not api_key:
        raise RuntimeError("QWEN_API_KEY required for Qwen evaluation")
    return api_key


def _extract_openai_compatible_text(payload: dict) -> str:
    """Extract text from an OpenAI-compatible chat completion payload."""
    choices = payload.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Qwen response did not include any choices")
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        raise RuntimeError("Qwen response had an invalid message payload")
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                if isinstance(text, str):
                    text_parts.append(text)
        return "\n".join(part for part in text_parts if part).strip()
    raise RuntimeError("Qwen response had an unsupported content payload")


def _call_qwen_chat(prompt: str, *, model: str, max_tokens: int) -> JudgeCallResult:
    """Call a Qwen model through DashScope's OpenAI-compatible endpoint."""
    api_key = _get_qwen_api_key()
    try:
        response = httpx.post(
            f"{QWEN_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Qwen API error ({model}): HTTP {e.response.status_code} — {e.response.text[:200]}"
        ) from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Qwen API connection failed ({model}): {e}") from e

    payload = response.json()
    text = _extract_openai_compatible_text(payload)
    if not text.strip():
        raise RuntimeError(f"Qwen API returned empty response ({model})")

    input_tokens, output_tokens = _extract_openai_compatible_usage(payload)
    return JudgeCallResult(
        text=text,
        provider="qwen",
        model_name=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _resolve_exec_model_name(provider: str, explicit_model_name: str = "") -> str:
    """Resolve the default execution model name for the chosen provider."""
    if explicit_model_name:
        return explicit_model_name
    if provider == "qwen":
        return DEFAULT_QWEN_EXEC_MODEL
    return DEFAULT_ANTHROPIC_EXEC_MODEL


def run_skill(skill: ParsedSkill, job: BenchmarkJob) -> WorkSampleResult:
    """Run a skill against a benchmark job. Returns raw output + metrics."""
    result = WorkSampleResult(job_id=job.id, skill_name=skill.name)

    prompt = _SKILL_EXECUTION_PROMPT.format(
        skill_content=skill.raw_content[:8000],
        task_prompt=job.input_prompt,
        task_context=job.input_context[:6000],
    )
    result.exec_prompt = prompt

    try:
        provider = getattr(skill, "exec_model_provider", DEFAULT_EXEC_MODEL_PROVIDER)
        model_name = _resolve_exec_model_name(
            provider,
            getattr(skill, "exec_model_name", DEFAULT_EXEC_MODEL_NAME),
        )
        result.exec_provider = provider

        if provider == "anthropic":
            client = _get_client()
            start = time.monotonic()
            response = client.messages.create(
                model=model_name,
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            result.runtime_ms = int((time.monotonic() - start) * 1000)
            result.raw_output = response.content[0].text
            result.exec_input_tokens = response.usage.input_tokens
            result.exec_output_tokens = response.usage.output_tokens
            result.exec_model = model_name
            result.sync_token_totals()
            return result

        if provider == "qwen":
            start = time.monotonic()
            response = _call_qwen_chat(
                prompt,
                model=model_name or DEFAULT_QWEN_EXEC_MODEL,
                max_tokens=8000,
            )
            result.runtime_ms = int((time.monotonic() - start) * 1000)
            result.raw_output = response.text
            result.exec_input_tokens = response.input_tokens
            result.exec_output_tokens = response.output_tokens
            result.exec_model = response.model_name
            result.sync_token_totals()
            return result

        raise RuntimeError(
            f"Unsupported execution provider={provider!r}; expected 'anthropic' or 'qwen'"
        )
    except Exception as e:
        error_str = str(e)
        result.error = error_str

        # Detect billing/auth failures and raise loud — don't silently continue
        fatal_patterns = [
            "credit", "billing", "payment", "insufficient", "quota",
            "402", "authentication", "unauthorized", "401", "403",
            "rate_limit", "rate limit", "overloaded",
        ]
        error_lower = error_str.lower()
        if any(p in error_lower for p in fatal_patterns):
            print(f"\n  *** FATAL: {error_str}")
            print(f"  *** Halting — fix your API key/billing before continuing.\n")
            raise RuntimeError(f"API billing/auth failure: {error_str}") from e

    return result


def _call_judge(prompt: str) -> JudgeCallResult:
    """Call the configured judge model and return raw text plus token usage."""
    if JUDGE_MODEL == "gemini":
        gemini = _get_gemini_client()
        if gemini is None:
            raise RuntimeError(
                "JUDGE_MODEL=gemini requires GEMINI_API_KEY; refusing to fall back to Claude"
            )
        from google.genai import types

        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=16384,
                response_mime_type="application/json",
            ),
        )
        input_tokens, output_tokens = _extract_gemini_usage(response)
        return JudgeCallResult(
            text=response.text.strip(),
            provider="gemini",
            model_name="gemini-2.5-flash",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    if JUDGE_MODEL == "anthropic":
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return JudgeCallResult(
            text=response.content[0].text.strip(),
            provider="anthropic",
            model_name="claude-haiku-4-5-20251001",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    if JUDGE_MODEL == "qwen":
        return _call_qwen_chat(
            prompt,
            model=DEFAULT_QWEN_JUDGE_MODEL,
            max_tokens=4096,
        )

    raise RuntimeError(
        f"Unsupported JUDGE_MODEL={JUDGE_MODEL!r}; expected 'gemini', 'anthropic', or 'qwen'"
    )


def judge_output(job: BenchmarkJob, result: WorkSampleResult) -> WorkSampleResult:
    """Judge a skill's output against acceptance criteria.

    Uses the explicitly configured judge provider and fails closed if the
    required provider key or SDK is unavailable.
    """
    if result.error:
        result.verdict = f"Execution failed: {result.error}"
        return result

    criteria_text = "\n".join(f"- {c}" for c in job.acceptance_criteria)

    prompt = _JUDGE_PROMPT.format(
        task_prompt=job.input_prompt,
        task_context=job.input_context[:4000],
        skill_output=result.raw_output[:6000],
        criteria=criteria_text,
    )
    result.judge_prompt = prompt

    try:
        judge = _call_judge(prompt)
        result.judge_provider = judge.provider
        result.judge_model = judge.model_name
        result.judge_input_tokens = judge.input_tokens
        result.judge_output_tokens = judge.output_tokens
        result.sync_token_totals()
        result.judge_raw_response = judge.text

        import re
        # Strip markdown code fences if present
        raw = judge.text
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        json_str = extract_json_object(raw)
        if not json_str:
            # Try repairing truncated JSON before retrying
            json_str = repair_truncated_json(raw)

        if not json_str:
            # Retry once before giving up
            retry_judge = _call_judge(prompt)
            result.judge_raw_response = retry_judge.text
            retry_raw = re.sub(r"^```(?:json)?\s*", "", retry_judge.text)
            retry_raw = re.sub(r"\s*```$", "", retry_raw)
            json_str = extract_json_object(retry_raw)
            if not json_str:
                json_str = repair_truncated_json(retry_raw)
            if not json_str:
                result.error = "Judge returned unparseable response (after retry)"
                return result

        # Fix trailing commas (common in Gemini output)
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
        # Fix invalid backslash escapes (common in code-containing JSON)
        json_str = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r"\\\\", json_str)

        data = json.loads(json_str)

        result.criteria_results = data.get("criteria_results", [])
        result.correctness = data.get("correctness", {}).get("score", 0) / 10
        result.safety = data.get("safety", {}).get("score", 0) / 10
        result.completeness = data.get("completeness", {}).get("score", 0) / 10
        result.quality = data.get("quality", {}).get("score", 0) / 10
        result.passed = data.get("passed", False)
        result.verdict = data.get("verdict", "")

        # Weighted overall: correctness matters most (weights sum to 1.0)
        result.overall = round(
            result.correctness * 0.40
            + result.safety * 0.25
            + result.completeness * 0.20
            + result.quality * 0.15,
            3,
        )

        # Build judge reasoning from dimension reasons
        reasons = []
        for dim in ["correctness", "safety", "completeness", "quality"]:
            r = data.get(dim, {}).get("reason", "")
            if r:
                reasons.append(f"{dim}: {r}")
        result.judge_reasoning = " | ".join(reasons)

    except Exception as e:
        error_str = str(e)
        result.error = f"Judge error: {error_str}"

        # Detect billing/auth failures on judge side too
        fatal_patterns = [
            "credit", "billing", "payment", "insufficient", "quota",
            "402", "authentication", "unauthorized", "401", "403",
            "rate_limit", "rate limit", "overloaded",
            "FreeTierOnly", "AllocationQuota",
        ]
        error_lower = error_str.lower()
        if any(p in error_lower for p in fatal_patterns):
            print(f"\n  *** FATAL (judge): {error_str}")
            print(f"  *** Halting — fix your judge API key/billing before continuing.\n")
            raise RuntimeError(f"Judge API billing/auth failure: {error_str}") from e

    return result


def run_benchmark(
    skill: ParsedSkill,
    job: BenchmarkJob,
    runs: int = 1,
) -> WorkSampleResult:
    """Run one skill against one job: execute then judge.

    When runs > 1, executes the job N times and returns an averaged result.
    The raw_output and judge_reasoning come from the median-scoring run.
    """
    if runs < 1:
        runs = 1

    if runs == 1:
        print(f"    Running: {job.name}...")
        result = run_skill(skill, job)
        if not result.error:
            result = judge_output(job, result)
        status = "PASS" if result.passed else "FAIL"
        print(f"    -> {status} ({result.overall:.2f}) {result.verdict}")
        return result

    # Multiple runs — collect results, then average
    print(f"    Running: {job.name} ({runs} runs)...")
    run_results: list[WorkSampleResult] = []
    for i in range(runs):
        r = run_skill(skill, job)
        if not r.error:
            r = judge_output(job, r)
        run_results.append(r)
        status = "PASS" if r.passed else "FAIL"
        print(f"      Run {i + 1}/{runs}: {status} ({r.overall:.2f})")

    # Average the scores across runs
    valid_runs = [r for r in run_results if not r.error]
    if not valid_runs:
        # All runs errored — return the first one
        return run_results[0]

    n = len(valid_runs)
    avg_correctness = sum(r.correctness for r in valid_runs) / n
    avg_safety = sum(r.safety for r in valid_runs) / n
    avg_completeness = sum(r.completeness for r in valid_runs) / n
    avg_quality = sum(r.quality for r in valid_runs) / n
    avg_overall = sum(r.overall for r in valid_runs) / n
    pass_rate = sum(1 for r in valid_runs if r.passed) / n

    # Pick the median-scoring run for raw_output and reasoning
    sorted_runs = sorted(valid_runs, key=lambda r: r.overall)
    median_run = sorted_runs[len(sorted_runs) // 2]

    averaged = WorkSampleResult(
        job_id=job.id,
        skill_name=median_run.skill_name,
        raw_output=median_run.raw_output,
        runtime_ms=sum(r.runtime_ms for r in valid_runs) // n,
        input_tokens=sum(r.input_tokens for r in valid_runs) // n,
        output_tokens=sum(r.output_tokens for r in valid_runs) // n,
        exec_input_tokens=sum(r.exec_input_tokens for r in valid_runs) // n,
        exec_output_tokens=sum(r.exec_output_tokens for r in valid_runs) // n,
        passed=pass_rate >= 0.5,
        correctness=round(avg_correctness, 3),
        safety=round(avg_safety, 3),
        completeness=round(avg_completeness, 3),
        quality=round(avg_quality, 3),
        overall=round(avg_overall, 3),
        verdict=f"Averaged {n} runs (pass rate {pass_rate:.0%}): {median_run.verdict}",
        criteria_results=median_run.criteria_results,
        judge_reasoning=median_run.judge_reasoning,
        judge_input_tokens=sum(r.judge_input_tokens for r in valid_runs) // n,
        judge_output_tokens=sum(r.judge_output_tokens for r in valid_runs) // n,
        judge_provider=median_run.judge_provider,
        exec_provider=median_run.exec_provider,
        exec_model=median_run.exec_model,
        judge_model=median_run.judge_model,
        exec_prompt=median_run.exec_prompt,
        judge_prompt=median_run.judge_prompt,
        judge_raw_response=median_run.judge_raw_response,
    )
    averaged.sync_token_totals()

    print(f"    -> {'PASS' if averaged.passed else 'FAIL'} ({averaged.overall:.2f}) {averaged.verdict}")
    return averaged


def run_benchmark_suite(
    skill: ParsedSkill,
    jobs: list[BenchmarkJob],
    test_set: str | None = None,
    runs_per_job: int = 1,
) -> list[WorkSampleResult]:
    """Run a skill against multiple jobs. Returns all results.

    Args:
        skill: The parsed skill to evaluate.
        jobs: List of benchmark jobs.
        test_set: If provided, only run jobs matching this test_set ("tune" or "holdout").
        runs_per_job: Number of times to run each job (scores are averaged).
    """
    if test_set:
        jobs = [j for j in jobs if j.test_set == test_set]

    print(f"\n  Benchmarking: {skill.name}")
    print(f"  Jobs: {len(jobs)}" + (f" (test_set={test_set})" if test_set else ""))
    if runs_per_job > 1:
        print(f"  Runs per job: {runs_per_job}")
    print(f"  {'─'*50}")

    results = []
    for job in jobs:
        r = run_benchmark(skill, job, runs=runs_per_job)
        results.append(r)

    # Summary
    passed = sum(1 for r in results if r.passed)
    avg_score = sum(r.overall for r in results) / len(results) if results else 0
    total_tokens = sum(r.input_tokens + r.output_tokens for r in results)
    total_ms = sum(r.runtime_ms for r in results)

    print(f"  {'─'*50}")
    print(f"  Results: {passed}/{len(results)} passed, avg score {avg_score:.2f}")
    print(f"  Tokens: {total_tokens:,}, Runtime: {total_ms:,}ms")

    return results


# ── Paired A/B benchmarking ──────────────────────────────────────────────────


def _run_baseline(job: BenchmarkJob) -> WorkSampleResult:
    """Run a job WITHOUT any skill (raw model baseline)."""
    result = WorkSampleResult(job_id=job.id, skill_name="(no skill)")

    prompt = _BASELINE_EXECUTION_PROMPT.format(
        task_prompt=job.input_prompt,
        task_context=job.input_context[:6000],
    )
    result.exec_prompt = prompt

    try:
        if DEFAULT_EXEC_MODEL_PROVIDER == "anthropic":
            result.exec_provider = DEFAULT_EXEC_MODEL_PROVIDER
            client = _get_client()
            start = time.monotonic()
            response = client.messages.create(
                model=_resolve_exec_model_name(DEFAULT_EXEC_MODEL_PROVIDER, DEFAULT_EXEC_MODEL_NAME),
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            result.runtime_ms = int((time.monotonic() - start) * 1000)
            result.raw_output = response.content[0].text
            result.exec_input_tokens = response.usage.input_tokens
            result.exec_output_tokens = response.usage.output_tokens
            result.exec_model = _resolve_exec_model_name(
                DEFAULT_EXEC_MODEL_PROVIDER,
                DEFAULT_EXEC_MODEL_NAME,
            )
            result.sync_token_totals()
            return result

        if DEFAULT_EXEC_MODEL_PROVIDER == "qwen":
            result.exec_provider = DEFAULT_EXEC_MODEL_PROVIDER
            start = time.monotonic()
            response = _call_qwen_chat(
                prompt,
                model=_resolve_exec_model_name(
                    DEFAULT_EXEC_MODEL_PROVIDER,
                    DEFAULT_EXEC_MODEL_NAME,
                ),
                max_tokens=8000,
            )
            result.runtime_ms = int((time.monotonic() - start) * 1000)
            result.raw_output = response.text
            result.exec_input_tokens = response.input_tokens
            result.exec_output_tokens = response.output_tokens
            result.exec_model = response.model_name
            result.sync_token_totals()
            return result

        raise RuntimeError(
            "Unsupported EXEC_MODEL_PROVIDER="
            f"{DEFAULT_EXEC_MODEL_PROVIDER!r}; expected 'anthropic' or 'qwen'"
        )
    except Exception as e:
        result.error = str(e)

    return result


def _load_baseline_cache() -> dict:
    """Load cached baseline results. Returns {job_id: {result_dict, timestamp}}."""
    if not BASELINE_CACHE_PATH.exists():
        return {}
    with open(BASELINE_CACHE_PATH) as f:
        return json.load(f)


def _save_baseline_cache(cache: dict) -> None:
    """Persist baseline cache."""
    BASELINE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def _is_cache_fresh(entry: dict) -> bool:
    """Check if a cached baseline result is less than BASELINE_CACHE_MAX_AGE_DAYS old."""
    ts = entry.get("timestamp", "")
    if not ts:
        return False
    from datetime import datetime, timezone
    try:
        cached_at = datetime.fromisoformat(ts)
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        return (
            datetime.now(timezone.utc) - cached_at
        ).days < BASELINE_CACHE_MAX_AGE_DAYS
    except ValueError:
        return False


def _result_from_cache(job_id: str, data: dict) -> WorkSampleResult:
    """Reconstruct a WorkSampleResult from cached dict."""
    result = WorkSampleResult(
        job_id=job_id,
        skill_name="(no skill)",
        passed=data.get("passed", False),
        correctness=data.get("correctness", 0),
        safety=data.get("safety", 0),
        completeness=data.get("completeness", 0),
        quality=data.get("quality", 0),
        overall=data.get("overall", 0),
        verdict=data.get("verdict", ""),
        runtime_ms=data.get("runtime_ms", 0),
        input_tokens=data.get("input_tokens", 0),
        output_tokens=data.get("output_tokens", 0),
        exec_input_tokens=data.get("exec_input_tokens", data.get("input_tokens", 0)),
        exec_output_tokens=data.get("exec_output_tokens", data.get("output_tokens", 0)),
        judge_input_tokens=data.get("judge_input_tokens", 0),
        judge_output_tokens=data.get("judge_output_tokens", 0),
        judge_provider=data.get("judge_provider", ""),
        exec_provider=data.get("exec_provider", ""),
        exec_model=data.get("exec_model", ""),
        judge_model=data.get("judge_model", ""),
        criteria_results=data.get("criteria_results", []),
        judge_reasoning=data.get("judge_reasoning", ""),
        error=data.get("error", ""),
    )
    if "exec_input_tokens" in data or "judge_input_tokens" in data:
        result.sync_token_totals()
    return result


def _aggregate_token_usage(results: list[WorkSampleResult]) -> dict[str, int]:
    """Aggregate token usage across benchmark runs."""
    exec_input = sum(r.exec_input_tokens for r in results)
    exec_output = sum(r.exec_output_tokens for r in results)
    judge_input = sum(r.judge_input_tokens for r in results)
    judge_output = sum(r.judge_output_tokens for r in results)
    input_tokens = sum(r.input_tokens for r in results)
    output_tokens = sum(r.output_tokens for r in results)
    return {
        "exec_input_tokens": exec_input,
        "exec_output_tokens": exec_output,
        "judge_input_tokens": judge_input,
        "judge_output_tokens": judge_output,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def load_or_run_baseline(job: BenchmarkJob) -> WorkSampleResult:
    """Load baseline from cache or run fresh. Cache results for reuse."""
    cache = _load_baseline_cache()

    if job.id in cache and _is_cache_fresh(cache[job.id]):
        print(f"    Baseline (cached): {job.name}")
        return _result_from_cache(job.id, cache[job.id]["result"])

    print(f"    Baseline (running): {job.name}...")
    result = _run_baseline(job)
    if not result.error:
        result = judge_output(job, result)

    status = "PASS" if result.passed else "FAIL"
    print(f"    -> Baseline: {status} ({result.overall:.2f})")

    cache[job.id] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result.to_dict(),
    }
    _save_baseline_cache(cache)

    return result


def run_paired_benchmark(
    skill: ParsedSkill,
    job: BenchmarkJob,
    runs: int = 1,
) -> PairedResult:
    """Run a job with skill AND without, compute upgrade."""
    baseline = load_or_run_baseline(job)
    skill_result = run_benchmark(skill, job, runs=runs)

    upgrade = round(skill_result.overall - baseline.overall, 3)

    return PairedResult(
        job_id=job.id,
        skill_name=skill.name,
        skill_result=skill_result,
        baseline_result=baseline,
        upgrade=upgrade,
    )


def run_paired_benchmark_suite(
    skill: ParsedSkill,
    jobs: list[BenchmarkJob],
    test_set: str | None = None,
    runs_per_job: int = 1,
) -> list[PairedResult]:
    """Run paired benchmarks across multiple jobs.

    Returns PairedResult list with upgrade stats.
    """
    if test_set:
        jobs = [j for j in jobs if j.test_set == test_set]

    print(f"\n  Paired Benchmark: {skill.name}")
    print(f"  Jobs: {len(jobs)}" + (f" (test_set={test_set})" if test_set else ""))
    if runs_per_job > 1:
        print(f"  Runs per job: {runs_per_job}")
    print(f"  {'─'*60}")

    results = []
    for job in jobs:
        pr = run_paired_benchmark(skill, job, runs=runs_per_job)
        sign = "+" if pr.upgrade >= 0 else ""
        print(f"    Upgrade: {sign}{pr.upgrade:.3f}")
        results.append(pr)

    # Summary
    upgrades = [r.upgrade for r in results]
    avg_upgrade = sum(upgrades) / len(upgrades) if upgrades else 0
    positive = sum(1 for u in upgrades if u > 0)
    avg_skill = sum(r.skill_result.overall for r in results) / len(results) if results else 0
    avg_baseline = sum(r.baseline_result.overall for r in results) / len(results) if results else 0

    print(f"  {'─'*60}")
    print(f"  Skill avg:    {avg_skill:.3f}")
    print(f"  Baseline avg: {avg_baseline:.3f}")
    print(f"  Avg upgrade:  {'+' if avg_upgrade >= 0 else ''}{avg_upgrade:.3f}")
    print(f"  Beat baseline: {positive}/{len(results)} jobs")

    return results


# ── Persistence ──────────────────────────────────────────────────────────────

RESULTS_PATH = Path("data/benchmark_results.json")
TRANSCRIPTS_DIR = Path("data/transcripts")


def save_results(
    skill_name: str,
    results: list[WorkSampleResult] | list[PairedResult],
) -> None:
    """Append benchmark results to the results file.

    Accepts either plain WorkSampleResults or PairedResults (with baseline + upgrade).
    """
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            existing = json.load(f)

    # Detect paired vs plain results
    is_paired = results and isinstance(results[0], PairedResult)

    if is_paired:
        paired: list[PairedResult] = results  # type: ignore[assignment]
        skill_results = [r.skill_result for r in paired]
        baseline_results = [r.baseline_result for r in paired]
        skill_tokens = _aggregate_token_usage(skill_results)
        baseline_tokens = _aggregate_token_usage(baseline_results)
        upgrades = [r.upgrade for r in paired]
        avg_upgrade = round(sum(upgrades) / len(upgrades), 3) if upgrades else 0
        entry = {
            "skill_name": skill_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "paired": True,
            "jobs_run": len(paired),
            "jobs_passed": sum(1 for r in skill_results if r.passed),
            "avg_overall": round(
                sum(r.overall for r in skill_results) / len(skill_results), 3
            ) if skill_results else 0,
            "avg_baseline": round(
                sum(r.baseline_result.overall for r in paired) / len(paired), 3
            ) if paired else 0,
            "avg_upgrade": avg_upgrade,
            "skill_total_tokens": skill_tokens["total_tokens"],
            "baseline_total_tokens": baseline_tokens["total_tokens"],
            "total_tokens": skill_tokens["total_tokens"] + baseline_tokens["total_tokens"],
            "token_usage": {
                "skill": skill_tokens,
                "baseline": baseline_tokens,
                "total_input_tokens": skill_tokens["input_tokens"] + baseline_tokens["input_tokens"],
                "total_output_tokens": skill_tokens["output_tokens"] + baseline_tokens["output_tokens"],
                "total_tokens": skill_tokens["total_tokens"] + baseline_tokens["total_tokens"],
            },
            "results": [r.to_dict() for r in paired],
        }
    else:
        plain: list[WorkSampleResult] = results  # type: ignore[assignment]
        token_usage = _aggregate_token_usage(plain)
        entry = {
            "skill_name": skill_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "paired": False,
            "jobs_run": len(plain),
            "jobs_passed": sum(1 for r in plain if r.passed),
            "avg_overall": round(
                sum(r.overall for r in plain) / len(plain), 3
            ) if plain else 0,
            "total_tokens": token_usage["total_tokens"],
            "token_usage": token_usage,
            "results": [r.to_dict() for r in plain],
        }

    existing.append(entry)
    with open(RESULTS_PATH, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"  Results saved to {RESULTS_PATH}")

    # Save full transcripts for review
    _save_transcripts(skill_name, results)


def _save_transcripts(
    skill_name: str,
    results: list[WorkSampleResult] | list[PairedResult],
) -> None:
    """Save full agent interaction transcripts for human review."""
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in skill_name)
    path = TRANSCRIPTS_DIR / f"{safe_name}_{timestamp}.json"

    transcripts = []
    is_paired = results and isinstance(results[0], PairedResult)

    if is_paired:
        for r in results:
            pr: PairedResult = r  # type: ignore[assignment]
            transcripts.append({
                "job_id": pr.job_id,
                "upgrade": pr.upgrade,
                "skill_transcript": pr.skill_result.to_transcript(),
                "baseline_transcript": pr.baseline_result.to_transcript(),
            })
    else:
        for r in results:
            wr: WorkSampleResult = r  # type: ignore[assignment]
            transcripts.append(wr.to_transcript())

    with open(path, "w") as f:
        json.dump({
            "skill_name": skill_name,
            "timestamp": timestamp,
            "paired": is_paired,
            "transcripts": transcripts,
        }, f, indent=2)
    print(f"  Transcripts saved to {path}")


def get_leaderboard_data() -> list[dict]:
    """Return leaderboard data as a list of dicts, sorted by upgrade then score."""
    if not RESULTS_PATH.exists():
        return []

    with open(RESULTS_PATH) as f:
        data = json.load(f)

    # Group by skill, take latest run
    latest: dict[str, dict] = {}
    for entry in data:
        name = entry["skill_name"]
        latest[name] = entry

    # Sort by upgrade (if available), then by score
    return sorted(
        latest.values(),
        key=lambda e: (-(e.get("avg_upgrade") or 0), -e["avg_overall"]),
    )


def print_leaderboard() -> None:
    """Print the current benchmark leaderboard."""
    ranked = get_leaderboard_data()
    if not ranked:
        print("  No benchmark results yet.")
        return

    has_paired = any(e.get("paired") for e in ranked)

    print(f"\n  {'='*75}")
    print(f"  AgentArena Leaderboard — AI Agent Benchmarks")
    print(f"  {'='*75}")
    if has_paired:
        print(f"  {'Rank':<5} {'Skill':<28} {'Upgrade':>8} {'Score':>7} {'Baseline':>9} {'Pass':>6}")
        print(f"  {'─'*68}")
        for i, entry in enumerate(ranked, 1):
            name = entry["skill_name"][:27]
            upgrade = entry.get("avg_upgrade")
            baseline = entry.get("avg_baseline")
            upgrade_str = f"{'+' if upgrade and upgrade >= 0 else ''}{upgrade:.3f}" if upgrade is not None else "—"
            baseline_str = f"{baseline:.3f}" if baseline is not None else "—"
            pass_rate = f"{entry['jobs_passed']}/{entry['jobs_run']}"
            score = f"{entry['avg_overall']:.3f}"
            print(f"  {i:<5} {name:<28} {upgrade_str:>8} {score:>7} {baseline_str:>9} {pass_rate:>6}")
    else:
        print(f"  {'Skill':<30} {'Pass':>6} {'Score':>7} {'Tokens':>8}")
        print(f"  {'─'*55}")
        for entry in ranked:
            name = entry["skill_name"][:29]
            pass_rate = f"{entry['jobs_passed']}/{entry['jobs_run']}"
            score = f"{entry['avg_overall']:.2f}"
            tokens = f"{entry['total_tokens']:,}"
            print(f"  {name:<30} {pass_rate:>6} {score:>7} {tokens:>8}")
    print(f"  {'='*75}\n")
