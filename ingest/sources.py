"""
Multi-source skill discovery adapters.

Each adapter implements the SourceAdapter protocol and returns
normalized RawSkillRecord objects that can be parsed into ParsedSkills.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class RawSkillRecord:
    """Normalized record from any source before parsing."""
    content: str
    source_type: str          # "github" | "smithery" | "skillsmp" | "local-curated"
    source_id: str            # unique within source
    source_url: str
    repo_or_package: str
    author: str = ""
    stars: int = 0
    install_count: int = 0
    last_updated: str = ""
    metadata: dict = field(default_factory=dict)


class SourceAdapter(Protocol):
    """Protocol for skill discovery source adapters."""
    source_type: str

    def discover(self, max_results: int = 100) -> list[RawSkillRecord]: ...


class GitHubAdapter:
    """Wraps existing ingest/github.py logic behind the adapter interface."""

    source_type: str = "github"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN")

    def discover(self, max_results: int = 100) -> list[RawSkillRecord]:
        """Use existing scrape functions, converting to RawSkillRecord format."""
        from ingest.github import scrape_all

        discovered = scrape_all(
            include_search=True,
            max_search_results=max_results,
        )
        records: list[RawSkillRecord] = []
        for d in discovered:
            if d.parsed:
                author = ""
                if "/" in d.parsed.source_repo:
                    author = d.parsed.source_repo.split("/")[0]
                records.append(RawSkillRecord(
                    content=d.parsed.raw_content,
                    source_type="github",
                    source_id=d.parsed.source_url,
                    source_url=d.parsed.source_url,
                    repo_or_package=d.parsed.source_repo,
                    author=author,
                    stars=d.parsed.github_stars,
                    install_count=d.parsed.install_count,
                ))
        return records


class LocalMarkdownDirectoryAdapter:
    """
    Discover markdown-packaged agents from local curated directories.

    These are useful for widening the comparable candidate pool without waiting
    on remote registry adapters.
    """

    def __init__(
        self,
        root_dir: str | Path,
        *,
        source_type: str = "local-curated",
    ) -> None:
        self.root_dir = Path(root_dir)
        self.source_type = source_type

    def discover(self, max_results: int = 100) -> list[RawSkillRecord]:
        if not self.root_dir.exists():
            return []

        records: list[RawSkillRecord] = []
        paths = sorted(self.root_dir.rglob("*.md"))
        for path in paths[:max_results]:
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue

            rel_path = path.as_posix()
            records.append(
                RawSkillRecord(
                    content=content,
                    source_type=self.source_type,
                    source_id=rel_path,
                    source_url=f"local://{rel_path}",
                    repo_or_package=rel_path,
                    author=path.parent.name,
                    metadata={
                        "path": rel_path,
                        "directory": self.root_dir.as_posix(),
                    },
                )
            )
        return records


class SmitheryAdapter:
    """Stub adapter for Smithery registry (not yet implemented)."""

    source_type: str = "smithery"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("SMITHERY_API_KEY")

    def discover(self, max_results: int = 100) -> list[RawSkillRecord]:
        raise NotImplementedError("Smithery adapter not yet implemented")


class SkillsMPAdapter:
    """Stub adapter for SkillsMP marketplace (not yet implemented)."""

    source_type: str = "skillsmp"

    def discover(self, max_results: int = 100) -> list[RawSkillRecord]:
        raise NotImplementedError("SkillsMP adapter not yet implemented")


def default_source_adapters() -> list[SourceAdapter]:
    """
    Return the default discovery stack.

    We do not rely on GitHub alone; the curated local agent directories should
    also flow through the same discovery + normalization pipeline so they can
    become real benchmark candidates.
    """

    adapters: list[SourceAdapter] = [GitHubAdapter()]

    curated_roots = (
        ("data/external-agents", "local-curated-external"),
        ("data/code-review-agents", "local-curated-code-review"),
    )
    for root, source_type in curated_roots:
        if Path(root).exists():
            adapters.append(
                LocalMarkdownDirectoryAdapter(root, source_type=source_type)
            )

    return adapters
