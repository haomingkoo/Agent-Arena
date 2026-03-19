# JD Refresh and Trend Spec

## Purpose

Keep lane definitions current with the job market.

This spec covers:

- weekly ATS refresh
- JD corpus versioning
- role-core updates
- skill trend tracking

## Core Idea

AgentArena should not define roles once and freeze them forever.

Job expectations change.
Tooling expectations change.
Language in job descriptions changes.

Weekly refresh gives us a live market signal.

## Refresh Cadence

### Weekly

- refresh ATS-backed job postings
- dedupe and normalize new postings
- update skill/responsibility frequency counts
- flag role-core drift candidates

### Monthly

- review role-core changes
- approve or reject lane updates
- publish trend summaries

### Quarterly

- version lane blueprints if the role has materially changed

## Source Mix

Use:

- O*NET and BLS as stable anchors
- ATS-backed JDs as current market signal

Do not define role changes from one week's noisy postings alone.

## JD Corpus Versioning

Each role should store:

- `jd_corpus_version`
- refresh date
- source counts
- company-size mix
- normalized skill counts
- responsibility clusters

## Trend Outputs

For each role, compute:

- newly rising skills
- declining skills
- tools newly appearing
- tools disappearing
- changes in required deliverables

Example future product pages:

- `skills added this quarter`
- `skills fading from software engineer JDs`
- `verification debug expectations by employer tier`

## Resume and Career Utility

This data can later power:

- role trend dashboards
- builder recommendations
- resume keyword support
- "skills becoming standard" views

That is a future benefit, not the primary benchmark function.

## Update Rules

- weekly refresh updates the corpus
- public lane changes require monthly review
- lane blueprint version changes should be explicit and auditable

## Anti-Noise Rules

- require multi-company support before treating a skill as a rising trend
- separate one-off vendor jargon from genuine market shift
- do not rewrite role-core from a single JD or single employer

## Recommended Thresholds

Suggested inference policy:

- treat a skill as "rising" only if it appears across at least 3 distinct companies and 2 company-size buckets
- treat a role-core change as real only if it persists across at least 2 refresh cycles

These thresholds are recommendations, not external standards.

## Implementation Tasks

1. Add JD refresh scheduler.
2. Add ATS source adapters and normalized storage.
3. Add corpus version records per role.
4. Add trend computation jobs.
5. Add role trend and skill trend APIs.
6. Add a future UI page for rising/falling skills.

## Acceptance Criteria

- weekly refresh can update the JD corpus without rewriting public lane logic immediately
- role trend changes are versioned and reviewable
- trend views can identify rising and declining skills with source support

## Test Cases

### Unit

- repeated weekly refreshes dedupe identical postings
- trend logic does not overreact to one employer

### Integration

- a weekly refresh updates role statistics
- a monthly review can approve a new role-core version

### Product

- a role trend page can show which skills were added, dropped, or stable over time
