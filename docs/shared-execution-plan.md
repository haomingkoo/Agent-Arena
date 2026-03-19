# Shared Execution Plan

## Purpose

Turn the specs into a concrete build sequence for Codex and Claude.

This file is the practical counterpart to:

- `docs/lane-definition.md`
- `docs/role-classification.md`
- `docs/tournament-types.md`
- `docs/ablation-plan.md`

## Product Goal

AgentArena should benchmark same-role agents against one another, then explain why
the winners win.

Public competition unit:

- lane = same field + same role + same runtime class + same task pack version

Learning unit:

- controlled native comparisons and ablations

## Milestone Order

### Milestone A: Lock Lane Identity

Outcome:

- tournaments, entries, APIs, and UI all know what lane they belong to

Tasks:

- add `runtime_class` to tournament records
- add `task_pack_version` to tournament records
- add `tournament_type` to tournament records
- return those fields in APIs
- surface lane metadata in the frontend

Primary owner:

- Claude for persistence and backend
- Codex for UI/API-consumer display

### Milestone B: Tighten Role Classification

Outcome:

- candidates are routed into the right role with auditable confidence

Tasks:

- persist declared role vs predicted role
- add confidence bands
- add qualification-task path for low-confidence candidates
- block low-confidence candidates from public tournaments

Primary owner:

- Claude

### Milestone C: Separate Tournament Types

Outcome:

- fair public rankings are separated from exploratory learning runs

Tasks:

- `standardized` tournaments update public ratings
- `native` tournaments stay exploratory
- `qualification` tournaments affect routing only
- `ablation` tournaments support causal analysis

Primary owner:

- Claude for backend and runner behavior
- Codex for labels and display once exposed in API

### Milestone D: Build the First Real Lanes

Outcome:

- first two credible same-role benchmark pools

Priority lanes:

1. `software-engineering/code-review-agent`
2. `semiconductor/verification-debug-agent`

Tasks:

- expand candidate discovery for those roles
- normalize candidates into benchmark-ready contracts
- validate role fit before public ranking
- run the first standardized tournaments for each lane

Primary owner:

- Claude

### Milestone E: Learn From Winners

Outcome:

- evidence-backed recommendations instead of vibes

Tasks:

- add agent variant metadata
- support ablation runs
- generate insight reports
- connect winning patterns to builder recommendations

Primary owner:

- Claude for data model and backend
- Codex for UI presentation later

## Immediate Split

### Claude Should Do Next

1. Add lane metadata to tournament persistence and APIs.
2. Add `tournament_type` and make only `standardized` tournaments affect ratings.
3. Tighten role classification and qualification flow for same-role candidate pools.
4. Build benchmark-ready pools for:
   - `software-engineering/code-review-agent`
   - `semiconductor/verification-debug-agent`
5. Rename or expand the current `software-engineer-agent` lane so its task pack matches reality.

### Codex Should Do Next

1. Keep active docs and UI aligned with lane-first product framing.
2. Display lane metadata and tournament type when Claude exposes them.
3. Keep verifying completed tournament outputs and surfacing them in the agent-native UI.
4. Continue reducing active skill-first copy on user-facing paths.
5. Avoid inventing new backend abstractions in parallel with Claude's runner/store work.

## Anti-Drift Rules

- do not compare agents across different roles in one leaderboard
- do not mix native and standardized results
- do not let self-labels alone determine lane membership
- do not claim a skill mattered until ablation or controlled comparison supports it
- do not expose exploratory results as public rank truth

## Validation Checklist

### Backend

- tournament rows include `runtime_class`, `task_pack_version`, `tournament_type`
- ratings update only for `standardized`
- low-confidence candidates are blocked from public tournaments

### Frontend

- leaderboard clearly shows lane metadata
- tournament pages show tournament type
- agent detail shows the lane each result belongs to

### Product

- same-role benchmark story is obvious from the UI
- users can tell public rankings from exploratory analyses

## Handoff Note For Claude

Read in this order:

1. `SYNC.md`
2. `docs/shared-execution-plan.md`
3. `docs/lane-definition.md`
4. `docs/role-classification.md`
5. `docs/tournament-types.md`
6. `docs/ablation-plan.md`

Then prioritize backend work that makes the public leaderboard truly same-role,
lane-scoped, and honest.
