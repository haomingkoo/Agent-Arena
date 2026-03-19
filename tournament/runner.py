"""
Tournament runner — agent-native tournament execution.

Supports two modes:
  1. Agent-native (field/role): Uses AgentVersion + RunnerContract
  2. Legacy (category): Uses Skill + ParsedSkill (preserved for backward compat)

Agent-native flow:
  1. Query benchmark-ready agents for a field/role
  2. Get RunnerContract for each agent version
  3. Select tasks from the field/role task pack
  4. Run baseline on all tasks (cached)
  5. Run each agent on all tasks via benchmark/executor.py
  6. Judge outputs
  7. Compute scores
  8. Update Glicko-2 ratings keyed by agent version ID
  9. Persist tournament entries + rating history
  10. Save transcripts
  11. Return tournament_id
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from agents.contracts import RunnerContract
from benchmark.executor import contract_to_parsed_skill, execute_agent_on_task
from benchmark.taskpacks import get_task_pack, select_holdout_jobs, select_task_pack_jobs
from evaluate.rubric import ParsedSkill
from evaluate.sandbox import (
    BenchmarkJob,
    WorkSampleResult,
    load_or_run_baseline,
    run_benchmark,
)
from store.models import RunTrace
from store.db import (
    add_run_trace,
    add_rating_history,
    add_tournament_entry,
    create_tournament,
    get_skill,
    get_jd_corpus_stats,
    get_latest_corpus_version,
    get_skill_rating,
    get_tournament_by_week,
    list_benchmark_ready_agents,
    list_skills_by_category,
    update_tournament,
    upsert_skill_rating,
)
from tournament.cost import EXEC_MODEL, JUDGE_MODEL, compute_actual_cost
from tournament.ranking import Rating, update_tournament_ratings
from tournament.tasks import select_tasks

TRANSCRIPTS_DIR = Path("data/transcripts")


# ── Config dataclasses ──────────────────────────────────────────────────────


@dataclass
class TournamentConfig:
    """Configuration for a single tournament run.

    Supports both agent-native (field/role) and legacy (category) modes.
    When field and role are set, uses agent-native mode.
    When only category is set, uses legacy skill mode.
    """
    category: str = ""
    field: str = ""
    role: str = ""
    week: str = ""                     # ISO week "2026-W12"
    tasks_per_tournament: int = 5
    runs_per_task: int = 1             # increase to 3-5 for production
    max_agents: int = 30
    max_skills: int = 30               # legacy compat alias
    runtime_class: str = "standard"
    tournament_type: str = "standardized"  # standardized | native | qualification | ablation
    task_pack_version: str = "v2"

    @property
    def is_agent_native(self) -> bool:
        return bool(self.field and self.role)

    @property
    def tournament_category(self) -> str:
        """Unified category key for DB storage."""
        if self.is_agent_native:
            return f"{self.field}/{self.role}"
        return self.category


@dataclass
class AgentRunSummary:
    """Summary of one agent version's performance across all tournament tasks."""
    version_id: str
    agent_name: str
    results: list[WorkSampleResult] = field(default_factory=list)
    avg_score: float = 0.0
    pass_rate: float = 0.0
    total_tokens: int = 0
    total_runtime_ms: int = 0
    total_cost_usd: float = 0.0


# Legacy alias for backward compatibility
SkillRunSummary = AgentRunSummary


# ── Shared helpers ──────────────────────────────────────────────────────────


def _load_last_task_ids(category: str, week: str) -> set[str]:
    """Load task IDs from the previous tournament in this category.

    Used to rotate tasks and prevent overfitting.
    """
    prev_tournament = get_tournament_by_week(category, week)
    if prev_tournament:
        try:
            return set(json.loads(prev_tournament.get("task_ids_json", "[]")))
        except (json.JSONDecodeError, TypeError):
            pass
    return set()


