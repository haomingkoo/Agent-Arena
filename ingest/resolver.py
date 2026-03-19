"""
Lead → artifact resolution pipeline.

Takes CandidateLead records from lead-gen sources and attempts to
resolve them into real agent artifacts that can enter the review
and normalization pipeline.

Resolution flow:
1. Extract outbound links from the lead
2. Classify each link (repo, registry, docs, demo, dead)
3. Fetch the best candidate artifact from the classified link
4. Route resolved artifacts into the discovery/normalization pipeline
5. Mark the lead as resolved or no-artifact
"""
from __future__ import annotations

import re
import subprocess
import time

import requests

from store.db import (
    list_candidate_leads,
    resolve_candidate_lead,
)


# ── Link Classification ────────────────────────────────────────────


def classify_link(url: str) -> str:
    """Classify a URL into a link type.

    Returns one of: repo, registry, docs, demo, dead, irrelevant
    """
    lower = url.lower()

    # GitHub/GitLab repos
    if re.match(r"https?://(www\.)?github\.com/[\w-]+/[\w.-]+/?$", url):
        return "repo"
    if re.match(r"https?://(www\.)?gitlab\.com/[\w-]+/[\w.-]+/?$", url):
        return "repo"

    # GitHub blob/tree links (specific files in repos)
    if "github.com" in lower and ("/blob/" in lower or "/tree/" in lower):
        return "repo"

    # Registry pages
    registry_hosts = ["smithery.ai", "npmjs.com", "pypi.org", "crates.io"]
    if any(host in lower for host in registry_hosts):
        return "registry"

    # Skills / agent marketplaces
    marketplace_hosts = ["agentskill.sh", "skills.sh", "skillsmp.com"]
    if any(host in lower for host in marketplace_hosts):
        return "registry"

    # Documentation pages
    docs_patterns = ["/docs/", "/documentation/", "/wiki/", "readthedocs"]
    if any(p in lower for p in docs_patterns):
        return "docs"

    # Demo / app pages
    demo_patterns = [".vercel.app", ".netlify.app", ".herokuapp.com", "demo"]
    if any(p in lower for p in demo_patterns):
        return "demo"

    # Common irrelevant links
    irrelevant = ["twitter.com", "x.com", "linkedin.com", "facebook.com",
                   "youtube.com", "youtu.be", "reddit.com", "medium.com"]
    if any(host in lower for host in irrelevant):
        return "irrelevant"

    return "docs"  # default to docs for unknown


def _extract_repo_from_url(url: str) -> str | None:
    """Extract owner/repo from a GitHub or GitLab URL."""
    match = re.match(
        r"https?://(?:www\.)?(github|gitlab)\.com/([\w.-]+/[\w.-]+)",
        url,
    )
    if match:
        repo = match.group(2).rstrip("/")
        # Strip /blob/... or /tree/... suffixes
        repo = re.sub(r"/(blob|tree)/.*$", "", repo)
        return repo
    return None


# ── Artifact Fetching ───────────────────────────────────────────────


def _check_repo_for_agents(repo: str) -> list[dict]:
    """Check a GitHub repo for agent config files.

    Returns a list of dicts with file path and type info.
    """
    agent_files: list[dict] = []

    # Use gh CLI for GitHub repos
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/trees/main",
         "--jq", '.tree[] | select(.type=="blob") | .path'],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        # Try master branch
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/git/trees/master",
             "--jq", '.tree[] | select(.type=="blob") | .path'],
            capture_output=True, text=True, timeout=15,
        )

    if result.returncode != 0:
        return agent_files

    files = result.stdout.strip().split("\n")
    target_names = {"SKILL.md", "AGENTS.md", "CLAUDE.md"}

    for f in files:
        name = f.split("/")[-1] if "/" in f else f
        if name in target_names:
            agent_files.append({"path": f, "type": "agent-config"})
        elif f.endswith(".md") and any(d in f.lower() for d in ["agent", "skill", "prompt"]):
            agent_files.append({"path": f, "type": "potential-agent"})

    return agent_files


# ── Resolution Pipeline ────────────────────────────────────────────


def resolve_leads(
    max_leads: int = 20,
    source_type: str = "",
) -> dict:
    """Process unresolved leads and attempt to resolve them.

    Returns a summary of resolution results.
    """
    leads = list_candidate_leads(
        source_type=source_type,
        resolution_state="unresolved",
        limit=max_leads,
    )

    resolved = 0
    no_artifact = 0
    dead = 0
    errors: list[str] = []

    for lead in leads:
        lead_id = lead["id"]
        title = lead.get("title", "")

        # Get artifact links (pre-extracted during lead ingestion)
        import json
        artifact_links = json.loads(
            lead.get("extracted_artifact_links_json", "[]")
        )

        if not artifact_links:
            # Try outbound links
            outbound = json.loads(lead.get("outbound_links_json", "[]"))
            artifact_links = [
                l for l in outbound
                if classify_link(l) in ("repo", "registry")
            ]

        if not artifact_links:
            resolve_candidate_lead(
                lead_id,
                resolution_state="no-artifact",
                resolver_note="No repo or registry links found",
            )
            no_artifact += 1
            continue

        # Try the best artifact link
        best_link = artifact_links[0]
        link_type = classify_link(best_link)

        if link_type == "repo":
            repo = _extract_repo_from_url(best_link)
            if not repo:
                resolve_candidate_lead(
                    lead_id,
                    resolution_state="no-artifact",
                    resolver_note=f"Could not parse repo from {best_link}",
                )
                no_artifact += 1
                continue

            # Check if repo has agent files
            try:
                agent_files = _check_repo_for_agents(repo)
                if agent_files:
                    resolve_candidate_lead(
                        lead_id,
                        resolution_state="resolved",
                        resolved_artifact_url=best_link,
                        resolver_note=f"Found {len(agent_files)} agent file(s): "
                                      f"{', '.join(f['path'] for f in agent_files[:3])}",
                    )
                    resolved += 1
                else:
                    resolve_candidate_lead(
                        lead_id,
                        resolution_state="no-artifact",
                        resolver_note=f"Repo {repo} has no agent config files",
                    )
                    no_artifact += 1
            except Exception as e:
                errors.append(f"Lead {lead_id}: {e}")
                continue

        elif link_type == "registry":
            # Registry links are directly resolvable
            resolve_candidate_lead(
                lead_id,
                resolution_state="resolved",
                resolved_artifact_url=best_link,
                resolver_note=f"Registry link: {best_link}",
            )
            resolved += 1

        else:
            resolve_candidate_lead(
                lead_id,
                resolution_state="no-artifact",
                resolver_note=f"Best link type is {link_type}, not directly ingestable",
            )
            no_artifact += 1

    return {
        "processed": len(leads),
        "resolved": resolved,
        "no_artifact": no_artifact,
        "dead": dead,
        "errors": errors,
    }
