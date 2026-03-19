# Sprint Plan

This file turns the design docs into an execution cadence that Codex, Claude,
and Koo can use to track progress without drifting.

## Sprint 0: Lock The Story

Status:
- mostly done

Goal:
- make the product story agent-first, lane-first, and role-based

Done:
- `AgentArena` rebrand across active product surfaces
- agent-vs-agent problem statement written
- lane, role, tournament-type, ablation, and benchmark-integrity specs written
- Codex/Claude split documented in `SYNC.md`

Exit criteria:
- active docs and UI no longer frame the product as skill-first
- `SYNC.md` is treated as the canonical operating note

## Sprint 1: Benchmark Integrity

Status:
- mostly done, keep hardening on real runs

Goal:
- make the leaderboard credible before expanding lanes

Claude owns:
- add `runtime_class`, `task_pack_version`, and `tournament_type` to tournament persistence and APIs
- make only `standardized` tournaments affect public ratings
- add hidden holdouts, anchors, and rotating private task support
- harden judge parsing, retry behavior, and invalid-response handling

Codex owns:
- prepare UI display for lane metadata once API fields exist
- keep public copy clear about what counts as public ranking vs exploratory runs

Exit criteria:
- public leaderboard rows are lane-scoped and tournament-type aware
- judge parse failures no longer silently zero out otherwise valid runs
- hidden holdouts and task freshness policy are implemented, not just documented
- standardized tournaments execute a separate private holdout-validation pass

## Sprint 2: First Credible Lane

Status:
- next shared sprint after integrity basics land

Goal:
- launch one public lane that is actually honest

Target lane:
- `software-engineering/code-review-agent`

Claude owns:
- build a benchmark-ready candidate pool for `code-review-agent`
- fix or rename the current `software-engineer-agent` lane so tasks match the role
- tighten role-fit gating so off-role artifacts do not enter public tournaments

Codex owns:
- surface real tournament results in the primary UI
- make lane identity obvious in the leaderboard and agent detail pages

Exit criteria:
- at least one public lane has enough benchmark-ready candidates to be believable
- task pack matches the lane name
- UI makes same-role comparison obvious

## Sprint 3: Human Review + Role Fit

Status:
- blocked on backend APIs

Goal:
- stop role classification from being heuristic-only

Claude owns:
- persist declared role, predicted role, reviewed role, and confidence bands
- build reviewer decision logging and review queue APIs

Codex owns:
- build the internal review console UI from `docs/human-review-console.md`
- render candidate provenance, sanitized artifact content, and reviewer controls

Exit criteria:
- low-confidence candidates can be reviewed, relabeled, or rejected
- public tournament admission can require human review where needed

## Sprint 4: JD / ATS Corpus

Status:
- backend-heavy

Goal:
- ground lanes in current job-market reality

Claude owns:
- implement ATS adapters for Greenhouse, Lever, and Ashby first
- add weekly refresh
- version the JD corpus used for each lane
- extract common responsibilities and tools by role

Codex owns:
- build the role-definition and market-trend display once APIs exist

Exit criteria:
- each priority lane has a current JD corpus
- role definition is tied to real market data, not only repo labels

## Sprint 5: Semiconductor Pilot

Status:
- later, after review and JD plumbing exist

Goal:
- launch a credible pilot lane around the founder moat

Target lane:
- `semiconductor/verification-debug-agent`

Claude owns:
- build the pilot candidate pool
- expand the task pack with domain-credible tasks

Codex owns:
- present the lane clearly as pilot/private if candidate supply is still thin

Exit criteria:
- semiconductor lane is either public-ready by threshold or explicitly marked pilot

## Sprint 6: Hosted Try-Agent Surface

Status:
- later product sprint

Goal:
- let users try or compare agents safely

Claude owns:
- hosted-run API
- spend caps, rate limits, concurrency limits, and usage ledger enforcement

Codex owns:
- try-an-agent page
- compare-two-agents page
- safe trace display and usage-limit messaging

Exit criteria:
- users can run agents on their own prompts without uncontrolled spend

## Launch Rules

Do not launch a public lane unless:
- it has enough benchmark-ready same-role candidates
- the task pack matches the role
- hidden holdouts and rotation policy are active
- judge reliability is acceptable
- role-fit gating is working

## Claude Brief

Tell Claude to work in this order:

1. Sprint 1: Benchmark Integrity
2. Sprint 2: First Credible Lane
3. Sprint 3: Human Review + Role Fit
4. Sprint 4: JD / ATS Corpus

And to read first:
- `SYNC.md`
- `docs/sprint-plan.md`
- `docs/shared-execution-plan.md`
- `docs/benchmark-integrity.md`
- `docs/role-classification.md`
- `docs/human-review-console.md`

## Codex Brief

Codex should focus on:
- UI and narrative alignment
- displaying lane metadata and real tournament results
- human review console UI after APIs exist
- market/JD display after APIs exist
- hosted sandbox UI after APIs exist