def _get_previous_week(week: str) -> str:
    """Get the ISO week string before the given week.

    Example: '2026-W12' -> '2026-W11', '2026-W01' -> '2025-W52'
    """
    parts = week.split("-W")
    if len(parts) != 2:
        return ""
    year, wk = int(parts[0]), int(parts[1])
    if wk > 1:
        return f"{year}-W{wk - 1:02d}"
    return f"{year - 1}-W52"


def _save_tournament_transcripts(
    tournament_id: str,
    summaries: dict[str, AgentRunSummary],
) -> Path | None:
    """Save full transcripts for all agents in a tournament."""
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = TRANSCRIPTS_DIR / f"tournament_{tournament_id}_{timestamp}.json"

    transcripts: list[dict] = []
    for version_id, summary in summaries.items():
        agent_transcript = {
            "version_id": version_id,
            "agent_name": summary.agent_name,
            "avg_score": summary.avg_score,
            "pass_rate": summary.pass_rate,
            "tasks": [r.to_transcript() for r in summary.results],
        }
        transcripts.append(agent_transcript)

    with open(path, "w") as f:
        json.dump({
            "tournament_id": tournament_id,
            "timestamp": timestamp,
            "agents": transcripts,
        }, f, indent=2)

    print(f"  Transcripts saved to {path}")
    return path


def _result_cost_usd(result: WorkSampleResult) -> float:
    """Compute total result cost from explicit execution and judge usage."""
    exec_cost = compute_actual_cost(
        result.exec_input_tokens,
        result.exec_output_tokens,
        result.exec_model or EXEC_MODEL,
    )
    judge_cost = compute_actual_cost(
        result.judge_input_tokens,
        result.judge_output_tokens,
        result.judge_model or JUDGE_MODEL,
    )
    return round(exec_cost + judge_cost, 6)


def _persist_agent_run_trace(
    *,
    tournament_id: str,
    tournament_run_id: str,
    version_id: str,
    contract: RunnerContract,
    job: BenchmarkJob,
    result: WorkSampleResult,
    trace_kind: str = "benchmark",
) -> str:
    """Persist one agent-native benchmark run as a RunTrace."""
    metadata = {
        "passed": result.passed,
        "overall": result.overall,
        "correctness": result.correctness,
        "safety": result.safety,
        "completeness": result.completeness,
        "quality": result.quality,
        "verdict": result.verdict,
        "criteria_results": result.criteria_results,
        "judge_reasoning": result.judge_reasoning,
    }
    prompt_payload = {
        "exec_prompt": result.exec_prompt,
        "task_prompt": job.input_prompt,
        "task_context": job.input_context,
        "system_instructions": contract.system_instructions,
    }
    trace = RunTrace(
        agent_version_id=version_id,
        field=contract.field,
        role=contract.role,
        tournament_id=tournament_id,
        tournament_run_id=tournament_run_id,
        task_id=job.id,
        trace_kind=trace_kind,
        status="failed" if result.error else "completed",
        exec_provider=result.exec_provider or contract.model_provider,
        judge_provider=result.judge_provider,
        final_output=result.raw_output,
        error=result.error,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_cost_usd=_result_cost_usd(result),
        runtime_ms=result.runtime_ms,
        prompt_json=json.dumps(prompt_payload),
        tool_calls_json="[]",
        tool_outputs_json="[]",
        judge_prompt=result.judge_prompt,
        judge_output=result.judge_raw_response,
        metadata_json=json.dumps(metadata),
    )
    return add_run_trace(trace)


def _run_internal_holdout_validation(
    *,
    tournament_id: str,
    version_id: str,
    contract: RunnerContract,
    tasks: list[BenchmarkJob],
) -> tuple[int, int, float]:
    """Run internal holdout tasks without affecting public ranking state."""
    holdout_input_tokens = 0
    holdout_output_tokens = 0
    holdout_cost = 0.0

    if not tasks:
        return holdout_input_tokens, holdout_output_tokens, holdout_cost

    print(f"    Holdout validation: {len(tasks)} private task(s)")
    for task in tasks:
        result = execute_agent_on_task(contract, task)
        holdout_input_tokens += result.input_tokens
        holdout_output_tokens += result.output_tokens
        result_cost = _result_cost_usd(result)
        holdout_cost += result_cost
        _persist_agent_run_trace(
            tournament_id=tournament_id,
            tournament_run_id=f"{tournament_id}:{version_id}:holdout",
            version_id=version_id,
            contract=contract,
            job=task,
            result=result,
            trace_kind="holdout",
        )

        status = "PASS" if result.passed else "FAIL"
        if result.error:
            status = "ERR"
        print(
            f"      {task.id}: {status} "
            f"({result.overall:.3f}) {result.verdict[:50]}"
        )

    return holdout_input_tokens, holdout_output_tokens, holdout_cost


