"""
Discovery orchestrator for both the legacy skill path and the new agent-native path.

Legacy path:
  1. Run source adapters to discover raw skills
  2. Parse raw records into ParsedSkill objects
  3. Deduplicate across sources
  4. Auto-categorize each unique skill

Agent-native path:
  1. Run source adapters to discover raw skills
  2. Parse and deduplicate
  3. Assign initial field/role
  4. Register hostile artifacts into the agent-native store
  5. Normalize supported versions into benchmark-ready contracts
"""
from __future__ import annotations

from dataclasses import dataclass

from agents.contracts import EligibilityState, PackagingType
from agents.normalizer import normalize_agent_version
from evaluate.rubric import ParsedSkill, parse_skill_md
from ingest.agent_roles import FieldRoleAssignment, assign_field_role
from ingest.categorize import CategoryAssignment, categorize_skill
from ingest.discovery import RawAgentArtifact, register_discovered_artifact
from ingest.dedup import DeduplicatedSkill, content_hash, deduplicate
from ingest.sources import RawSkillRecord, SourceAdapter, default_source_adapters


@dataclass
class DiscoveredAgentCandidate:
    name: str
    source_url: str
    source_repo: str
    field: str
    role: str
    source_category: str
    category_confidence: float
    field_role_confidence: float
    field_role_method: str
    profile_id: str
    artifact_id: str
    version_id: str
    eligibility: EligibilityState
    normalization_reason: str = ""
    content_hash: str = ""
    duplicate_count: int = 0


def _records_to_parsed(records: list[RawSkillRecord]) -> list[ParsedSkill]:
    """Convert RawSkillRecords to ParsedSkill objects."""
    parsed: list[ParsedSkill] = []
    for rec in records:
        skill = parse_skill_md(
            content=rec.content,
            source_repo=rec.repo_or_package,
            source_url=rec.source_url,
        )
        skill.github_stars = rec.stars
        skill.install_count = rec.install_count
        parsed.append(skill)
    return parsed


def _discover_records(
    sources: list[SourceAdapter] | None = None,
    max_per_source: int = 200,
) -> list[RawSkillRecord]:
    """Run configured adapters and collect raw records."""
    if sources is None:
        sources = default_source_adapters()

    all_records: list[RawSkillRecord] = []
    for adapter in sources:
        try:
            records = adapter.discover(max_results=max_per_source)
            all_records.extend(records)
            print(
                f"[orchestrator] {adapter.source_type}: "
                f"{len(records)} skills discovered"
            )
        except NotImplementedError:
            print(
                f"[orchestrator] {adapter.source_type}: "
                "adapter not yet implemented, skipping"
            )
        except Exception as e:
            print(
                f"[orchestrator] {adapter.source_type}: "
                f"error during discovery: {e}"
            )
    return all_records


def _discover_deduped_skills(
    sources: list[SourceAdapter] | None = None,
    max_per_source: int = 200,
) -> list[DeduplicatedSkill]:
    """Discover, parse, and deduplicate candidate skills."""
    all_records = _discover_records(
        sources=sources,
        max_per_source=max_per_source,
    )
    if not all_records:
        print("[orchestrator] No skills discovered from any source")
        return []

    parsed_skills = _records_to_parsed(all_records)
    print(f"[orchestrator] Parsed {len(parsed_skills)} skills")

    deduped = deduplicate(parsed_skills)
    dupe_count = sum(len(d.duplicates) for d in deduped)
    print(
        f"[orchestrator] Deduplicated: {len(deduped)} unique "
        f"({dupe_count} duplicates removed)"
    )
    return deduped


