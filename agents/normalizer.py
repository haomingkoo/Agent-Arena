"""
Normalize stored artifacts into explicit runner contracts.

Discovery is intentionally conservative: it stores hostile content and marks
versions as pending. This module is the bridge from stored artifact to
benchmarkable contract when the artifact is supported and sufficiently scoped.
"""
from __future__ import annotations

from dataclasses import dataclass

from agents.contracts import EligibilityState, PackagingType, RunnerContract


UNASSIGNED_FIELD = "unassigned"
UNASSIGNED_ROLE = "unassigned-agent"

TOOL_HINTS = {
    "pytest": "pytest",
    "unit test": "pytest",
    "test suite": "pytest",
    "rg": "rg",
    "ripgrep": "rg",
    "grep": "rg",
    "git": "git",
    "bash": "bash",
    "shell": "bash",
    "python": "python",
}


@dataclass
class NormalizationResult:
    version_id: str
    eligibility: EligibilityState
    reason: str = ""
    runner_contract: RunnerContract | None = None


def normalize_agent_version(
    db_module,
    version_id: str,
    *,
    model_provider: str = "anthropic",
    model_name: str = "claude-haiku",
) -> NormalizationResult:
    """Attach a runner contract when an artifact is benchmarkable."""

    version = db_module.get_agent_version(version_id)
    if version is None:
        raise ValueError(f"Unknown agent version: {version_id}")
    profile = db_module.get_agent_profile(version.profile_id)
    if profile is None:
        raise ValueError(
            f"Agent version {version_id} references a missing profile"
        )
    if not version.artifact_id:
        raise ValueError(
            f"Agent version {version_id} has no artifact to normalize"
        )
    artifact = db_module.get_artifact_record(version.artifact_id)
    if artifact is None:
        raise ValueError(
            f"Agent version {version_id} references a missing artifact"
        )

    result = _build_normalization_result(
        profile=profile,
        version=version,
        artifact=artifact,
        model_provider=model_provider,
        model_name=model_name,
    )
    db_module.update_agent_version(
        version_id,
        runner_contract=result.runner_contract,
        eligibility=result.eligibility,
        ineligibility_reason=result.reason,
        security_findings=sorted(
            set(version.security_findings + artifact.security_findings)
        ),
        content_hash=artifact.content_hash or version.content_hash,
    )
    return result


def _build_normalization_result(
    *,
    profile,
    version,
    artifact,
    model_provider: str,
    model_name: str,
) -> NormalizationResult:
    if version.packaging_type == PackagingType.unsupported:
        return NormalizationResult(
            version_id=version.id,
            eligibility=EligibilityState.unsupported,
            reason="Unsupported packaging type for normalization.",
        )
    if not artifact.sanitized_content.strip():
        return NormalizationResult(
            version_id=version.id,
            eligibility=EligibilityState.pending,
            reason="Artifact content is empty after sanitization.",
        )
    if (
        profile.field == UNASSIGNED_FIELD
        or profile.role == UNASSIGNED_ROLE
    ):
        return NormalizationResult(
            version_id=version.id,
            eligibility=EligibilityState.pending,
            reason="Field and role must be assigned before normalization.",
        )

    contract = RunnerContract(
        field=profile.field,
        role=profile.role,
        profile_name=profile.name,
        version_id=version.id,
        source_url=profile.source_url,
        packaging_type=version.packaging_type,
        system_instructions=artifact.sanitized_content,
        allowed_tools=_infer_allowed_tools(artifact.sanitized_content),
        model_provider=model_provider,
        model_name=model_name,
        max_steps=8,
        timeout_seconds=120,
        max_input_tokens=4000,
        max_output_tokens=2000,
        max_total_tokens=7000,
        filesystem_access="read-only",
        network_access=False,
        sandbox_mode="workspace-write",
        secrets_policy="none",
    )
    requires_review = bool(
        set(version.security_findings + artifact.security_findings)
    )
    if requires_review:
        return NormalizationResult(
            version_id=version.id,
            eligibility=EligibilityState.pending,
            reason="Artifact requires manual security review before benchmarking.",
            runner_contract=contract,
        )
    return NormalizationResult(
        version_id=version.id,
        eligibility=EligibilityState.eligible,
        runner_contract=contract,
    )


def _infer_allowed_tools(text: str) -> list[str]:
    lower_text = text.lower()
    allowed_tools: list[str] = []
    for needle, tool_name in TOOL_HINTS.items():
        if needle in lower_text and tool_name not in allowed_tools:
            allowed_tools.append(tool_name)
    return allowed_tools
