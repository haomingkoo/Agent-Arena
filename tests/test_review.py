"""Tests for human review backend and JD corpus persistence."""
from __future__ import annotations

import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from agents.contracts import EligibilityState, ReviewState
from store.db import (
    _conn,
    apply_review_decision,
    create_corpus_version,
    get_jd_corpus_stats,
    get_latest_corpus_version,
    get_review_candidate_detail,
    get_review_history,
    init_db,
    list_jd_postings,
    list_review_queue,
    upsert_jd_posting,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Use a fresh temp DB for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("store.db.DB_PATH", db_path)
    init_db()


def _insert_test_agent(
    name: str = "test-agent",
    field: str = "software-engineering",
    role: str = "code-review-agent",
    eligibility: str = "pending",
    review_state: str = "pending-review",
) -> tuple[str, str]:
    """Insert a test agent profile + version, return (profile_id, version_id)."""
    conn = _conn()
    profile_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    conn.execute(
        "INSERT INTO agent_profiles (id, name, field, role, packaging_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (profile_id, name, field, role, "markdown_prompt_bundle"),
    )

    contract = json.dumps({
        "field": field,
        "role": role,
        "profile_name": name,
        "version_id": version_id,
        "source_url": "https://example.com",
        "packaging_type": "markdown_prompt_bundle",
        "system_instructions": "You are a test agent.",
        "model_provider": "qwen",
        "model_name": "qwen-plus",
        "max_steps": 8,
        "timeout_seconds": 120,
        "max_total_tokens": 10000,
    })

    conn.execute(
        "INSERT INTO agent_versions "
        "(id, profile_id, version_label, packaging_type, eligibility, "
        " review_state, runner_contract_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (version_id, profile_id, "v1", "markdown_prompt_bundle",
         eligibility, review_state, contract),
    )
    conn.commit()
    conn.close()
    return profile_id, version_id


# ── Review Queue Tests ──────────────────────────────────────────────


class TestReviewQueue:
    def test_empty_queue(self):
        result = list_review_queue()
        assert result == []

    def test_lists_pending_review_candidates(self):
        _insert_test_agent("agent-a", review_state="pending-review")
        _insert_test_agent("agent-b", review_state="approved-public")

        pending = list_review_queue(review_state="pending-review")
        assert len(pending) == 1
        assert pending[0]["profile_name"] == "agent-a"

    def test_filters_by_field_and_role(self):
        _insert_test_agent("cr-agent", field="software-engineering", role="code-review-agent")
        _insert_test_agent("semi-agent", field="semiconductor", role="verification-debug-agent")

        cr = list_review_queue(field="software-engineering")
        assert len(cr) == 1
        assert cr[0]["profile_name"] == "cr-agent"

    def test_returns_review_metadata(self):
        _insert_test_agent("agent-x", review_state="pending-review")

        queue = list_review_queue()
        assert len(queue) == 1
        candidate = queue[0]
        assert "review_state" in candidate
        assert "predicted_field" in candidate
        assert "predicted_role" in candidate
        assert "jd_fit_score" in candidate
        assert "manual_review_required" in candidate


# ── Review Candidate Detail Tests ───────────────────────────────────


class TestReviewCandidateDetail:
    def test_returns_none_for_missing(self):
        assert get_review_candidate_detail("nonexistent") is None

    def test_returns_detail_with_review_history(self):
        _, vid = _insert_test_agent("detail-agent")
        detail = get_review_candidate_detail(vid)

        assert detail is not None
        assert detail["profile_name"] == "detail-agent"
        assert "review_history" in detail
        assert detail["review_history"] == []


# ── Review Decision Tests ───────────────────────────────────────────


