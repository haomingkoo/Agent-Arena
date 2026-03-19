"""
Skill Store — SQLite persistence for certified skills, votes, and feedback.
"""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from agents.contracts import (
    EligibilityState,
    PackagingType,
    ProvenanceRef,
    ReviewState,
    RunnerContract,
    Visibility,
)
from store.models import (
    AgentProfile,
    AgentVersion,
    ArtifactRecord,
    CertTier,
    FeedbackEntry,
    HostedRun,
    ReviewDecision,
    RunTrace,
    Skill,
    UsageLedgerEntry,
    Vote,
)

DB_PATH = Path("data/certified.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables."""
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            raw_content TEXT DEFAULT '',
            instructions TEXT DEFAULT '',
            triggers_json TEXT DEFAULT '[]',
            allowed_tools_json TEXT DEFAULT '[]',
            line_count INTEGER DEFAULT 0,
            token_estimate INTEGER DEFAULT 0,

            source_repo TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            github_stars INTEGER DEFAULT 0,
            install_count INTEGER DEFAULT 0,

            overall_score REAL DEFAULT 0,
            confidence REAL DEFAULT 0,
            frequency_value REAL DEFAULT 0,
            capability_upgrade REAL DEFAULT 0,
            specificity REAL DEFAULT 0,
            token_efficiency REAL DEFAULT 0,
            source_credibility REAL DEFAULT 0,
            trigger_clarity REAL DEFAULT 0,
            methodology_depth REAL DEFAULT 0,
            llm_quality REAL DEFAULT 0,

            cert_tier TEXT DEFAULT 'uncertified',
            cert_checks_json TEXT DEFAULT '[]',
            cert_date TEXT DEFAULT '',
            cert_expires TEXT DEFAULT '',

            upvotes INTEGER DEFAULT 0,
            downvotes INTEGER DEFAULT 0,
            community_score REAL DEFAULT 0,
            report_count INTEGER DEFAULT 0,

            flags_json TEXT DEFAULT '[]',
            strengths_json TEXT DEFAULT '[]',
            llm_reasoning TEXT DEFAULT '',
            needs_review INTEGER DEFAULT 0,

            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS votes (
            id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL REFERENCES skills(id),
            voter_fingerprint TEXT NOT NULL,
            value INTEGER NOT NULL CHECK(value IN (-1, 1)),
            reason TEXT DEFAULT '',
            voter_reputation REAL DEFAULT 1.0,
            created_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_vote_unique
            ON votes(skill_id, voter_fingerprint);

        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            skill_name TEXT NOT NULL,
            source_url TEXT DEFAULT '',
            predicted_grade TEXT DEFAULT '',
            predicted_score REAL DEFAULT 0,
            confidence REAL DEFAULT 0,
            dimensions_json TEXT DEFAULT '{}',
            outcome_installs INTEGER,
            outcome_stars INTEGER,
            outcome_deprecated INTEGER,
            outcome_community_score REAL,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_skills_cert ON skills(cert_tier);
        CREATE INDEX IF NOT EXISTS idx_skills_score ON skills(overall_score DESC);
        CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
        CREATE INDEX IF NOT EXISTS idx_votes_skill ON votes(skill_id);

        CREATE TABLE IF NOT EXISTS categories (
            slug TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT DEFAULT '',
            task_count INTEGER DEFAULT 0,
            skill_count INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS tournaments (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            week TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            task_ids_json TEXT DEFAULT '[]',
            num_skills INTEGER DEFAULT 0,
            baseline_avg REAL DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            total_cost_usd REAL DEFAULT 0,
            total_input_tokens INTEGER DEFAULT 0,
            total_output_tokens INTEGER DEFAULT 0
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tournament_week
            ON tournaments(category, week);

        CREATE TABLE IF NOT EXISTS tournament_entries (
            id TEXT PRIMARY KEY,
            tournament_id TEXT NOT NULL REFERENCES tournaments(id),
            skill_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            rank INTEGER DEFAULT 0,
            avg_score REAL DEFAULT 0,
            pass_rate REAL DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            total_runtime_ms INTEGER DEFAULT 0,
            rating_before REAL DEFAULT 1500,
            rating_after REAL DEFAULT 1500,
            task_results_json TEXT DEFAULT '[]',
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tent_tournament
            ON tournament_entries(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_tent_skill
            ON tournament_entries(skill_id);

        CREATE TABLE IF NOT EXISTS skill_ratings (
            skill_id TEXT NOT NULL,
            category TEXT NOT NULL,
            mu REAL DEFAULT 1500.0,
            rd REAL DEFAULT 350.0,
            sigma REAL DEFAULT 0.06,
            tournaments_played INTEGER DEFAULT 0,
            last_tournament_week TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT,
            PRIMARY KEY (skill_id, category)
        );

        CREATE TABLE IF NOT EXISTS skill_rating_history (
            id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            category TEXT NOT NULL,
            week TEXT NOT NULL,
            mu REAL,
            rd REAL,
            rank INTEGER,
            avg_score REAL,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_rating_history_skill
            ON skill_rating_history(skill_id, category);
        CREATE INDEX IF NOT EXISTS idx_rating_history_week
            ON skill_rating_history(category, week);

        CREATE TABLE IF NOT EXISTS coaching (
            id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            category TEXT NOT NULL,
            tournament_id TEXT DEFAULT '',
            tournament_week TEXT NOT NULL,
            current_rank INTEGER DEFAULT 0,
            current_rating REAL DEFAULT 0,
            recommendations_json TEXT DEFAULT '[]',
            summary TEXT DEFAULT '',
            estimated_rank_improvement INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            generated_at TEXT,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_coaching_skill ON coaching(skill_id);
        CREATE INDEX IF NOT EXISTS idx_coaching_tournament ON coaching(tournament_id);

        CREATE TABLE IF NOT EXISTS skill_duplicates (
            primary_skill_id TEXT NOT NULL,
            duplicate_skill_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            similarity REAL DEFAULT 1.0,
            detected_at TEXT,
            PRIMARY KEY (primary_skill_id, duplicate_skill_id)
        );

        CREATE TABLE IF NOT EXISTS agent_profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            field TEXT NOT NULL,
            role TEXT NOT NULL,
            summary TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            packaging_type TEXT NOT NULL,
            visibility TEXT DEFAULT 'public',
            license TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_agent_profiles_field_role
            ON agent_profiles(field, role);
        CREATE INDEX IF NOT EXISTS idx_agent_profiles_visibility
            ON agent_profiles(visibility);

        CREATE TABLE IF NOT EXISTS artifact_records (
            id TEXT PRIMARY KEY,
            packaging_type TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_commit TEXT DEFAULT '',
            raw_content TEXT DEFAULT '',
            sanitized_content TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            security_findings_json TEXT DEFAULT '[]',
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_artifacts_source
            ON artifact_records(source_type, source_url);
        CREATE INDEX IF NOT EXISTS idx_artifacts_hash
            ON artifact_records(content_hash);

        CREATE TABLE IF NOT EXISTS agent_versions (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL REFERENCES agent_profiles(id),
            version_label TEXT NOT NULL,
            source_commit TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            packaging_type TEXT NOT NULL,
            provenance_json TEXT DEFAULT '{}',
            artifact_id TEXT DEFAULT '',
            runner_contract_json TEXT DEFAULT '',
            eligibility TEXT DEFAULT 'pending',
            ineligibility_reason TEXT DEFAULT '',
            security_findings_json TEXT DEFAULT '[]',
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_agent_versions_profile
            ON agent_versions(profile_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_agent_versions_eligibility
            ON agent_versions(eligibility);

        CREATE TABLE IF NOT EXISTS run_traces (
            id TEXT PRIMARY KEY,
            agent_version_id TEXT NOT NULL REFERENCES agent_versions(id),
            field TEXT DEFAULT '',
            role TEXT DEFAULT '',
            tournament_id TEXT DEFAULT '',
            tournament_run_id TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            trace_kind TEXT DEFAULT 'benchmark',
            status TEXT DEFAULT 'pending',
            exec_provider TEXT DEFAULT '',
            judge_provider TEXT DEFAULT '',
            final_output TEXT DEFAULT '',
            error TEXT DEFAULT '',
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0,
            runtime_ms INTEGER DEFAULT 0,
            prompt_json TEXT DEFAULT '{}',
            tool_calls_json TEXT DEFAULT '[]',
            tool_outputs_json TEXT DEFAULT '[]',
            judge_prompt TEXT DEFAULT '',
            judge_output TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_run_traces_version
            ON run_traces(agent_version_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_run_traces_tournament
            ON run_traces(tournament_id, tournament_run_id);

        CREATE TABLE IF NOT EXISTS hosted_runs (
            id TEXT PRIMARY KEY,
            agent_profile_id TEXT DEFAULT '',
            agent_version_id TEXT DEFAULT '',
            user_fingerprint TEXT NOT NULL,
            prompt TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0,
            runtime_ms INTEGER DEFAULT 0,
            error TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_hosted_runs_user
            ON hosted_runs(user_fingerprint, created_at DESC);

        CREATE TABLE IF NOT EXISTS usage_ledger (
            id TEXT PRIMARY KEY,
            user_fingerprint TEXT NOT NULL,
            hosted_run_id TEXT DEFAULT '',
            provider TEXT DEFAULT '',
            window_date TEXT DEFAULT '',
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_usage_ledger_user_day
            ON usage_ledger(user_fingerprint, window_date);

        CREATE TABLE IF NOT EXISTS review_decisions (
            id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL REFERENCES agent_versions(id),
            reviewer TEXT NOT NULL,
            action TEXT NOT NULL,
            previous_state TEXT DEFAULT '',
            new_state TEXT NOT NULL,
            previous_role TEXT DEFAULT '',
            new_role TEXT DEFAULT '',
            previous_field TEXT DEFAULT '',
            new_field TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_review_decisions_version
            ON review_decisions(version_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_review_decisions_reviewer
            ON review_decisions(reviewer, created_at DESC);

        CREATE TABLE IF NOT EXISTS jd_postings (
            id TEXT PRIMARY KEY,
            source_ats TEXT NOT NULL,
            source_board_id TEXT DEFAULT '',
            company_name TEXT NOT NULL,
            company_size_bucket TEXT DEFAULT '',
            title TEXT NOT NULL,
            normalized_role TEXT DEFAULT '',
            field TEXT DEFAULT '',
            role TEXT DEFAULT '',
            location TEXT DEFAULT '',
            department TEXT DEFAULT '',
            content TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            responsibilities_json TEXT DEFAULT '[]',
            tools_json TEXT DEFAULT '[]',
            skills_json TEXT DEFAULT '[]',
            posted_at TEXT DEFAULT '',
            expires_at TEXT DEFAULT '',
            corpus_version TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(source_ats, source_board_id, content_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_jd_postings_role
            ON jd_postings(field, role);
        CREATE INDEX IF NOT EXISTS idx_jd_postings_corpus
            ON jd_postings(corpus_version);

        CREATE TABLE IF NOT EXISTS jd_corpus_versions (
            id TEXT PRIMARY KEY,
            field TEXT NOT NULL,
            role TEXT NOT NULL,
            version_label TEXT NOT NULL,
            posting_count INTEGER DEFAULT 0,
            company_count INTEGER DEFAULT 0,
            source_mix_json TEXT DEFAULT '{}',
            responsibilities_summary_json TEXT DEFAULT '[]',
            tools_summary_json TEXT DEFAULT '[]',
            skills_summary_json TEXT DEFAULT '[]',
            created_at TEXT,
            UNIQUE(field, role, version_label)
        );
        CREATE INDEX IF NOT EXISTS idx_jd_corpus_field_role
            ON jd_corpus_versions(field, role);

        CREATE TABLE IF NOT EXISTS candidate_leads (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            outbound_links_json TEXT DEFAULT '[]',
            extracted_artifact_links_json TEXT DEFAULT '[]',
            mention_count INTEGER DEFAULT 1,
            signal_strength REAL DEFAULT 0,
            discovered_at TEXT,
            review_state TEXT DEFAULT 'new',
            resolution_state TEXT DEFAULT 'unresolved',
            resolved_artifact_url TEXT DEFAULT '',
            resolved_version_id TEXT DEFAULT '',
            resolver_note TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(source_type, content_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_candidate_leads_state
            ON candidate_leads(review_state, resolution_state);
        CREATE INDEX IF NOT EXISTS idx_candidate_leads_source
            ON candidate_leads(source_type, created_at DESC);

        CREATE TABLE IF NOT EXISTS duplicate_groups (
            id TEXT PRIMARY KEY,
            canonical_version_id TEXT NOT NULL,
            duplicate_version_id TEXT NOT NULL,
            similarity_score REAL DEFAULT 0,
            match_type TEXT DEFAULT 'exact',
            review_state TEXT DEFAULT 'pending',
            reviewed_by TEXT DEFAULT '',
            reviewed_at TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT,
            UNIQUE(canonical_version_id, duplicate_version_id)
        );
        CREATE INDEX IF NOT EXISTS idx_duplicate_groups_canonical
            ON duplicate_groups(canonical_version_id);
        CREATE INDEX IF NOT EXISTS idx_duplicate_groups_duplicate
            ON duplicate_groups(duplicate_version_id);
    """)

    # Migration: add category columns to skills table
    for col, default in [
        ("primary_category", "''"),
        ("secondary_category", "''"),
        ("category_confidence", "0"),
        ("category_method", "''"),
        ("content_hash", "''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE skills ADD COLUMN {col} DEFAULT {default}")
        except sqlite3.OperationalError:
            pass  # column already exists

    # Migration: add review fields to agent_versions table
    for col, default in [
        ("review_state", "'pending-review'"),
        ("predicted_field", "''"),
        ("predicted_role", "''"),
        ("jd_fit_score", "0"),
        ("qualification_fit_score", "0"),
        ("work_sample_fit_score", "0"),
        ("manual_review_required", "0"),
        ("reviewed_by", "''"),
        ("reviewed_at", "''"),
    ]:
        try:
            conn.execute(
                f"ALTER TABLE agent_versions ADD COLUMN {col} DEFAULT {default}"
            )
        except sqlite3.OperationalError:
            pass  # column already exists

    # Migration: add lane metadata to tournaments table
    for col, default in [
        ("field", "''"),
        ("role", "''"),
        ("runtime_class", "'standard'"),
        ("task_pack_version", "''"),
        ("tournament_type", "'standardized'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE tournaments ADD COLUMN {col} DEFAULT {default}")
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.commit()
    conn.close()


def add_skill(skill: Skill) -> str:
    """Insert a skill, return its ID."""
    skill.id = skill.id or str(uuid.uuid4())
    skill.created_at = skill.created_at or _now()
    skill.updated_at = _now()
    conn = _conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO skills (
            id, name, description, raw_content, instructions,
            triggers_json, allowed_tools_json, line_count, token_estimate,
            source_repo, source_url, github_stars, install_count,
            overall_score, confidence,
            frequency_value, capability_upgrade, specificity,
            token_efficiency, source_credibility, trigger_clarity,
            methodology_depth, llm_quality,
            cert_tier, cert_checks_json, cert_date, cert_expires,
            upvotes, downvotes, community_score, report_count,
            flags_json, strengths_json, llm_reasoning, needs_review,
            status, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            skill.id, skill.name, skill.description,
            skill.raw_content, skill.instructions,
            json.dumps(skill.triggers), json.dumps(skill.allowed_tools),
            skill.line_count, skill.token_estimate,
            skill.source_repo, skill.source_url,
            skill.github_stars, skill.install_count,
            skill.overall_score, skill.confidence,
            skill.frequency_value, skill.capability_upgrade, skill.specificity,
            skill.token_efficiency, skill.source_credibility, skill.trigger_clarity,
            skill.methodology_depth, skill.llm_quality,
            skill.cert_tier.value, skill.cert_checks_json,
            skill.cert_date, skill.cert_expires,
            skill.upvotes, skill.downvotes, skill.community_score, skill.report_count,
            skill.flags_json, skill.strengths_json, skill.llm_reasoning,
            1 if skill.needs_review else 0,
            skill.status, skill.created_at, skill.updated_at,
        ),
    )
    conn.commit()
    conn.close()
    return skill.id


def get_skill(skill_id: str) -> Optional[Skill]:
    """Fetch a single skill by ID."""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM skills WHERE id = ?", (skill_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_skill(dict(row))


def list_skills(
    cert_tier: Optional[str] = None,
    status: str = "active",
    min_score: float = 0.0,
    sort_by: str = "overall_score",
    limit: int = 50,
) -> list[Skill]:
    """List skills with optional filters."""
    conn = _conn()
    clauses = ["status = ?", "overall_score >= ?"]
    params: list = [status, min_score]
    if cert_tier:
        clauses.append("cert_tier = ?")
        params.append(cert_tier)
    valid_sorts = {
        "overall_score", "community_score", "install_count",
        "github_stars", "created_at", "cert_date",
    }
    if sort_by not in valid_sorts:
        sort_by = "overall_score"
    query = (
        f"SELECT * FROM skills WHERE {' AND '.join(clauses)} "
        f"ORDER BY {sort_by} DESC LIMIT ?"
    )
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_skill(dict(r)) for r in rows]


def search_skills(query: str, limit: int = 20) -> list[Skill]:
    """Simple LIKE-based text search across key fields."""
    conn = _conn()
    pattern = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM skills WHERE status = 'active'
        AND (name LIKE ? OR description LIKE ?
             OR instructions LIKE ? OR source_repo LIKE ?)
        ORDER BY overall_score DESC LIMIT ?
        """,
        (pattern, pattern, pattern, pattern, limit),
    ).fetchall()
    conn.close()
    return [_row_to_skill(dict(r)) for r in rows]


SKILL_COLUMNS = {
    "name", "description", "raw_content", "instructions",
    "triggers_json", "allowed_tools_json", "line_count", "token_estimate",
    "source_repo", "source_url", "github_stars", "install_count",
    "overall_score", "confidence",
    "frequency_value", "capability_upgrade", "specificity",
    "token_efficiency", "source_credibility", "trigger_clarity",
    "methodology_depth", "llm_quality",
    "cert_tier", "cert_checks_json", "cert_date", "cert_expires",
    "upvotes", "downvotes", "community_score", "report_count",
    "flags_json", "strengths_json", "llm_reasoning", "needs_review",
    "status", "updated_at",
    "primary_category", "secondary_category", "category_confidence",
    "category_method", "content_hash",
}

FEEDBACK_COLUMNS = {
    "outcome_installs", "outcome_stars", "outcome_deprecated",
    "outcome_community_score", "updated_at",
}


def update_skill(skill_id: str, **fields) -> bool:
    """Update arbitrary fields on a skill."""
    invalid = set(fields) - SKILL_COLUMNS
    if invalid:
        raise ValueError(f"Invalid columns: {invalid}")
    conn = _conn()
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [skill_id]
    conn.execute(
        f"UPDATE skills SET {set_clause} WHERE id = ?", values
    )
    conn.commit()
    conn.close()
    return True


def get_stats() -> dict:
    """Return aggregate stats for the skill store."""
    conn = _conn()
    total = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    tier_rows = conn.execute(
        "SELECT cert_tier, COUNT(*) as cnt FROM skills "
        "WHERE status='active' GROUP BY cert_tier"
    ).fetchall()
    tiers = {r["cert_tier"]: r["cnt"] for r in tier_rows}
    avg_row = conn.execute(
        "SELECT AVG(overall_score) as avg_score, "
        "AVG(confidence) as avg_conf "
        "FROM skills WHERE status='active'"
    ).fetchone()
    conn.close()
    return {
        "total_skills": total,
        "gold": tiers.get("gold", 0),
        "silver": tiers.get("silver", 0),
        "bronze": tiers.get("bronze", 0),
        "uncertified": tiers.get("uncertified", 0),
        "avg_score": round(avg_row["avg_score"] or 0, 3),
        "avg_confidence": round(avg_row["avg_conf"] or 0, 3),
    }


# ── Vote operations (with anti-gaming) ──────────────────────────────


def cast_vote(vote: Vote) -> tuple[bool, str]:
    """Cast a vote with anti-gaming checks."""
    conn = _conn()
    # Check for existing vote
    existing = conn.execute(
        "SELECT id FROM votes WHERE skill_id = ? AND voter_fingerprint = ?",
        (vote.skill_id, vote.voter_fingerprint),
    ).fetchone()
    if existing:
        conn.close()
        return False, "already voted on this skill"

    # Rate limit: max 20 votes per hour per voter
    one_hour_ago = (
        (datetime.now(timezone.utc) - timedelta(hours=1))
        .replace(microsecond=0)
        .isoformat()
    )
    recent = conn.execute(
        "SELECT COUNT(*) FROM votes "
        "WHERE voter_fingerprint = ? AND created_at > ?",
        (vote.voter_fingerprint, one_hour_ago),
    ).fetchone()[0]
    if recent >= 20:
        conn.close()
        return False, "vote rate limit exceeded (20/hr)"

    vote.id = str(uuid.uuid4())
    vote.created_at = _now()
    conn.execute(
        "INSERT INTO votes "
        "(id, skill_id, voter_fingerprint, value, reason, "
        "voter_reputation, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            vote.id, vote.skill_id, vote.voter_fingerprint,
            vote.value, vote.reason, vote.voter_reputation,
            vote.created_at,
        ),
    )

    # Update skill vote counts and community score (Wilson score)
    _update_community_score(conn, vote.skill_id)
    conn.commit()
    conn.close()
    return True, "vote recorded"


def _update_community_score(
    conn: sqlite3.Connection, skill_id: str
) -> None:
    """Recalculate community score using Wilson score interval."""
    rows = conn.execute(
        "SELECT value, voter_reputation FROM votes WHERE skill_id = ?",
        (skill_id,),
    ).fetchall()
    ups = sum(r["voter_reputation"] for r in rows if r["value"] == 1)
    downs = sum(
        r["voter_reputation"] for r in rows if r["value"] == -1
    )
    n = ups + downs
    if n == 0:
        score = 0.0
    else:
        z = 1.96
        p = ups / n
        score = (
            p + z * z / (2 * n)
            - z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
        ) / (1 + z * z / n)
    conn.execute(
        "UPDATE skills SET upvotes=?, downvotes=?, community_score=? "
        "WHERE id=?",
        (int(ups), int(downs), round(score, 4), skill_id),
    )


# ── Feedback operations ─────────────────────────────────────────────


def add_feedback(entry: FeedbackEntry) -> str:
    """Record a prediction for the learning loop."""
    entry.id = str(uuid.uuid4())
    entry.created_at = _now()
    conn = _conn()
    conn.execute(
        "INSERT INTO feedback "
        "(id, skill_name, source_url, predicted_grade, "
        "predicted_score, confidence, dimensions_json, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            entry.id, entry.skill_name, entry.source_url,
            entry.predicted_grade, entry.predicted_score,
            entry.confidence, entry.dimensions_json,
            entry.created_at,
        ),
    )
    conn.commit()
    conn.close()
    return entry.id


def update_feedback_outcome(skill_name: str, **outcomes) -> bool:
    """Attach real-world outcomes to a previous prediction."""
    invalid = set(outcomes) - FEEDBACK_COLUMNS
    if invalid:
        raise ValueError(f"Invalid columns: {invalid}")
    conn = _conn()
    outcomes["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in outcomes)
    values = list(outcomes.values()) + [skill_name]
    conn.execute(
        f"UPDATE feedback SET {set_clause} WHERE skill_name = ?",
        values,
    )
    conn.commit()
    conn.close()
    return True


def get_feedback_entries(
    with_outcomes_only: bool = False,
) -> list[dict]:
    """Return feedback entries, optionally filtered to those with outcomes."""
    conn = _conn()
    if with_outcomes_only:
        rows = conn.execute(
            "SELECT * FROM feedback "
            "WHERE outcome_installs IS NOT NULL "
            "OR outcome_community_score IS NOT NULL"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM feedback").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Agent-native persistence ──────────────────────────────────────────


def add_agent_profile(profile: AgentProfile) -> str:
    """Insert an agent profile and return its ID."""
    profile.id = profile.id or str(uuid.uuid4())
    profile.created_at = profile.created_at or _now()
    profile.updated_at = _now()
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO agent_profiles "
        "(id, name, field, role, summary, owner, source_url, packaging_type, visibility, license, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            profile.id,
            profile.name,
            profile.field,
            profile.role,
            profile.summary,
            profile.owner,
            profile.source_url,
            profile.packaging_type.value,
            profile.visibility.value,
            profile.license,
            profile.created_at,
            profile.updated_at,
        ),
    )
    conn.commit()
    conn.close()
    return profile.id


def get_agent_profile(profile_id: str) -> Optional[AgentProfile]:
    """Fetch a single agent profile by ID."""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM agent_profiles WHERE id = ?", (profile_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_agent_profile(dict(row))


def list_agent_profiles(
    field: Optional[str] = None,
    role: Optional[str] = None,
    visibility: Optional[str] = None,
    limit: int = 50,
) -> list[AgentProfile]:
    """List agent profiles with optional field/role filters."""
    conn = _conn()
    clauses: list[str] = ["1=1"]
    params: list[object] = []
    if field:
        clauses.append("field = ?")
        params.append(field)
    if role:
        clauses.append("role = ?")
        params.append(role)
    if visibility:
        clauses.append("visibility = ?")
        params.append(visibility)
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM agent_profiles WHERE {' AND '.join(clauses)} "
        "ORDER BY updated_at DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [_row_to_agent_profile(dict(r)) for r in rows]


def add_artifact_record(record: ArtifactRecord) -> str:
    """Insert a raw artifact record and return its ID."""
    record.id = record.id or str(uuid.uuid4())
    record.created_at = record.created_at or _now()
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO artifact_records "
        "(id, packaging_type, source_type, source_url, source_commit, raw_content, sanitized_content, content_hash, security_findings_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            record.id,
            record.packaging_type.value,
            record.source_type,
            record.source_url,
            record.source_commit,
            record.raw_content,
            record.sanitized_content,
            record.content_hash,
            json.dumps(record.security_findings),
            record.created_at,
        ),
    )
    conn.commit()
    conn.close()
    return record.id


def get_artifact_record(record_id: str) -> Optional[ArtifactRecord]:
    """Fetch a stored artifact record by ID."""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM artifact_records WHERE id = ?", (record_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_artifact_record(dict(row))


def add_agent_version(version: AgentVersion) -> str:
    """Insert an agent version and return its ID."""
    version.id = version.id or str(uuid.uuid4())
    version.created_at = version.created_at or _now()
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO agent_versions "
        "(id, profile_id, version_label, source_commit, content_hash, packaging_type, provenance_json, artifact_id, runner_contract_json, eligibility, ineligibility_reason, security_findings_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            version.id,
            version.profile_id,
            version.version_label,
            version.source_commit,
            version.content_hash,
            version.packaging_type.value,
            json.dumps(version.provenance.model_dump(mode="json")),
            version.artifact_id,
            json.dumps(version.runner_contract.model_dump(mode="json")) if version.runner_contract else "",
            version.eligibility.value,
            version.ineligibility_reason,
            json.dumps(version.security_findings),
            version.created_at,
        ),
    )
    conn.commit()
    conn.close()
    return version.id


def get_agent_version(version_id: str) -> Optional[AgentVersion]:
    """Fetch a stored agent version by ID."""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM agent_versions WHERE id = ?", (version_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_agent_version(dict(row))


def find_agent_version_by_content_hash(content_hash: str) -> Optional[AgentVersion]:
    """Fetch the latest agent version for an exact sanitized content hash."""
    if not content_hash:
        return None
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM agent_versions WHERE content_hash = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (content_hash,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_agent_version(dict(row))


def list_agent_versions(
    profile_id: Optional[str] = None,
    eligibility: Optional[str] = None,
    limit: int = 50,
) -> list[AgentVersion]:
    """List agent versions with optional filters."""
    conn = _conn()
    clauses: list[str] = ["1=1"]
    params: list[object] = []
    if profile_id:
        clauses.append("profile_id = ?")
        params.append(profile_id)
    if eligibility:
        clauses.append("eligibility = ?")
        params.append(eligibility)
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM agent_versions WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [_row_to_agent_version(dict(r)) for r in rows]


def list_benchmark_ready_agents(
    field: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Return eligible normalized agent versions joined with profile metadata."""
    conn = _conn()
    clauses = [
        "av.eligibility = ?",
        "av.runner_contract_json != ''",
    ]
    params: list[object] = [EligibilityState.eligible.value]
    if field:
        clauses.append("ap.field = ?")
        params.append(field)
    if role:
        clauses.append("ap.role = ?")
        params.append(role)
    params.append(limit)
    rows = conn.execute(
        "SELECT "
        "ap.id AS profile_id, ap.name AS profile_name, ap.field, ap.role, "
        "ap.summary, ap.owner, ap.source_url, ap.visibility, ap.license, "
        "av.id AS version_id, av.version_label, av.source_commit, av.content_hash, "
        "av.packaging_type, av.artifact_id, av.runner_contract_json, "
        "av.security_findings_json, av.created_at AS version_created_at "
        "FROM agent_versions av "
        "JOIN agent_profiles ap ON av.profile_id = ap.id "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY av.created_at DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


AGENT_VERSION_COLUMNS = {
    "version_label",
    "source_commit",
    "content_hash",
    "artifact_id",
    "runner_contract_json",
    "eligibility",
    "ineligibility_reason",
    "security_findings_json",
}


def update_agent_version(version_id: str, **fields) -> bool:
    """Update mutable fields on an agent version."""
    invalid = set(fields) - (
        AGENT_VERSION_COLUMNS | {"runner_contract", "security_findings"}
    )
    if invalid:
        raise ValueError(f"Invalid agent_version columns: {invalid}")
    serialized_fields: dict[str, object] = {}
    for key, value in fields.items():
        if key == "runner_contract":
            serialized_fields["runner_contract_json"] = (
                json.dumps(value.model_dump(mode="json")) if value else ""
            )
        elif key == "security_findings":
            serialized_fields["security_findings_json"] = json.dumps(value)
        elif key == "eligibility" and isinstance(value, EligibilityState):
            serialized_fields["eligibility"] = value.value
        else:
            serialized_fields[key] = value
    conn = _conn()
    set_clause = ", ".join(f"{k} = ?" for k in serialized_fields)
    conn.execute(
        f"UPDATE agent_versions SET {set_clause} WHERE id = ?",
        list(serialized_fields.values()) + [version_id],
    )
    conn.commit()
    conn.close()
    return True


def add_run_trace(trace: RunTrace) -> str:
    """Insert a run trace and return its ID."""
    trace.id = trace.id or str(uuid.uuid4())
    trace.created_at = trace.created_at or _now()
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO run_traces "
        "(id, agent_version_id, field, role, tournament_id, tournament_run_id, task_id, trace_kind, status, exec_provider, judge_provider, final_output, error, input_tokens, output_tokens, total_cost_usd, runtime_ms, prompt_json, tool_calls_json, tool_outputs_json, judge_prompt, judge_output, metadata_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            trace.id,
            trace.agent_version_id,
            trace.field,
            trace.role,
            trace.tournament_id,
            trace.tournament_run_id,
            trace.task_id,
            trace.trace_kind,
            trace.status,
            trace.exec_provider,
            trace.judge_provider,
            trace.final_output,
            trace.error,
            trace.input_tokens,
            trace.output_tokens,
            trace.total_cost_usd,
            trace.runtime_ms,
            trace.prompt_json,
            trace.tool_calls_json,
            trace.tool_outputs_json,
            trace.judge_prompt,
            trace.judge_output,
            trace.metadata_json,
            trace.created_at,
        ),
    )
    conn.commit()
    conn.close()
    return trace.id


def get_run_trace(trace_id: str) -> Optional[RunTrace]:
    """Fetch a run trace by ID."""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM run_traces WHERE id = ?", (trace_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_run_trace(dict(row))


def list_run_traces(
    agent_version_id: Optional[str] = None,
    tournament_id: Optional[str] = None,
    limit: int = 50,
) -> list[RunTrace]:
    """List traces by version or tournament."""
    conn = _conn()
    clauses: list[str] = ["1=1"]
    params: list[object] = []
    if agent_version_id:
        clauses.append("agent_version_id = ?")
        params.append(agent_version_id)
    if tournament_id:
        clauses.append("tournament_id = ?")
        params.append(tournament_id)
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM run_traces WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [_row_to_run_trace(dict(r)) for r in rows]


HOSTED_RUN_COLUMNS = {
    "status", "input_tokens", "output_tokens", "total_cost_usd",
    "runtime_ms", "error", "updated_at",
}


def add_hosted_run(run: HostedRun) -> str:
    """Insert a hosted run and return its ID."""
    run.id = run.id or str(uuid.uuid4())
    run.created_at = run.created_at or _now()
    run.updated_at = _now()
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO hosted_runs "
        "(id, agent_profile_id, agent_version_id, user_fingerprint, prompt, status, input_tokens, output_tokens, total_cost_usd, runtime_ms, error, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run.id,
            run.agent_profile_id,
            run.agent_version_id,
            run.user_fingerprint,
            run.prompt,
            run.status,
            run.input_tokens,
            run.output_tokens,
            run.total_cost_usd,
            run.runtime_ms,
            run.error,
            run.created_at,
            run.updated_at,
        ),
    )
    conn.commit()
    conn.close()
    return run.id


def update_hosted_run(run_id: str, **fields) -> bool:
    """Update a hosted run."""
    invalid = set(fields) - HOSTED_RUN_COLUMNS
    if invalid:
        raise ValueError(f"Invalid hosted_run columns: {invalid}")
    conn = _conn()
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE hosted_runs SET {set_clause} WHERE id = ?",
        list(fields.values()) + [run_id],
    )
    conn.commit()
    conn.close()
    return True


def get_hosted_run(run_id: str) -> Optional[HostedRun]:
    """Fetch a hosted run by ID."""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM hosted_runs WHERE id = ?", (run_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_hosted_run(dict(row))


def add_usage_ledger_entry(entry: UsageLedgerEntry) -> str:
    """Insert a usage ledger entry and return its ID."""
    entry.id = entry.id or str(uuid.uuid4())
    entry.created_at = entry.created_at or _now()
    conn = _conn()
    conn.execute(
        "INSERT INTO usage_ledger "
        "(id, user_fingerprint, hosted_run_id, provider, window_date, input_tokens, output_tokens, total_cost_usd, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            entry.id,
            entry.user_fingerprint,
            entry.hosted_run_id,
            entry.provider,
            entry.window_date,
            entry.input_tokens,
            entry.output_tokens,
            entry.total_cost_usd,
            entry.created_at,
        ),
    )
    conn.commit()
    conn.close()
    return entry.id


def list_usage_ledger(user_fingerprint: str, limit: int = 100) -> list[UsageLedgerEntry]:
    """List usage ledger entries for a user."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM usage_ledger WHERE user_fingerprint = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_fingerprint, limit),
    ).fetchall()
    conn.close()
    return [_row_to_usage_ledger_entry(dict(r)) for r in rows]


def get_daily_usage_summary(user_fingerprint: str, window_date: str) -> dict:
    """Summarize one user's usage for a given day."""
    conn = _conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(input_tokens), 0) AS input_tokens, "
        "COALESCE(SUM(output_tokens), 0) AS output_tokens, "
        "COALESCE(SUM(total_cost_usd), 0) AS total_cost_usd, "
        "COUNT(*) AS run_count "
        "FROM usage_ledger WHERE user_fingerprint = ? AND window_date = ?",
        (user_fingerprint, window_date),
    ).fetchone()
    conn.close()
    return {
        "user_fingerprint": user_fingerprint,
        "window_date": window_date,
        "input_tokens": row["input_tokens"] if row else 0,
        "output_tokens": row["output_tokens"] if row else 0,
        "total_cost_usd": round(row["total_cost_usd"], 6) if row else 0.0,
        "run_count": row["run_count"] if row else 0,
    }


# ── Category operations ──────────────────────────────────────────────


def upsert_category(slug: str, display_name: str, **kwargs) -> None:
    conn = _conn()
    existing = conn.execute("SELECT slug FROM categories WHERE slug = ?", (slug,)).fetchone()
    if existing:
        fields = {"display_name": display_name, "updated_at": _now(), **kwargs}
        valid = {"display_name", "description", "task_count", "skill_count", "active", "updated_at"}
        fields = {k: v for k, v in fields.items() if k in valid}
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE categories SET {set_clause} WHERE slug = ?",
                     list(fields.values()) + [slug])
    else:
        conn.execute(
            "INSERT INTO categories (slug, display_name, description, task_count, skill_count, active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (slug, display_name, kwargs.get("description", ""), kwargs.get("task_count", 0),
             kwargs.get("skill_count", 0), 1 if kwargs.get("active", True) else 0, _now(), _now()),
        )
    conn.commit()
    conn.close()


def list_categories(active_only: bool = True) -> list[dict]:
    conn = _conn()
    if active_only:
        rows = conn.execute("SELECT * FROM categories WHERE active = 1 ORDER BY skill_count DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM categories ORDER BY skill_count DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Tournament operations ────────────────────────────────────────────


def create_tournament(
    category: str,
    week: str,
    task_ids: list[str],
    *,
    field: str = "",
    role: str = "",
    runtime_class: str = "standard",
    task_pack_version: str = "",
    tournament_type: str = "standardized",
) -> str:
    tid = str(uuid.uuid4())
    conn = _conn()
    conn.execute(
        "INSERT INTO tournaments "
        "(id, category, week, task_ids_json, field, role, runtime_class, "
        "task_pack_version, tournament_type, started_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tid, category, week, json.dumps(task_ids),
         field, role, runtime_class, task_pack_version, tournament_type, _now()),
    )
    conn.commit()
    conn.close()
    return tid


def update_tournament(tournament_id: str, **fields) -> bool:
    valid = {"status", "num_skills", "baseline_avg", "completed_at",
             "total_cost_usd", "total_input_tokens", "total_output_tokens",
             "field", "role", "runtime_class", "task_pack_version", "tournament_type"}
    invalid = set(fields) - valid
    if invalid:
        raise ValueError(f"Invalid tournament columns: {invalid}")
    conn = _conn()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE tournaments SET {set_clause} WHERE id = ?",
                 list(fields.values()) + [tournament_id])
    conn.commit()
    conn.close()
    return True


def get_tournament(tournament_id: str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_tournament_by_week(category: str, week: str) -> dict | None:
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM tournaments WHERE category = ? AND week = ?",
        (category, week),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_tournaments(category: str | None = None, limit: int = 20) -> list[dict]:
    conn = _conn()
    if category:
        rows = conn.execute(
            "SELECT * FROM tournaments WHERE category = ? ORDER BY week DESC LIMIT ?",
            (category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tournaments ORDER BY week DESC LIMIT ?", (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Tournament entry operations ──────────────────────────────────────


def add_tournament_entry(tournament_id: str, entry: dict) -> str:
    eid = str(uuid.uuid4())
    conn = _conn()
    conn.execute(
        "INSERT INTO tournament_entries "
        "(id, tournament_id, skill_id, skill_name, rank, avg_score, pass_rate, "
        "total_tokens, total_runtime_ms, rating_before, rating_after, task_results_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (eid, tournament_id, entry["skill_id"], entry["skill_name"],
         entry.get("rank", 0), entry.get("avg_score", 0), entry.get("pass_rate", 0),
         entry.get("total_tokens", 0), entry.get("total_runtime_ms", 0),
         entry.get("rating_before", 1500), entry.get("rating_after", 1500),
         json.dumps(entry.get("task_results", [])), _now()),
    )
    conn.commit()
    conn.close()
    return eid


def get_tournament_entries(tournament_id: str) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM tournament_entries WHERE tournament_id = ? ORDER BY rank",
        (tournament_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Rating operations ────────────────────────────────────────────────


def get_skill_rating(skill_id: str, category: str) -> dict | None:
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM skill_ratings WHERE skill_id = ? AND category = ?",
        (skill_id, category),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_skill_rating(
    skill_id: str, category: str,
    mu: float, rd: float, sigma: float, **kwargs,
) -> None:
    conn = _conn()
    existing = conn.execute(
        "SELECT skill_id FROM skill_ratings WHERE skill_id = ? AND category = ?",
        (skill_id, category),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE skill_ratings SET mu=?, rd=?, sigma=?, tournaments_played=?, "
            "last_tournament_week=?, updated_at=? WHERE skill_id=? AND category=?",
            (mu, rd, sigma, kwargs.get("tournaments_played", 0),
             kwargs.get("last_tournament_week", ""), _now(), skill_id, category),
        )
    else:
        conn.execute(
            "INSERT INTO skill_ratings "
            "(skill_id, category, mu, rd, sigma, tournaments_played, last_tournament_week, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (skill_id, category, mu, rd, sigma,
             kwargs.get("tournaments_played", 0), kwargs.get("last_tournament_week", ""),
             _now(), _now()),
        )
    conn.commit()
    conn.close()


def add_rating_history(
    skill_id: str, category: str, week: str,
    mu: float, rd: float, rank: int, avg_score: float,
) -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO skill_rating_history (id, skill_id, category, week, mu, rd, rank, avg_score, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), skill_id, category, week, mu, rd, rank, avg_score, _now()),
    )
    conn.commit()
    conn.close()


def get_rating_history(skill_id: str, category: str, limit: int = 52) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM skill_rating_history WHERE skill_id = ? AND category = ? "
        "ORDER BY week DESC LIMIT ?",
        (skill_id, category, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Coaching operations ──────────────────────────────────────────────


def add_coaching(rec: dict) -> str:
    cid = str(uuid.uuid4())
    conn = _conn()
    conn.execute(
        "INSERT INTO coaching "
        "(id, skill_id, skill_name, category, tournament_id, tournament_week, "
        "current_rank, current_rating, recommendations_json, summary, "
        "estimated_rank_improvement, status, generated_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (cid, rec["skill_id"], rec["skill_name"], rec["category"],
         rec.get("tournament_id", ""), rec.get("tournament_week", ""),
         rec.get("current_rank", 0), rec.get("current_rating", 0),
         json.dumps(rec.get("recommendations", [])), rec.get("summary", ""),
         rec.get("estimated_rank_improvement", 0), "pending", _now(), _now()),
    )
    conn.commit()
    conn.close()
    return cid


def get_coaching_for_skill(skill_id: str, limit: int = 5) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM coaching WHERE skill_id = ? ORDER BY created_at DESC LIMIT ?",
        (skill_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Category-aware skill queries ─────────────────────────────────────


def list_skills_by_category(category: str, limit: int = 50) -> list[Skill]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM skills WHERE primary_category = ? AND status = 'active' "
        "ORDER BY overall_score DESC LIMIT ?",
        (category, limit),
    ).fetchall()
    conn.close()
    return [_row_to_skill(dict(r)) for r in rows]


def get_category_leaderboard(category: str) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT sr.*, s.name as skill_name FROM skill_ratings sr "
        "JOIN skills s ON sr.skill_id = s.id "
        "WHERE sr.category = ? ORDER BY sr.mu DESC",
        (category,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Agent-native leaderboard and queries ─────────────────────────────


def get_agent_leaderboard(field: str, role: str) -> list[dict]:
    """Glicko-2 leaderboard for a field/role, keyed by agent version ID.

    Joins skill_ratings (where skill_id holds the agent version_id for
    agent-native tournaments) with agent_versions and agent_profiles.
    """
    category = f"{field}/{role}"
    conn = _conn()
    rows = conn.execute(
        "SELECT sr.skill_id AS version_id, sr.mu, sr.rd, sr.sigma, "
        "sr.tournaments_played, sr.last_tournament_week, "
        "ap.name AS agent_name, ap.field, ap.role, ap.owner, ap.source_url, "
        "av.version_label, av.content_hash "
        "FROM skill_ratings sr "
        "JOIN agent_versions av ON sr.skill_id = av.id "
        "JOIN agent_profiles ap ON av.profile_id = ap.id "
        "WHERE sr.category = ? "
        "ORDER BY sr.mu DESC",
        (category,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_agent_version_detail(version_id: str) -> dict | None:
    """Full detail for one agent version including profile and latest rating."""
    conn = _conn()
    row = conn.execute(
        "SELECT av.*, ap.name AS profile_name, ap.field, ap.role, "
        "ap.summary, ap.owner, ap.source_url AS profile_source_url, "
        "ap.visibility, ap.license "
        "FROM agent_versions av "
        "JOIN agent_profiles ap ON av.profile_id = ap.id "
        "WHERE av.id = ?",
        (version_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    detail = dict(row)

    # Attach latest rating if available
    category = f"{detail['field']}/{detail['role']}"
    rating_row = conn.execute(
        "SELECT mu, rd, sigma, tournaments_played, last_tournament_week "
        "FROM skill_ratings WHERE skill_id = ? AND category = ?",
        (version_id, category),
    ).fetchone()
    detail["rating"] = dict(rating_row) if rating_row else None

    # Attach tournament history
    history_rows = conn.execute(
        "SELECT week, mu, rd, rank, avg_score "
        "FROM skill_rating_history WHERE skill_id = ? AND category = ? "
        "ORDER BY week DESC LIMIT 52",
        (version_id, category),
    ).fetchall()
    detail["rating_history"] = [dict(r) for r in history_rows]

    lane_row = conn.execute(
        "SELECT runtime_class, task_pack_version, tournament_type "
        "FROM tournaments WHERE category = ? "
        "ORDER BY week DESC LIMIT 1",
        (category,),
    ).fetchone()
    if lane_row:
        detail["runtime_class"] = lane_row["runtime_class"]
        detail["task_pack_version"] = lane_row["task_pack_version"]
        detail["tournament_type"] = lane_row["tournament_type"]
    else:
        detail["runtime_class"] = "standard"
        detail["task_pack_version"] = "v1"
        detail["tournament_type"] = "standardized"

    # Attach latest tournament entries
    entry_rows = conn.execute(
        "SELECT te.tournament_id, te.rank, te.avg_score, te.pass_rate, "
        "te.total_tokens, te.rating_before, te.rating_after, "
        "t.week, t.category, t.runtime_class, t.task_pack_version, "
        "t.tournament_type "
        "FROM tournament_entries te "
        "JOIN tournaments t ON te.tournament_id = t.id "
        "WHERE te.skill_id = ? "
        "ORDER BY te.created_at DESC LIMIT 10",
        (version_id,),
    ).fetchall()
    detail["tournament_entries"] = [dict(r) for r in entry_rows]

    trace_rows = conn.execute(
        "SELECT id, tournament_id, tournament_run_id, task_id, trace_kind, status, "
        "exec_provider, judge_provider, total_cost_usd, runtime_ms, "
        "created_at "
        "FROM run_traces WHERE agent_version_id = ? "
        "ORDER BY created_at DESC LIMIT 20",
        (version_id,),
    ).fetchall()
    detail["recent_traces"] = [dict(r) for r in trace_rows]

    conn.close()
    return detail


def list_agent_fields_roles() -> list[dict]:
    """List distinct field/role pairs that have agent profiles.

    Returns a list of dicts with field, role, and agent_count.
    """
    conn = _conn()
    rows = conn.execute(
        "SELECT field, role, COUNT(*) AS agent_count "
        "FROM agent_profiles "
        "GROUP BY field, role "
        "ORDER BY field, role"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Human review operations ──────────────────────────────────────────


def list_review_queue(
    review_state: str = "",
    field: str = "",
    role: str = "",
    limit: int = 50,
) -> list[dict]:
    """Return agent versions needing or having review, with profile metadata."""
    conn = _conn()
    clauses: list[str] = []
    params: list[object] = []

    if review_state:
        clauses.append("av.review_state = ?")
        params.append(review_state)
    if field:
        clauses.append("ap.field = ?")
        params.append(field)
    if role:
        clauses.append("ap.role = ?")
        params.append(role)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = conn.execute(
        "SELECT "
        "av.id AS version_id, av.version_label, av.eligibility, "
        "av.review_state, av.predicted_field, av.predicted_role, "
        "av.jd_fit_score, av.qualification_fit_score, av.work_sample_fit_score, "
        "av.manual_review_required, av.reviewed_by, av.reviewed_at, "
        "av.ineligibility_reason, av.security_findings_json, av.created_at, "
        "ap.id AS profile_id, ap.name AS profile_name, ap.field, ap.role, "
        "ap.summary, ap.owner, ap.source_url, ap.packaging_type, ap.visibility "
        "FROM agent_versions av "
        "JOIN agent_profiles ap ON av.profile_id = ap.id "
        f"{where} "
        "ORDER BY av.manual_review_required DESC, av.created_at DESC "
        "LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_review_candidate_detail(version_id: str) -> dict | None:
    """Full detail for a review candidate including sanitized content."""
    conn = _conn()
    row = conn.execute(
        "SELECT av.*, "
        "ap.name AS profile_name, ap.field, ap.role, ap.summary, "
        "ap.owner, ap.source_url AS profile_source_url, "
        "ap.packaging_type AS profile_packaging_type, ap.visibility, "
        "ar.sanitized_content, ar.security_findings_json AS artifact_security "
        "FROM agent_versions av "
        "JOIN agent_profiles ap ON av.profile_id = ap.id "
        "LEFT JOIN artifact_records ar ON av.artifact_id = ar.id "
        "WHERE av.id = ?",
        (version_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None

    result = dict(row)

    # Attach review history
    decisions = conn.execute(
        "SELECT * FROM review_decisions "
        "WHERE version_id = ? ORDER BY created_at DESC",
        (version_id,),
    ).fetchall()
    result["review_history"] = [dict(d) for d in decisions]

    conn.close()
    return result


_REVIEW_VALID_COLUMNS = frozenset({
    "review_state", "eligibility", "ineligibility_reason",
    "predicted_field", "predicted_role",
    "jd_fit_score", "qualification_fit_score", "work_sample_fit_score",
    "manual_review_required", "reviewed_by", "reviewed_at",
})


def apply_review_decision(
    version_id: str,
    reviewer: str,
    action: str,
    new_state: str,
    reason: str = "",
    note: str = "",
    new_field: str = "",
    new_role: str = "",
    eligibility_update: str = "",
) -> str:
    """Apply a review decision and persist the audit trail.

    Returns the review_decision ID.
    """
    conn = _conn()

    # Read current state
    row = conn.execute(
        "SELECT av.review_state, av.eligibility, ap.field, ap.role "
        "FROM agent_versions av "
        "JOIN agent_profiles ap ON av.profile_id = ap.id "
        "WHERE av.id = ?",
        (version_id,),
    ).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Agent version not found: {version_id}")

    previous_state = row["review_state"] or "pending-review"
    previous_field = row["field"]
    previous_role = row["role"]

    # Persist the decision audit record
    decision_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO review_decisions "
        "(id, version_id, reviewer, action, previous_state, new_state, "
        " previous_role, new_role, previous_field, new_field, reason, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (decision_id, version_id, reviewer, action, previous_state, new_state,
         previous_role, new_role or previous_role,
         previous_field, new_field or previous_field,
         reason, note, _now()),
    )

    # Update agent_version review state
    updates = {
        "review_state": new_state,
        "reviewed_by": reviewer,
        "reviewed_at": _now(),
    }

    # Handle eligibility change
    if eligibility_update:
        updates["eligibility"] = eligibility_update
    elif action == "approve":
        updates["eligibility"] = EligibilityState.eligible.value
    elif action == "reject":
        updates["eligibility"] = EligibilityState.ineligible.value
        updates["ineligibility_reason"] = reason or f"Rejected by {reviewer}"

    # Validate all update keys
    for key in updates:
        if key not in _REVIEW_VALID_COLUMNS:
            conn.close()
            raise ValueError(f"Invalid column for review update: {key}")

    set_clauses = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [version_id]
    conn.execute(
        f"UPDATE agent_versions SET {set_clauses} WHERE id = ?",
        params,
    )

    # Handle relabel: update the profile's field/role
    if action == "relabel" and (new_field or new_role):
        profile_id = conn.execute(
            "SELECT profile_id FROM agent_versions WHERE id = ?",
            (version_id,),
        ).fetchone()["profile_id"]

        profile_updates = []
        profile_params: list[object] = []
        if new_field:
            profile_updates.append("field = ?")
            profile_params.append(new_field)
        if new_role:
            profile_updates.append("role = ?")
            profile_params.append(new_role)
        profile_updates.append("updated_at = ?")
        profile_params.append(_now())
        profile_params.append(profile_id)

        conn.execute(
            f"UPDATE agent_profiles SET {', '.join(profile_updates)} WHERE id = ?",
            profile_params,
        )

    conn.commit()
    conn.close()
    return decision_id


def get_review_history(version_id: str) -> list[dict]:
    """Return all review decisions for a version, newest first."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM review_decisions WHERE version_id = ? ORDER BY created_at DESC",
        (version_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── JD corpus operations ────────────────────────────────────────────


def upsert_jd_posting(posting: dict) -> str:
    """Insert or update a job posting. Returns the posting ID."""
    posting_id = posting.get("id") or str(uuid.uuid4())
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO jd_postings "
        "(id, source_ats, source_board_id, company_name, company_size_bucket, "
        " title, normalized_role, field, role, location, department, "
        " content, content_hash, responsibilities_json, tools_json, skills_json, "
        " posted_at, expires_at, corpus_version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (posting_id,
         posting["source_ats"], posting.get("source_board_id", ""),
         posting["company_name"], posting.get("company_size_bucket", ""),
         posting["title"], posting.get("normalized_role", ""),
         posting.get("field", ""), posting.get("role", ""),
         posting.get("location", ""), posting.get("department", ""),
         posting.get("content", ""), posting.get("content_hash", ""),
         json.dumps(posting.get("responsibilities", [])),
         json.dumps(posting.get("tools", [])),
         json.dumps(posting.get("skills", [])),
         posting.get("posted_at", ""), posting.get("expires_at", ""),
         posting.get("corpus_version", ""),
         _now(), _now()),
    )
    conn.commit()
    conn.close()
    return posting_id


def list_jd_postings(
    field: str = "",
    role: str = "",
    corpus_version: str = "",
    source_ats: str = "",
    limit: int = 50,
) -> list[dict]:
    """List job postings with optional filters."""
    conn = _conn()
    clauses: list[str] = []
    params: list[object] = []

    if field:
        clauses.append("field = ?")
        params.append(field)
    if role:
        clauses.append("role = ?")
        params.append(role)
    if corpus_version:
        clauses.append("corpus_version = ?")
        params.append(corpus_version)
    if source_ats:
        clauses.append("source_ats = ?")
        params.append(source_ats)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM jd_postings {where} ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_corpus_version(
    field: str,
    role: str,
    version_label: str,
    posting_count: int = 0,
    company_count: int = 0,
    source_mix: dict | None = None,
    responsibilities_summary: list | None = None,
    tools_summary: list | None = None,
    skills_summary: list | None = None,
) -> str:
    """Create or update a JD corpus version record. Returns the version ID."""
    vid = str(uuid.uuid4())
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO jd_corpus_versions "
        "(id, field, role, version_label, posting_count, company_count, "
        " source_mix_json, responsibilities_summary_json, "
        " tools_summary_json, skills_summary_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (vid, field, role, version_label, posting_count, company_count,
         json.dumps(source_mix or {}),
         json.dumps(responsibilities_summary or []),
         json.dumps(tools_summary or []),
         json.dumps(skills_summary or []),
         _now()),
    )
    conn.commit()
    conn.close()
    return vid


def get_latest_corpus_version(field: str, role: str) -> dict | None:
    """Get the latest corpus version for a field/role."""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM jd_corpus_versions "
        "WHERE field = ? AND role = ? ORDER BY created_at DESC LIMIT 1",
        (field, role),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_jd_corpus_stats(field: str, role: str) -> dict:
    """Get posting statistics for a field/role corpus."""
    conn = _conn()
    stats = conn.execute(
        "SELECT count(*) as total, "
        "count(DISTINCT company_name) as companies, "
        "count(DISTINCT source_ats) as sources "
        "FROM jd_postings WHERE field = ? AND role = ?",
        (field, role),
    ).fetchone()
    conn.close()
    return dict(stats)


# ── Candidate lead operations ───────────────────────────────────────


def upsert_candidate_lead(lead: dict) -> str:
    """Insert or update a candidate lead. Returns the lead ID.

    Deduplicates by (source_type, content_hash). If an existing lead matches,
    increments mention_count instead of creating a duplicate.
    """
    content_hash = lead.get("content_hash", "")
    source_type = lead["source_type"]

    conn = _conn()

    # Check for existing lead with same source_type + content_hash
    if content_hash:
        existing = conn.execute(
            "SELECT id, mention_count FROM candidate_leads "
            "WHERE source_type = ? AND content_hash = ?",
            (source_type, content_hash),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE candidate_leads SET mention_count = mention_count + 1, "
                "updated_at = ? WHERE id = ?",
                (_now(), existing["id"]),
            )
            conn.commit()
            conn.close()
            return existing["id"]

    lead_id = lead.get("id") or str(uuid.uuid4())
    conn.execute(
        "INSERT OR REPLACE INTO candidate_leads "
        "(id, source_type, source_url, title, description, "
        " outbound_links_json, extracted_artifact_links_json, "
        " mention_count, signal_strength, discovered_at, "
        " review_state, resolution_state, resolved_artifact_url, "
        " content_hash, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (lead_id, source_type, lead["source_url"],
         lead.get("title", ""), lead.get("description", ""),
         json.dumps(lead.get("outbound_links", [])),
         json.dumps(lead.get("extracted_artifact_links", [])),
         lead.get("mention_count", 1),
         lead.get("signal_strength", 0),
         lead.get("discovered_at", _now()),
         "new", "unresolved",
         lead.get("resolved_artifact_url", ""),
         content_hash,
         _now(), _now()),
    )
    conn.commit()
    conn.close()
    return lead_id


def list_candidate_leads(
    source_type: str = "",
    review_state: str = "",
    resolution_state: str = "",
    limit: int = 50,
) -> list[dict]:
    """List candidate leads with optional filters."""
    conn = _conn()
    clauses: list[str] = []
    params: list[object] = []

    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    if review_state:
        clauses.append("review_state = ?")
        params.append(review_state)
    if resolution_state:
        clauses.append("resolution_state = ?")
        params.append(resolution_state)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM candidate_leads {where} "
        "ORDER BY signal_strength DESC, created_at DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_candidate_lead(
    lead_id: str,
    resolution_state: str,
    resolved_artifact_url: str = "",
    resolved_version_id: str = "",
    resolver_note: str = "",
) -> None:
    """Mark a lead as resolved (or dead/no-artifact)."""
    conn = _conn()
    conn.execute(
        "UPDATE candidate_leads SET "
        "resolution_state = ?, resolved_artifact_url = ?, "
        "resolved_version_id = ?, resolver_note = ?, "
        "review_state = 'resolved', updated_at = ? "
        "WHERE id = ?",
        (resolution_state, resolved_artifact_url,
         resolved_version_id, resolver_note,
         _now(), lead_id),
    )
    conn.commit()
    conn.close()


def get_lead_stats() -> dict:
    """Get summary stats for the lead pipeline."""
    conn = _conn()
    stats = conn.execute(
        "SELECT "
        "count(*) as total, "
        "sum(CASE WHEN resolution_state = 'unresolved' THEN 1 ELSE 0 END) as unresolved, "
        "sum(CASE WHEN resolution_state = 'resolved' THEN 1 ELSE 0 END) as resolved, "
        "sum(CASE WHEN resolution_state = 'no-artifact' THEN 1 ELSE 0 END) as no_artifact, "
        "sum(CASE WHEN resolution_state = 'dead-link' THEN 1 ELSE 0 END) as dead_link "
        "FROM candidate_leads",
    ).fetchone()
    conn.close()
    return dict(stats)


# ── Duplicate detection ─────────────────────────────────────────────


def find_exact_duplicates(field: str = "", role: str = "") -> list[dict]:
    """Find agents with identical content_hash in the same lane."""
    conn = _conn()
    clauses = ["av1.content_hash != ''", "av1.content_hash = av2.content_hash",
               "av1.id < av2.id"]
    params: list[object] = []

    if field:
        clauses.append("ap1.field = ?")
        params.append(field)
    if role:
        clauses.append("ap1.role = ?")
        params.append(role)

    where = " AND ".join(clauses)
    rows = conn.execute(
        "SELECT av1.id AS id_a, av2.id AS id_b, "
        "ap1.name AS name_a, ap2.name AS name_b, "
        "av1.content_hash, ap1.field, ap1.role, "
        "ap1.source_url AS src_a, ap2.source_url AS src_b "
        "FROM agent_versions av1 "
        "JOIN agent_profiles ap1 ON av1.profile_id = ap1.id "
        "JOIN agent_versions av2 ON av1.content_hash = av2.content_hash AND av1.id < av2.id "
        "JOIN agent_profiles ap2 ON av2.profile_id = ap2.id AND ap1.role = ap2.role "
        f"WHERE {where} "
        "ORDER BY ap1.role, ap1.name",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_name_duplicates(field: str = "", role: str = "") -> list[dict]:
    """Find agents with identical names in the same lane (different content)."""
    conn = _conn()
    clauses = ["ap1.name = ap2.name", "av1.id < av2.id",
               "ap1.role = ap2.role", "ap1.field = ap2.field"]
    params: list[object] = []

    if field:
        clauses.append("ap1.field = ?")
        params.append(field)
    if role:
        clauses.append("ap1.role = ?")
        params.append(role)

    where = " AND ".join(clauses)
    rows = conn.execute(
        "SELECT av1.id AS id_a, av2.id AS id_b, "
        "ap1.name, av1.content_hash AS hash_a, av2.content_hash AS hash_b, "
        "ap1.field, ap1.role, "
        "ap1.source_url AS src_a, ap2.source_url AS src_b, "
        "ap1.owner AS owner_a, ap2.owner AS owner_b "
        "FROM agent_versions av1 "
        "JOIN agent_profiles ap1 ON av1.profile_id = ap1.id "
        "JOIN agent_versions av2 ON av1.id < av2.id "
        "JOIN agent_profiles ap2 ON av2.profile_id = ap2.id "
        f"WHERE {where} "
        "ORDER BY ap1.role, ap1.name",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_duplicate(
    canonical_version_id: str,
    duplicate_version_id: str,
    similarity_score: float = 1.0,
    match_type: str = "exact",
    note: str = "",
) -> str:
    """Record a duplicate relationship between two agent versions."""
    dup_id = str(uuid.uuid4())
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO duplicate_groups "
            "(id, canonical_version_id, duplicate_version_id, similarity_score, "
            " match_type, review_state, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (dup_id, canonical_version_id, duplicate_version_id,
             similarity_score, match_type, note, _now()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Already recorded
        conn.close()
        return ""
    conn.close()
    return dup_id


def list_duplicate_groups(
    review_state: str = "",
    limit: int = 50,
) -> list[dict]:
    """List duplicate groups with agent metadata."""
    conn = _conn()
    clauses: list[str] = []
    params: list[object] = []

    if review_state:
        clauses.append("dg.review_state = ?")
        params.append(review_state)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = conn.execute(
        "SELECT dg.*, "
        "ap1.name AS canonical_name, ap1.source_url AS canonical_src, "
        "ap2.name AS duplicate_name, ap2.source_url AS duplicate_src "
        "FROM duplicate_groups dg "
        "JOIN agent_versions av1 ON dg.canonical_version_id = av1.id "
        "JOIN agent_profiles ap1 ON av1.profile_id = ap1.id "
        "JOIN agent_versions av2 ON dg.duplicate_version_id = av2.id "
        "JOIN agent_profiles ap2 ON av2.profile_id = ap2.id "
        f"{where} "
        "ORDER BY dg.created_at DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def scan_and_record_duplicates() -> dict:
    """Scan all lanes for duplicates and record them.

    Finds exact-hash duplicates and same-name duplicates.
    Returns summary counts.
    """
    exact = find_exact_duplicates()
    name_dups = find_name_duplicates()

    exact_recorded = 0
    name_recorded = 0

    for dup in exact:
        did = record_duplicate(
            canonical_version_id=dup["id_a"],
            duplicate_version_id=dup["id_b"],
            similarity_score=1.0,
            match_type="exact-hash",
            note=f"Identical content_hash={dup['content_hash']}",
        )
        if did:
            exact_recorded += 1

    for dup in name_dups:
        # Skip if already recorded as exact duplicate
        if dup.get("hash_a") == dup.get("hash_b"):
            continue
        did = record_duplicate(
            canonical_version_id=dup["id_a"],
            duplicate_version_id=dup["id_b"],
            similarity_score=0.8,
            match_type="same-name-different-content",
            note=f"Same name '{dup['name']}' in {dup['field']}/{dup['role']}, "
                 f"different hashes: {dup['hash_a'][:8]} vs {dup['hash_b'][:8]}",
        )
        if did:
            name_recorded += 1

    return {
        "exact_found": len(exact),
        "exact_recorded": exact_recorded,
        "name_found": len(name_dups),
        "name_recorded": name_recorded,
    }


# ── Row conversion ──────────────────────────────────────────────────


def _row_to_skill(row: dict) -> Skill:
    """Convert a sqlite3.Row dict to a Skill model."""
    return Skill(
        id=row["id"],
        name=row["name"],
        description=row.get("description", ""),
        raw_content=row.get("raw_content", ""),
        instructions=row.get("instructions", ""),
        triggers=json.loads(row.get("triggers_json", "[]")),
        allowed_tools=json.loads(row.get("allowed_tools_json", "[]")),
        line_count=row.get("line_count", 0),
        token_estimate=row.get("token_estimate", 0),
        source_repo=row.get("source_repo", ""),
        source_url=row.get("source_url", ""),
        github_stars=row.get("github_stars", 0),
        install_count=row.get("install_count", 0),
        overall_score=row.get("overall_score", 0),
        confidence=row.get("confidence", 0),
        frequency_value=row.get("frequency_value", 0),
        capability_upgrade=row.get("capability_upgrade", 0),
        specificity=row.get("specificity", 0),
        token_efficiency=row.get("token_efficiency", 0),
        source_credibility=row.get("source_credibility", 0),
        trigger_clarity=row.get("trigger_clarity", 0),
        methodology_depth=row.get("methodology_depth", 0),
        llm_quality=row.get("llm_quality", 0),
        cert_tier=CertTier(row.get("cert_tier", "uncertified")),
        cert_checks_json=row.get("cert_checks_json", "[]"),
        cert_date=row.get("cert_date", ""),
        cert_expires=row.get("cert_expires", ""),
        upvotes=row.get("upvotes", 0),
        downvotes=row.get("downvotes", 0),
        community_score=row.get("community_score", 0),
        report_count=row.get("report_count", 0),
        flags_json=row.get("flags_json", "[]"),
        strengths_json=row.get("strengths_json", "[]"),
        llm_reasoning=row.get("llm_reasoning", ""),
        needs_review=bool(row.get("needs_review", 0)),
        status=row.get("status", "active"),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


def _row_to_agent_profile(row: dict) -> AgentProfile:
    """Convert a sqlite3.Row dict to an AgentProfile model."""
    return AgentProfile(
        id=row["id"],
        name=row["name"],
        field=row["field"],
        role=row["role"],
        summary=row.get("summary", ""),
        owner=row.get("owner", ""),
        source_url=row.get("source_url", ""),
        packaging_type=PackagingType(row["packaging_type"]),
        visibility=Visibility(row.get("visibility", Visibility.public.value)),
        license=row.get("license", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


def _row_to_artifact_record(row: dict) -> ArtifactRecord:
    """Convert a sqlite3.Row dict to an ArtifactRecord model."""
    return ArtifactRecord(
        id=row["id"],
        packaging_type=PackagingType(row["packaging_type"]),
        source_type=row["source_type"],
        source_url=row["source_url"],
        source_commit=row.get("source_commit", ""),
        raw_content=row.get("raw_content", ""),
        sanitized_content=row.get("sanitized_content", ""),
        content_hash=row.get("content_hash", ""),
        security_findings=json.loads(
            row.get("security_findings_json", "[]")
        ),
        created_at=row.get("created_at", ""),
    )


def _row_to_agent_version(row: dict) -> AgentVersion:
    """Convert a sqlite3.Row dict to an AgentVersion model."""
    provenance_json = row.get("provenance_json", "{}") or "{}"
    runner_contract_json = row.get("runner_contract_json", "") or ""
    return AgentVersion(
        id=row["id"],
        profile_id=row["profile_id"],
        version_label=row["version_label"],
        source_commit=row.get("source_commit", ""),
        content_hash=row.get("content_hash", ""),
        packaging_type=PackagingType(row["packaging_type"]),
        provenance=ProvenanceRef(**json.loads(provenance_json)),
        artifact_id=row.get("artifact_id", ""),
        runner_contract=(
            RunnerContract(**json.loads(runner_contract_json))
            if runner_contract_json
            else None
        ),
        eligibility=EligibilityState(
            row.get("eligibility", EligibilityState.pending.value)
        ),
        ineligibility_reason=row.get("ineligibility_reason", ""),
        security_findings=json.loads(
            row.get("security_findings_json", "[]")
        ),
        created_at=row.get("created_at", ""),
    )


def _row_to_run_trace(row: dict) -> RunTrace:
    """Convert a sqlite3.Row dict to a RunTrace model."""
    return RunTrace(
        id=row["id"],
        agent_version_id=row["agent_version_id"],
        field=row.get("field", ""),
        role=row.get("role", ""),
        tournament_id=row.get("tournament_id", ""),
        tournament_run_id=row.get("tournament_run_id", ""),
        task_id=row.get("task_id", ""),
        trace_kind=row.get("trace_kind", "benchmark"),
        status=row.get("status", "pending"),
        exec_provider=row.get("exec_provider", ""),
        judge_provider=row.get("judge_provider", ""),
        final_output=row.get("final_output", ""),
        error=row.get("error", ""),
        input_tokens=row.get("input_tokens", 0),
        output_tokens=row.get("output_tokens", 0),
        total_cost_usd=row.get("total_cost_usd", 0.0),
        runtime_ms=row.get("runtime_ms", 0),
        prompt_json=row.get("prompt_json", "{}"),
        tool_calls_json=row.get("tool_calls_json", "[]"),
        tool_outputs_json=row.get("tool_outputs_json", "[]"),
        judge_prompt=row.get("judge_prompt", ""),
        judge_output=row.get("judge_output", ""),
        metadata_json=row.get("metadata_json", "{}"),
        created_at=row.get("created_at", ""),
    )


def _row_to_hosted_run(row: dict) -> HostedRun:
    """Convert a sqlite3.Row dict to a HostedRun model."""
    return HostedRun(
        id=row["id"],
        agent_profile_id=row.get("agent_profile_id", ""),
        agent_version_id=row.get("agent_version_id", ""),
        user_fingerprint=row["user_fingerprint"],
        prompt=row.get("prompt", ""),
        status=row.get("status", "pending"),
        input_tokens=row.get("input_tokens", 0),
        output_tokens=row.get("output_tokens", 0),
        total_cost_usd=row.get("total_cost_usd", 0.0),
        runtime_ms=row.get("runtime_ms", 0),
        error=row.get("error", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


def _row_to_usage_ledger_entry(row: dict) -> UsageLedgerEntry:
    """Convert a sqlite3.Row dict to a UsageLedgerEntry model."""
    return UsageLedgerEntry(
        id=row["id"],
        user_fingerprint=row["user_fingerprint"],
        hosted_run_id=row.get("hosted_run_id", ""),
        provider=row.get("provider", ""),
        window_date=row.get("window_date", ""),
        input_tokens=row.get("input_tokens", 0),
        output_tokens=row.get("output_tokens", 0),
        total_cost_usd=row.get("total_cost_usd", 0.0),
        created_at=row.get("created_at", ""),
    )
