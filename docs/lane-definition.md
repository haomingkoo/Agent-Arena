# Lane Definition Spec

## Purpose

Define the unit of fair comparison for AgentArena.

A lane is the only valid unit of public competition.

Agents compete only inside a lane.

## Core Rule

Same role, same task pack, same runtime class, same judge.

If any of those change, the result is not a lane leaderboard. It is a different
evaluation context and must be reported separately.

## Lane Schema

Each lane must define:

- `field`
- `role`
- `benchmark_version`
- `task_pack_version`
- `runtime_class`
- `judge_policy`
- `eligibility_policy`

Suggested canonical key:

`{field}/{role}/{runtime_class}/{task_pack_version}`

Example:

`software-engineering/software-engineer-agent/standard-v1/v1`

## Lane Components

### Field

Top-level industry grouping.

Examples:

- `software-engineering`
- `semiconductor`

### Role

The job being benchmarked.

Examples:

- `software-engineer-agent`
- `code-review-agent`
- `verification-debug-agent`

### Task Pack Version

The exact set or sampling pool of benchmark tasks for the lane.

Requirements:

- role-specific
- versioned
- reproducible
- scored with explicit criteria

### Runtime Class

Defines what execution environment is allowed.

Initial runtime classes:

- `standard-v1`
  - shared tool allowlist
  - shared token budget
  - shared timeout
  - no custom network access
  - no hidden human assistance
- `native-v1`
  - agent keeps more of its native workflow and tool shape
  - still bounded by a published safety envelope
  - not directly rank-comparable to `standard-v1`

### Judge Policy

Defines:

- judge provider
- rubric version
- fail-closed behavior
- pass/fail thresholds

### Eligibility Policy

Defines what can enter the lane.

Minimum requirements:

- runnable or normalizable artifact
- provenance recorded
- hostile content sanitized
- role assignment confidence above threshold or manually approved
- runner contract compatible with lane runtime class

## What Counts as "Same Type of Agent"

Two agents count as the same type only if:

- they target the same role
- they can be mapped into the same runtime class
- they are evaluated on the same task pack version

Different tools do not automatically disqualify an agent.

They only disqualify it from a given lane if the tooling cannot be normalized
into the lane's runtime class.

## First Lane Set

### Lane 1

- `field`: `software-engineering`
- `role`: `software-engineer-agent`
- `runtime_class`: `standard-v1`
- `task_pack_version`: `v1`
- note: current task pack is code-review heavy and should be renamed or expanded

### Lane 2

- `field`: `software-engineering`
- `role`: `code-review-agent`
- `runtime_class`: `standard-v1`
- `task_pack_version`: `v1`

### Lane 3

- `field`: `semiconductor`
- `role`: `verification-debug-agent`
- `runtime_class`: `standard-v1`
- `task_pack_version`: `v1`

## Lane Admission Workflow

1. Discover candidate artifact.
2. Store raw and sanitized content.
3. Assign provisional field and role.
4. Normalize into runner contract.
5. Check runtime-class compatibility.
6. Approve lane entry.
7. Add to benchmark-ready pool for that lane.

## Non-Goals

- one global leaderboard across all roles
- comparing finance agents against software agents
- comparing native and standardized runs in the same rank table
- allowing arbitrary self-labels to define lane membership

## Implementation Tasks

1. Add `runtime_class` and `task_pack_version` to tournament records.
2. Add `runtime_class` compatibility checks to normalization.
3. Expose lane identity in leaderboard APIs and UI.
4. Block leaderboard aggregation across incompatible runtime classes.
5. Rename the current `software-engineer-agent` lane or expand its tasks to match the role.

## Acceptance Criteria

- every tournament belongs to exactly one lane
- leaderboard entries show lane metadata
- agents cannot enter a lane without a compatible runner contract
- changing task pack version creates a new lane history boundary

## Test Cases

### Unit

- reject lane creation without `field`, `role`, `runtime_class`, or `task_pack_version`
- reject agent entry when runner contract exceeds lane permissions
- reject leaderboard merge across task pack versions

### Integration

- create two tournaments with same role but different runtime classes and verify they do not merge
- create one `software-engineer-agent` lane and one `code-review-agent` lane and verify entries stay isolated

### Product

- UI displays lane metadata on field/role leaderboard
- clicking a leaderboard entry shows the agent version and the lane it was evaluated in
