"""
Ingest agents from msitarzewski/agency-agents GitHub repo.

This repo contains 190+ well-structured agent configs organized by domain.
Each agent is a markdown file with YAML frontmatter (name, description).

We map their directory structure to our field/role taxonomy:
  engineering/* -> software-engineering/*
  testing/* -> software-engineering/qa-agent or code-review-agent
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agents.contracts import (
    EligibilityState,
    PackagingType,
    ProvenanceRef,
    RunnerContract,
)
from evaluate.safety import scan_text
from store.db import _conn, _now, init_db


REPO = "msitarzewski/agency-agents"
REPO_URL = f"https://github.com/{REPO}"

# Map repo directories to our field/role taxonomy
# Only map directories we have task packs for (or plan to)
ROLE_MAP: dict[str, tuple[str, str]] = {
    # engineering/ agents that do code review or security review
    "engineering/engineering-code-reviewer.md": ("software-engineering", "code-review-agent"),
    "engineering/engineering-security-engineer.md": ("software-engineering", "code-review-agent"),
    "engineering/engineering-threat-detection-engineer.md": ("software-engineering", "code-review-agent"),

    # engineering/ agents that are general SWE
    "engineering/engineering-senior-developer.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-backend-architect.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-software-architect.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-frontend-developer.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-ai-engineer.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-data-engineer.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-rapid-prototyper.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-mobile-app-builder.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-database-optimizer.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-sre.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-devops-automator.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-incident-response-commander.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-git-workflow-master.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-embedded-firmware-engineer.md": ("software-engineering", "software-engineer-agent"),
    "engineering/engineering-technical-writer.md": ("software-engineering", "software-engineer-agent"),

    # testing/ agents -> code-review or QA
    "testing/testing-reality-checker.md": ("software-engineering", "code-review-agent"),
    "testing/testing-api-tester.md": ("software-engineering", "code-review-agent"),
    "testing/testing-accessibility-auditor.md": ("software-engineering", "code-review-agent"),
    "testing/testing-performance-benchmarker.md": ("software-engineering", "code-review-agent"),
    "testing/testing-evidence-collector.md": ("software-engineering", "code-review-agent"),
    "testing/testing-test-results-analyzer.md": ("software-engineering", "code-review-agent"),
}


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown. Returns (metadata, body)."""
    if not content.startswith("---"):
        return {}, content

    end = content.find("---", 3)
    if end == -1:
        return {}, content

    frontmatter = content[3:end].strip()
    body = content[end + 3:].strip()

    metadata: dict[str, str] = {}
    for line in frontmatter.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip().strip('"').strip("'")

    return metadata, body


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _build_runner_contract(
    field: str,
    role: str,
    name: str,
    body: str,
    version_id: str,
    source_url: str,
) -> dict:
    """Build a RunnerContract dict from agent markdown body."""
    # Use the full body as system instructions (up to 8000 chars)
    system_instructions = body[:8000]

    return {
        "field": field,
        "role": role,
        "profile_name": name,
        "version_id": version_id,
        "source_url": source_url,
        "packaging_type": "markdown_prompt_bundle",
        "system_instructions": system_instructions,
        "model_provider": "qwen",
        "model_name": "qwen-plus",
        "max_steps": 8,
        "timeout_seconds": 120,
        "max_total_tokens": 10000,
    }


def fetch_and_register(
    dry_run: bool = False,
    paths: list[str] | None = None,
) -> dict:
    """Fetch agents from agency-agents repo and register them.

    Args:
        dry_run: If True, only print what would be registered.
        paths: Optional list of specific paths to fetch. If None, uses ROLE_MAP keys.

    Returns:
        Summary dict with counts.
    """
    target_paths = paths or list(ROLE_MAP.keys())
    registered = 0
    skipped = 0
    errors: list[str] = []

    conn = _conn()

    for file_path in target_paths:
        mapping = ROLE_MAP.get(file_path)
        if not mapping:
            skipped += 1
            continue

        field, role = mapping

        # Fetch content via gh CLI
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{REPO}/contents/{file_path}",
                 "--jq", ".content"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                errors.append(f"{file_path}: gh api failed: {result.stderr[:100]}")
                continue

            import base64
            content = base64.b64decode(result.stdout.strip()).decode("utf-8")
        except Exception as e:
            errors.append(f"{file_path}: fetch error: {e}")
            continue

        metadata, body = _parse_frontmatter(content)
        name = metadata.get("name", file_path.split("/")[-1].replace(".md", ""))
        description = metadata.get("description", "")
        ch = _content_hash(content)

        # Check if already registered by content hash
        existing = conn.execute(
            "SELECT id FROM agent_versions WHERE content_hash = ?", (ch,)
        ).fetchone()
        if existing:
            print(f"  Skip (exists): {name} [{field}/{role}]")
            skipped += 1
            continue

        source_url = f"{REPO_URL}/blob/main/{file_path}"

        # Safety scan before registration
        threats = scan_text(content)
        if threats:
            eligibility = EligibilityState.pending.value
            print(f"  Safety threats in {name}: {threats}")
        else:
            eligibility = EligibilityState.eligible.value

        if dry_run:
            print(f"  Would register: {name} -> {field}/{role}")
            registered += 1
            continue

        # Create profile
        profile_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO agent_profiles "
            "(id, name, field, role, summary, owner, source_url, packaging_type, "
            " visibility, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (profile_id, name, field, role, description,
             REPO, source_url, "markdown_prompt_bundle",
             "public", _now(), _now()),
        )

        # Create version
        version_id = str(uuid.uuid4())
        contract = _build_runner_contract(
            field, role, name, body, version_id, source_url,
        )

        provenance = {
            "source_type": "github",
            "source_url": source_url,
            "discovered_at": _now(),
        }
        if threats:
            provenance["safety_threats"] = threats

        conn.execute(
            "INSERT INTO agent_versions "
            "(id, profile_id, version_label, content_hash, packaging_type, "
            " provenance_json, runner_contract_json, eligibility, "
            " review_state, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (version_id, profile_id, "v1", ch,
             "markdown_prompt_bundle",
             json.dumps(provenance), json.dumps(contract),
             eligibility,
             "pending-review",
             _now()),
        )

        print(f"  Registered: {name} -> {field}/{role} (vid: {version_id[:8]})")
        registered += 1

    conn.commit()
    conn.close()

    return {
        "source": REPO,
        "registered": registered,
        "skipped": skipped,
        "errors": errors,
    }


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    print(f"Ingesting from {REPO} {'(dry run)' if dry else ''}")
    print(f"Mapped paths: {len(ROLE_MAP)}")
    print()
    result = fetch_and_register(dry_run=dry)
    print()
    print(f"Registered: {result['registered']}")
    print(f"Skipped: {result['skipped']}")
    if result["errors"]:
        print(f"Errors: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  {e}")
