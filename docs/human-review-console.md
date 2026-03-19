# Human Review Console Spec

## Purpose

Add a human-in-the-loop control surface for lane admission and role quality.

Automation should propose.
Humans should approve public competition eligibility when confidence is weak or
the lane fit is important.

## Why This Exists

The pipeline can misclassify agents.

Examples:

- generic coding bundle labeled as `software-engineer-agent`
- testing-focused artifact landing in a software-engineering lane
- semiconductor artifact with too little evidence for public ranking

The review console exists to prevent weak or mislabeled candidates from entering
public tournaments.

## Core Workflows

### 1. Triage Queue

Show all candidates needing review, sorted by:

- low role confidence
- high visibility candidates
- public-lane candidates
- security findings
- newly discovered artifacts

### 2. Candidate Review

For one candidate, show:

- profile name
- source URL
- owner
- packaging type
- claimed role
- predicted role
- confidence scores
- security findings
- sanitized artifact content
- runner contract preview
- qualification results if available
- benchmark eligibility state

### 3. Reviewer Actions

Allow:

- approve as predicted role
- approve but relabel role
- reject from public lanes
- route to qualification tasks
- mark unsupported
- add reviewer note

### 4. Audit Trail

Every review action must record:

- reviewer
- timestamp
- previous state
- new state
- reason
- optional note

## Review States

- `pending-review`
- `qualification-required`
- `approved-public`
- `approved-private-only`
- `relabelled`
- `rejected`
- `unsupported`

## Data To Persist

Recommended fields:

- `claimed_field`
- `claimed_role`
- `predicted_field`
- `predicted_role`
- `jd_fit_score`
- `qualification_fit_score`
- `work_sample_fit_score`
- `manual_review_required`
- `review_state`
- `review_decision_reason`
- `reviewed_by`
- `reviewed_at`

## UI Surfaces

### Review Queue Page

Columns:

- candidate
- source
- predicted lane
- confidence
- security status
- review state
- discovered at

### Candidate Detail Page

Sections:

- overview
- classification evidence
- sanitized content
- runner contract
- qualification traces
- review history

### Decision Controls

Buttons:

- approve
- relabel
- send to qualification
- reject

## Access Control

Only internal reviewers should access this console.

Minimum controls:

- authenticated reviewers
- action logging
- read-only vs reviewer roles

## Product Rules

- public tournament entry requires either high-confidence auto-accept or human approval
- low-confidence candidates cannot silently enter public lanes
- reviewer decisions override raw self-labels
- rejected candidates remain stored for audit but not public competition

## Implementation Tasks

1. Add review-state fields to persistence.
2. Add reviewer decision APIs.
3. Add reviewer history log.
4. Build review queue UI.
5. Build candidate detail/review UI.

## Acceptance Criteria

- reviewers can inspect sanitized artifacts before public approval
- reviewer can relabel a candidate before lane entry
- every public candidate has an auditable approval path
- rejected candidates do not enter public leaderboards

## Test Cases

### Unit

- relabel action updates predicted role and review metadata
- reject action blocks public eligibility
- review history persists immutable prior state

### Integration

- low-confidence candidate enters review queue, is relabelled, then appears only in the approved lane
- rejected candidate remains queryable in admin but never appears in public pools

### Product

- reviewer can open a candidate, read the sanitized content, and approve or reject without needing raw database access
