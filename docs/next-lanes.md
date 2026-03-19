# Next Lanes

## Purpose

Rank the next AgentArena lanes from the **current repo state**, not from
aspiration.

Public same-role lanes should be chosen using:

- benchmark-ready pool size
- distinct owner/source depth
- role clarity
- task-pack availability
- completed tournament evidence
- JD/ATS grounding

## Current Snapshot

As of 2026-03-18, the local DB shows:

| Field | Role | Eligible | Benchmark-ready | Distinct owners | Completed tournaments | Notes |
|---|---|---:|---:|---:|---:|---|
| software-engineering | code-review-agent | 16 | 16 | 13 | 2 | strongest current lane |
| software-engineering | software-engineer-agent | 15 | 15 | 2 | 1 | broad lane, weaker owner diversity |
| semiconductor | semiconductor-agent | 1 | 1 | 1 | 0 | not a real public lane |
| software-engineering | database-agent | 1 | 1 | 1 | 0 | too shallow |
| software-engineering | devops-agent | 1 | 1 | 1 | 0 | too shallow |
| software-engineering | frontend-agent | 1 | 1 | 1 | 0 | too shallow |
| software-engineering | security-audit-agent | 0 | 0 | 1 | 0 | not launchable |

Important constraint:

- `jd_postings` is currently empty, so JD-backed role grounding is not live yet.

## Ranked Recommendation

### 1. `software-engineering/code-review-agent`

Status:

- strongest current public lane candidate

Why:

- deepest current ready pool
- best owner diversity
- already has completed tournaments
- role is narrower and easier to judge than broad SWE

What to do:

- keep as the benchmark integrity reference lane
- continue duplicate cleanup and adjudication discipline
- use it as the standard for what a credible same-role lane looks like

### 2. `software-engineering/software-engineer-agent`

Status:

- next most important lane
- should be the next major same-role tournament focus

Why:

- enough ready agents to run
- real SWE task pack now exists
- broad role and product relevance make it strategically important

Risks:

- only `2` distinct owners right now, so the pool may be deeper than it is broad
- broad SWE roles are easier to misclassify than code review

What to do:

- clean the lane before overclaiming
- run the first real same-role SWE tournament
- treat results as provisional until duplicate risk and role fit are reviewed

### 3. `software-engineering/frontend-agent`

Status:

- not a public lane
- only a sourcing target right now

Why it is interesting:

- clear role boundary
- user-visible outputs are easy to inspect
- adjacent to existing SWE sourcing

Why it is not ready:

- only `1` ready candidate

What to do:

- use source expansion to find real frontend-agent artifacts
- do not launch until the lane has real depth

### 4. `software-engineering/devops-agent`

Status:

- not a public lane
- sourcing target only

Why it is interesting:

- clear operational tasks
- good long-term hosted sandbox value

Why it is not ready:

- only `1` ready candidate

What to do:

- gather more real agents first
- only then design the lane’s task blueprint and qualification flow

### 5. `software-engineering/database-agent`

Status:

- not a public lane
- sourcing target only

Why it is interesting:

- narrower role, potentially easier to evaluate than full SWE

Why it is not ready:

- only `1` ready candidate

What to do:

- source more role-specific agents before any tournament work

### 6. `semiconductor/verification-debug-agent`

Status:

- strategic moat lane
- not ready yet

Why it matters:

- strong differentiation potential
- aligns with domain expertise

Why it is not ready:

- current live pool is effectively absent
- no completed tournament evidence
- needs intentional sourcing, not generic scraping

What to do:

- keep as a pilot/private build target
- do not market as a public lane yet

## Public Expansion Rule

After the first real SWE tournament, do **not** just launch the next trendy role.

Launch order should be:

1. keep `code-review-agent` healthy
2. make `software-engineer-agent` credible
3. source one narrower software lane until it reaches real depth
4. keep semiconductor in pilot mode until real supply exists

## What Not To Do

- do not launch frontend/devops/database just because they sound clean
- do not launch semiconductor publicly just because it is strategically attractive
- do not count raw scrape volume as role readiness
- do not let one curator or mirrored repo family masquerade as a healthy lane

## Recommended Next Actions

### Claude

1. finish the first real `software-engineer-agent` tournament
2. run ATS/JD refreshes so role grounding stops being theoretical
3. add fuzzy duplicate detection
4. pick one narrow software lane to source next:
   - `frontend-agent` first
   - `devops-agent` second

### Codex

1. keep surfacing provisional vs clean lane status in the UI
2. keep duplicate/source-risk visible in ops and review
3. add role-ranking visibility once JD data starts landing

## Bottom Line

There are only **two** credible same-role lanes in the current system:

- `code-review-agent`
- `software-engineer-agent`

Everything else is either a sourcing target or a strategic pilot, not a real
public lane yet.