class TestApplyReviewDecision:
    def test_approve_sets_eligible(self):
        _, vid = _insert_test_agent("approve-me", eligibility="pending")

        decision_id = apply_review_decision(
            version_id=vid,
            reviewer="koo",
            action="approve",
            new_state="approved-public",
            reason="Looks good",
        )
        assert decision_id

        conn = _conn()
        row = conn.execute(
            "SELECT eligibility, review_state, reviewed_by FROM agent_versions WHERE id = ?",
            (vid,),
        ).fetchone()
        conn.close()

        assert row["eligibility"] == "eligible"
        assert row["review_state"] == "approved-public"
        assert row["reviewed_by"] == "koo"

    def test_reject_sets_ineligible(self):
        _, vid = _insert_test_agent("reject-me", eligibility="pending")

        apply_review_decision(
            version_id=vid,
            reviewer="koo",
            action="reject",
            new_state="rejected",
            reason="Not a code reviewer",
        )

        conn = _conn()
        row = conn.execute(
            "SELECT eligibility, review_state, ineligibility_reason FROM agent_versions WHERE id = ?",
            (vid,),
        ).fetchone()
        conn.close()

        assert row["eligibility"] == "ineligible"
        assert row["review_state"] == "rejected"
        assert "Not a code reviewer" in row["ineligibility_reason"]

    def test_relabel_updates_profile_role(self):
        pid, vid = _insert_test_agent(
            "relabel-me", field="software-engineering", role="software-engineer-agent",
        )

        apply_review_decision(
            version_id=vid,
            reviewer="koo",
            action="relabel",
            new_state="relabelled",
            reason="Actually a code reviewer",
            new_role="code-review-agent",
        )

        conn = _conn()
        profile = conn.execute(
            "SELECT field, role FROM agent_profiles WHERE id = ?", (pid,)
        ).fetchone()
        conn.close()

        assert profile["role"] == "code-review-agent"
        assert profile["field"] == "software-engineering"

    def test_review_history_persists_immutable(self):
        _, vid = _insert_test_agent("history-test")

        apply_review_decision(
            version_id=vid,
            reviewer="koo",
            action="approve",
            new_state="approved-public",
            reason="First review",
        )
        apply_review_decision(
            version_id=vid,
            reviewer="koo",
            action="reject",
            new_state="rejected",
            reason="Changed my mind",
        )

        history = get_review_history(vid)
        assert len(history) == 2
        # Newest first
        assert history[0]["action"] == "reject"
        assert history[0]["previous_state"] == "approved-public"
        assert history[1]["action"] == "approve"
        assert history[1]["previous_state"] == "pending-review"

    def test_send_to_qualification(self):
        _, vid = _insert_test_agent("qual-me")

        apply_review_decision(
            version_id=vid,
            reviewer="koo",
            action="send-to-qualification",
            new_state="qualification-required",
            reason="Need to test role fit",
        )

        conn = _conn()
        row = conn.execute(
            "SELECT review_state FROM agent_versions WHERE id = ?", (vid,)
        ).fetchone()
        conn.close()

        assert row["review_state"] == "qualification-required"

    def test_raises_for_missing_version(self):
        with pytest.raises(ValueError, match="not found"):
            apply_review_decision(
                version_id="nonexistent",
                reviewer="koo",
                action="approve",
                new_state="approved-public",
            )

    def test_rejected_candidate_excluded_from_benchmark_ready(self):
        """Rejected candidate must not appear in benchmark-ready pool."""
        from store.db import list_benchmark_ready_agents

        _, vid = _insert_test_agent("reject-pool-test", eligibility="eligible")

        # Should appear before rejection
        before = list_benchmark_ready_agents(
            field="software-engineering", role="code-review-agent",
        )
        assert any(a["version_id"] == vid for a in before)

        # Reject
        apply_review_decision(
            version_id=vid,
            reviewer="koo",
            action="reject",
            new_state="rejected",
            reason="Test rejection",
        )

        # Should not appear after rejection
        after = list_benchmark_ready_agents(
            field="software-engineering", role="code-review-agent",
        )
        assert not any(a["version_id"] == vid for a in after)


# ── JD Corpus Persistence Tests ─────────────────────────────────────


