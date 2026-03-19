from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from agents.contracts import (
    EligibilityState,
    PackagingType,
    ProvenanceRef,
    RunnerContract,
)
from evaluate.sandbox import BenchmarkJob, WorkSampleResult
from store.models import AgentProfile, AgentVersion, ArtifactRecord
from store.db import create_corpus_version, upsert_jd_posting
from tournament.runner import TournamentConfig, run_tournament


def _add_ready_agent(
    db_setup,
    *,
    name: str,
    source_url: str,
    field: str = "software-engineering",
    role: str = "code-review-agent",
) -> str:
    profile_id = db_setup.add_agent_profile(
        AgentProfile(
            name=name,
            field=field,
            role=role,
            source_url=source_url,
            packaging_type=PackagingType.markdown_prompt_bundle,
        )
    )
    artifact_id = db_setup.add_artifact_record(
        ArtifactRecord(
            packaging_type=PackagingType.markdown_prompt_bundle,
            source_type="github",
            source_url=source_url,
            raw_content=f"# {name}",
            sanitized_content=f"Review code carefully as {name}.",
            content_hash=f"hash-{name}",
        )
    )
    version_id = db_setup.add_agent_version(
        AgentVersion(
            profile_id=profile_id,
            version_label="v1",
            packaging_type=PackagingType.markdown_prompt_bundle,
            provenance=ProvenanceRef(
                source_type="github",
                source_url=source_url,
            ),
            artifact_id=artifact_id,
            runner_contract=RunnerContract(
                field=field,
                role=role,
                profile_name=name,
                packaging_type=PackagingType.markdown_prompt_bundle,
                system_instructions=f"Review code carefully as {name}.",
                model_provider="anthropic",
                model_name="claude-haiku",
                max_input_tokens=1000,
                max_output_tokens=800,
                max_total_tokens=2200,
                allowed_tools=["rg", "pytest"],
            ),
            eligibility=EligibilityState.eligible,
        )
    )
    return version_id


def _seed_jd_corpus(field: str, role: str) -> None:
    upsert_jd_posting({
        "source_ats": "greenhouse",
        "source_board_id": f"{role}-job-1",
        "company_name": "TestCorp",
        "title": "Software Engineer",
        "content": "Build, debug, test, and maintain production systems.",
        "content_hash": f"jd-{field}-{role}",
        "field": field,
        "role": role,
    })
    create_corpus_version(
        field=field,
        role=role,
        version_label="2026-W13",
        posting_count=1,
        company_count=1,
        source_mix={"greenhouse": 1},
    )


def _fake_result(
    *,
    job_id: str,
    agent_name: str,
    overall: float,
    passed: bool,
    exec_provider: str = "anthropic",
    exec_model: str = "claude-haiku",
    exec_in: int = 10,
    exec_out: int = 20,
    judge_in: int = 5,
    judge_out: int = 8,
) -> WorkSampleResult:
    result = WorkSampleResult(
        job_id=job_id,
        skill_name=agent_name,
        raw_output=f"{agent_name} output for {job_id}",
        runtime_ms=321,
        exec_input_tokens=exec_in,
        exec_output_tokens=exec_out,
        judge_input_tokens=judge_in,
        judge_output_tokens=judge_out,
        passed=passed,
        correctness=overall,
        safety=overall,
        completeness=overall,
        quality=overall,
        overall=overall,
        verdict=f"{agent_name} scored {overall}",
        criteria_results=[{"criterion": "x", "met": passed, "reason": "ok"}],
        judge_reasoning="solid review",
        judge_provider="gemini",
        exec_provider=exec_provider,
        exec_model=exec_model,
        judge_model="gemini-2.5-flash",
        exec_prompt=f"exec prompt {agent_name} {job_id}",
        judge_prompt=f"judge prompt {job_id}",
        judge_raw_response='{"passed": true}',
    )
    result.sync_token_totals()
    return result


