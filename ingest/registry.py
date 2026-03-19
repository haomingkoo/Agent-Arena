"""
Registry adapters — discover role-like agents from registries and collections.

Smithery (smithery.ai) is a registry for MCP servers and agent tools.
We also support awesome-list ingestion as a fallback discovery source, but we
filter aggressively so generic prompt, skills, and rules collections do not get
mistaken for benchmark-ready agent candidates.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field

import requests


ROLE_MARKERS = [
    "agent",
    "assistant",
    "review",
    "reviewer",
    "engineer",
    "developer",
    "architect",
    "verifier",
    "verification",
    "debug",
    "debugger",
    "security",
    "qa",
    "tester",
]

NOISY_COLLECTION_MARKERS = [
    "awesome",
    "skills",
    "skill pack",
    "prompts",
    "prompt pack",
    "rules",
    "cursor rules",
    "gpts",
    "templates",
]


def _looks_like_role_agent(name: str, description: str, tags: list[str] | None = None) -> bool:
    """Return True only for agent-like, role-ish candidates.

    The benchmark funnel should discover full agents for a role, not generic
    prompt packs, rules collections, or "awesome" lists of tips.
    """
    text = " ".join(part for part in [name, description, " ".join(tags or [])] if part).lower()
    if not text:
        return False

    if any(marker in text for marker in NOISY_COLLECTION_MARKERS):
        # Allow a noisy label only if it still clearly reads like a role-scoped
        # agent. This covers names like "security reviewer agent" while keeping
        # out "awesome skills" and generic prompt/rules collections.
        return ("agent" in text or "assistant" in text) and any(
            marker in text for marker in ROLE_MARKERS if marker not in {"agent", "assistant"}
        )

    return any(marker in text for marker in ROLE_MARKERS)


@dataclass
class RegistryDiscovery:
    name: str
    description: str
    raw_content: str
    source_url: str
    source_registry: str
    stars: int = 0
    owner: str = ""
    tags: list[str] = field(default_factory=list)


# ── Smithery Adapter ────────────────────────────────────────────────


SMITHERY_BASE = "https://registry.smithery.ai/api"
SMITHERY_TIMEOUT = 15


class SmitheryAdapter:
    """Discover role-like agent/tool configs from Smithery registry.

    Smithery hosts MCP servers and agent tools. We only keep entries that look
    like role-oriented agents rather than generic toolkits or prompt bundles.
    """

    source_registry = "smithery"

    def search(
        self,
        query: str = "",
        max_results: int = 50,
    ) -> list[RegistryDiscovery]:
        """Search Smithery for agent configs."""
        discoveries: list[RegistryDiscovery] = []

        try:
            params: dict[str, object] = {"pageSize": min(max_results, 50)}
            if query:
                params["q"] = query

            resp = requests.get(
                f"{SMITHERY_BASE}/servers",
                params=params,
                timeout=SMITHERY_TIMEOUT,
            )
            if resp.status_code != 200:
                return discoveries

            data = resp.json()
            servers = data.get("servers", data) if isinstance(data, dict) else data
            if not isinstance(servers, list):
                return discoveries

            for server in servers[:max_results]:
                name = server.get("displayName", "") or server.get("name", "")
                description = server.get("description", "")
                qualified_name = server.get("qualifiedName", "")
                homepage = server.get("homepage", "")
                tags = server.get("tags", [])

                if not _looks_like_role_agent(name, description, tags):
                    continue

                # Build content from available metadata
                content_parts = [f"# {name}", ""]
                if description:
                    content_parts.append(description)
                    content_parts.append("")

                # Try to get README or config if available
                readme = server.get("readme", "")
                if readme:
                    content_parts.append(readme)

                content = "\n".join(content_parts)
                if len(content) < 50:
                    continue

                source_url = homepage or f"https://smithery.ai/server/{qualified_name}"

                discoveries.append(RegistryDiscovery(
                    name=name,
                    description=description,
                    raw_content=content,
                    source_url=source_url,
                    source_registry="smithery",
                    owner=server.get("owner", ""),
                    tags=tags,
                ))

        except requests.RequestException:
            pass

        return discoveries


# ── Awesome-List Adapter ────────────────────────────────────────────


class AwesomeListAdapter:
    """Extract agent references from GitHub awesome-list repos.

    Parses markdown lists to find linked repos/artifacts, but only keeps links
    that plausibly point to role-like agents. Generic prompt/rules/skills lists
    should stay in the lead-gen layer, not enter the benchmark path directly.
    """

    source_registry = "awesome-list"

    def ingest_from_url(
        self,
        repo: str,
        file_path: str = "README.md",
        max_results: int = 100,
    ) -> list[RegistryDiscovery]:
        """Parse an awesome-list README and extract agent references."""
        import subprocess

        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/contents/{file_path}", "--jq", ".content"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return []

        import base64
        content = base64.b64decode(result.stdout.strip()).decode("utf-8")
        return self._parse_awesome_list(content, repo, max_results)

    def _parse_awesome_list(
        self,
        content: str,
        source_repo: str,
        max_results: int,
    ) -> list[RegistryDiscovery]:
        """Extract linked repos from a markdown awesome-list."""
        discoveries: list[RegistryDiscovery] = []

        # Match markdown links: [Name](url) - description
        link_pattern = re.compile(
            r'\[([^\]]+)\]\((https?://[^\)]+)\)\s*[-–—]?\s*(.*)',
        )

        for match in link_pattern.finditer(content):
            if len(discoveries) >= max_results:
                break

            name = match.group(1).strip()
            url = match.group(2).strip()
            description = match.group(3).strip()

            # Only keep GitHub/GitLab links (potential agent repos)
            if not any(host in url for host in ["github.com", "gitlab.com"]):
                continue

            if not _looks_like_role_agent(name, description):
                continue

            discoveries.append(RegistryDiscovery(
                name=name,
                description=description,
                raw_content="",  # Will be fetched during resolution
                source_url=url,
                source_registry=f"awesome-list:{source_repo}",
                owner=source_repo,
            ))

        return discoveries