class TestJDCorpus:
    def test_upsert_and_list_postings(self):
        pid = upsert_jd_posting({
            "source_ats": "greenhouse",
            "source_board_id": "job-123",
            "company_name": "TestCorp",
            "title": "Senior Software Engineer",
            "content": "Build distributed systems...",
            "content_hash": "abc123",
            "field": "software-engineering",
            "role": "software-engineer-agent",
        })
        assert pid

        postings = list_jd_postings(field="software-engineering")
        assert len(postings) == 1
        assert postings[0]["company_name"] == "TestCorp"
        assert postings[0]["title"] == "Senior Software Engineer"

    def test_dedup_by_content_hash(self):
        """Duplicate postings by source+hash should not create duplicates."""
        for _ in range(3):
            upsert_jd_posting({
                "source_ats": "greenhouse",
                "source_board_id": "job-456",
                "company_name": "DupCorp",
                "title": "Engineer",
                "content": "Same content",
                "content_hash": "same-hash",
                "field": "software-engineering",
                "role": "code-review-agent",
            })

        postings = list_jd_postings(role="code-review-agent")
        assert len(postings) == 1

    def test_filter_by_source_ats(self):
        upsert_jd_posting({
            "source_ats": "greenhouse",
            "source_board_id": "g-1",
            "company_name": "GreenCorp",
            "title": "SWE",
            "content": "content-g",
            "content_hash": "hash-g",
            "field": "software-engineering",
            "role": "software-engineer-agent",
        })
        upsert_jd_posting({
            "source_ats": "lever",
            "source_board_id": "l-1",
            "company_name": "LeverCorp",
            "title": "SWE",
            "content": "content-l",
            "content_hash": "hash-l",
            "field": "software-engineering",
            "role": "software-engineer-agent",
        })

        gh = list_jd_postings(source_ats="greenhouse")
        assert len(gh) == 1
        assert gh[0]["company_name"] == "GreenCorp"

    def test_corpus_version_creation(self):
        vid = create_corpus_version(
            field="software-engineering",
            role="code-review-agent",
            version_label="2026-W12",
            posting_count=15,
            company_count=8,
            source_mix={"greenhouse": 5, "lever": 5, "ashby": 5},
        )
        assert vid

        latest = get_latest_corpus_version(
            "software-engineering", "code-review-agent",
        )
        assert latest is not None
        assert latest["version_label"] == "2026-W12"
        assert latest["posting_count"] == 15

    def test_corpus_stats(self):
        upsert_jd_posting({
            "source_ats": "greenhouse",
            "source_board_id": "s1",
            "company_name": "Corp-A",
            "title": "SWE",
            "content": "c1",
            "content_hash": "h1",
            "field": "software-engineering",
            "role": "code-review-agent",
        })
        upsert_jd_posting({
            "source_ats": "lever",
            "source_board_id": "s2",
            "company_name": "Corp-B",
            "title": "SWE",
            "content": "c2",
            "content_hash": "h2",
            "field": "software-engineering",
            "role": "code-review-agent",
        })

        stats = get_jd_corpus_stats("software-engineering", "code-review-agent")
        assert stats["total"] == 2
        assert stats["companies"] == 2
        assert stats["sources"] == 2


# ── SWE Task Pack Tests ─────────────────────────────────────────────


