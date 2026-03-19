"""Greenhouse Job Board API adapter.

API docs: https://developers.greenhouse.io/job-board.html

Public job board endpoints (no auth required):
  GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
  GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}
"""
from __future__ import annotations

import re

import requests

from ingest.jd.base import ATSAdapter, RawPosting

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
_TIMEOUT = 15


def _strip_html(html: str) -> str:
    """Minimal HTML tag removal for plain-text extraction."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class GreenhouseAdapter(ATSAdapter):
    source_ats = "greenhouse"

    def fetch_postings(
        self,
        board_id: str,
        role_filter: str = "",
        max_results: int = 50,
    ) -> list[RawPosting]:
        url = f"{_BASE_URL}/{board_id}/jobs"
        params: dict[str, object] = {"content": "true"}
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        jobs = data.get("jobs", [])
        postings: list[RawPosting] = []

        for job in jobs[:max_results]:
            title = job.get("title", "")
            if role_filter and role_filter.lower() not in title.lower():
                continue

            content_html = job.get("content", "")
            content = _strip_html(content_html)
            location = ""
            if job.get("location"):
                location = job["location"].get("name", "")

            departments = job.get("departments", [])
            department = departments[0].get("name", "") if departments else ""

            postings.append(RawPosting(
                source_ats="greenhouse",
                source_board_id=str(job.get("id", "")),
                company_name=board_id,
                title=title,
                content=content,
                location=location,
                department=department,
                posted_at=job.get("updated_at", ""),
                url=job.get("absolute_url", ""),
                raw_json=job,
            ))

        return postings

    def list_boards(self, **kwargs: object) -> list[dict]:
        raise NotImplementedError(
            "Greenhouse does not support board discovery; "
            "provide a known board_token (company slug)"
        )
