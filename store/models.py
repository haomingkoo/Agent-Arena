"""
Data models for the legacy skill pipeline and the new agent-tournament platform.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from agents.contracts import (
    AgentProfile,
    AgentVersion,
    ArtifactRecord,
    EligibilityState,
    PackagingType,
    ProvenanceRef,
    ReviewState,
    RunnerContract,
    Visibility,
)


class CertTier(str, Enum):
    uncertified = "uncertified"
    bronze = "bronze"       # "Not Slop" — basic quality bar
    silver = "silver"       # "Verified Quality" — LLM evaluated, safety vetted
    gold = "gold"           # "Production Ready" — proven adoption, trusted source


class Skill(BaseModel):
    """A discovered skill from the ecosystem."""

    id: str = ""
    name: str
    description: str = ""

    # Content
    raw_content: str = ""           # full SKILL.md text
    instructions: str = ""          # body after frontmatter
    triggers: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    line_count: int = 0
    token_estimate: int = 0

    # Source
    source_repo: str = ""           # e.g. "anthropics/skills"
    source_url: str = ""
    github_stars: int = 0
    install_count: int = 0

    # Scores (from evaluate/)
    overall_score: float = 0.0
    confidence: float = 0.0
    frequency_value: float = 0.0
    capability_upgrade: float = 0.0
    specificity: float = 0.0
    token_efficiency: float = 0.0
    source_credibility: float = 0.0
    trigger_clarity: float = 0.0
    methodology_depth: float = 0.0
    llm_quality: float = 0.0

    # Certification
    cert_tier: CertTier = CertTier.uncertified
    cert_checks_json: str = "[]"    # JSON of all check results
    cert_date: str = ""
    cert_expires: str = ""

    # Community
    upvotes: int = 0
    downvotes: int = 0
    community_score: float = 0.0
    report_count: int = 0

    # Flags
    flags_json: str = "[]"
    strengths_json: str = "[]"
    llm_reasoning: str = ""
    needs_review: bool = False

    # Lifecycle
    status: str = "active"          # active / deprecated / revoked
    created_at: str = ""
    updated_at: str = ""


class Vote(BaseModel):
    """Community vote on a certified skill."""

    id: str = ""
    skill_id: str
    voter_fingerprint: str
    value: int                      # +1 or -1
    reason: str = ""
    voter_reputation: float = 1.0
    created_at: str = ""


class FeedbackEntry(BaseModel):
    """Prediction vs outcome for learning loop."""

    id: str = ""
    skill_name: str
    source_url: str = ""
    predicted_grade: str = ""
    predicted_score: float = 0.0
    confidence: float = 0.0
    dimensions_json: str = "{}"
    # Outcomes (filled in later)
    outcome_installs: Optional[int] = None
    outcome_stars: Optional[int] = None
    outcome_deprecated: Optional[bool] = None
    outcome_community_score: Optional[float] = None
    created_at: str = ""
    updated_at: str = ""


# ── AgentArena Tournament Models ────────────────────────────────────


class Category(BaseModel):
    slug: str                    # "code-review"
    display_name: str            # "Code Review"
    description: str = ""
    task_count: int = 0
    skill_count: int = 0
    active: bool = True
    created_at: str = ""
    updated_at: str = ""


class Tournament(BaseModel):
    id: str = ""
    category: str
    week: str                    # "2026-W12"
    status: str = "pending"      # pending | running | completed | failed
    task_ids: list[str] = Field(default_factory=list)
    num_skills: int = 0
    baseline_avg: float = 0.0
    started_at: str = ""
    completed_at: str = ""
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class TournamentEntry(BaseModel):
    id: str = ""
    tournament_id: str
    skill_id: str
    skill_name: str
    rank: int = 0
    avg_score: float = 0.0
    pass_rate: float = 0.0
    total_tokens: int = 0
    total_runtime_ms: int = 0
    rating_before: float = 1500.0
    rating_after: float = 1500.0
    task_results_json: str = "[]"
    created_at: str = ""


class SkillRating(BaseModel):
    skill_id: str
    category: str
    mu: float = 1500.0           # Glicko-2 rating
    rd: float = 350.0            # rating deviation (uncertainty)
    sigma: float = 0.06          # volatility
    tournaments_played: int = 0
    last_tournament_week: str = ""
    created_at: str = ""
    updated_at: str = ""


class CoachingRecommendation(BaseModel):
    id: str = ""
    skill_id: str
    skill_name: str
    category: str
    tournament_id: str = ""
    tournament_week: str = ""
    current_rank: int = 0
    current_rating: float = 0.0
    recommendations_json: str = "[]"
    summary: str = ""
    estimated_rank_improvement: int = 0
    status: str = "pending"      # pending | delivered | applied | dismissed
    generated_at: str = ""
    created_at: str = ""


# ── Agent-Native Platform Models ─────────────────────────────────────


class RunTrace(BaseModel):
    id: str = ""
    agent_version_id: str
    field: str = ""
    role: str = ""
    tournament_id: str = ""
    tournament_run_id: str = ""
    task_id: str = ""
    trace_kind: str = "benchmark"   # benchmark | hosted
    status: str = "pending"         # pending | completed | failed
    exec_provider: str = ""
    judge_provider: str = ""
    final_output: str = ""
    error: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    runtime_ms: int = 0
    prompt_json: str = "{}"
    tool_calls_json: str = "[]"
    tool_outputs_json: str = "[]"
    judge_prompt: str = ""
    judge_output: str = ""
    metadata_json: str = "{}"
    created_at: str = ""


class HostedRun(BaseModel):
    id: str = ""
    agent_profile_id: str = ""
    agent_version_id: str = ""
    user_fingerprint: str
    prompt: str = ""
    status: str = "pending"      # pending | running | completed | failed | blocked
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    runtime_ms: int = 0
    error: str = ""
    created_at: str = ""
    updated_at: str = ""


class UsageLedgerEntry(BaseModel):
    id: str = ""
    user_fingerprint: str
    hosted_run_id: str = ""
    provider: str = ""
    window_date: str = ""        # YYYY-MM-DD
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    created_at: str = ""


class ReviewDecision(BaseModel):
    """Immutable audit record for a human review action."""

    id: str = ""
    version_id: str
    reviewer: str
    action: str              # approve | relabel | reject | send-to-qualification | unsupported
    previous_state: str      # previous review_state
    new_state: str           # new review_state
    previous_role: str = ""  # only set on relabel
    new_role: str = ""       # only set on relabel
    previous_field: str = ""
    new_field: str = ""
    reason: str = ""
    note: str = ""
    created_at: str = ""


class CandidateLead(BaseModel):
    """A lead from a non-benchmark source (YouTube, Reddit, HN, blogs).

    Leads are discovered mentions of potential agents. They must be
    resolved into real artifact URLs before entering the review pipeline.
    """

    id: str = ""
    source_type: str             # youtube | reddit | hackernews | blog | awesome-list
    source_url: str
    title: str = ""
    description: str = ""
    outbound_links: list[str] = Field(default_factory=list)
    extracted_artifact_links: list[str] = Field(default_factory=list)
    mention_count: int = 1
    signal_strength: float = 0.0
    discovered_at: str = ""
    review_state: str = "new"    # new | reviewing | resolved | dismissed
    resolution_state: str = "unresolved"  # unresolved | resolved | no-artifact | dead-link
    resolved_artifact_url: str = ""
    resolved_version_id: str = ""
    resolver_note: str = ""
    content_hash: str = ""
    created_at: str = ""
    updated_at: str = ""
