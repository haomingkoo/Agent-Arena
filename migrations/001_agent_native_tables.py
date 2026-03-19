"""Create agent-native persistence tables without disturbing legacy skill data."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/certified.db")


MIGRATION_SQL = """
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
"""


def run_migration(db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(MIGRATION_SQL)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create agent-native AgentArena tables."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the SQLite database file.",
    )
    args = parser.parse_args()
    run_migration(Path(args.db))
    print(f"Applied migration 001_agent_native_tables to {args.db}")


if __name__ == "__main__":
    main()
