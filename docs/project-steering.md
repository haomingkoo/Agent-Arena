# AgentArena Project Steering

Last updated: 2026-03-18

This document is the anti-drift contract for AgentArena.
If another doc, task list, or chat summary conflicts with this file, this file wins.

## Core Product Rule

AgentArena benchmarks who built the better agent for the same job.

Public comparison is only valid when all of these match:
- `field`
- `role`
- `runtime_class`
- `task_pack_version`
- `tournament_type=standardized`

Valid examples:
- `software-engineering/software-engineer-agent` vs `software-engineering/software-engineer-agent`
- `software-engineering/code-review-agent` vs `software-engineering/code-review-agent`
- `semiconductor/verification-debug-agent` vs `semiconductor/verification-debug-agent`

Invalid examples:
- software engineer vs code reviewer
- code reviewer vs security auditor
- software engineer vs semiconductor verifier

## Unit Of Evaluation

Primary unit:
- `AgentProfile`
- `AgentVersion`

Secondary explanatory factors:
- prompt bundle
- skills
- tools
- workflow steps
- planner/reviewer structure
- memory setup

Do not reframe product questions about agents into skill certification.
Skills are one possible component inside a full agent.

## How Roles Are Defined

Each public lane must be grounded in:
1. `O*NET` / `BLS` role definition
2. A weekly refreshed corpus of ATS-backed job descriptions
3. A role blueprint extracted from that corpus
4. Qualification prompts for lane admission
5. Work-sample tournament tasks derived from the role blueprint

Use ATS-backed company postings as primary current-market evidence:
- Greenhouse
- Lever
- Ashby
- SmartRecruiters
- Workable

Use job aggregators only for lead generation and trend checking, not as the primary source of truth.

## How Tests Must Be Designed

For each lane:
1. Build a role blueprint from multiple current JDs across large and small companies
2. Extract common responsibilities, outputs, tools, and failure modes
3. Create qualification prompts to test role fit
4. Create work-sample tasks for public benchmarking
5. Version the task pack

The public benchmark is not built from interview trivia alone.
Interview-style prompts are for qualification.
Work-sample tasks are for ranking.

## Tournament Types

- `standardized`
  - same role
  - same task pack
  - same runtime class
  - affects public ratings

- `native`
  - same role
  - agents keep more of their original stack
  - does not affect public ratings
  - used to learn what stronger agents are doing differently

- `qualification`
  - short role-fit screen
  - used for routing and lane admission
  - does not affect public ratings

- `ablation`
  - controlled comparison of one factor at a time
  - used to determine whether a skill/tool/workflow actually mattered
  - does not affect public ratings

## Benchmark Integrity Rules

Within one tournament:
- every agent in the lane gets the same public task set

Across tournaments:
- task sets rotate
- competency coverage stays stable

Each lane should maintain:
- anchor tasks for longitudinal comparability
- rotating tasks for freshness
- hidden holdouts for anti-gaming and integrity checks

Holdouts:
- are never part of public scoring
- are stored separately
- are used to validate whether public winners still generalize

Do not call a tournament fully credible if:
- public benchmark traces contain unresolved failures
- provider attribution is not auditable
- judge outputs are not parseable enough to support the conclusions

## Human Review Rules

Human review is required for:
- low-confidence role classification
- manual eligibility changes
- promotion from `pending` to `eligible`
- public-lane exceptions
- suspicious benchmark outcomes

Every manual decision must be reviewable later.
Ad hoc direct DB edits are not enough as the long-term workflow.

## Provider And Cost Truthfulness

Never claim a provider/model was used unless the persisted trace can prove it.

Required:
- effective execution provider must be stored from the actual run result
- judge provider must be stored from the actual judge call
- no silent fallback between providers
- no secret values printed in logs or terminal output

## Phases

### Phase 1: Credible Infrastructure
- agent-native persistence
- safe discovery and normalization
- lane metadata in APIs
- holdout separation
- truthful provider attribution
- judge fail-closed behavior

### Phase 2: First Credible Public Lane
- `software-engineering/code-review-agent`
- enough benchmark-ready agents for a credible public lane
- at least one provisional tournament
- reruns until rating behavior is stable

### Phase 3: Role Definition Engine
- ATS/JD ingestion
- weekly refresh
- role blueprint extraction
- qualification prompts tied to current market language

### Phase 4: Human Review Console
- queue for manual role/eligibility review
- reviewer decisions persisted
- buddy-check workflow before public admission

### Phase 5: Second Wedge Lane
- `semiconductor/verification-debug-agent`
- likely private or pilot before public launch

### Phase 6: Hosted Comparison And Builder Loop
- users can try agents on their own prompts
- budget/rate limits
- compare agents head-to-head
- eventually fork/build/improve and marketplace strong agents

## Current Implementation Guardrails

Right now:
- `software-engineering/code-review-agent` is the strongest public-lane candidate
- `software-engineering/software-engineer-agent` is not yet honest if it still uses code-review-heavy tasks
- `semiconductor/verification-debug-agent` is strategic but supply-constrained

Do not expand the marketing story beyond what the lanes can actually support.

## What To Do Next

Backend:
- finish truthful provider attribution
- keep improving judge robustness
- build ATS/JD ingestion
- build review-decision persistence
- fix or retire mismatched lanes

Frontend:
- keep the lane-first story honest
- expose lane metadata and tournament type clearly
- show holdouts as internal validation, not public score
- build the human review console UI once backend exists

QA:
- require tests for every sprint claim
- treat "some tests passed" as insufficient for signoff
- review real tournament outputs against DB evidence before accepting the narrative
