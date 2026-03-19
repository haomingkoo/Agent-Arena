# Implementation Backlog

## Milestone 0: Stop Drift

Goal:

- make the repo consistently describe the product as agent-vs-agent tournaments

Tasks:

- add root product docs
- mark legacy skill flows as transitional
- remove inactive provider hints from active env templates

Status:

- mostly done

## Milestone 1: Agent-Native Data Model

Goal:

- add agent-native persistence without breaking legacy skill data

Tasks:

- add `AgentProfile` model
- add `AgentVersion` model
- add `RunnerContract` model
- add `ArtifactRecord` model
- add `RunTrace` model
- add `HostedRun` model
- add `UsageLedger` model
- add migration script for new tables

Likely files:

- `store/models.py`
- `store/db.py`
- `migrations/`

Acceptance criteria:

- new tables created without breaking old data
- agent profile can be inserted and retrieved
- agent version can reference an artifact and contract
- run traces can be stored independently of old benchmark entries

## Milestone 2: Discovery and Security Pipeline

Goal:

- discover agent candidates safely

Tasks:

- define discovery adapter interface for agent artifacts
- add GitHub agent artifact adapter
- add ingestion sanitizer
- add prompt injection detector for scraped content
- store provenance and benchmark eligibility decisions

Likely files:

- `ingest/sources.py`
- `ingest/orchestrator.py`
- `ingest/discovery.py`
- `security/ingest_guard.py`
- `security/prompt_injection.py`

Acceptance criteria:

- raw artifact can be stored without being treated as instructions
- malicious markdown or HTML is flagged
- unsupported candidates are recorded but not executed

## Milestone 3: Runner Contract and Normalizer

Goal:

- convert artifacts into comparable runner contracts

Tasks:

- define contract schema
- build markdown prompt bundle normalizer
- build repo config bundle normalizer
- add unsupported-state reasons
- add contract validation rules

Likely files:

- `agents/contracts.py`
- `agents/normalizer.py`
- `agents/packaging.py`

Acceptance criteria:

- normalized agent version can be generated from supported artifact types
- invalid contracts fail with explicit reasons
- permissions and budgets are visible in persisted records

## Milestone 4: Task Packs and Benchmark Engine

Goal:

- run role-specific benchmarks with trace capture

Tasks:

- define task pack schema
- create software engineering code review pack
- create semiconductor verification debug pack
- build executor around runner contract
- persist traces and scorecards
- keep judge provider explicit and fail closed

Likely files:

- `benchmark/taskpacks.py`
- `benchmark/executor.py`
- `benchmark/judging.py`
- `benchmark/traces.py`
- `evaluate/sandbox.py`

Acceptance criteria:

- one agent version can run end to end on one role-specific task
- trace is stored with prompts, tool calls, judge prompts, and usage
- judge fails closed if required provider config is missing

## Milestone 5: Tournament and Leaderboard Layer

Goal:

- run field-role tournaments and publish scoped leaderboards

Tasks:

- split categories into `field` and `role`
- refactor tournament runner to use `AgentVersion`
- publish role-specific leaderboard endpoints
- add benchmark version and contract version to leaderboard entries
- add trace detail endpoint

Likely files:

- `tournament/runner.py`
- `tournament/ranking.py`
- `api/app.py`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/`

Acceptance criteria:

- tournament can run for one role with multiple agents
- leaderboard is scoped to field, role, benchmark version
- detail page shows costs and trace availability

## Milestone 6: Learning Loop

Goal:

- turn tournament outputs into build guidance

Tasks:

- compare top and bottom performers
- extract structure, tool-use, and safety patterns
- save design insights
- connect insights to builder workflow

Likely files:

- `coach/analyzer.py`
- `coach/recommender.py`
- `learn/design_insights.py`

Acceptance criteria:

- post-tournament report highlights repeatable patterns
- insights cite benchmark evidence rather than generic advice

## Milestone 7: Hosted Use and Builder

Goal:

- let users build and run agents safely on-platform

Tasks:

- add builder project model
- add draft agent editor flow
- add private eval flow
- add hosted run API
- add per-user rate limits
- add spend caps and concurrency limits

Likely files:

- `runtime/hosted_runs.py`
- `runtime/budgeting.py`
- `runtime/rate_limits.py`
- `api/app.py`
- `frontend/src/pages/Builder*.tsx`

Acceptance criteria:

- user can create a draft agent
- user can run a bounded private eval
- hosted runs stop at limit boundaries

## Field-Specific Initial Tasks

### Software Engineering

- create code review role spec
- normalize 5 to 10 public candidates
- finalize first task pack
- run first tournament

### Semiconductor

- define verification debug role spec
- create compact benchmark fixtures
- define deterministic and expert-review graders
- run internal pilot before public leaderboard

## Migration Tasks

- rename user-facing API copy from `skill` to `agent`
- preserve legacy endpoints temporarily behind compatibility shims
- add new frontend routes for field-role leaderboards
- eventually deprecate legacy skill-first terminology
