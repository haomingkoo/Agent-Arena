from __future__ import annotations

from fastapi.testclient import TestClient

from agents.contracts import (
    EligibilityState,
    PackagingType,
    ProvenanceRef,
    RunnerContract,
)
from store.models import AgentProfile, AgentVersion, ArtifactRecord, RunTrace, Skill


def _seed_agent_version(
    db_setup,
    *,
    name: str,
    field: str,
    role: str,
    source_url: str,
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
                version_id="",
                source_url=source_url,
                packaging_type=PackagingType.markdown_prompt_bundle,
                system_instructions=f"System instructions for {name}.",
                model_provider="anthropic",
                model_name="claude-haiku",
                max_input_tokens=1000,
                max_output_tokens=800,
                max_total_tokens=2200,
                allowed_tools=["rg"],
            ),
            eligibility=EligibilityState.eligible,
        )
    )
    return version_id


def test_agents_fields_endpoint_groups_fields_roles(db_setup):
    from api import app as api_app

    _seed_agent_version(
        db_setup,
        name="Agent Alpha",
        field="software-engineering",
        role="software-engineer-agent",
        source_url="https://example.com/alpha",
    )
    _seed_agent_version(
        db_setup,
        name="Verifier One",
        field="semiconductor",
        role="verification-debug-agent",
        source_url="https://example.com/verifier",
    )
    db_setup.create_tournament(
        "software-engineering/software-engineer-agent",
        "2026-W12",
        ["task-1"],
        field="software-engineering",
        role="software-engineer-agent",
        runtime_class="standard-v1",
        task_pack_version="v2",
        tournament_type="standardized",
    )

    with TestClient(api_app.app) as client:
        response = client.get("/api/agents/fields")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    fields = {row["field"]: row for row in payload["fields"]}
    assert fields["software-engineering"]["total_agents"] == 1
    software_role = fields["software-engineering"]["roles"][0]
    assert software_role["role"] == "software-engineer-agent"
    assert software_role["runtime_class"] == "standard-v1"
    assert software_role["task_pack_version"] == "v2"
    assert software_role["tournament_type"] == "standardized"
    assert fields["semiconductor"]["roles"][0]["role"] == "verification-debug-agent"