def test_run_tournament_agent_native_persists_entries_and_traces(db_setup):
    alpha_version_id = _add_ready_agent(
        db_setup,
        name="Agent Alpha",
        source_url="https://example.com/alpha",
    )
    beta_version_id = _add_ready_agent(
        db_setup,
        name="Agent Beta",
        source_url="https://example.com/beta",
    )
    jobs = [
        BenchmarkJob(
            id="task-1",
            name="Task 1",
            category="review",
            input_prompt="Review task 1",
            input_context="diff 1",
            acceptance_criteria=["find issue 1"],
            skill_domain="code-review-agent",
        ),
        BenchmarkJob(
            id="task-2",
            name="Task 2",
            category="review",
            input_prompt="Review task 2",
            input_context="diff 2",
            acceptance_criteria=["find issue 2"],
            skill_domain="code-review-agent",
        ),
    ]

    def fake_execute(contract, job):
        if contract.profile_name == "Agent Alpha":
            return _fake_result(
                job_id=job.id,
                agent_name=contract.profile_name,
                overall=0.9,
                passed=True,
            )
        return _fake_result(
            job_id=job.id,
            agent_name=contract.profile_name,
            overall=0.6,
            passed=False,
        )

    def fake_baseline(job):
        return _fake_result(
            job_id=job.id,
            agent_name="(no skill)",
            overall=0.4,
            passed=False,
            exec_in=4,
            exec_out=6,
            judge_in=3,
            judge_out=4,
        )

    with patch("tournament.runner.select_task_pack_jobs", return_value=jobs), patch(
        "tournament.runner.select_holdout_jobs",
        return_value=[],
    ), patch(
        "tournament.runner.execute_agent_on_task",
        side_effect=fake_execute,
    ), patch(
        "tournament.runner.load_or_run_baseline",
        side_effect=fake_baseline,
    ), patch(
        "tournament.runner._save_tournament_transcripts",
        return_value=None,
    ):
        tournament_id = run_tournament(
            TournamentConfig(
                field="software-engineering",
                role="code-review-agent",
                week="2026-W12",
                tasks_per_tournament=2,
                task_pack_version="v1",
                max_agents=10,
            )
        )

    tournament = db_setup.get_tournament(tournament_id)
    entries = db_setup.get_tournament_entries(tournament_id)
    traces = db_setup.list_run_traces(tournament_id=tournament_id, limit=10)
    leaderboard = db_setup.get_agent_leaderboard(
        "software-engineering",
        "code-review-agent",
    )
    alpha_detail = db_setup.get_agent_version_detail(alpha_version_id)

    assert tournament is not None
    assert tournament["category"] == "software-engineering/code-review-agent"
    assert tournament["status"] == "completed"
    assert tournament["num_skills"] == 2
    assert tournament["runtime_class"] == "standard"
    assert tournament["task_pack_version"] == "v1"
    assert tournament["tournament_type"] == "standardized"
    assert len(entries) == 2
    assert entries[0]["skill_id"] == alpha_version_id
    assert entries[0]["skill_name"] == "Agent Alpha"
    assert entries[0]["rank"] == 1
    assert entries[1]["skill_id"] == beta_version_id
    assert len(traces) == 4
    assert {trace.agent_version_id for trace in traces} == {
        alpha_version_id,
        beta_version_id,
    }
    assert all(trace.tournament_id == tournament_id for trace in traces)
    assert all(trace.trace_kind == "benchmark" for trace in traces)
    assert all(json.loads(trace.metadata_json)["overall"] in {0.9, 0.6} for trace in traces)
    assert leaderboard[0]["version_id"] == alpha_version_id
    assert leaderboard[1]["version_id"] == beta_version_id
    assert alpha_detail is not None
    assert alpha_detail["runtime_class"] == "standard"
    assert alpha_detail["task_pack_version"] == "v1"
    assert alpha_detail["tournament_type"] == "standardized"
    assert len(alpha_detail["recent_traces"]) == 2
    assert {
        trace["task_id"] for trace in alpha_detail["recent_traces"]
    } == {"task-1", "task-2"}


