"""JD corpus refresh orchestrator.

Coordinates ATS adapter calls, deduplication, and corpus versioning.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone

from ingest.jd.ashby import AshbyAdapter
from ingest.jd.base import ATSAdapter, RawPosting
from ingest.jd.greenhouse import GreenhouseAdapter
from ingest.jd.lever import LeverAdapter
from store.db import (
    create_corpus_version,
    get_jd_corpus_stats,
    list_jd_postings,
    upsert_jd_posting,
)

ADAPTERS: dict[str, type[ATSAdapter]] = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
}


def _classify_company_size(company_name: str) -> str:
    """Placeholder for company-size classification.

    In production this should use a lookup table or external data source.
    Returns empty string until real data is available.
    """
    return ""


def refresh_lane_corpus(
    field: str,
    role: str,
    sources: list[dict],
    role_filter: str = "",
    max_per_source: int = 50,
) -> dict:
    """Refresh JD corpus for a lane from configured ATS sources.

    Args:
        field: Lane field (e.g. "software-engineering")
        role: Lane role (e.g. "code-review-agent")
        sources: List of dicts with keys: ats, board_id, company_name
        role_filter: Optional keyword filter for job titles
        max_per_source: Max postings to fetch per source

    Returns:
        Summary dict with counts and version info.
    """
    total_fetched = 0
    total_new = 0
    total_deduped = 0
    errors: list[str] = []
    seen_hashes: set[str] = set()

    # Load existing content hashes for dedup
    existing = list_jd_postings(field=field, role=role, limit=1000)
    for p in existing:
        h = p.get("content_hash", "")
        if h:
            seen_hashes.add(h)

    for source in sources:
        ats_name = source["ats"]
        board_id = source["board_id"]
        company_name = source.get("company_name", board_id)

        adapter_cls = ADAPTERS.get(ats_name)
        if not adapter_cls:
            errors.append(f"Unknown ATS: {ats_name}")
            continue

        adapter = adapter_cls()
        try:
            postings = adapter.fetch_postings(
                board_id=board_id,
                role_filter=role_filter,
                max_results=max_per_source,
            )
        except Exception as e:
            errors.append(f"{ats_name}/{board_id}: {e}")
            continue

        total_fetched += len(postings)

        for posting in postings:
            ch = posting.content_hash
            if ch in seen_hashes:
                total_deduped += 1
                continue
            seen_hashes.add(ch)

            upsert_jd_posting({
                "source_ats": posting.source_ats,
                "source_board_id": posting.source_board_id,
                "company_name": company_name,
                "company_size_bucket": _classify_company_size(company_name),
                "title": posting.title,
                "field": field,
                "role": role,
                "location": posting.location,
                "department": posting.department,
                "content": posting.content,
                "content_hash": ch,
                "posted_at": posting.posted_at,
                "expires_at": posting.expires_at,
            })
            total_new += 1

    # Create corpus version snapshot
    stats = get_jd_corpus_stats(field, role)
    now = datetime.now(timezone.utc)
    version_label = now.strftime("%Y-W%V")

    version_id = create_corpus_version(
        field=field,
        role=role,
        version_label=version_label,
        posting_count=stats["total"],
        company_count=stats["companies"],
        source_mix={"sources": stats["sources"]},
    )

    return {
        "field": field,
        "role": role,
        "corpus_version": version_label,
        "corpus_version_id": version_id,
        "total_fetched": total_fetched,
        "new_postings": total_new,
        "deduped": total_deduped,
        "errors": errors,
        "stats": stats,
    }
