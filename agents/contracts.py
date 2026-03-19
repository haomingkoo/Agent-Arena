"""
Agent-native benchmark contract models.

These models sit beside the legacy skill-oriented models and define the target
abstraction for agent-vs-agent benchmarking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class PackagingType(str, Enum):
    markdown_prompt_bundle = "markdown_prompt_bundle"
    repo_config_bundle = "repo_config_bundle"
    platform_native_builder_project = "platform_native_builder_project"
    unsupported = "unsupported"


class Visibility(str, Enum):
    public = "public"
    private = "private"
    unlisted = "unlisted"


class EligibilityState(str, Enum):
    pending = "pending"
    eligible = "eligible"
    ineligible = "ineligible"
    unsupported = "unsupported"


class ReviewState(str, Enum):
    pending_review = "pending-review"
    qualification_required = "qualification-required"
    approved_public = "approved-public"
    approved_private_only = "approved-private-only"
    relabelled = "relabelled"
    rejected = "rejected"
    unsupported = "unsupported"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProvenanceRef(BaseModel):
    source_type: str
    source_url: str
    source_commit: str = ""
    discovered_at: str = Field(default_factory=_utc_now)


class ToolPolicy(BaseModel):
    name: str
    description: str = ""
    read_only: bool = True
    side_effects_allowed: bool = False
    max_calls: int = 0

    @model_validator(mode="after")
    def validate_limits(self) -> "ToolPolicy":
        if self.max_calls < 0:
            raise ValueError("max_calls must be non-negative")
        return self


class RunnerContract(BaseModel):
    field: str
    role: str
    profile_name: str
    version_id: str = ""
    source_url: str = ""
    packaging_type: PackagingType

    system_instructions: str
    developer_instructions: str = ""
    task_input_template: str = "{task}"
    refusal_policy: str = ""

    allowed_tools: list[str] = Field(default_factory=list)
    tool_policies: list[ToolPolicy] = Field(default_factory=list)

    memory_mode: str = "stateless"
    memory_budget: int = 0
    cross_task_memory_allowed: bool = False

    model_provider: str
    model_name: str
    max_steps: int = 8
    timeout_seconds: int = 120
    max_input_tokens: int = 0
    max_output_tokens: int = 0
    max_total_tokens: int = 1

    filesystem_access: str = "read-only"
    network_access: bool = False
    sandbox_mode: str = "workspace-write"
    secrets_policy: str = "none"

    trace_capture: bool = True
    log_tool_calls: bool = True
    log_judge_prompts: bool = True
    provider_routing_visible: bool = True

    @model_validator(mode="after")
    def validate_contract(self) -> "RunnerContract":
        if not self.field.strip():
            raise ValueError("field is required")
        if not self.role.strip():
            raise ValueError("role is required")
        if not self.system_instructions.strip():
            raise ValueError("system_instructions is required")
        if not self.model_provider.strip():
            raise ValueError("model_provider is required")
        if not self.model_name.strip():
            raise ValueError("model_name is required")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_total_tokens <= 0:
            raise ValueError("max_total_tokens must be positive")
        if self.max_input_tokens < 0 or self.max_output_tokens < 0:
            raise ValueError("token limits must be non-negative")
        if (
            self.max_input_tokens
            and self.max_output_tokens
            and self.max_input_tokens + self.max_output_tokens > self.max_total_tokens
        ):
            raise ValueError("max_total_tokens must cover input + output token limits")
        if self.cross_task_memory_allowed and self.memory_mode == "stateless":
            raise ValueError(
                "cross_task_memory_allowed cannot be true when memory_mode is stateless"
            )
        return self


class ArtifactRecord(BaseModel):
    id: str = ""
    packaging_type: PackagingType
    source_type: str
    source_url: str
    source_commit: str = ""
    raw_content: str = ""
    sanitized_content: str = ""
    content_hash: str = ""
    security_findings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now)


class AgentProfile(BaseModel):
    id: str = ""
    name: str
    field: str
    role: str
    summary: str = ""
    owner: str = ""
    source_url: str = ""
    packaging_type: PackagingType
    visibility: Visibility = Visibility.public
    license: str = ""
    created_at: str = Field(default_factory=_utc_now)
    updated_at: str = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def validate_profile(self) -> "AgentProfile":
        if not self.name.strip():
            raise ValueError("name is required")
        if not self.field.strip():
            raise ValueError("field is required")
        if not self.role.strip():
            raise ValueError("role is required")
        return self


class AgentVersion(BaseModel):
    id: str = ""
    profile_id: str
    version_label: str
    source_commit: str = ""
    content_hash: str = ""
    packaging_type: PackagingType
    provenance: ProvenanceRef
    artifact_id: str = ""
    runner_contract: RunnerContract | None = None
    eligibility: EligibilityState = EligibilityState.pending
    ineligibility_reason: str = ""
    security_findings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def validate_version(self) -> "AgentVersion":
        if not self.profile_id.strip():
            raise ValueError("profile_id is required")
        if not self.version_label.strip():
            raise ValueError("version_label is required")
        if self.eligibility in {
            EligibilityState.ineligible,
            EligibilityState.unsupported,
        } and not self.ineligibility_reason.strip():
            raise ValueError("ineligibility_reason is required for non-eligible versions")
        if self.eligibility == EligibilityState.eligible and self.runner_contract is None:
            raise ValueError("eligible versions require a runner_contract")
        return self