class TestSWETaskPack:
    def test_swe_task_pack_has_real_swe_tasks(self):
        from benchmark.taskpacks import get_task_pack

        # v2 (JD-generated) is default; fall back to v1 if v2 not generated yet
        pack = get_task_pack("software-engineering", "software-engineer-agent")
        task_ids = {t.id for t in pack.tasks}

        # Must NOT contain code-review tasks
        assert not any(tid.startswith("cr-") for tid in task_ids), (
            "SWE task pack should not contain code-review tasks"
        )

        # Must contain SWE tasks (swe-* for v1, jd-* for v2)
        has_swe = any(tid.startswith("swe-") for tid in task_ids)
        has_jd = any(tid.startswith("jd-") for tid in task_ids)
        assert has_swe or has_jd, (
            "SWE task pack should contain swe-* or jd-* tasks"
        )

    def test_swe_tasks_have_proper_metadata(self):
        from tournament.swe_tasks import SOFTWARE_ENGINEER_TASKS

        for task in SOFTWARE_ENGINEER_TASKS:
            assert task.skill_domain == "software-engineer-agent"
            assert task.task_bucket in {"anchor", "rotating", "holdout"}
            assert task.difficulty in {"easy", "medium", "hard", "adversarial"}
            assert len(task.acceptance_criteria) >= 3

    def test_swe_pack_has_anchors_and_holdout(self):
        from tournament.swe_tasks import SOFTWARE_ENGINEER_TASKS

        buckets = {t.task_bucket for t in SOFTWARE_ENGINEER_TASKS}
        assert "anchor" in buckets, "SWE tasks need anchor tasks"
        assert "holdout" in buckets, "SWE tasks need holdout tasks"


# ── Review API Tests ────────────────────────────────────────────────


class TestReviewAPI:
    @pytest.fixture(autouse=True)
    def _set_admin_key(self, monkeypatch):
        monkeypatch.setattr("api.app.ADMIN_API_KEY", "test-admin-key")

    @pytest.fixture
    def client(self):
        from api.app import app
        return TestClient(app)

    @pytest.fixture
    def admin_headers(self):
        return {"Authorization": "Bearer test-admin-key"}

    def test_review_queue_empty(self, client):
        resp = client.get("/api/review/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidates"] == []
        assert data["count"] == 0

    def test_review_queue_with_filter(self, client):
        _insert_test_agent("api-test-agent", review_state="pending-review")
        resp = client.get("/api/review/queue?review_state=pending-review")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_review_candidate_detail_rejects_without_auth(self, client):
        resp = client.get("/api/review/candidate/nonexistent")
        assert resp.status_code == 401

    def test_review_candidate_detail_404(self, client, admin_headers):
        resp = client.get("/api/review/candidate/nonexistent", headers=admin_headers)
        assert resp.status_code == 404

    def test_review_candidate_detail_found(self, client, admin_headers):
        _, vid = _insert_test_agent("detail-api-test")
        resp = client.get(f"/api/review/candidate/{vid}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["profile_name"] == "detail-api-test"

    def test_review_decide_approve(self, client, admin_headers):
        _, vid = _insert_test_agent("approve-api-test", eligibility="pending")
        resp = client.post(
            f"/api/review/candidate/{vid}/decide",
            json={"reviewer": "koo", "action": "approve", "reason": "Looks good"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "approve"
        assert data["new_state"] == "approved-public"

    def test_review_decide_rejects_without_auth(self, client):
        _, vid = _insert_test_agent("no-auth-test", eligibility="pending")
        resp = client.post(
            f"/api/review/candidate/{vid}/decide",
            json={"reviewer": "koo", "action": "approve"},
        )
        assert resp.status_code == 401

    def test_review_decide_invalid_action(self, client):
        _, vid = _insert_test_agent("bad-action-test")
        resp = client.post(
            f"/api/review/candidate/{vid}/decide",
            json={"reviewer": "koo", "action": "invalid-action"},
        )
        assert resp.status_code == 422

    def test_review_history_api(self, client):
        _, vid = _insert_test_agent("history-api-test")
        apply_review_decision(
            version_id=vid,
            reviewer="koo",
            action="approve",
            new_state="approved-public",
        )
        resp = client.get(f"/api/review/candidate/{vid}/history")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_jd_corpus_api(self, client):
        resp = client.get("/api/jd/corpus/software-engineering/code-review-agent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["field"] == "software-engineering"
        assert data["role"] == "code-review-agent"

    def test_jd_postings_api(self, client):
        resp = client.get("/api/jd/postings")
        assert resp.status_code == 200
        assert "postings" in resp.json()
