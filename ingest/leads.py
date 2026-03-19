"""
Lead-generation adapters for non-benchmark sources.

These adapters discover mentions of AI agents on YouTube, Reddit,
Hacker News, and blogs/awesome-lists. They produce CandidateLead
records — NOT benchmark-ready agents.

Leads must be resolved into real artifact URLs before entering
the review pipeline.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── YouTube Adapter ─────────────────────────────────────────────────


def search_youtube(
    query: str,
    api_key: str = "",
    max_results: int = 20,
) -> list[dict]:
    """Search YouTube for videos mentioning AI agents.

    Returns CandidateLead-shaped dicts.
    Requires YOUTUBE_API_KEY for the Data API v3.
    Falls back to empty if no key.
    """
    if not api_key:
        import os
        api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return []

    leads: list[dict] = []
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(max_results, 50),
                "order": "relevance",
                "key": api_key,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return leads

        data = resp.json()
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            url = f"https://www.youtube.com/watch?v={video_id}"

            # Extract links from description
            links = re.findall(r'https?://[^\s<>"]+', description)
            artifact_links = [
                l for l in links
                if any(h in l for h in ["github.com", "gitlab.com", "smithery.ai"])
            ]

            leads.append({
                "source_type": "youtube",
                "source_url": url,
                "title": title,
                "description": description[:500],
                "outbound_links": links[:20],
                "extracted_artifact_links": artifact_links,
                "signal_strength": len(artifact_links) * 0.5,
                "content_hash": _content_hash(url),
                "discovered_at": _utc_now(),
            })

    except requests.RequestException:
        pass

    return leads


# ── Reddit Adapter ──────────────────────────────────────────────────


REDDIT_HEADERS = {"User-Agent": "agentarena/1.0 (benchmark discovery)"}


def search_reddit(
    query: str,
    subreddits: list[str] | None = None,
    max_results: int = 25,
) -> list[dict]:
    """Search Reddit for posts mentioning AI agents.

    Uses Reddit's public JSON API (no auth needed for search).
    """
    if subreddits is None:
        subreddits = [
            "ClaudeAI", "ChatGPT", "LocalLLaMA", "MachineLearning",
            "artificial", "programming", "coding",
        ]

    leads: list[dict] = []
    seen_urls: set[str] = set()

    for sub in subreddits:
        if len(leads) >= max_results:
            break

        try:
            time.sleep(1.0)  # Reddit rate limit
            resp = requests.get(
                f"https://www.reddit.com/r/{sub}/search.json",
                params={
                    "q": query,
                    "sort": "relevance",
                    "t": "month",
                    "limit": 10,
                    "restrict_sr": "on",
                },
                headers=REDDIT_HEADERS,
                timeout=15,
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            posts = data.get("data", {}).get("children", [])

            for post in posts:
                pd = post.get("data", {})
                url = pd.get("url", "")
                permalink = f"https://www.reddit.com{pd.get('permalink', '')}"

                if permalink in seen_urls:
                    continue
                seen_urls.add(permalink)

                title = pd.get("title", "")
                selftext = pd.get("selftext", "")
                score = pd.get("score", 0)

                # Extract links from selftext and url
                all_text = f"{url} {selftext}"
                links = re.findall(r'https?://[^\s<>")\]]+', all_text)
                artifact_links = [
                    l for l in links
                    if any(h in l for h in ["github.com", "gitlab.com", "smithery.ai"])
                ]

                leads.append({
                    "source_type": "reddit",
                    "source_url": permalink,
                    "title": title,
                    "description": selftext[:500],
                    "outbound_links": links[:20],
                    "extracted_artifact_links": artifact_links,
                    "signal_strength": min(score / 100, 5.0) + len(artifact_links) * 0.5,
                    "content_hash": _content_hash(permalink),
                    "discovered_at": _utc_now(),
                })

        except requests.RequestException:
            continue

    return leads[:max_results]


# ── Hacker News Adapter ────────────────────────────────────────────


def search_hackernews(
    query: str,
    max_results: int = 25,
) -> list[dict]:
    """Search Hacker News via Algolia API for agent-related posts.

    Uses the public HN Algolia API (no auth needed).
    """
    leads: list[dict] = []

    try:
        resp = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": query,
                "tags": "story",
                "hitsPerPage": min(max_results, 50),
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return leads

        data = resp.json()
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            url = hit.get("url", "")
            story_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            points = hit.get("points", 0) or 0
            num_comments = hit.get("num_comments", 0) or 0

            # Extract artifact links from the story URL
            artifact_links = []
            if url and any(h in url for h in ["github.com", "gitlab.com"]):
                artifact_links.append(url)

            leads.append({
                "source_type": "hackernews",
                "source_url": story_url,
                "title": title,
                "description": f"URL: {url}" if url else "",
                "outbound_links": [url] if url else [],
                "extracted_artifact_links": artifact_links,
                "signal_strength": min(points / 50, 5.0) + len(artifact_links),
                "content_hash": _content_hash(story_url),
                "discovered_at": _utc_now(),
            })

    except requests.RequestException:
        pass

    return leads[:max_results]


# ── Blog / Awesome-List Adapter ─────────────────────────────────────


def extract_leads_from_awesome_list(
    repo: str,
    file_path: str = "README.md",
) -> list[dict]:
    """Extract candidate leads from a GitHub awesome-list README.

    Parses markdown links and classifies them as potential agent sources.
    """
    import subprocess
    import base64

    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{file_path}", "--jq", ".content"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        return []

    content = base64.b64decode(result.stdout.strip()).decode("utf-8")
    leads: list[dict] = []

    # Match markdown links
    link_pattern = re.compile(
        r'\[([^\]]+)\]\((https?://[^\)]+)\)\s*[-–—]?\s*(.*)',
    )

    for match in link_pattern.finditer(content):
        name = match.group(1).strip()
        url = match.group(2).strip()
        description = match.group(3).strip()

        # Score based on link target
        artifact_links = []
        signal = 0.0

        if "github.com" in url or "gitlab.com" in url:
            artifact_links.append(url)
            signal += 1.0
        if "smithery" in url or "skills" in url.lower():
            artifact_links.append(url)
            signal += 0.5

        # Skip non-repo links with no artifact potential
        if not artifact_links:
            continue

        leads.append({
            "source_type": "awesome-list",
            "source_url": url,
            "title": name,
            "description": description[:300],
            "outbound_links": [url],
            "extracted_artifact_links": artifact_links,
            "signal_strength": signal,
            "content_hash": _content_hash(url),
            "discovered_at": _utc_now(),
        })

    return leads
