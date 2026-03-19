"""Tests for fuzzy duplicate detection and review-based dedup."""
from __future__ import annotations

import json
import uuid

import pytest

from store.db import (
    _conn,
    apply_review_decision,
    find_exact_duplicates,
    find_name_duplicates,
    init_db,
    list_benchmark_ready_agents,
    list_duplicate_groups,
    record_duplicate,
    scan_and_record_duplicates,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("store.db.DB_PATH", db_path)
    init_db()


def _insert_agent(
    name: str,
    field: str = "software-engineering",
    role: str = "code-review-agent",
    content_hash: str = "",
    owner: str = "test",
    source_url: str = "",
    eligibility: str = "eligible",
) -> tuple[str, str]:
    """Insert a test agent. Returns (profile_id, version_id)."""
    conn = _conn()
    profile_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    conn.execute(
        "INSERT INTO agent_profiles "
        "(id, name, field, role, owner, source_url, packaging_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (profile_id, name, field, role, owner, source_url, "markdown_prompt_bundle"),
    )

    contract = json.dumps({
        "field": field, "role": role, "profile_name": name,
        "version_id": version_id, "source_url": source_url,
        "packaging_type": "markdown_prompt_bundle",
        "system_instructions": f"You are {name}.",
        "model_provider": "qwen", "model_name": "qwen-plus",
        "max_steps": 8, "timeout_seconds": 120, "max_total_tokens": 10000,
    })

    conn.execute(
        "INSERT INTO agent_versions "
        "(id, profile_id, version_label, content_hash, packaging_type, "
        " eligibility, runner_contract_json, review_state, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending-review', datetime('now'))",
        (version_id, profile_id, "v1", content_hash,
         "markdown_prompt_bundle", eligibility, contract),
    )
    conn.commit()
    conn.close()
    return profile_id, version_id


class TestExactDuplicateDetection:
    def test_finds_exact_hash_match(self):
        _insert_agent("Agent A", content_hash="abc123", source_url="src1")
        _insert_agent("Agent A Copy", content_hash="abc123", source_url="src2")

        dupes = find_exact_duplicates()
        assert len(dupes) == 1
        assert dupes[0]["content_hash"] == "abc123"

    def test_different_hashes_not_exact(self):
        _insert_agent("Agent X", content_hash="hash1")
        _insert_agent("Agent Y", content_hash="hash2")

        dupes = find_exact_duplicates()
        assert len(dupes) == 0

    def test_same_hash_different_lanes_not_flagged(self):
        _insert_agent("Agent A", content_hash="same",
                      role="code-review-agent")
        _insert_agent("Agent A", content_hash="same",
                      role="software-engineer-agent")

        dupes = find_exact_duplicates()
        assert len(dupes) == 0  # different roles, not a duplicate


class TestNameDuplicateDetection:
    def test_finds_same_name_different_content(self):
        _insert_agent("Code Reviewer", content_hash="h1", owner="source-a")
        _insert_agent("Code Reviewer", content_hash="h2", owner="source-b")

        dupes = find_name_duplicates()
        assert len(dupes) == 1
        assert dupes[0]["name"] == "Code Reviewer"

    def test_different_names_not_flagged(self):
        _insert_agent("Agent Alpha", content_hash="h1")
        _insert_agent("Agent Beta", content_hash="h2")

        dupes = find_name_duplicates()
        assert len(dupes) == 0


class TestDuplicateRecording:
    def test_record_and_list(self):
        _, vid_a = _insert_agent("Canon", content_hash="c1")
        _, vid_b = _insert_agent("Dupe", content_hash="c1")

        did = record_duplicate(vid_a, vid_b, match_type="exact-hash")
        assert did

        groups = list_duplicate_groups()
        assert len(groups) == 1
        assert groups[0]["canonical_name"] == "Canon"
        assert groups[0]["duplicate_name"] == "Dupe"
        assert groups[0]["match_type"] == "exact-hash"

    def test_no_double_recording(self):
        _, vid_a = _insert_agent("A", content_hash="x")
        _, vid_b = _insert_agent("B", content_hash="x")

        did1 = record_duplicate(vid_a, vid_b)
        did2 = record_duplicate(vid_a, vid_b)
        assert did1
        assert did2 == ""  # already exists

    def test_filter_by_review_state(self):
        _, vid_a = _insert_agent("A1", content_hash="p1")
        _, vid_b = _insert_agent("B1", content_hash="p1")

        record_duplicate(vid_a, vid_b)

        pending = list_duplicate_groups(review_state="pending")
        assert len(pending) == 1

        resolved = list_duplicate_groups(review_state="resolved")
        assert len(resolved) == 0


class TestScanAndRecord:
    def test_full_scan(self):
        _insert_agent("Agent X", content_hash="same-hash", owner="a")
        _insert_agent("Agent X Mirror", content_hash="same-hash", owner="b")
        _insert_agent("Code Reviewer", content_hash="cr1", owner="c")
        _insert_agent("Code Reviewer", content_hash="cr2", owner="d")

        result = scan_and_record_duplicates()
        assert result["exact_found"] == 1
        assert result["name_found"] >= 1


class TestDuplicateRetirementViaReview:
    def test_reject_duplicate_removes_from_pool(self):
        _, vid_a = _insert_agent("Upstream Agent", content_hash="u1",
                                 owner="upstream", eligibility="eligible")
        _, vid_b = _insert_agent("Mirror Agent", content_hash="u1",
                                 owner="mirror", eligibility="eligible")

        # Both should be in pool initially
        pool = list_benchmark_ready_agents(
            field="software-engineering", role="code-review-agent",
        )
        assert len([a for a in pool if a["version_id"] in (vid_a, vid_b)]) == 2

        # Reject the mirror through review
        apply_review_decision(
            version_id=vid_b,
            reviewer="dedup-bot",
            action="reject",
            new_state="rejected",
            reason="Duplicate of upstream",
        )

        # Only upstream should remain
        pool = list_benchmark_ready_agents(
            field="software-engineering", role="code-review-agent",
        )
        vids = [a["version_id"] for a in pool]
        assert vid_a in vids
        assert vid_b not in vids