def _parsed_to_agent_artifact(
    skill: ParsedSkill,
    assignment: FieldRoleAssignment,
) -> RawAgentArtifact:
    """Convert a parsed skill into a stored raw agent artifact."""
    owner = ""
    if "/" in skill.source_repo:
        owner = skill.source_repo.split("/", 1)[0]
    return RawAgentArtifact(
        name=skill.name,
        summary=skill.description,
        source_type="github",
        source_id=skill.source_url or skill.source_repo,
        source_url=skill.source_url,
        raw_content=skill.raw_content,
        packaging_type=PackagingType.markdown_prompt_bundle,
        repo_or_package=skill.source_repo,
        owner=owner,
        field=assignment.field,
        role=assignment.role,
        metadata={
            "triggers": skill.triggers,
            "allowed_tools": skill.allowed_tools,
        },
    )


def run_discovery(
    sources: list[SourceAdapter] | None = None,
    max_per_source: int = 200,
) -> list[tuple[ParsedSkill, CategoryAssignment, str]]:
    """Run the full discovery pipeline.

    1. Run all source adapters
    2. Parse into ParsedSkill
    3. Deduplicate
    4. Auto-categorize
    5. Return list of (ParsedSkill, CategoryAssignment, content_hash)

    Args:
        sources: List of source adapters to run. Defaults to [GitHubAdapter].
        max_per_source: Maximum skills to discover per source.

    Returns:
        List of (skill, category, hash) tuples for each unique skill.
    """
    deduped = _discover_deduped_skills(
        sources=sources,
        max_per_source=max_per_source,
    )
    if not deduped:
        return []

    # Step 4: Auto-categorize
    results: list[tuple[ParsedSkill, CategoryAssignment, str]] = []
    for deduped_skill in deduped:
        skill = deduped_skill.primary
        category = categorize_skill(skill)
        skill_hash = content_hash(skill.raw_content)
        results.append((skill, category, skill_hash))

    # Summary by category
    cat_counts: dict[str, int] = {}
    for _, cat, _ in results:
        cat_counts[cat.primary_category] = (
            cat_counts.get(cat.primary_category, 0) + 1
        )
    print(f"[orchestrator] Categories: {cat_counts}")

    return results


def run_agent_discovery(
    db_module,
    sources: list[SourceAdapter] | None = None,
    max_per_source: int = 200,
    normalize: bool = True,
    eligible_only: bool = False,
) -> list[DiscoveredAgentCandidate]:
    """Run the agent-native discovery pipeline into the store."""

    deduped = _discover_deduped_skills(
        sources=sources,
        max_per_source=max_per_source,
    )
    if not deduped:
        return []

    candidates: list[DiscoveredAgentCandidate] = []
    role_counts: dict[str, int] = {}
    for deduped_skill in deduped:
        skill = deduped_skill.primary
        category = categorize_skill(skill)
        assignment = assign_field_role(skill, category)
        registered = register_discovered_artifact(
            db_module,
            _parsed_to_agent_artifact(skill, assignment),
        )
        normalization_reason = ""
        eligibility = registered.eligibility
        if normalize:
            normalized = normalize_agent_version(db_module, registered.version_id)
            eligibility = normalized.eligibility
            normalization_reason = normalized.reason
        candidate = DiscoveredAgentCandidate(
            name=skill.name,
            source_url=skill.source_url,
            source_repo=skill.source_repo,
            field=assignment.field,
            role=assignment.role,
            source_category=category.primary_category,
            category_confidence=category.confidence,
            field_role_confidence=assignment.confidence,
            field_role_method=assignment.method,
            profile_id=registered.profile_id,
            artifact_id=registered.artifact_id,
            version_id=registered.version_id,
            eligibility=eligibility,
            normalization_reason=normalization_reason,
            content_hash=deduped_skill.content_hash,
            duplicate_count=len(deduped_skill.duplicates),
        )
        if not eligible_only or eligibility == EligibilityState.eligible:
            candidates.append(candidate)
        role_key = f"{assignment.field}/{assignment.role}"
        role_counts[role_key] = role_counts.get(role_key, 0) + 1

    print(f"[orchestrator] Field/role assignments: {role_counts}")
    if normalize:
        ready = sum(
            1 for candidate in candidates
            if candidate.eligibility == EligibilityState.eligible
        )
        print(f"[orchestrator] Benchmark-ready candidates: {ready}")
    return candidates