def test_standardized_tournament_runs_holdout_validation_without_affecting_rankings(
    db_setup,
):
    alpha_version_id = _add_ready_agent(
        db_setup,
        name="Agent Alpha",
        source_url="https://example.com/alpha",
    )
    beta_version_id = _add_ready_agent(
        db_setup,
        name="Agent Beta",
        source_url="https://example.com/beta",
    )
    public_jobs = [
        BenchmarkJob(
            id="task-1",
            name="Task 1",
            category="review",
            input_prompt="Review task 1",
            input_context="diff 1",
            acceptance_criteria=["find issue 1"],
            skill_domain="code-review-agent",
        ),
        BenchmarkJob(
            id="task-2",
            name="Task 2",
            category="review",
            input_prompt="Review task 2",
            input_context="diff 2",
            acceptance_criteria=["find issue 2"],
            skill_domain="code-review-agent",
        ),
    ]
    holdout_jobs = [
        BenchmarkJob(
            id="holdout-1",
            name="Holdout 1",
            category="review",
            input_prompt="Review holdout",
            input_context="hidden diff",
            acceptance_criteria=["find hidden issue"],
            skill_domain="code-review-agent",
            task_bucket="holdout",
        )
    ]

    def fake_execute(contract, job):
        if job.id == "holdout-1":
            overall = 0.2 if contract.profile_name == "Agent Alpha" else 0.95
            passed = contract.profile_name == "Agent Beta"
        else:
            overall = 0.9 if contract.profile_name == "Agent Alpha" else 0.6
            passed = contract.profile_name == "Agent Alpha"
        return _fake_result(
            job_id=job.id,
            agent_name=contract.profile_name,
            overall=overall,
            passed=passed,
        )

    with patch(
        "tournament.runner.select_task_pack_jobs",
        return_value=public_jobs,
    ), patch(
        "tournament.runner.select_holdout_jobs",
        return_value=holdout_jobs,
    ), patch(
        "tournament.runner.execute_agent_on_task",
        side_effect=fake_execute,
    ), patch(
        "tournament.runner.load_or_run_baseline",
        side_effect=lambda job: _fake_result(
            job_id=job.id,
            agent_name="(no skill)",
            overall=0.4,
            passed=False,
            exec_in=4,
            exec_out=6,
            judge_in=3,
            judge_out=4,
        ),
    ), patch(
        "tournament.runner._save_tournament_transcripts",
        return_value=None,
    ):
        tournament_id = run_tournament(
            TournamentConfig(
                field="software-engineering",
                role="code-review-agent",
                week="2026-W14",
                tasks_per_tournament=2,
                task_pack_version="v1",
                max_agents=10,
            )
        )

    entries = db_setup.get_tournament_entries(tournament_id)
    traces = db_setup.list_run_traces(tournament_id=tournament_id, limit=20)
    leaderboard = db_setup.get_agent_leaderboard(
        "software-engineering",
        "code-review-agent",
    )

    assert len(entries) == 2
    assert entries[0]["skill_id"] == alpha_version_id
    assert entries[1]["skill_id"] == beta_version_id
    assert all(len(json.loads(entry["task_results_json"])) == 2 for entry in entries)
    assert len(traces) == 6
    assert sum(1 for trace in traces if trace.trace_kind == "benchmark") == 4
    assert sum(1 for trace in traces if trace.trace_kind == "holdout") == 2
    holdout_trace_ids = {trace.task_id for trace in traces if trace.trace_kind == "holdout"}
    assert holdout_trace_ids == {"holdout-1"}
    assert leaderboard[0]["version_id"] == alpha_version_id
    assert leaderboard[1]["version_id"] == beta_version_id


def test_non_standardized_tournament_does_not_update_public_ratings(db_setup):
    _add_ready_agent(
        db_setup,
        name="Agent Alpha",
        source_url="https://example.com/alpha",
    )
    _add_ready_agent(
        db_setup,
        name="Agent Beta",
        source_url="https://example.com/beta",
    )
    jobs = [
        BenchmarkJob(
            id="task-1",
            name="Task 1",
            category="review",
            input_prompt="Review task 1",
            input_context="diff 1",
            acceptance_criteria=["find issue 1"],
            skill_domain="code-review-agent",
        ),
        BenchmarkJob(
            id="task-2",
            name="Task 2",
            category="review",
            input_prompt="Review task 2",
            input_context="diff 2",
            acceptance_criteria=["find issue 2"],
            skill_domain="code-review-agent",
        ),
    ]

    with patch("tournament.runner.select_task_pack_jobs", return_value=jobs), patch(
        "tournament.runner.select_holdout_jobs",
        return_value=[],
    ), patch(
        "tournament.runner.execute_agent_on_task",
        side_effect=lambda contract, job: _fake_result(
            job_id=job.id,
            agent_name=contract.profile_name,
            overall=0.8 if contract.profile_name == "Agent Alpha" else 0.5,
            passed=contract.profile_name == "Agent Alpha",
        ),
    ), patch(
        "tournament.runner.load_or_run_baseline",
        side_effect=lambda job: _fake_result(
            job_id=job.id,
            agent_name="(no skill)",
            overall=0.4,
            passed=False,
            exec_in=4,
            exec_out=6,
            judge_in=3,
            judge_out=4,
        ),
    ), patch(
        "tournament.runner._save_tournament_transcripts",
        return_value=None,
    ):
        tournament_id = run_tournament(
            TournamentConfig(
                field="software-engineering",
                role="code-review-agent",
                week="2026-W13",
                tasks_per_tournament=2,
                task_pack_version="v1",
                max_agents=10,
                tournament_type="native",
            )
        )

    tournament = db_setup.get_tournament(tournament_id)
    leaderboard = db_setup.get_agent_leaderboard(
        "software-engineering",
        "code-review-agent",
    )

    assert tournament is not None
    assert tournament["tournament_type"] == "native"
    assert leaderboard == []


