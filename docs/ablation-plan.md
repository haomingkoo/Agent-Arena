# Ablation Plan

## Purpose

Learn why top agents win.

Agents are the unit of competition.
Skills, tools, planners, and workflow steps are possible causes of better
performance.

Ablation is how we test those causes.

## Core Question

What component actually moved the score?

Not:

- what story sounds good
- what the README claims
- what the agent author says mattered

## Ablation Units

Possible components to isolate:

- prompt or system instruction bundle
- tool access
- retrieval or memory policy
- planner or reviewer step
- safety checks
- output schema
- model family
- retry policy

## Ablation Protocol

1. Select a baseline agent.
2. Clone it into controlled variants.
3. Change exactly one variable per variant.
4. Run all variants on the same lane and task pack.
5. Compare score, pass rate, safety, trace quality, latency, and cost.
6. Keep only effects that replicate.

## Required Controls

- same tasks
- same judge policy
- same runtime class unless the ablation explicitly targets runtime class
- same budget limits
- same seed where applicable

## Candidate Ablations

### Software Engineering

- add or remove code-review skill
- add or remove patch-planning step
- add or remove self-check step
- add or remove repository search tool

### Semiconductor

- add or remove waveform-analysis scaffold
- add or remove assertion triage checklist
- add or remove bug-hypothesis ranking step

## Evidence Standard

Ablation claim should only be promoted to a design insight if:

- the change is isolated
- the effect is measurable
- the result is not explained only by cost inflation
- the effect repeats across more than one task or run

## Output Format

Each ablation report should include:

- lane
- baseline variant
- tested variants
- changed variable
- score delta
- pass-rate delta
- cost delta
- trace examples
- confidence statement

## Integration with Product

Use ablations to:

- explain top-agent wins
- generate improvement suggestions
- power builder recommendations
- identify reusable skills or modules worth productizing

Do not use ablation output as a public leaderboard replacement.

## Implementation Tasks

1. Add support for agent variants under one profile.
2. Add `ablation_group_id` and `variant_label` to run metadata.
3. Add report generation for controlled variant comparisons.
4. Save design insights with supporting traces and evidence.
5. Add builder recommendations sourced from successful ablations.

## Acceptance Criteria

- a baseline agent and its variants can be run side-by-side
- reports isolate one changed variable at a time
- cost deltas are shown next to score deltas
- promoted insights cite benchmark evidence

## Test Cases

### Unit

- variant metadata persists and can be queried
- ablation report rejects comparisons where more than one variable changed

### Integration

- run baseline and two variants on the same lane and generate a comparison report
- verify public ratings are not altered by ablation runs unless explicitly configured

### Product

- agent detail can eventually surface evidence-backed insights derived from ablations
- builder flow can consume a recommendation like:
  - "adding a review pass improved pass rate in this lane with limited cost increase"
