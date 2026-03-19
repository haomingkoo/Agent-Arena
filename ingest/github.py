"""
Skill Scraper — discovers and ingests SKILL.md files from GitHub.

Sources:
  - anthropics/skills (official)
  - Awesome lists (VoltAgent/awesome-agent-skills, travisvn/awesome-claude-skills)
  - GitHub code search for SKILL.md files
  - Individual repos with high star counts

Each discovered skill is parsed, scored, and stored for curation.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from evaluate.rubric import ParsedSkill, SkillScore, parse_skill_md
from evaluate.heuristic import score_skill_stage1

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "agentarena/1.0",
}
if GITHUB_TOKEN:
    GITHUB_HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

# Rate limit: GitHub allows 5000/hr with token, 60/hr without
RATE_LIMIT_DELAY = 0.8  # seconds between requests


@dataclass
class DiscoveredSkill:
    """A skill discovered from a source."""
    name: str
    description: str
    raw_content: str
    source_repo: str
    source_url: str
    file_path: str           # path within repo
    github_stars: int = 0
    repo_owner: str = ""
    parsed: ParsedSkill | None = None
    score: SkillScore | None = None


def _github_get(url: str, params: dict | None = None) -> dict | list | None:
    """Make a rate-limited GitHub API request."""
    time.sleep(RATE_LIMIT_DELAY)
    try:
        resp = httpx.get(
            url, headers=GITHUB_HEADERS, params=params, timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403:
            print(f"  [skill-scraper] Rate limited. Waiting 60s...")
            time.sleep(60)
            return _github_get(url, params)
        print(f"  [skill-scraper] GitHub API {resp.status_code}: {url}")
        return None
    except httpx.HTTPError as e:
        print(f"  [skill-scraper] HTTP error: {e}")
        return None


def _get_repo_stars(owner: str, repo: str) -> int:
    """Get star count for a repo."""
    data = _github_get(f"https://api.github.com/repos/{owner}/{repo}")
    if data and isinstance(data, dict):
        return data.get("stargazers_count", 0)
    return 0


def _get_raw_file(owner: str, repo: str, path: str, branch: str = "main") -> str | None:
    """Fetch raw file content from GitHub."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    time.sleep(RATE_LIMIT_DELAY)
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        # Try master branch
        if branch == "main":
            return _get_raw_file(owner, repo, path, branch="master")
        return None
    except httpx.HTTPError:
        return None


def scrape_repo_skills(owner: str, repo: str) -> list[DiscoveredSkill]:
    """Scrape all SKILL.md files from a single GitHub repo."""
    skills = []
    full_repo = f"{owner}/{repo}"
    print(f"  [skill-scraper] Scanning {full_repo}...")

    stars = _get_repo_stars(owner, repo)

    # Get repo tree
    tree_data = _github_get(
        f"https://api.github.com/repos/{full_repo}/git/trees/main",
        params={"recursive": "1"},
    )
    if not tree_data:
        # Try master
        tree_data = _github_get(
            f"https://api.github.com/repos/{full_repo}/git/trees/master",
            params={"recursive": "1"},
        )
    if not tree_data or not isinstance(tree_data, dict):
        print(f"  [skill-scraper] Could not read tree for {full_repo}")
        return skills

    # Find all SKILL.md files
    skill_paths = [
        item["path"]
        for item in tree_data.get("tree", [])
        if item["type"] == "blob"
        and item["path"].upper().endswith("SKILL.MD")
    ]

    print(f"  [skill-scraper] Found {len(skill_paths)} SKILL.md files in {full_repo}")

    for path in skill_paths:
        content = _get_raw_file(owner, repo, path)
        if not content or len(content) < 50:
            continue

        # Determine branch used
        source_url = f"https://github.com/{full_repo}/blob/main/{path}"

        parsed = parse_skill_md(content, source_repo=full_repo, source_url=source_url)
        parsed.github_stars = stars

        score = score_skill_stage1(parsed)

        skill = DiscoveredSkill(
            name=parsed.name or path.split("/")[-2] if "/" in path else path,
            description=parsed.description,
            raw_content=content,
            source_repo=full_repo,
            source_url=source_url,
            file_path=path,
            github_stars=stars,
            repo_owner=owner,
            parsed=parsed,
            score=score,
        )
        skills.append(skill)
        grade = score.grade
        print(f"    [{grade}] {skill.name} ({score.overall:.2f}) — {parsed.line_count} lines")

    return skills