def test_agent_leaderboard_endpoint_returns_ranked_versions(db_setup):
    from api import app as api_app

    alpha_id = _seed_agent_version(
        db_setup,
        name="Agent Alpha",
        field="software-engineering",
        role="software-engineer-agent",
        source_url="https://example.com/alpha",
    )
    beta_id = _seed_agent_version(
        db_setup,
        name="Agent Beta",
        field="software-engineering",
        role="software-engineer-agent",
        source_url="https://example.com/beta",
    )
    db_setup.upsert_skill_rating(
        alpha_id,
        "software-engineering/software-engineer-agent",
        mu=1620,
        rd=80,
        sigma=0.06,
        tournaments_played=3,
        last_tournament_week="2026-W12",
    )
    db_setup.upsert_skill_rating(
        beta_id,
        "software-engineering/software-engineer-agent",
        mu=1510,
        rd=95,
        sigma=0.06,
        tournaments_played=2,
        last_tournament_week="2026-W12",
    )
    db_setup.create_tournament(
        "software-engineering/software-engineer-agent",
        "2026-W12",
        ["task-1"],
        field="software-engineering",
        role="software-engineer-agent",
        runtime_class="standard-v1",
        task_pack_version="v2",
        tournament_type="standardized",
    )

    with TestClient(api_app.app) as client:
        response = client.get(
            "/api/agents/leaderboard/software-engineering/software-engineer-agent"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["runtime_class"] == "standard-v1"
    assert payload["task_pack_version"] == "v2"
    assert payload["tournament_type"] == "standardized"
    assert payload["leaderboard"][0]["version_id"] == alpha_id
    assert payload["leaderboard"][0]["agent_name"] == "Agent Alpha"
    assert payload["leaderboard"][1]["version_id"] == beta_id


def test_agent_detail_endpoint_includes_recent_traces(db_setup):
    from api import app as api_app

    version_id = _seed_agent_version(
        db_setup,
        name="Agent Alpha",
        field="software-engineering",
        role="software-engineer-agent",
        source_url="https://example.com/alpha",
    )
    db_setup.upsert_skill_rating(
        version_id,
        "software-engineering/software-engineer-agent",
        mu=1605,
        rd=88,
        sigma=0.06,
        tournaments_played=1,
        last_tournament_week="2026-W12",
    )
    db_setup.create_tournament(
        "software-engineering/software-engineer-agent",
        "2026-W12",
        ["task-1"],
        field="software-engineering",
        role="software-engineer-agent",
        runtime_class="standard-v1",
        task_pack_version="v2",
        tournament_type="standardized",
    )
    trace_id = db_setup.add_run_trace(
        RunTrace(
            agent_version_id=version_id,
            field="software-engineering",
            role="software-engineer-agent",
            tournament_id="tour-1",
            tournament_run_id="tour-1:alpha",
            task_id="task-1",
            trace_kind="benchmark",
            status="completed",
            exec_provider="anthropic",
            judge_provider="gemini",
            final_output="Looks good",
            input_tokens=20,
            output_tokens=30,
            total_cost_usd=0.12,
            runtime_ms=456,
            prompt_json='{"exec_prompt":"prompt"}',
            tool_calls_json="[]",
            tool_outputs_json="[]",
            judge_prompt="judge prompt",
            judge_output='{"passed": true}',
            metadata_json='{"overall": 0.9}',
        )
    )

    with TestClient(api_app.app) as client:
        response = client.get(f"/api/agents/{version_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == version_id
    assert payload["profile_name"] == "Agent Alpha"
    assert payload["runtime_class"] == "standard-v1"
    assert payload["task_pack_version"] == "v2"
    assert payload["tournament_type"] == "standardized"
    assert payload["rating"]["mu"] == 1605
    assert payload["recent_traces"][0]["id"] == trace_id
    assert payload["recent_traces"][0]["task_id"] == "task-1"
    assert payload["recent_traces"][0]["trace_kind"] == "benchmark"


def test_trace_detail_endpoint_returns_trace_payload(db_setup):
    from api import app as api_app

    version_id = _seed_agent_version(
        db_setup,
        name="Agent Alpha",
        field="software-engineering",
        role="software-engineer-agent",
        source_url="https://example.com/alpha",
    )
    tournament_id = db_setup.create_tournament(
        "software-engineering/software-engineer-agent",
        "2026-W12",
        ["task-2"],
        field="software-engineering",
        role="software-engineer-agent",
        runtime_class="standard-v1",
        task_pack_version="v2",
        tournament_type="standardized",
    )
    trace_id = db_setup.add_run_trace(
        RunTrace(
            agent_version_id=version_id,
            field="software-engineering",
            role="software-engineer-agent",
            tournament_id=tournament_id,
            tournament_run_id="tour-1:alpha",
            task_id="task-2",
            trace_kind="benchmark",
            status="completed",
            exec_provider="anthropic",
            judge_provider="gemini",
            final_output="Detailed answer",
            input_tokens=11,
            output_tokens=13,
            total_cost_usd=0.08,
            runtime_ms=210,
            prompt_json='{"exec_prompt":"prompt"}',
            tool_calls_json="[]",
            tool_outputs_json="[]",
            judge_prompt="judge prompt",
            judge_output='{"passed": true}',
            metadata_json='{"overall": 0.8}',
        )
    )

    with TestClient(api_app.app) as client:
        response = client.get(f"/api/traces/{trace_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace"]["id"] == trace_id
    assert payload["trace"]["runtime_class"] == "standard-v1"
    assert payload["trace"]["task_pack_version"] == "v2"
    assert payload["trace"]["tournament_type"] == "standardized"
    assert payload["trace"]["final_output"] == "Detailed answer"


def test_legacy_skill_endpoints_return_deprecation_headers(db_setup):
    from api import app as api_app

    skill_id = db_setup.add_skill(
        Skill(
            name="Legacy Skill",
            raw_content="# Legacy Skill",
            instructions="Do the thing.",
            source_repo="legacy/repo",
            source_url="https://example.com/legacy",
        )
    )
    db_setup.upsert_skill_rating(
        skill_id,
        "code-review",
        mu=1500,
        rd=100,
        sigma=0.06,
        tournaments_played=1,
        last_tournament_week="2026-W12",
    )
    db_setup.add_rating_history(
        skill_id,
        "code-review",
        "2026-W12",
        mu=1500,
        rd=100,
        rank=1,
        avg_score=0.7,
    )

    with TestClient(api_app.app) as client:
        detail_response = client.get("/api/skill/Legacy%20Skill")
        history_response = client.get(
            f"/api/skill/{skill_id}/rating-history?category=code-review"
        )

    for response in (detail_response, history_response):
        assert response.status_code == 200
        assert response.headers["deprecation"] == "true"
        assert response.headers["sunset"] == "2026-12-31"
        assert '/api/agents/fields' in response.headers["link"]
