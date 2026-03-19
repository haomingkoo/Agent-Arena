from __future__ import annotations

from agents.contracts import EligibilityState, PackagingType, ProvenanceRef
from agents.normalizer import normalize_agent_version
from store.models import AgentProfile, AgentVersion, ArtifactRecord


def _create_pending_version(
    db_setup,
    *,
    field: str = "software-engineering",
    role: str = "code-review-agent",
    packaging_type: PackagingType = PackagingType.markdown_prompt_bundle,
    sanitized_content: str = (
        "Review code carefully.\nUse pytest for tests and rg for search."
    ),
    security_findings: list[str] | None = None,
):
    profile_id = db_setup.add_agent_profile(
        AgentProfile(
            name="Reviewer One",
            field=field,
            role=role,
            source_url="https://example.com/repo",
            packaging_type=packaging_type,
        )
    )
    artifact_id = db_setup.add_artifact_record(
        ArtifactRecord(
            packaging_type=packaging_type,
            source_type="github",
            source_url="https://example.com/repo",
            raw_content=sanitized_content,
            sanitized_content=sanitized_content,
            content_hash="hash-123",
            security_findings=security_findings or [],
        )
    )
    version_id = db_setup.add_agent_version(
        AgentVersion(
            profile_id=profile_id,
            version_label="v1",
            packaging_type=packaging_type,
            provenance=ProvenanceRef(
                source_type="github",
                source_url="https://example.com/repo",
            ),
            artifact_id=artifact_id,
            eligibility=EligibilityState.pending,
            security_findings=security_findings or [],
        )
    )
    return version_id


def test_normalize_agent_version_makes_supported_agent_eligible(db_setup):
    version_id = _create_pending_version(db_setup)

    result = normalize_agent_version(db_setup, version_id)
    stored = db_setup.get_agent_version(version_id)

    assert result.eligibility == EligibilityState.eligible
    assert result.runner_contract is not None
    assert result.runner_contract.allowed_tools == ["pytest", "rg"]
    assert stored is not None
    assert stored.eligibility == EligibilityState.eligible
    assert stored.runner_contract is not None
    assert stored.runner_contract.model_name == "claude-haiku"


def test_normalize_agent_version_requires_field_and_role_assignment(db_setup):
    version_id = _create_pending_version(
        db_setup,
        field="unassigned",
        role="unassigned-agent",
    )

    result = normalize_agent_version(db_setup, version_id)
    stored = db_setup.get_agent_version(version_id)

    assert result.eligibility == EligibilityState.pending
    assert result.reason == "Field and role must be assigned before normalization."
    assert stored is not None
    assert stored.eligibility == EligibilityState.pending
    assert stored.runner_contract is None


def test_normalize_agent_version_preserves_manual_security_review(db_setup):
    version_id = _create_pending_version(
        db_setup,
        security_findings=["instruction_override"],
    )

    result = normalize_agent_version(db_setup, version_id)
    stored = db_setup.get_agent_version(version_id)

    assert result.eligibility == EligibilityState.pending
    assert result.reason == (
        "Artifact requires manual security review before benchmarking."
    )
    assert result.runner_contract is not None
    assert stored is not None
    assert stored.runner_contract is not None
    assert stored.eligibility == EligibilityState.pending
    assert stored.security_findings == ["instruction_override"]


def test_normalize_agent_version_keeps_unsupported_packaging_unsupported(
    db_setup,
):
    version_id = _create_pending_version(
        db_setup,
        packaging_type=PackagingType.unsupported,
    )

    result = normalize_agent_version(db_setup, version_id)
    stored = db_setup.get_agent_version(version_id)

    assert result.eligibility == EligibilityState.unsupported
    assert result.runner_contract is None
    assert stored is not None
    assert stored.eligibility == EligibilityState.unsupported
    assert stored.ineligibility_reason == (
        "Unsupported packaging type for normalization."
    )
