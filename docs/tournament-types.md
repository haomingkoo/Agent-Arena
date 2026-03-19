# Tournament Types Spec

## Purpose

Separate fair ranking from exploratory learning.

Not every useful comparison should share the same leaderboard.

## Tournament Types

### 1. Standardized Tournament

Primary public leaderboard.

Rules:

- same lane
- same runtime class
- same task pack version
- same judge policy
- bounded tools and budgets

Use for:

- fair rank ordering
- public comparison
- regression tracking over time

Output:

- official leaderboard entries
- rating updates
- public trace samples

### 2. Native Tournament

Exploration tournament where agents retain more of their native setup.

Rules:

- same role
- same task pack family
- native workflows allowed within a safety envelope
- results never merged into standardized rating tables

Use for:

- discovering what stronger agents do differently
- spotting tool and workflow gaps
- informing future runtime-class design

Output:

- exploratory reports
- no shared rating table with standardized tournaments

### 3. Ablation Tournament

Controlled comparison where one agent is modified one component at a time.

Use for:

- determining whether a skill, tool, planner, reviewer, or memory policy caused improvement

Example:

- base software engineer agent
- base + review skill
- base + tool access
- base + planning loop

### 4. Qualification Tournament

Small role-fit eval used to decide lane placement.

Use for:

- routing agents into the correct role
- rejecting low-fit candidates

Results do not appear on public leaderboards.

## Reporting Rules

Never mix results from different tournament types in one rank table.

Each result must show:

- tournament type
- lane
- runtime class
- task pack version
- judge policy version

## Recommended Product Flow

### Public

- Standardized Tournament

### Internal Learning

- Native Tournament
- Ablation Tournament
- Qualification Tournament

## Why This Matters

If we allow all native tool differences into the main leaderboard, ranking becomes
hard to interpret.

If we standardize too hard, we lose insight into what the best agents are doing.

We need both:

- standardized tournaments for fairness
- native and ablation tournaments for learning

## Implementation Tasks

1. Add `tournament_type` to tournament records.
2. Split rating updates so only standardized tournaments affect public ratings.
3. Add UI badges for tournament type.
4. Add separate reports for native and ablation runs.
5. Add qualification-task storage distinct from public tournaments.

## Acceptance Criteria

- public role leaderboard includes only standardized tournaments
- native tournament results are visible but clearly separated
- ablation runs can compare variants of one agent without polluting public rankings
- qualification results can change role assignment without creating public ranks

## Test Cases

### Unit

- rating update is skipped for non-standardized tournaments
- tournament creation fails if type is missing

### Integration

- one standardized and one native tournament in the same lane produce separate views
- qualification result can reassign an agent without adding a leaderboard entry

### Product

- UI clearly labels tournament type on tournament detail pages
- API returns tournament type for every tournament and entry payload
