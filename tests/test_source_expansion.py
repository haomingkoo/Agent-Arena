"""Tests for source expansion: leads, resolution, GitLab, registry."""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from store.db import (
    _conn,
    get_lead_stats,
    init_db,
    list_candidate_leads,
    resolve_candidate_lead,
    upsert_candidate_lead,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("store.db.DB_PATH", db_path)
    init_db()


# ── CandidateLead Persistence ───────────────────────────────────────


class TestCandidateLeads:
    def test_upsert_creates_lead(self):
        lid = upsert_candidate_lead({
            "source_type": "reddit",
            "source_url": "https://reddit.com/r/ClaudeAI/post1",
            "title": "Amazing agent tool",
            "description": "Check out this agent",
            "outbound_links": ["https://github.com/foo/bar"],
            "extracted_artifact_links": ["https://github.com/foo/bar"],
            "signal_strength": 2.5,
            "content_hash": "abc123",
        })
        assert lid

        leads = list_candidate_leads(source_type="reddit")
        assert len(leads) == 1
        assert leads[0]["title"] == "Amazing agent tool"
        assert leads[0]["review_state"] == "new"
        assert leads[0]["resolution_state"] == "unresolved"

    def test_dedup_increments_mention_count(self):
        for _ in range(3):
            upsert_candidate_lead({
                "source_type": "hackernews",
                "source_url": "https://news.ycombinator.com/item?id=123",
                "title": "Same post",
                "content_hash": "same-hash",
            })

        leads = list_candidate_leads(source_type="hackernews")
        assert len(leads) == 1
        assert leads[0]["mention_count"] == 3

    def test_filter_by_resolution_state(self):
        upsert_candidate_lead({
            "source_type": "youtube",
            "source_url": "https://youtube.com/watch?v=1",
            "title": "Unresolved",
            "content_hash": "h1",
        })
        lid2 = upsert_candidate_lead({
            "source_type": "youtube",
            "source_url": "https://youtube.com/watch?v=2",
            "title": "Will resolve",
            "content_hash": "h2",
        })
        resolve_candidate_lead(lid2, "resolved", "https://github.com/foo/bar")

        unresolved = list_candidate_leads(resolution_state="unresolved")
        assert len(unresolved) == 1
        assert unresolved[0]["title"] == "Unresolved"

        resolved = list_candidate_leads(resolution_state="resolved")
        assert len(resolved) == 1
        assert resolved[0]["title"] == "Will resolve"

    def test_resolve_marks_lead(self):
        lid = upsert_candidate_lead({
            "source_type": "reddit",
            "source_url": "https://reddit.com/r/test/1",
            "title": "Resolve me",
            "content_hash": "resolve-hash",
        })

        resolve_candidate_lead(
            lid,
            resolution_state="resolved",
            resolved_artifact_url="https://github.com/example/agent",
            resolver_note="Found SKILL.md in repo",
        )

        leads = list_candidate_leads()
        assert len(leads) == 1
        assert leads[0]["resolution_state"] == "resolved"
        assert leads[0]["resolved_artifact_url"] == "https://github.com/example/agent"
        assert leads[0]["review_state"] == "resolved"

    def test_resolve_no_artifact(self):
        lid = upsert_candidate_lead({
            "source_type": "blog",
            "source_url": "https://blog.example.com/agents",
            "title": "No artifact here",
            "content_hash": "no-art",
        })

        resolve_candidate_lead(lid, "no-artifact", resolver_note="Just a blog post")

        leads = list_candidate_leads()
        assert leads[0]["resolution_state"] == "no-artifact"

    def test_lead_stats(self):
        upsert_candidate_lead({
            "source_type": "reddit",
            "source_url": "u1",
            "title": "r1",
            "content_hash": "s1",
        })
        lid2 = upsert_candidate_lead({
            "source_type": "hackernews",
            "source_url": "u2",
            "title": "r2",
            "content_hash": "s2",
        })
        resolve_candidate_lead(lid2, "resolved")

        stats = get_lead_stats()
        assert stats["total"] == 2
        assert stats["unresolved"] == 1
        assert stats["resolved"] == 1


# ── Link Classification ────────────────────────────────────────────


class TestLinkClassification:
    def test_github_repo(self):
        from ingest.resolver import classify_link
        assert classify_link("https://github.com/foo/bar") == "repo"
        assert classify_link("https://github.com/foo/bar/blob/main/SKILL.md") == "repo"

    def test_gitlab_repo(self):
        from ingest.resolver import classify_link
        assert classify_link("https://gitlab.com/foo/bar") == "repo"

    def test_registry(self):
        from ingest.resolver import classify_link
        assert classify_link("https://smithery.ai/server/foo") == "registry"
        assert classify_link("https://www.npmjs.com/package/foo") == "registry"

    def test_irrelevant(self):
        from ingest.resolver import classify_link
        assert classify_link("https://twitter.com/user") == "irrelevant"
        assert classify_link("https://youtube.com/watch?v=123") == "irrelevant"

    def test_extract_repo(self):
        from ingest.resolver import _extract_repo_from_url
        assert _extract_repo_from_url("https://github.com/foo/bar") == "foo/bar"
        assert _extract_repo_from_url("https://github.com/foo/bar/blob/main/x.md") == "foo/bar"
        assert _extract_repo_from_url("https://twitter.com/user") is None


# ── Lead-Gen Adapters ──────────────────────────────────────────────


class TestLeadAdapters:
    def test_hackernews_search_returns_list(self):
        """HN Algolia API is public — this should work without auth."""
        from ingest.leads import search_hackernews
        leads = search_hackernews("AI agent", max_results=3)
        # May return results or empty depending on network
        assert isinstance(leads, list)
        for lead in leads:
            assert lead["source_type"] == "hackernews"
            assert "source_url" in lead
            assert "title" in lead

    def test_youtube_without_key_returns_empty(self):
        from ingest.leads import search_youtube
        leads = search_youtube("AI agent", api_key="")
        assert leads == []

    def test_awesome_list_extraction_format(self):
        from ingest.leads import extract_leads_from_awesome_list
        # This will try to actually fetch — may fail without network
        # Just verify it doesn't crash
        leads = extract_leads_from_awesome_list("nonexistent/repo")
        assert isinstance(leads, list)


# ── GitLab Adapter ─────────────────────────────────────────────────


class TestGitLabAdapter:
    def test_classify_agent_path(self):
        from ingest.gitlab import _is_agent_config_path
        targets = ["SKILL.md", "AGENTS.md"]
        assert _is_agent_config_path("SKILL.md", targets)
        assert _is_agent_config_path("agents/foo.md", targets)
        assert _is_agent_config_path("skills/review/SKILL.md", targets)
        assert _is_agent_config_path("prompts/code-review-agent/CLAUDE.md", targets)
        assert not _is_agent_config_path("prompts/system-prompt.md", targets)
        assert not _is_agent_config_path("rules/cursor/general.md", targets)
        assert not _is_agent_config_path("docs/readme.md", targets)


# ── Registry Adapter ──────────────────────────────────────────────


class TestRegistryAdapter:
    def test_role_agent_filter_rejects_generic_prompt_collections(self):
        from ingest.registry import _looks_like_role_agent

        assert _looks_like_role_agent("Code Review Agent", "Reviews pull requests")
        assert _looks_like_role_agent("Security Reviewer", "Agent for secure code review")
        assert not _looks_like_role_agent("Awesome Skills", "Collection of 2000 skill files")
        assert not _looks_like_role_agent("Cursor Rules", "A prompt/rules collection")
        assert not _looks_like_role_agent("GPT Prompts", "Prompt pack for general use")

    def test_awesome_list_parse_links(self):
        from ingest.registry import AwesomeListAdapter
        adapter = AwesomeListAdapter()

        # Test the parser directly with fake content
        content = """
# Awesome Agents

- [Agent A](https://github.com/foo/agent-a) - Great code review agent
- [Agent B](https://github.com/bar/agent-b) - SWE agent
- [Awesome Skills](https://github.com/baz/awesome-skills) - Large list of prompts and skills
- [Blog Post](https://medium.com/article) - Not a repo
- [Registry](https://smithery.ai/server/test) - Registry link
"""
        results = adapter._parse_awesome_list(content, "test/repo", 50)
        # Should find the GitHub links
        repo_links = [r for r in results if "github.com" in r.source_url]
        assert len(repo_links) == 2
        assert repo_links[0].name == "Agent A"


# ── API Endpoints ──────────────────────────────────────────────────


class TestLeadAPI:
    @pytest.fixture
    def client(self):
        from api.app import app
        return TestClient(app)

    def test_leads_empty(self, client):
        resp = client.get("/api/leads")
        assert resp.status_code == 200
        assert resp.json()["leads"] == []

    def test_leads_with_data(self, client):
        upsert_candidate_lead({
            "source_type": "hackernews",
            "source_url": "https://news.ycombinator.com/item?id=1",
            "title": "Test lead",
            "content_hash": "api-test",
        })
        resp = client.get("/api/leads?source_type=hackernews")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_leads_stats(self, client):
        resp = client.get("/api/leads/stats")
        assert resp.status_code == 200
        assert "total" in resp.json()