# ── Agent-native tournament ─────────────────────────────────────────────────


def _parse_runner_contract(row: dict) -> RunnerContract | None:
    """Parse a RunnerContract from a benchmark-ready agent DB row."""
    contract_json = row.get("runner_contract_json", "")
    if not contract_json:
        return None
    try:
        data = json.loads(contract_json)
        return RunnerContract(**data)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def run_tournament(config: TournamentConfig) -> str:
    """Execute a full tournament.

    Routes to agent-native or legacy mode based on config.
    Agent-native mode: uses field/role with AgentVersion + RunnerContract.
    Legacy mode: uses category with Skill + ParsedSkill.

    Returns the tournament_id.
    """
    if config.is_agent_native:
        return _run_agent_tournament(config)
    return _run_legacy_tournament(config)


def _run_agent_tournament(config: TournamentConfig) -> str:
    """Full agent-native tournament.

    1. Load benchmark-ready agents for field/role from DB
    2. Select tasks from the field/role task pack
    3. Run baseline on all tasks (cached)
    4. Run each agent on all tasks via executor
    5. Judge outputs
    6. Compute scores
    7. Update Glicko-2 ratings using agent version IDs
    8. Persist tournament + entries + rating history
    9. Save transcripts
    10. Return tournament_id
    """
    category = config.tournament_category

    print(f"\n{'='*70}")
    print(f"  AgentArena Tournament: {config.field}/{config.role} — {config.week}")
    print(f"{'='*70}")

    # ── Step 1: Get benchmark-ready agents ────────────────────────────
    agent_rows = list_benchmark_ready_agents(
        field=config.field,
        role=config.role,
        limit=config.max_agents,
    )

    # Parse contracts and filter to agents with valid contracts
    agent_contracts: dict[str, RunnerContract] = {}
    agent_names: dict[str, str] = {}
    for row in agent_rows:
        version_id = row["version_id"]
        contract = _parse_runner_contract(row)
        if contract is not None:
            agent_contracts[version_id] = contract
            agent_names[version_id] = row["profile_name"]

    if len(agent_contracts) < 2:
        raise ValueError(
            f"Need at least 2 benchmark-ready agents for "
            f"'{config.field}/{config.role}', found {len(agent_contracts)}"
        )

    print(f"  Agents: {len(agent_contracts)} competing")

    tournament_type = getattr(config, "tournament_type", "standardized")
    task_pack_version = getattr(config, "task_pack_version", "v1")
    task_pack = get_task_pack(
        config.field,
        config.role,
        version=task_pack_version,
    )

    if tournament_type == "standardized" and task_pack.requires_jd_corpus:
        latest_corpus = get_latest_corpus_version(config.field, config.role)
        corpus_stats = get_jd_corpus_stats(config.field, config.role)
        if not latest_corpus or corpus_stats.get("total", 0) <= 0:
            raise ValueError(
                "Standardized tournament for "
                f"{config.field}/{config.role} requires a live JD corpus. "
                "Run JD refresh first before treating this lane as market-backed."
            )
        print(
            "  JD corpus: "
            f"{latest_corpus.get('version_label', 'unknown')} "
            f"({corpus_stats.get('total', 0)} postings, "
            f"{corpus_stats.get('companies', 0)} companies, "
            f"{corpus_stats.get('sources', 0)} ATS sources)"
        )

    # ── Step 2: Select tasks from task pack ───────────────────────────
    prev_week = _get_previous_week(config.week)
    exclude_ids = _load_last_task_ids(category, prev_week)
    tasks = select_task_pack_jobs(
        config.field,
        config.role,
        version=task_pack_version,
        count=config.tasks_per_tournament,
        exclude_ids=exclude_ids,
    )

    if not tasks:
        raise ValueError(
            f"No tasks available for {config.field}/{config.role}"
        )

    task_ids = [t.id for t in tasks]
    print(f"  Tasks:  {len(tasks)} selected ({', '.join(task_ids)})")

    holdout_tasks: list[BenchmarkJob] = []
    if tournament_type == "standardized":
        holdout_tasks = select_holdout_jobs(
            config.field,
            config.role,
            version=task_pack_version,
        )
        if holdout_tasks:
            print(
                f"  Holdouts: {len(holdout_tasks)} internal "
                f"({', '.join(t.id for t in holdout_tasks)})"
            )

    # ── Step 3: Create tournament record ──────────────────────────────
    tournament_id = create_tournament(
        category,
        config.week,
        task_ids,
        field=config.field,
        role=config.role,
        runtime_class=config.runtime_class,
        task_pack_version=task_pack_version,
        tournament_type=tournament_type,
    )

    try:
        update_tournament(
            tournament_id,
            status="running",
            num_skills=len(agent_contracts),
        )
        print(f"  Tournament ID: {tournament_id}")

        # ── Step 4: Run baselines (cached) ────────────────────────────────
        print(f"\n  Running baselines...")
        baseline_results: dict[str, WorkSampleResult] = {}
        for task in tasks:
            baseline_results[task.id] = load_or_run_baseline(task)

        baseline_scores = [r.overall for r in baseline_results.values()]
        baseline_avg = (
            sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0
        )
        print(f"  Baseline avg: {baseline_avg:.3f}")

        # ── Step 5: Run each agent on all tasks ───────────────────────────
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0

        summaries: dict[str, AgentRunSummary] = {}

        for baseline in baseline_results.values():
            total_input_tokens += baseline.input_tokens
            total_output_tokens += baseline.output_tokens
            total_cost += _result_cost_usd(baseline)

        for version_id, contract in agent_contracts.items():
            agent_name = agent_names[version_id]
            print(f"\n  Agent: {agent_name} (v:{version_id[:8]})")

            summary = AgentRunSummary(
                version_id=version_id,
                agent_name=agent_name,
            )

            for task in tasks:
                result = execute_agent_on_task(contract, task)
                summary.results.append(result)
                summary.total_tokens += result.input_tokens + result.output_tokens
                summary.total_runtime_ms += result.runtime_ms

                total_input_tokens += result.input_tokens
                total_output_tokens += result.output_tokens
                result_cost = _result_cost_usd(result)
                summary.total_cost_usd += result_cost
                total_cost += result_cost
                _persist_agent_run_trace(
                    tournament_id=tournament_id,
                    tournament_run_id=f"{tournament_id}:{version_id}",
                    version_id=version_id,
                    contract=contract,
                    job=task,
                    result=result,
                )

                status = "PASS" if result.passed else "FAIL"
                if result.error:
                    status = "ERR"
                print(
                    f"    {task.id}: {status} "
                    f"({result.overall:.3f}) {result.verdict[:50]}"
                )

            # Compute summary stats
            valid_results = [r for r in summary.results if not r.error]
            if valid_results:
                summary.avg_score = (
                    sum(r.overall for r in valid_results) / len(valid_results)
                )
                summary.pass_rate = (
                    sum(1 for r in valid_results if r.passed) / len(valid_results)
                )

            summaries[version_id] = summary

            if holdout_tasks:
                holdout_in, holdout_out, holdout_cost = _run_internal_holdout_validation(
                    tournament_id=tournament_id,
                    version_id=version_id,
                    contract=contract,
                    tasks=holdout_tasks,
                )
                total_input_tokens += holdout_in
                total_output_tokens += holdout_out
                total_cost += holdout_cost

        # ── Step 6: Update Glicko-2 ratings ───────────────────────────────
        if tournament_type != "standardized":
            print(f"\n  Skipping Glicko-2 update (tournament_type={tournament_type}, not standardized)")
        else:
            print(f"\n  Updating Glicko-2 ratings (standardized tournament)...")

        # Load current ratings keyed by version_id
        current_ratings: dict[str, Rating] = {}
        for version_id in summaries:
            db_rating = get_skill_rating(version_id, category)
            if db_rating:
                current_ratings[version_id] = Rating(
                    mu=db_rating["mu"],
                    rd=db_rating["rd"],
                    sigma=db_rating["sigma"],
                )
            else:
                current_ratings[version_id] = Rating()

        # Build score map for Glicko-2
        score_map: dict[str, float] = {
            vid: summaries[vid].avg_score for vid in summaries
        }

        # Run the rating update
        new_ratings = update_tournament_ratings(current_ratings, score_map)

        # ── Step 7: Rank and persist entries ──────────────────────────────
        ranked = sorted(
            summaries.items(),
            key=lambda item: item[1].avg_score,
            reverse=True,
        )

        print(f"\n  {'─'*65}")
        print(
            f"  {'Rank':<5} {'Agent':<30} {'Score':>7} "
            f"{'Pass':>6} {'Rating':>8} {'Delta':>7}"
        )
        print(f"  {'─'*65}")

        for rank, (version_id, summary) in enumerate(ranked, 1):
            old_rating = current_ratings.get(version_id, Rating())
            new_rating = new_ratings[version_id]
            rating_delta = new_rating.mu - old_rating.mu

            # Get tournaments_played count
            db_rating = get_skill_rating(version_id, category)
            tournaments_played = (
                (db_rating["tournaments_played"] + 1) if db_rating else 1
            )

            # Only update public ratings for standardized tournaments
            if tournament_type == "standardized":
                upsert_skill_rating(
                    version_id, category,
                    mu=new_rating.mu,
                    rd=new_rating.rd,
                    sigma=new_rating.sigma,
                    tournaments_played=tournaments_played,
                    last_tournament_week=config.week,
                )
                add_rating_history(
                    version_id, category, config.week,
                    mu=new_rating.mu,
                    rd=new_rating.rd,
                    rank=rank,
                    avg_score=summary.avg_score,
                )

            # Always persist tournament entry (using version_id as skill_id)
            add_tournament_entry(tournament_id, {
                "skill_id": version_id,
                "skill_name": summary.agent_name,
                "rank": rank,
                "avg_score": round(summary.avg_score, 3),
                "pass_rate": round(summary.pass_rate, 3),
                "total_tokens": summary.total_tokens,
                "total_runtime_ms": summary.total_runtime_ms,
                "rating_before": round(old_rating.mu, 1),
                "rating_after": round(new_rating.mu, 1),
                "task_results": [r.to_dict() for r in summary.results],
            })

            # Print rank line
            pass_str = f"{summary.pass_rate:.0%}"
            delta_str = f"{'+' if rating_delta >= 0 else ''}{rating_delta:.1f}"
            print(
                f"  {rank:<5} {summary.agent_name[:29]:<30} "
                f"{summary.avg_score:.3f} {pass_str:>6} "
                f"{new_rating.mu:>8.1f} {delta_str:>7}"
            )

        # ── Step 8: Finalize tournament ───────────────────────────────────
        update_tournament(
            tournament_id,
            status="completed",
            baseline_avg=round(baseline_avg, 3),
            completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            total_cost_usd=round(total_cost, 4),
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
        )

        # ── Step 9: Save transcripts ──────────────────────────────────────
        _save_tournament_transcripts(tournament_id, summaries)

        print(f"\n  {'='*65}")
        print(f"  Tournament completed: {tournament_id}")
        print(f"  Cost: ${total_cost:.4f}")
        print(f"  Tokens: {total_input_tokens + total_output_tokens:,}")
        print(f"  {'='*65}\n")

    except Exception:
        update_tournament(tournament_id, status="failed")
        raise

    return tournament_id


