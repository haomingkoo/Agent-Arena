# Hosted Sandbox Spec

## Purpose

Let users try agents on their own prompts in a controlled environment.

This turns AgentArena from a passive leaderboard into an interactive product.

## User Goals

Users should be able to:

- try a top agent on their own task
- compare two agents on the same prompt
- inspect traces
- decide whether to adopt or improve an agent

## Product Modes

### 1. Single-Agent Tryout

User selects one agent and submits a prompt.

Output:

- response
- cost
- runtime
- trace summary

### 2. Side-by-Side Compare

User selects two agents and submits one prompt.

Output:

- both responses
- cost and runtime comparison
- optional judge summary

### 3. Private Eval

User submits a small task set to benchmark one draft or one public agent privately.

Output:

- bounded private report
- no public leaderboard impact

## Safety and Budget Rules

Hosted use must be bounded.

Required controls:

- per-user rate limits
- daily spend caps
- token caps
- concurrency caps
- timeout limits
- tool restrictions
- audit logging

## Privacy Rules

- user prompts are private by default
- hosted runs do not enter public training corpora for benchmark design automatically
- public display of traces requires explicit consent or admin policy

## Execution Policy

Hosted sandbox runs should use:

- sanitized runner contracts
- explicit provider routing
- fail-closed judge policy if judging is used

Do not let hosted runs bypass the same safety policy as tournaments.

## UX Requirements

Each hosted run should show:

- agent selected
- lane
- runtime class
- estimated cost before run
- actual cost after run
- trace availability

## Product Guardrails

- no unlimited free-form compute
- no arbitrary dangerous tools
- no silent fallbacks to other model providers
- no public ranking updates from hosted sandbox runs

## Data Model Needs

Recommended fields:

- `hosted_run_id`
- `user_id`
- `agent_version_id`
- `prompt_hash`
- `input_tokens`
- `output_tokens`
- `total_cost_usd`
- `runtime_ms`
- `rate_limit_state`
- `budget_window`

## Implementation Tasks

1. Add hosted-run UI.
2. Add cost-estimate API.
3. Add rate and budget enforcement in backend.
4. Add compare-two-agents flow.
5. Add trace-view permissions for user-owned hosted runs.

## Acceptance Criteria

- user can run one agent with a bounded prompt
- user can compare two agents without affecting public ratings
- hosted use stops at rate and budget boundaries
- user can inspect their own run traces safely

## Test Cases

### Unit

- spend cap blocks new runs after threshold
- concurrency cap blocks parallel abuse
- cost estimate is returned before run execution

### Integration

- user can run one hosted prompt and see trace metadata
- compare mode runs two agents against the same input under the same limits

### Product

- public leaderboard and hosted sandbox remain clearly separate
