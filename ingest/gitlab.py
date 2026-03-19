"""
GitLab discovery adapter — discovers agent configs from GitLab repos.

Uses the GitLab REST API v4 (public, no auth required for public repos).
Searches for AGENTS.md / CLAUDE.md / SKILL.md and agent-oriented markdown
bundles. The goal is still agent discovery, not generic prompt hunting.

Produces DiscoveredSkill records that feed the standard normalization pipeline.
"""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass

import requests

GITLAB_BASE = "https://gitlab.com/api/v4"
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
RATE_LIMIT_DELAY = 1.0


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"User-Agent": "agentarena/1.0"}
    if GITLAB_TOKEN:
        h["PRIVATE-TOKEN"] = GITLAB_TOKEN
    return h


def _gitlab_get(url: str, params: dict | None = None) -> dict | list | None:
    """Rate-limited GitLab API request."""
    time.sleep(RATE_LIMIT_DELAY)
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.RequestException:
        return None


@dataclass
class GitLabDiscovery:
    name: str
    raw_content: str
    source_url: str
    project_path: str
    file_path: str
    stars: int = 0


def search_projects(
    query: str = "agent",
    min_stars: int = 5,
    max_results: int = 50,
) -> list[dict]:
    """Search GitLab for projects matching a query."""
    results: list[dict] = []
    page = 1
    per_page = 20

    while len(results) < max_results:
        data = _gitlab_get(
            f"{GITLAB_BASE}/projects",
            params={
                "search": query,
                "order_by": "stars_count",
                "sort": "desc",
                "min_access_level": 0,
                "per_page": per_page,
                "page": page,
                "visibility": "public",
            },
        )
        if not data or not isinstance(data, list):
            break

        for project in data:
            stars = project.get("star_count", 0)
            if stars >= min_stars:
                results.append({
                    "id": project["id"],
                    "path": project["path_with_namespace"],
                    "name": project["name"],
                    "description": project.get("description", ""),
                    "stars": stars,
                    "web_url": project.get("web_url", ""),
                })

        if len(data) < per_page:
            break
        page += 1

    return results[:max_results]


def search_files_in_project(
    project_id: int,
    filenames: list[str] | None = None,
) -> list[dict]:
    """Search for agent config files in a GitLab project."""
    if filenames is None:
        filenames = ["SKILL.md", "AGENTS.md", "CLAUDE.md"]

    found: list[dict] = []

    # Use repository tree API to list files
    data = _gitlab_get(
        f"{GITLAB_BASE}/projects/{project_id}/repository/tree",
        params={"recursive": "true", "per_page": 100},
    )
    if not data or not isinstance(data, list):
        return found

    for item in data:
        if item.get("type") != "blob":
            continue
        name = item.get("name", "")
        path = item.get("path", "")
        if name in filenames or path.endswith(".md"):
            # Check if the file looks like an agent config
            if _is_agent_config_path(path, filenames):
                found.append({
                    "path": path,
                    "name": name,
                })

    return found


def _is_agent_config_path(path: str, target_names: list[str]) -> bool:
    """Check if a file path likely contains an agent config."""
    name = path.split("/")[-1]
    if name in target_names:
        return True

    lower = path.lower()
    if not name.endswith(".md"):
        return False

    # Strong agent-oriented locations are allowed directly.
    agent_dirs = ["agents/", "agent/", "assistants/", "reviewers/", "roles/"]
    if any(d in lower for d in agent_dirs):
        return True

    # Skill/prompt/rules locations are only acceptable when the file path also
    # looks role-oriented. This keeps us focused on agent configs instead of
    # indiscriminately sweeping up prompt packs and generic rules.
    weaker_dirs = ["skills/", "skill/", "prompts/", "prompt/", "rules/"]
    role_markers = [
        "agent",
        "review",
        "reviewer",
        "engineer",
        "developer",
        "architect",
        "verifier",
        "security",
        "qa",
    ]
    if any(d in lower for d in weaker_dirs):
        return any(marker in lower for marker in role_markers)

    return False


def fetch_file_content(project_id: int, file_path: str) -> str | None:
    """Fetch raw file content from a GitLab project."""
    import urllib.parse
    encoded_path = urllib.parse.quote(file_path, safe="")
    data = _gitlab_get(
        f"{GITLAB_BASE}/projects/{project_id}/repository/files/{encoded_path}",
        params={"ref": "main"},
    )
    if not data:
        # Try master branch
        data = _gitlab_get(
            f"{GITLAB_BASE}/projects/{project_id}/repository/files/{encoded_path}",
            params={"ref": "master"},
        )
    if not data:
        return None

    content_b64 = data.get("content", "")
    encoding = data.get("encoding", "base64")
    if encoding == "base64" and content_b64:
        return base64.b64decode(content_b64).decode("utf-8", errors="replace")
    return content_b64


def discover_agents(
    queries: list[str] | None = None,
    min_stars: int = 5,
    max_projects: int = 30,
    target_filenames: list[str] | None = None,
) -> list[GitLabDiscovery]:
    """Full discovery pipeline: search projects → find agent files → fetch content."""
    if queries is None:
        queries = [
            "coding agent",
            "code review agent",
            "software engineer agent",
            "verification agent",
            "AGENTS.md",
            "CLAUDE.md",
        ]
    if target_filenames is None:
        target_filenames = ["SKILL.md", "AGENTS.md", "CLAUDE.md"]

    seen_projects: set[int] = set()
    discoveries: list[GitLabDiscovery] = []

    for query in queries:
        projects = search_projects(query, min_stars=min_stars, max_results=max_projects)

        for project in projects:
            pid = project["id"]
            if pid in seen_projects:
                continue
            seen_projects.add(pid)

            files = search_files_in_project(pid, filenames=target_filenames)
            for f in files:
                content = fetch_file_content(pid, f["path"])
                if not content or len(content) < 50:
                    continue

                discoveries.append(GitLabDiscovery(
                    name=f["name"],
                    raw_content=content,
                    source_url=f"{project['web_url']}/-/blob/main/{f['path']}",
                    project_path=project["path"],
                    file_path=f["path"],
                    stars=project["stars"],
                ))

    return discoveries