# ── Legacy skill-based tournament ───────────────────────────────────────────


def _skill_to_parsed(skill) -> ParsedSkill | None:
    """Convert a DB Skill model to a ParsedSkill for the sandbox."""
    if not skill.raw_content:
        return None
    from evaluate.rubric import parse_skill_md
    return parse_skill_md(
        skill.raw_content,
        source_repo=skill.source_repo,
        source_url=skill.source_url,
    )


def _run_legacy_tournament(config: TournamentConfig) -> str:
    """Execute a legacy skill-based tournament for one category.

    Preserved for backward compatibility. New tournaments should use
    agent-native mode (field/role).

    Returns the tournament_id.
    """
    print(f"\n{'='*70}")
    print(f"  AgentArena Tournament (legacy): {config.category} — {config.week}")
    print(f"{'='*70}")

    # ── Step 1: Get skills for this category ─────────────────────────
    skills = list_skills_by_category(
        config.category, limit=config.max_skills,
    )
    if len(skills) < 2:
        raise ValueError(
            f"Need at least 2 skills in '{config.category}', "
            f"found {len(skills)}"
        )

    # Filter to skills that have raw_content (needed for execution)
    skill_map: dict[str, ParsedSkill] = {}
    for s in skills:
        parsed = _skill_to_parsed(s)
        if parsed:
            skill_map[s.id] = parsed

    if len(skill_map) < 2:
        raise ValueError(
            f"Need at least 2 skills with content in '{config.category}', "
            f"found {len(skill_map)}"
        )

    print(f"  Skills: {len(skill_map)} competing")

    # ── Step 2: Select tasks (rotate from pool) ─────────────────────
    prev_week = _get_previous_week(config.week)
    exclude_ids = _load_last_task_ids(config.category, prev_week)
    tasks = select_tasks(
        config.category,
        count=config.tasks_per_tournament,
        exclude_ids=exclude_ids,
    )

    if not tasks:
        raise ValueError(
            f"No tasks available for domain '{config.category}'"
        )

    task_ids = [t.id for t in tasks]
    print(f"  Tasks:  {len(tasks)} selected ({', '.join(task_ids)})")
    if exclude_ids:
        print(f"  Excluded from last week: {exclude_ids}")

    # ── Step 3: Create tournament record ─────────────────────────────
    tournament_id = create_tournament(
        config.category, config.week, task_ids,
    )

    try:
        update_tournament(
            tournament_id, status="running", num_skills=len(skill_map),
        )
        print(f"  Tournament ID: {tournament_id}")

        # ── Step 4: Run baselines (cached) ───────────────────────────────
        print(f"\n  Running baselines...")
        baseline_results: dict[str, WorkSampleResult] = {}
        for task in tasks:
            baseline_results[task.id] = load_or_run_baseline(task)

        baseline_scores = [r.overall for r in baseline_results.values()]
        baseline_avg = (
            sum(baseline_scores) / len(baseline_scores)
            if baseline_scores else 0
        )
        print(f"  Baseline avg: {baseline_avg:.3f}")

        # ── Step 5: Run each skill on all tasks ──────────────────────────
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0

        summaries: dict[str, AgentRunSummary] = {}

        for baseline in baseline_results.values():
            total_input_tokens += baseline.input_tokens
            total_output_tokens += baseline.output_tokens
            total_cost += _result_cost_usd(baseline)

        for skill_id, parsed_skill in skill_map.items():
            skill_obj = get_skill(skill_id)
            skill_name = skill_obj.name if skill_obj else parsed_skill.name
            print(f"\n  Skill: {skill_name}")

            summary = AgentRunSummary(
                version_id=skill_id, agent_name=skill_name,
            )

            for task in tasks:
                result = run_benchmark(
                    parsed_skill, task, runs=config.runs_per_task,
                )
                summary.results.append(result)
                summary.total_tokens += (
                    result.input_tokens + result.output_tokens
                )
                summary.total_runtime_ms += result.runtime_ms

                total_input_tokens += result.input_tokens
                total_output_tokens += result.output_tokens
                result_cost = _result_cost_usd(result)
                summary.total_cost_usd += result_cost
                total_cost += result_cost

            # Compute summary stats
            valid_results = [r for r in summary.results if not r.error]
            if valid_results:
                summary.avg_score = (
                    sum(r.overall for r in valid_results)
                    / len(valid_results)
                )
                summary.pass_rate = (
                    sum(1 for r in valid_results if r.passed)
                    / len(valid_results)
                )

            summaries[skill_id] = summary

        # ── Step 6: Update Glicko-2 ratings ──────────────────────────────
        print(f"\n  Updating Glicko-2 ratings...")

        current_ratings: dict[str, Rating] = {}
        for skill_id in summaries:
            db_rating = get_skill_rating(skill_id, config.category)
            if db_rating:
                current_ratings[skill_id] = Rating(
                    mu=db_rating["mu"],
                    rd=db_rating["rd"],
                    sigma=db_rating["sigma"],
                )
            else:
                current_ratings[skill_id] = Rating()

        score_map: dict[str, float] = {
            sid: summaries[sid].avg_score for sid in summaries
        }

        new_ratings = update_tournament_ratings(current_ratings, score_map)

        # ── Step 7: Rank and persist entries ─────────────────────────────
        ranked = sorted(
            summaries.items(),
            key=lambda item: item[1].avg_score,
            reverse=True,
        )

        print(f"\n  {'─'*60}")
        print(
            f"  {'Rank':<5} {'Skill':<30} {'Score':>7} "
            f"{'Pass':>6} {'Rating':>8} {'Delta':>7}"
        )
        print(f"  {'─'*60}")

        for rank, (skill_id, summary) in enumerate(ranked, 1):
            old_rating = current_ratings.get(skill_id, Rating())
            new_rating = new_ratings[skill_id]
            rating_delta = new_rating.mu - old_rating.mu

            db_rating = get_skill_rating(skill_id, config.category)
            tournaments_played = (
                (db_rating["tournaments_played"] + 1) if db_rating else 1
            )

            upsert_skill_rating(
                skill_id, config.category,
                mu=new_rating.mu,
                rd=new_rating.rd,
                sigma=new_rating.sigma,
                tournaments_played=tournaments_played,
                last_tournament_week=config.week,
            )

            add_rating_history(
                skill_id, config.category, config.week,
                mu=new_rating.mu,
                rd=new_rating.rd,
                rank=rank,
                avg_score=summary.avg_score,
            )

            add_tournament_entry(tournament_id, {
                "skill_id": skill_id,
                "skill_name": summary.agent_name,
                "rank": rank,
                "avg_score": round(summary.avg_score, 3),
                "pass_rate": round(summary.pass_rate, 3),
                "total_tokens": summary.total_tokens,
                "total_runtime_ms": summary.total_runtime_ms,
                "rating_before": round(old_rating.mu, 1),
                "rating_after": round(new_rating.mu, 1),
                "task_results": [r.to_dict() for r in summary.results],
            })

            pass_str = f"{summary.pass_rate:.0%}"
            delta_str = f"{'+' if rating_delta >= 0 else ''}{rating_delta:.1f}"
            print(
                f"  {rank:<5} {summary.agent_name[:29]:<30} "
                f"{summary.avg_score:.3f} {pass_str:>6} "
                f"{new_rating.mu:>8.1f} {delta_str:>7}"
            )

        # ── Step 8: Finalize tournament ──────────────────────────────────
        update_tournament(
            tournament_id,
            status="completed",
            baseline_avg=round(baseline_avg, 3),
            completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            total_cost_usd=round(total_cost, 4),
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
        )

        print(f"\n  {'='*60}")
        print(f"  Tournament completed: {tournament_id}")
        print(f"  Cost: ${total_cost:.4f}")
        print(f"  Tokens: {total_input_tokens + total_output_tokens:,}")
        print(f"  {'='*60}\n")

    except Exception:
        update_tournament(tournament_id, status="failed")
        raise

    return tournament_id
