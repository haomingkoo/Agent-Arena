"""
Agent-native discovery registration.

This layer treats remote artifacts as hostile data. Discovery stores raw and
sanitized artifacts, records provenance, and creates a pending or unsupported
agent version without turning scraped content into runnable instructions.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from hashlib import sha256
from typing import Protocol

from agents.contracts import EligibilityState, PackagingType, ProvenanceRef, Visibility
from security.ingest_guard import IngestScanResult, scan_untrusted_content
from store.models import AgentProfile, AgentVersion, ArtifactRecord


DEFAULT_FIELD = "unassigned"
DEFAULT_ROLE = "unassigned-agent"


@dataclass
class RawAgentArtifact:
    """Untrusted artifact discovered from an external source."""

    name: str
    source_type: str
    source_id: str
    source_url: str
    raw_content: str
    packaging_type: PackagingType
    repo_or_package: str = ""
    owner: str = ""
    summary: str = ""
    field: str = DEFAULT_FIELD
    role: str = DEFAULT_ROLE
    source_commit: str = ""
    version_label: str = "discovered"
    visibility: Visibility = Visibility.public
    metadata: dict = dc_field(default_factory=dict)


@dataclass
class RegisteredArtifact:
    """Result of storing one discovered artifact in the agent-native store."""

    profile_id: str
    artifact_id: str
    version_id: str
    eligibility: EligibilityState
    scan_result: IngestScanResult


class AgentDiscoveryAdapter(Protocol):
    """Protocol for safe agent artifact discovery adapters."""

    source_type: str

    def discover(self, max_results: int = 100) -> list[RawAgentArtifact]:
        ...


class GitHubAgentArtifactAdapter:
    """
    Transitional GitHub adapter.

    This wraps the legacy skill scraper and records markdown prompt bundles as
    discovered artifacts. They remain unassigned until a normalizer/classifier
    converts them into role-comparable runner contracts.
    """

    source_type: str = "github"

    def discover(self, max_results: int = 100) -> list[RawAgentArtifact]:
        from ingest.github import scrape_all

        discovered = scrape_all(
            include_search=True,
            max_search_results=max_results,
        )
        artifacts: list[RawAgentArtifact] = []
        for item in discovered:
            artifacts.append(
                RawAgentArtifact(
                    name=item.name or item.file_path.rsplit("/", 1)[-1],
                    summary=item.description,
                    source_type=self.source_type,
                    source_id=item.source_url,
                    source_url=item.source_url,
                    raw_content=item.raw_content,
                    packaging_type=PackagingType.markdown_prompt_bundle,
                    repo_or_package=item.source_repo,
                    owner=item.repo_owner,
                    source_commit="",
                )
            )
        return artifacts


def register_discovered_artifact(
    db_module,
    artifact: RawAgentArtifact,
) -> RegisteredArtifact:
    """
    Persist a discovered artifact and create a non-runnable agent version record.

    The discovery step never produces an eligible runnable version. It only
    stores hostile input, sanitizes it, and records whether it is supported for
    later normalization.
    """

    scan_result = scan_untrusted_content(artifact.raw_content)
    sanitized_hash = sha256(
        scan_result.sanitized_text.encode("utf-8")
    ).hexdigest()
    existing_version = db_module.find_agent_version_by_content_hash(sanitized_hash)
    if existing_version is not None:
        return RegisteredArtifact(
            profile_id=existing_version.profile_id,
            artifact_id=existing_version.artifact_id,
            version_id=existing_version.id,
            eligibility=existing_version.eligibility,
            scan_result=scan_result,
        )

    artifact_id = db_module.add_artifact_record(
        ArtifactRecord(
            packaging_type=artifact.packaging_type,
            source_type=artifact.source_type,
            source_url=artifact.source_url,
            source_commit=artifact.source_commit,
            raw_content=artifact.raw_content,
            sanitized_content=scan_result.sanitized_text,
            content_hash=sanitized_hash,
            security_findings=scan_result.findings,
        )
    )
    profile_id = db_module.add_agent_profile(
        AgentProfile(
            name=artifact.name,
            field=artifact.field or DEFAULT_FIELD,
            role=artifact.role or DEFAULT_ROLE,
            summary=artifact.summary,
            owner=artifact.owner,
            source_url=artifact.source_url,
            packaging_type=artifact.packaging_type,
            visibility=artifact.visibility,
        )
    )
    eligibility, ineligibility_reason = _derive_eligibility(artifact)
    version_id = db_module.add_agent_version(
        AgentVersion(
            profile_id=profile_id,
            version_label=artifact.version_label,
            source_commit=artifact.source_commit,
            content_hash=sanitized_hash,
            packaging_type=artifact.packaging_type,
            provenance=ProvenanceRef(
                source_type=artifact.source_type,
                source_url=artifact.source_url,
                source_commit=artifact.source_commit,
            ),
            artifact_id=artifact_id,
            eligibility=eligibility,
            ineligibility_reason=ineligibility_reason,
            security_findings=scan_result.findings,
        )
    )
    return RegisteredArtifact(
        profile_id=profile_id,
        artifact_id=artifact_id,
        version_id=version_id,
        eligibility=eligibility,
        scan_result=scan_result,
    )


def discover_and_register_artifacts(
    db_module,
    adapters: list[AgentDiscoveryAdapter],
    max_per_source: int = 100,
) -> list[RegisteredArtifact]:
    """Run adapters and register each discovered artifact in the store."""

    registered: list[RegisteredArtifact] = []
    for adapter in adapters:
        for artifact in adapter.discover(max_results=max_per_source):
            registered.append(register_discovered_artifact(db_module, artifact))
    return registered


def _derive_eligibility(
    artifact: RawAgentArtifact,
) -> tuple[EligibilityState, str]:
    """Discovery only records support state; normalization decides true eligibility."""

    if artifact.packaging_type == PackagingType.unsupported:
        return (
            EligibilityState.unsupported,
            "Unsupported packaging type for normalization.",
        )
    return (EligibilityState.pending, "")
