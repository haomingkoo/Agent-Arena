"""Lever Postings API adapter.

API docs: https://github.com/lever/postings-api

Public postings endpoints (no auth required):
  GET https://api.lever.co/v0/postings/{company}
  GET https://api.lever.co/v0/postings/{company}/{posting_id}
"""
from __future__ import annotations

import re

import requests

from ingest.jd.base import ATSAdapter, RawPosting

_BASE_URL = "https://api.lever.co/v0/postings"
_TIMEOUT = 15


def _strip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class LeverAdapter(ATSAdapter):
    source_ats = "lever"

    def fetch_postings(
        self,
        board_id: str,
        role_filter: str = "",
        max_results: int = 50,
    ) -> list[RawPosting]:
        url = f"{_BASE_URL}/{board_id}"
        params: dict[str, object] = {"mode": "json"}
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        jobs = resp.json()

        if not isinstance(jobs, list):
            return []

        postings: list[RawPosting] = []
        for job in jobs[:max_results]:
            title = job.get("text", "")
            if role_filter and role_filter.lower() not in title.lower():
                continue

            # Build content from description + lists
            parts: list[str] = []
            desc = job.get("descriptionPlain", "") or job.get("description", "")
            if desc:
                parts.append(_strip_html(desc) if "<" in desc else desc)

            for section in job.get("lists", []):
                section_text = section.get("text", "")
                section_content = section.get("content", "")
                if section_text:
                    parts.append(f"\n{section_text}")
                if section_content:
                    parts.append(_strip_html(section_content))

            content = "\n\n".join(parts)

            categories = job.get("categories", {})
            location = categories.get("location", "")
            department = categories.get("department", "")

            postings.append(RawPosting(
                source_ats="lever",
                source_board_id=str(job.get("id", "")),
                company_name=board_id,
                title=title,
                content=content,
                location=location,
                department=department,
                posted_at=str(job.get("createdAt", "")),
                url=job.get("hostedUrl", ""),
                raw_json=job,
            ))

        return postings
