from __future__ import annotations

import pytest
from pydantic import ValidationError

from agents.contracts import (
    AgentProfile,
    AgentVersion,
    EligibilityState,
    PackagingType,
    ProvenanceRef,
    RunnerContract,
    Visibility,
)
from benchmark.executor import contract_to_parsed_skill


def test_runner_contract_accepts_valid_config():
    contract = RunnerContract(
        field="software-engineering",
        role="code-review-agent",
        profile_name="Reviewer One",
        packaging_type=PackagingType.markdown_prompt_bundle,
        system_instructions="Review code carefully.",
        model_provider="anthropic",
        model_name="claude-haiku",
        max_input_tokens=1000,
        max_output_tokens=1000,
        max_total_tokens=2500,
    )

    assert contract.field == "software-engineering"
    assert contract.provider_routing_visible is True


def test_runner_contract_rejects_invalid_token_budget():
    with pytest.raises(ValidationError):
        RunnerContract(
            field="software-engineering",
            role="code-review-agent",
            profile_name="Reviewer One",
            packaging_type=PackagingType.markdown_prompt_bundle,
            system_instructions="Review code carefully.",
            model_provider="anthropic",
            model_name="claude-haiku",
            max_input_tokens=2000,
            max_output_tokens=2000,
            max_total_tokens=1000,
        )


def test_contract_to_parsed_skill_preserves_execution_provider_metadata():
    contract = RunnerContract(
        field="software-engineering",
        role="code-review-agent",
        profile_name="Reviewer One",
        packaging_type=PackagingType.markdown_prompt_bundle,
        system_instructions="Review code carefully.",
        model_provider="qwen",
        model_name="qwen-plus",
        max_input_tokens=1000,
        max_output_tokens=1000,
        max_total_tokens=2500,
    )

    skill = contract_to_parsed_skill(contract)

    assert skill.exec_model_provider == "qwen"
    assert skill.exec_model_name == "qwen-plus"


def test_agent_profile_requires_field_and_role():
    with pytest.raises(ValidationError):
        AgentProfile(
            name="",
            field="",
            role="",
            packaging_type=PackagingType.repo_config_bundle,
            visibility=Visibility.public,
        )


def test_agent_version_requires_reason_when_ineligible():
    with pytest.raises(ValidationError):
        AgentVersion(
            profile_id="p1",
            version_label="v1",
            packaging_type=PackagingType.unsupported,
            provenance=ProvenanceRef(
                source_type="github",
                source_url="https://example.com/repo",
            ),
            eligibility=EligibilityState.unsupported,
        )


def test_agent_version_requires_contract_when_eligible():
    with pytest.raises(ValidationError):
        AgentVersion(
            profile_id="p1",
            version_label="v1",
            packaging_type=PackagingType.markdown_prompt_bundle,
            provenance=ProvenanceRef(
                source_type="github",
                source_url="https://example.com/repo",
            ),
            eligibility=EligibilityState.eligible,
        )