def scrape_github_search(
    query: str = "filename:SKILL.md",
    max_results: int = 100,
) -> list[DiscoveredSkill]:
    """Search GitHub for SKILL.md files via code search API."""
    skills = []
    seen_repos: set[str] = set()
    page = 1
    per_page = 30

    print(f"  [skill-scraper] GitHub code search: {query}")

    while len(skills) < max_results:
        data = _github_get(
            "https://api.github.com/search/code",
            params={
                "q": query,
                "per_page": per_page,
                "page": page,
                "sort": "indexed",
            },
        )
        if not data or not isinstance(data, dict):
            break

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            repo_full = item.get("repository", {}).get("full_name", "")
            if not repo_full or repo_full in seen_repos:
                continue
            seen_repos.add(repo_full)

            owner, repo = repo_full.split("/", 1)
            repo_skills = scrape_repo_skills(owner, repo)
            skills.extend(repo_skills)

            if len(skills) >= max_results:
                break

        page += 1
        if page > 10:  # GitHub search caps at ~1000 results
            break

    return skills


# -- Known high-quality repos -------------------------------------------------

SEED_REPOS = [
    ("anthropics", "skills"),
    ("VoltAgent", "awesome-agent-skills"),
    ("travisvn", "awesome-claude-skills"),
    ("anthropics", "claude-plugins-official"),
]


def scrape_seed_repos() -> list[DiscoveredSkill]:
    """Scrape all known high-quality skill repos."""
    all_skills = []
    for owner, repo in SEED_REPOS:
        repo_skills = scrape_repo_skills(owner, repo)
        all_skills.extend(repo_skills)
    return all_skills


def scrape_all(
    include_search: bool = True,
    max_search_results: int = 100,
) -> list[DiscoveredSkill]:
    """Full scrape: seed repos + optional GitHub search."""
    print("\n[skill-scraper] Starting skill discovery...")

    all_skills = scrape_seed_repos()
    print(f"\n[skill-scraper] Seed repos: {len(all_skills)} skills found")

    if include_search:
        search_skills = scrape_github_search(max_results=max_search_results)
        # Dedup by source_url
        seen_urls = {s.source_url for s in all_skills}
        new_skills = [s for s in search_skills if s.source_url not in seen_urls]
        all_skills.extend(new_skills)
        print(f"[skill-scraper] GitHub search: {len(new_skills)} new skills")

    # Sort by score descending
    all_skills.sort(key=lambda s: s.score.overall if s.score else 0, reverse=True)

    # Summary
    grades = {}
    for s in all_skills:
        g = s.score.grade if s.score else "?"
        grades[g] = grades.get(g, 0) + 1

    print(f"\n[skill-scraper] Total: {len(all_skills)} skills discovered")
    print(f"  Grade distribution: {json.dumps(grades, sort_keys=True)}")
    s_and_a = grades.get("S", 0) + grades.get("A", 0)
    print(f"  Worth curating (S+A): {s_and_a}")

    return all_skills


def save_results(skills: list[DiscoveredSkill], output_path: str = "data/skill_audit.json") -> None:
    """Save scrape results to JSON."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    results = []
    for s in skills:
        entry = {
            "name": s.name,
            "description": s.description,
            "source_repo": s.source_repo,
            "source_url": s.source_url,
            "file_path": s.file_path,
            "github_stars": s.github_stars,
            "line_count": s.parsed.line_count if s.parsed else 0,
            "token_estimate": s.parsed.token_estimate if s.parsed else 0,
            "triggers": s.parsed.triggers if s.parsed else [],
            "allowed_tools": s.parsed.allowed_tools if s.parsed else [],
        }
        if s.score:
            entry["score"] = s.score.to_dict()
        results.append(entry)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[skill-scraper] Results saved to {output_path}")
