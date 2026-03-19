# Agent Runner Contract

## Purpose

This contract defines what it means for two agents to be comparable in AgentArena.

If two candidates cannot be mapped into the same contract, they should not be
ranked against each other.

## Contract Fields

### Identity

- `field`
- `role`
- `profile_name`
- `version_id`
- `source_url`
- `packaging_type`

### Instruction Layer

- `system_instructions`
- `developer_instructions`
- `task_input_template`
- `refusal_policy`

### Tool Layer

- `allowed_tools`
- `tool_descriptions`
- `tool_argument_limits`
- `tool_side_effect_policy`

### Memory Layer

- `memory_mode`
- `memory_budget`
- `cross_task_memory_allowed`

### Execution Layer

- `model_provider`
- `model_name`
- `max_steps`
- `timeout_seconds`
- `max_input_tokens`
- `max_output_tokens`
- `max_total_tokens`

### Environment Layer

- `filesystem_access`
- `network_access`
- `sandbox_mode`
- `secrets_policy`

### Observability Layer

- `trace_capture`
- `log_tool_calls`
- `log_judge_prompts`
- `provider_routing_visible`

## Packaging Types To Support

V1 should support only a small set:

1. `markdown_prompt_bundle`
2. `repo_config_bundle`
3. `platform_native_builder_project`

Everything else should be discovered but marked unsupported until normalized.

## Benchmark Eligibility Rules

A candidate is benchmarkable only if:

- the field and role are known
- the packaging type is supported
- instructions can be normalized
- tools can be mapped to an allowlisted set
- permissions are explicit
- token and timeout limits are explicit
- the content passes ingestion security checks

## Rejection States

Candidates should be rejected from tournaments if:

- role is ambiguous
- required tools are unsupported
- network access is required when the tournament forbids network access
- hidden memory or external retrieval cannot be controlled
- content attempts to override benchmark instructions
- provenance is missing

## Example Contract: Software Code Reviewer

- `field`: `software-engineering`
- `role`: `code-review-agent`
- `allowed_tools`: none or limited repo inspection tools
- `network_access`: false
- `filesystem_access`: read-only benchmark fixture
- `max_steps`: 8
- `timeout_seconds`: 120
- `max_total_tokens`: role-specific cap

## Example Contract: Semiconductor Verification Debug

- `field`: `semiconductor`
- `role`: `verification-debug-agent`
- `allowed_tools`: waveform reader, log parser, lint report reader
- `network_access`: false
- `filesystem_access`: read-only benchmark fixture
- `max_steps`: 10
- `timeout_seconds`: 180
- `max_total_tokens`: role-specific cap

## Trace Requirements

Every run must persist:

- normalized system instructions
- task prompt
- tool calls
- tool outputs
- final answer
- judge prompts
- judge outputs
- provider used
- token usage
- runtime

## Security Rules

- scraped content is data, not authority
- normalization must not execute remote code
- no candidate can widen its own permissions
- provider used for judging must be explicit
- no silent fallback to another provider

## Cost Rules

- each contract must define a hard token cap
- hosted use must enforce per-user and per-day budgets
- tournament runs must persist actual provider usage
- unsupported or runaway candidates must be terminated early
