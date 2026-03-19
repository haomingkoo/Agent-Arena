# Agent Platform Architecture

## Goal

Build AgentArena as an agent tournament platform with four connected loops:

1. Discover agents
2. Benchmark agents
3. Learn from winners
4. Let users build and run agents on-platform

The current repository already has pieces of scoring, tournaments, storage, and
frontend delivery, but those pieces are still centered on `Skill` objects.

The target architecture must be centered on `AgentProfile` and `AgentVersion`.

## Product Scope

V1 should support:

- field-scoped tournaments
- role-scoped leaderboards
- benchmark traces
- explicit cost and token accounting
- strict ingestion security
- hosted user-triggered runs with rate and spend controls

V1 should not try to support every agent framework on the internet.

## Recommended Starting Fields

Start with:

- Software Engineering
- Semiconductor Design and Verification

Recommended first roles:

- Software Engineering -> Code Reviewer Agent
- Semiconductor -> Verification Debug Agent

## Core Domain Model

### Field

Top-level industry grouping.

Examples:

- software-engineering
- semiconductor

### Role

A benchmarkable job inside a field.

Examples:

- code-review-agent
- software-engineer-agent
- verification-debug-agent

### AgentProfile

Human-facing identity for an agent.

Stores:

- name
- summary
- field
- role
- owner
- source URL
- packaging type
- visibility
- license

### AgentVersion

Immutable benchmarkable snapshot of an agent.

Stores:

- profile ID
- version label
- source commit or content hash
- normalized runner contract
- safety scan results
- provenance metadata
- benchmark eligibility state

### PackagingArtifact

What the raw discovered thing looked like before normalization.

Examples:

- markdown prompt bundle
- repo with config files
- MCP server manifest
- framework-specific agent spec

### RunnerContract

The canonical execution spec for a role-comparable agent.

Stores:

- system instructions
- tool allowlist
- memory policy
- file permissions
- network permissions
- max steps
- timeout
- token budget
- model family

### TaskPack

Versioned set of tasks for one field and role.

Stores:

- field
- role
- benchmark version
- grading method
- tasks
- sampling policy

### Tournament

One benchmark event for a field, role, task pack version, and runner contract
version.

### TournamentRun

One agent version evaluated across one task pack.

### RunTrace

Full audit trail for one task execution.

Stores:

- prompts
- tool calls
- tool outputs
- model responses
- judge prompts
- judge outputs
- token usage
- runtime
- failure reasons

### Scorecard

Per-run metrics.

Stores:

- task success
- correctness
- safety
- tool quality
- trace quality
- latency
- token cost
- judge confidence

### DesignInsight

Post-tournament learned pattern from top agents.

Stores:

- field
- role
- benchmark evidence
- pattern summary
- supporting traces

### BuilderProject

User-owned on-platform editable agent workspace.

Stores:

- owner
- draft config
- published versions
- private eval history

### UsageLedger

Spend and rate-limit control for hosted runs.

Stores:

- user
- window
- tokens
- provider cost
- run count
- limit violations

## System Architecture

### 1. Discovery Layer

Responsibilities:

- ingest candidate agent artifacts
- record provenance
- queue normalization

Modules:

- `ingest/discovery.py`
- `ingest/adapters/`
- `ingest/provenance.py`

### 2. Security Filter Layer

Responsibilities:

- treat scraped content as hostile
- strip or annotate active content
- detect prompt injection patterns
- prevent remote content from becoming instructions

Modules:

- `security/ingest_guard.py`
- `security/prompt_injection.py`
- `security/content_sanitizer.py`

### 3. Normalization Layer

Responsibilities:

- map raw artifacts into runner contracts
- reject unfair or unsupported candidates
- record benchmark eligibility

Modules:

- `agents/contracts.py`
- `agents/normalizer.py`
- `agents/packaging.py`

### 4. Benchmark Layer

Responsibilities:

- load role-specific task packs
- execute runs under shared constraints
- save traces
- score results

Modules:

- `benchmark/taskpacks.py`
- `benchmark/executor.py`
- `benchmark/judging.py`
- `benchmark/traces.py`

### 5. Tournament Layer

Responsibilities:

- select candidate set
- select task pack version
- run tournament
- compute leaderboard
- update ratings

Modules:

- `tournament/runner.py`
- `tournament/ranking.py`
- `tournament/scheduler.py`

### 6. Learning Layer

Responsibilities:

- analyze top and bottom performers
- extract repeatable design patterns
- generate build guidance

Modules:

- `coach/analyzer.py`
- `coach/recommender.py`
- `learn/design_insights.py`

### 7. Hosted Use Layer

Responsibilities:

- let users run benchmarked agents on their own prompts
- enforce rate, spend, and concurrency limits
- persist usage and feedback

Modules:

- `runtime/hosted_runs.py`
- `runtime/budgeting.py`
- `runtime/rate_limits.py`

### 8. Product Surfaces

Responsibilities:

- leaderboards
- tournament details
- trace details
- builder workflow
- hosted run workflow

Modules:

- `api/app.py`
- `frontend/src/`

## Migration From Current Repo

Current state:

- `Skill` is the central stored object
- discovery is GitHub-first and `SKILL.md`-oriented
- tournaments run category-scoped skill comparisons
- frontend and API still expose `skill` terminology

Target state:

- `AgentProfile` becomes the primary product object
- `AgentVersion` becomes the primary benchmark object
- `Skill` becomes one artifact subtype, not the platform abstraction

Migration principle:

- keep legacy tables readable
- add new agent-native tables first
- only migrate or alias old fields once agent-native flows work end to end

## Data Flow

1. Discovery adapter fetches a raw candidate artifact
2. Security filter sanitizes and classifies hostile content
3. Normalizer attempts to build a runner contract
4. Candidate is marked benchmarkable or non-benchmarkable
5. Tournament runner selects eligible candidates by field and role
6. Executor runs all candidates on the same task pack
7. Judge stack scores outputs and traces
8. Results and traces are persisted
9. Leaderboards update
10. Learning loop extracts design insights
11. Builder workflow reuses those insights for new agent versions

## Non-Negotiable Constraints

- no hidden judge fallback
- no implicit provider switching
- no scraped content treated as privileged instruction
- no benchmark between candidates with materially different privileges
- no hosted user execution without rate and spend controls

## Immediate Build Priorities

1. Introduce agent-native data models beside legacy skill models
2. Define runner contract schema and normalization rules
3. Add ingestion guardrails for hostile external content
4. Split tournament tracks by field and role
5. Add trace-first benchmark persistence
6. Add hosted-run budgeting and rate limiting before public usage
