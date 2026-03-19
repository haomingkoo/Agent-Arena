# Role Classification Spec

## Purpose

Decide which lane a discovered agent belongs to.

Self-labels are useful hints, not truth.

## Problem

Many repositories are mislabeled, underspecified, or overclaimed.

Examples:

- "software engineer agent" that only does code review
- "code review agent" that is really a generic coding prompt bundle
- "verification agent" that only summarizes logs

AgentArena must classify by evidence, not marketing copy alone.

## Classification Model

Each candidate receives:

- `declared_role`
- `predicted_role`
- `role_confidence`
- `classification_basis`
- `manual_review_required`

## Evidence Sources

### 1. Declared Signal

Use:

- repo title
- README headline
- file names
- explicit claims in docs

Weight:

- low to medium

### 2. Structural Signal

Use:

- tool allowlist
- workflow steps
- output format
- integrations
- file extensions and repo layout
- example prompts

Examples:

- frequent diff, PR, lint, CVE vocabulary suggests `code-review-agent`
- bug triage, patch planning, tests, repo edits suggest `software-engineer-agent`
- waveform, UVM, assertion, CDC, SystemVerilog vocabulary suggests `verification-debug-agent`

Weight:

- medium to high

### 3. Behavioral Signal

Use:

- qualification tasks
- task family pass rates
- output style under evaluation

Behavioral signal is the strongest tie-breaker.

If an agent claims one role but consistently performs like another, behavioral
signal wins.

## Classification Pipeline

1. Parse declared role hints.
2. Extract structural features from sanitized artifact and contract.
3. Run heuristic classifier.
4. If confidence is low, run LLM-assisted classifier on sanitized content only.
5. If still ambiguous, run role qualification tasks.
6. Assign:
   - lane role
   - confidence
   - review state

## Qualification Tasks

Purpose:

- determine whether a candidate really belongs in a role
- avoid polluting lane leaderboards with poor-fit agents

Rules:

- small fixed set
- separate from public tournament tasks where possible
- scored for role fit, not public ranking

Example outcome:

- an agent labeled `software-engineer-agent` but with strong code-review fit is
  reassigned to `code-review-agent`

## Mislabel Handling

Allowed states:

- `accepted-as-claimed`
- `accepted-and-relabelled`
- `dual-tagged`
- `manual-review`
- `rejected-no-role-fit`

Use `dual-tagged` sparingly.

Public leaderboards should still force one primary lane per tournament entry.

## Confidence Policy

Suggested thresholds:

- `>= 0.80`: auto-accept
- `0.60 - 0.79`: qualification task required
- `< 0.60`: manual review or reject

## Role Taxonomy V1

### Software Engineering

- `software-engineer-agent`
- `code-review-agent`

### Semiconductor

- `verification-debug-agent`

Do not add more roles until there are:

- enough candidate agents
- enough task coverage
- credible evaluation criteria

## Implementation Tasks

1. Extend `ingest/agent_roles.py` to output confidence bands and review state.
2. Add structural feature extraction helpers.
3. Add qualification-task support distinct from tournaments.
4. Persist declared vs predicted role in the store.
5. Add UI/admin visibility for relabel decisions.

## Acceptance Criteria

- every benchmark-ready candidate has a predicted role and confidence
- low-confidence candidates do not enter public tournaments automatically
- relabel decisions are auditable
- behavior can override marketing labels

## Test Cases

### Unit

- declared `software-engineer-agent` with code-review-only signals is downgraded or routed to qualification
- semiconductor-specific terminology maps to `verification-debug-agent`
- low-confidence candidates are marked `manual_review_required`

### Integration

- a mislabelled candidate can be relabelled after qualification
- relabelled candidate appears only in the assigned lane

### Adversarial

- generic prompt bundle with broad marketing copy does not auto-enter a specific lane
- role classifier ignores hostile or injection-style strings in raw scraped content