def test_tournament_persists_effective_exec_provider_from_result(db_setup):
    _add_ready_agent(
        db_setup,
        name="Agent Alpha",
        source_url="https://example.com/alpha",
    )
    _add_ready_agent(
        db_setup,
        name="Agent Beta",
        source_url="https://example.com/beta",
    )
    jobs = [
        BenchmarkJob(
            id="task-1",
            name="Task 1",
            category="review",
            input_prompt="Review task 1",
            input_context="diff 1",
            acceptance_criteria=["find issue 1"],
            skill_domain="code-review-agent",
        ),
    ]

    with patch("tournament.runner.select_task_pack_jobs", return_value=jobs), patch(
        "tournament.runner.select_holdout_jobs",
        return_value=[],
    ), patch(
        "tournament.runner.execute_agent_on_task",
        side_effect=lambda contract, job: _fake_result(
            job_id=job.id,
            agent_name=contract.profile_name,
            overall=0.8,
            passed=True,
            exec_provider="qwen",
            exec_model="qwen-plus",
        ),
    ), patch(
        "tournament.runner.load_or_run_baseline",
        side_effect=lambda job: _fake_result(
            job_id=job.id,
            agent_name="(no skill)",
            overall=0.4,
            passed=False,
            exec_provider="anthropic",
            exec_model="claude-haiku",
            exec_in=4,
            exec_out=6,
            judge_in=3,
            judge_out=4,
        ),
    ), patch(
        "tournament.runner._save_tournament_transcripts",
        return_value=None,
    ):
        tournament_id = run_tournament(
            TournamentConfig(
                field="software-engineering",
                role="code-review-agent",
                week="2026-W15",
                tasks_per_tournament=1,
                task_pack_version="v1",
                max_agents=10,
            )
        )

    traces = db_setup.list_run_traces(tournament_id=tournament_id, limit=10)

    assert len(traces) == 2
    assert {trace.exec_provider for trace in traces} == {"qwen"}


def test_standardized_swe_tournament_requires_live_jd_corpus(db_setup):
    _add_ready_agent(
        db_setup,
        name="SWE Alpha",
        source_url="https://example.com/swe-alpha",
        role="software-engineer-agent",
    )
    _add_ready_agent(
        db_setup,
        name="SWE Beta",
        source_url="https://example.com/swe-beta",
        role="software-engineer-agent",
    )

    with pytest.raises(ValueError, match="requires a live JD corpus"):
        run_tournament(
            TournamentConfig(
                field="software-engineering",
                role="software-engineer-agent",
                week="2026-W16",
                tasks_per_tournament=1,
                max_agents=10,
                task_pack_version="v2",
            )
        )


def test_standardized_swe_tournament_runs_when_jd_corpus_exists(db_setup):
    _seed_jd_corpus("software-engineering", "software-engineer-agent")
    _add_ready_agent(
        db_setup,
        name="SWE Alpha",
        source_url="https://example.com/swe-alpha",
        role="software-engineer-agent",
    )
    _add_ready_agent(
        db_setup,
        name="SWE Beta",
        source_url="https://example.com/swe-beta",
        role="software-engineer-agent",
    )
    jobs = [
        BenchmarkJob(
            id="swe-task-1",
            name="Task 1",
            category="software-engineering",
            input_prompt="Implement a feature",
            input_context="spec",
            acceptance_criteria=["works"],
            skill_domain="software-engineer-agent",
        ),
    ]

    with patch("tournament.runner.select_task_pack_jobs", return_value=jobs), patch(
        "tournament.runner.select_holdout_jobs",
        return_value=[],
    ), patch(
        "tournament.runner.execute_agent_on_task",
        side_effect=lambda contract, job: _fake_result(
            job_id=job.id,
            agent_name=contract.profile_name,
            overall=0.8 if contract.profile_name == "SWE Alpha" else 0.6,
            passed=contract.profile_name == "SWE Alpha",
        ),
    ), patch(
        "tournament.runner.load_or_run_baseline",
        side_effect=lambda job: _fake_result(
            job_id=job.id,
            agent_name="(no skill)",
            overall=0.4,
            passed=False,
            exec_in=4,
            exec_out=6,
            judge_in=3,
            judge_out=4,
        ),
    ), patch(
        "tournament.runner._save_tournament_transcripts",
        return_value=None,
    ):
        tournament_id = run_tournament(
            TournamentConfig(
                field="software-engineering",
                role="software-engineer-agent",
                week="2026-W17",
                tasks_per_tournament=1,
                task_pack_version="v1",
                max_agents=10,
            )
        )

    tournament = db_setup.get_tournament(tournament_id)
    assert tournament is not None
    assert tournament["category"] == "software-engineering/software-engineer-agent"
