"""Ashby Job Postings API adapter.

API docs: https://developers.ashbyhq.com/docs/public-job-posting-api

Public posting endpoints (no auth required):
  POST https://api.ashbyhq.com/posting-api/job-board/{board_id}
"""
from __future__ import annotations

import re

import requests

from ingest.jd.base import ATSAdapter, RawPosting

_BASE_URL = "https://api.ashbyhq.com/posting-api"
_TIMEOUT = 15


def _strip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class AshbyAdapter(ATSAdapter):
    source_ats = "ashby"

    def fetch_postings(
        self,
        board_id: str,
        role_filter: str = "",
        max_results: int = 50,
    ) -> list[RawPosting]:
        url = f"{_BASE_URL}/job-board/{board_id}"
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        jobs = data.get("jobs", [])
        postings: list[RawPosting] = []

        for job in jobs[:max_results]:
            title = job.get("title", "")
            if role_filter and role_filter.lower() not in title.lower():
                continue

            desc_html = job.get("descriptionHtml", "") or job.get("description", "")
            content = _strip_html(desc_html) if "<" in desc_html else desc_html

            location = job.get("location", "")
            department = job.get("department", "")
            if isinstance(department, dict):
                department = department.get("name", "")

            postings.append(RawPosting(
                source_ats="ashby",
                source_board_id=str(job.get("id", "")),
                company_name=board_id,
                title=title,
                content=content,
                location=location,
                department=department,
                posted_at=job.get("publishedAt", ""),
                url=job.get("jobUrl", ""),
                raw_json=job,
            ))

        return postings
