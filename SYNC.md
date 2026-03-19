# AgentArena Sync

Last updated: 2026-03-18

This is the shared progress file for Codex, Claude, and Koo.
Use this as the live source of truth for:
- current state
- in-progress work
- safe next steps
- hard constraints

Primary phase tracker:
- `docs/project-steering.md`
- `docs/sprint-plan.md`
- `docs/test-review-checklist.md`

Project-steering rule:
- Read `docs/project-steering.md` before planning or implementing major work.
- If a chat summary or quick task list conflicts with `docs/project-steering.md`, trust the steering doc.

## Brand

Use `AgentArena` in active product copy, docs, API titles, and frontend UI.
Keep legacy command names like `wh-bench` only where backward compatibility matters.

## North Star

AgentArena is an agent-vs-agent tournament platform.

Primary unit:
- `AgentProfile`
- `AgentVersion`

Not the primary unit:
- `Skill`

Skills are only one packaging type for discovered agent artifacts.

## Ground Truth

The agent-native backend is now real:
- agent-native persistence exists
- safe discovery registration exists
- field/role assignment exists
- normalization into `RunnerContract` exists
- benchmark-ready agent selection exists
- versioned task packs exist
- agent-native tournament runner exists
- per-task `RunTrace` persistence exists
- agent-native API endpoints exist
- explicit Qwen provider support exists for execution and judging via DashScope-compatible routing

Operational safety:
- never print, echo, or visibly inspect secret values from `.env` or provider credentials in terminal output
- when checking provider readiness, report only provider availability or boolean presence

## Current Ready Tracks

Observed from local DB:
- `software-engineering/software-engineer-agent`: 5 benchmark-ready agents
- `software-engineering/code-review-agent`: 9 benchmark-ready agents
- `semiconductor/verification-debug-agent`: 0 benchmark-ready agents
- additional off-plan lanes currently exist but are not launch-ready:
  - `semiconductor/semiconductor-agent`: 1 eligible
  - `software-engineering/database-agent`: 1 eligible
  - `software-engineering/devops-agent`: 1 eligible
  - `software-engineering/frontend-agent`: 1 eligible

Registered task packs:
- `software-engineering/software-engineer-agent` `v1`
- `software-engineering/code-review-agent` `v1`
- `semiconductor/verification-debug-agent` `v1`

## Claude Activity

Latest observed from local DB:
- tournament `d023e474-cdff-491c-b10e-9f9ce9a468c2` is `completed` for `software-engineering/code-review-agent`
- lane size at run time: `9` eligible agents
- persisted outcomes for that lane:
  - `9` tournament entries
  - `54` run traces across public benchmark plus internal holdout validation
  - `2` failed traces from judge parse failure
- top current leaderboard for that lane:
  - `comprehensive-reviewer`
  - `Code Reviewer`
  - `Security Engineer`
- tournament `dda5727e-079b-41ec-9241-54421fb3c1a0` completed for `software-engineering/software-engineer-agent`
- task pack in use:
  - `cr-logging-pii`
  - `cr-sql-injection`
  - `cr-auth-bypass`
  - `cr-race-condition`
  - `cr-memory-leak`
- `RunTrace` rows persisted: 25
- tournament entries persisted: 5
- top leaderboard after first run:
  - `Senior Developer`
  - `Reality Checker`
  - `Null Baseline`
  - `Software Architect`
  - `Backend Architect`
- notable credibility gaps:
  - the `software-engineer-agent` lane still uses a code-review-heavy task pack
  - some judge responses were unparseable, producing zeroed task results
  - role classification still looks noisy, for example `Reality Checker` is sourced from a testing artifact but landed in the software-engineer lane

Do not treat the first `code-review-agent` tournament as fully credible until:
- the failed public benchmark trace is rerun or adjudicated
- judge parse robustness improves further
- manual eligibility decisions are review-loggable
- task-pack alignment and role-fit filtering improve across public lanes

Provider-attribution note:
- historical traces written before 2026-03-18 may still show the contract provider instead of the effective execution provider
- current code now persists `result.exec_provider` for new tournament traces
- do not use older pre-fix trace rows alone to infer whether a Qwen override actually applied

Latest code-level backend progress observed:
- Claude has started Sprint 1 backend work in `store/db.py` and `tournament/runner.py`
- tournament persistence now includes:
  - `runtime_class`
  - `task_pack_version`
  - `tournament_type`
- runner behavior now skips Glicko-2 updates for non-`standardized` tournaments

Still incomplete from the same sprint:
- benchmark-ready pools have not moved yet:
  - `semiconductor/verification-debug-agent`: still `0`

Codex Sprint 1 takeover completed:
- lane metadata is now exposed through active agent APIs:
  - `/api/agents/fields`
  - `/api/agents/leaderboard/{field}/{role}`
  - `/api/agents/{version_id}`
  - `/api/traces/{trace_id}`
- agent-native tournament selection now rotates previous-week rotating tasks while keeping anchors stable
- holdout tasks stay excluded from public task-pack selection by default
- targeted Sprint 1 tests now exist for:
  - lane metadata in API payloads
  - tournament metadata persistence
  - non-`standardized` tournaments not updating public ratings
  - task-pack holdout/anchor/exclusion behavior
  - judge parse retry behavior

Current Sprint 1 validation:
- `./.venv/bin/python -m pytest tests/test_taskpacks.py tests/test_agent_tournament.py tests/test_api_agents.py tests/test_core.py -q --tb=short`
- result: `170 passed`

Latest focused validation:
- `./.venv/bin/python -m pytest tests/test_agent_tournament.py tests/test_api_agents.py tests/test_core.py -q --tb=short`
- result: `164 passed`
- `python -m py_compile evaluate/sandbox.py tournament/runner.py tests/test_agent_tournament.py`
- result: success

Latest Codex Sprint 1 hardening:
- fixed a real runner bug where holdout selection referenced `tournament_type` before assignment
- standardized tournaments now run a separate private holdout-validation pass
- holdout runs persist as `RunTrace(trace_kind="holdout")`
- holdout runs add real cost/tokens but do not affect public entries, averages, or ratings
- added targeted tournament coverage proving:
  - standardized tournaments persist holdout traces separately
  - public rankings stay based on public task-pack results only
  - non-standardized tournaments still do not update public ratings
- persisted effective execution provider/model metadata from actual run results instead of trusting only the contract provider
- added targeted coverage proving env-overridden execution provider is what gets stored on new traces

## Ownership Split

This is the current working split so Codex and Claude can move in parallel.

### Codex Owns

- active frontend migration to the agent-native UI
- API-consumer work for the new frontend pages
- API tests for agent-native endpoints
- test review / QA gate for sprint claims
- Sprint 1 cleanup and validation when backend gaps are small and unblocked
- active copy cleanup from `Skill` to `Agent`
- verification of completed tournament outputs and surfacing them in UI
- keeping this file current
- docs and product framing alignment so the repo stays agent-first

### Claude Owns

- backend-heavy tournament and scheduler work
- improving discovery/normalization coverage for new agent tracks
- preparing more benchmark-ready candidates for missing field/role lanes
- semiconductor task-pack expansion
- running real tournaments once candidate pools are ready
- judge parse robustness and tournament credibility fixes
- lane metadata in persistence and APIs
- JD/ATS ingestion and review-console backend plumbing

### Avoid Overlap

Codex should avoid editing unless coordinated:
- `tournament/runner.py`
- `tournament/scheduler.py`
- `ingest/orchestrator.py`
- `agents/normalizer.py`

Claude should avoid editing unless coordinated:
- `frontend/src/App.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/Fields.tsx`
- `frontend/src/pages/FieldRoleLeaderboard.tsx`
- `frontend/src/pages/AgentDetail.tsx`
- `frontend/src/pages/TraceDetail.tsx`
- `frontend/src/components/NavBar.tsx`

## Codex Completed

Backend and pipeline:
- finished agent-native store round-trip support
- added explicit migration for agent-native tables
- added safe artifact registration
- added first markdown-bundle normalizer
- added benchmark-ready selector
- added field/role assignment heuristics
- added agent-native orchestrator path
- added task pack registry and semiconductor starter pack
- persisted agent-native tournament `RunTrace` records
- exposed recent traces on agent detail
- added `/api/traces/{trace_id}`
- added explicit Qwen execution/judge support without hidden fallback or secret logging

Validation:
- agent-native tests are in place and passing
- legacy core suite is still passing

## Codex In Progress

Frontend agent-native UI:
- added `frontend/src/pages/Fields.tsx`
- added `frontend/src/pages/ControlRoom.tsx`
- added `frontend/src/pages/ReviewQueue.tsx`
- added `frontend/src/pages/ReviewCandidate.tsx`
- added `frontend/src/pages/FieldRoleLeaderboard.tsx`
- added `frontend/src/pages/AgentDetail.tsx`
- added `frontend/src/pages/TraceDetail.tsx`
- added `frontend/src/pages/SourceQueue.tsx`
- updated `frontend/src/lib/api.ts` with agent-native types/fetchers
- updated `frontend/src/components/NavBar.tsx` to point to `Fields`
- added `frontend/src/components/ReviewStateBadge.tsx`
- updated `frontend/src/App.tsx` with `/fields`, `/fields/:field/:role`, `/agent/:versionId`, `/traces/:traceId`
- updated `frontend/src/App.tsx` with `/ops` control-room route
- updated `frontend/src/App.tsx` with `/review` and `/review/:versionId`
- updated `frontend/src/App.tsx` with `/jd/:field/:role`
- updated `frontend/src/App.tsx` with `/sources`
- `/` now redirects to `/fields`
- legacy artifact leaderboard remains available at `/leaderboard`
- active UI copy now labels legacy skill-first pages as legacy artifact flows
- `/sources` now uses the real `/api/leads` and `/api/leads/stats` backend instead of a placeholder shell
- `/ops` now shows duplicate backlog visibility from `/api/duplicates`
- `/review` now flags candidates already linked to recorded duplicate groups

Current Claude handoff:
- read `docs/claude-follow-up-current.md`
- lane prioritization is in `docs/next-lanes.md`
- JD activation and the new `agentarena jd-refresh` flow are in `docs/jd-activation.md`
- JD source-selection rules are in `docs/jd-source-curation.md`
- first live SWE JD refresh succeeded: fetched=26, new=20, deduped=6
- SWE lane now has live JD backing in the DB, but the board list still needs ongoing curation
- field/role leaderboard now shows lane maturity honestly:
  - `Public Lane` at 8+ benchmark-ready agents
  - `Pilot Lane` at 5-7 benchmark-ready agents
  - `Emerging Lane` below 5 benchmark-ready agents
- fields landing page now explains the ranking rules up front:
  - same-role only
  - standardized tournaments drive public ratings
  - holdouts stay internal
  - public lanes need enough candidate depth
- fields landing page now has a stronger product hero and a dedicated live-tournaments strip
- fields grid now shows lane maturity per role card using the same thresholds
- fields grid now shows lane metadata badges:
  - `runtime_class`
  - `task_pack_version`
  - `tournament_type`
- fields landing page now also shows latest tournament status per role card when a lane has a recorded run
- role leaderboard now shows lane metadata from the agent API payload
- role leaderboard now also shows the latest tournament record for that lane, including live `running` state when a tournament is in progress
- reusable UI components now exist for lane metadata badges and tournament status chips
- navigation now includes a `Control Room` path for operator-facing lane readiness and credibility review
- navigation now includes a `Review` path for the human review console
- control room now shows:
  - lane readiness counts
  - live run counts
  - lanes needing audit
  - source-risk lane counts
  - per-lane credibility notes using live tournament + candidate-depth data
  - direct links back to lane leaderboards and tournament records
- control room now links directly into the review queue
- control room now links directly into each lane's JD corpus view
- control room now pulls live lane leaderboards to compute source diversity:
  - distinct owners
  - source-family mix
  - host diversity
  - concentration risk
- review console UI now exists on top of the live backend APIs:
  - queue view with filters for review state, field, and role
  - candidate detail page with sanitized artifact, runner contract, and review history
  - live decision form for approve / relabel / reject / send-to-qualification / unsupported
- review queue now links candidates directly to their claimed lane and claimed JD corpus
- review candidate detail now links to:
  - claimed lane leaderboard
  - claimed JD corpus
  - predicted JD corpus when role prediction differs
- new `/sources` page now exists as a lead-queue shell:
  - shows current live source mix from ranked lanes
  - highlights lanes with concentrated source bases
  - keeps an explicit blocked state for future `CandidateLead` backend work
  - links source-discovery work back to lane leaderboard and JD corpus
- agent detail and review candidate pages now show a reusable `Source Provenance` card:
  - discovery source type
  - source location
  - discovered timestamp
  - source commit
  - packaging and owner
  - content hash
- this UI is ready for broader discovery sources like GitLab, registries, and lead-resolved artifacts
- JD corpus page is now wired into the live app:
  - latest corpus version and ATS source-mix display
  - per-lane posting counts, companies, and source counts
  - ATS-backed posting table for role-definition evidence
  - direct navigation between lane leaderboard, review, and role corpus
- tournament detail page now understands agent-native tournaments:
  - routes back to lane leaderboards instead of only legacy category pages
  - links tournament rows to `/agent/{version_id}` for agent-native runs
  - shows lane metadata and standardized/provisional context instead of only legacy skill framing
- agent detail and trace detail now pull live lane leaderboard/tournament context and show a shared `Lane Health` card:
  - candidate depth
  - current lane credibility headline
  - same-role public-rating caveats
  - direct links back to lane leaderboard and control room
- agent detail now has a dedicated `Competition Lane` panel with a direct link back to the role leaderboard
- agent detail now shows lane metadata from the latest tournament context
- trace detail now links back to the role lane and agent detail, and explains that traces should be read in same-role lane context
- trace detail now shows lane metadata badges from the trace API payload
- agent detail now separates public benchmark traces from internal holdout-validation traces
- agent detail recent traces now consume `trace_kind`
- trace detail now shows explicit `Benchmark` vs `Holdout` labeling and explains whether a trace affects public ranking
- navigation now labels the old scanner path as `Artifact Scan`
- About page now spells out the public-rating policy versus internal holdout validation
- legacy tournament page now explicitly says it is the old category/skill-style flow and points users to `Fields`
- frontend validation passed:
  - `npm run build`
  - `npm run lint`

API and integration coverage:
- added tests for `/api/agents/fields`
- added tests for `/api/agents/leaderboard/{field}/{role}`
- added tests for `/api/agents/{version_id}`
- added tests for `/api/traces/{trace_id}`
- added deprecation-header checks for legacy `/api/skill/*`
- focused backend and integration validation passed

Discovery breadth hardening:
- widened the default discovery stack so it no longer relies on GitHub alone
- `ingest/orchestrator.py` now uses `default_source_adapters()`
- `ingest/sources.py` now includes `LocalMarkdownDirectoryAdapter`
- curated local pools now flow through default discovery when present:
  - `data/external-agents`
  - `data/code-review-agents`
- targeted validation passed:
  - `tests/test_agent_orchestrator.py`
  - `python -m py_compile ingest/sources.py ingest/orchestrator.py tests/test_agent_orchestrator.py`

Still to finish in the broader frontend migration:
- clean remaining active user-facing `Skill` copy where it clashes with the new agent-native path
- connect the default navigation and homepage strategy more tightly to the agent-native flow
- add frontend tests for the new pages

Current Codex next moves:
1. keep verifying Claude's running tournament outputs and surface them in UI once entries finalize
2. continue copy cleanup in remaining active user-facing legacy pages where helpful
3. polish the JD/review/operator surfaces now that the backend APIs are real
4. avoid creating a new frontend test harness until there is an agreed test stack

## Claude Sprint 1 Completed (Benchmark Integrity)

Changes made:
- Added `field`, `role`, `runtime_class`, `task_pack_version`, `tournament_type` to tournaments table (migration + schema)
- Updated `create_tournament()` to accept and persist lane metadata
- Updated `update_tournament()` valid columns to include lane metadata
- **Only standardized tournaments update Glicko-2 ratings** — native/qualification/ablation tournaments persist entries but skip rating updates
- Added `TournamentConfig.tournament_type` and `task_pack_version` fields
- Added `BenchmarkJob.task_bucket` (anchor | rotating | holdout) and `difficulty` (easy | medium | hard | adversarial)
- `select_task_pack_jobs()` now excludes holdout tasks from public packs, always includes anchors
- Added `select_holdout_jobs()` for internal validation
- Codex completed the missing internal holdout execution path in `tournament/runner.py`
- Judge retry on parse failure (already done previous session)
- Judge + execution API fatal error detection — halts tournament on billing/auth/quota errors instead of silently continuing
- Explicit Qwen error messages on failure
- focused Sprint 1 gate: `170 passed`

What Codex should display next:
- Tournament API responses now include `field`, `role`, `runtime_class`, `task_pack_version`, `tournament_type`
- Leaderboard and tournament detail pages should show tournament_type badge (standardized vs native vs qualification)
- Tournament detail should show task_pack_version
- Only show "Public Rating" label for standardized tournament results

Resolved:
- `code-review-agent` lane now has 9 benchmark-ready agents and one completed tournament
- Tournament data now includes full lane metadata (field, role, runtime_class, task_pack_version, tournament_type)

## Claude Sprint 2 Progress (First Public Lane Candidate)

Done:
- Tagged code-review tasks with bucket (anchor/rotating/holdout) and difficulty metadata
- `select_task_pack_jobs()` now excludes holdouts, always includes anchors
- Added `select_holdout_jobs()` for internal validation
- Created `data/code-review-agents/` with 5 distinct review archetypes (security, performance, comprehensive, minimal, test-coverage)
- Discovered and registered 10 additional code-review agents from GitHub
- Fixed executor to respect `EXEC_MODEL_PROVIDER` env var override
- Cleaned code-review lane: marked 8 irrelevant agents ineligible (interview, gate, ide, go-development-expert, tutorial content, example template)
- Reset corrupted Glicko-2 ratings from network-failure tournament
- Promoted Security Engineer from pending to eligible
- **Successfully ran first provisional code-review-agent tournament (2026-03-18)**
  - 9 benchmark-ready agents competed
  - Claimed execution/judge mix: Qwen exec + Gemini judge, cost: $0.07
  - No network/provider outage during the run
  - Holdout validation ran for all 9 agents
  - Glicko-2 ratings persisted (standardized tournament)

First provisional tournament results (tournament d023e474):
| Rank | Agent | Score | Pass | Rating |
|------|-------|-------|------|--------|
| 1 | comprehensive-reviewer | 0.972 | 80% | 1856.4 |
| 2 | Code Reviewer | 0.970 | 80% | 1856.4 |
| 3 | Security Engineer | 0.926 | 100% | 1652.7 |
| 4 | security-focused-reviewer | 0.908 | 40% | 1652.7 |
| 5 | minimal-reviewer | 0.858 | 0% | 1500.0 |
| 6 | review-pr | 0.825 | 20% | 1398.2 |
| 7 | test-coverage-reviewer | 0.754 | 0% | 1296.3 |
| 8 | code-review | 0.729 | 40% | 1143.6 |
| 9 | performance-reviewer | 0.729 | 40% | 1143.6 |

Observations:
- comprehensive-reviewer and Code Reviewer nearly tied at top
- Security Engineer has highest pass rate (100%) despite lower score
- Pass rate threshold may be too strict — agents scoring 0.85+ still fail
- 2 failed traces still matter:
  - public benchmark trace: Security Engineer on async-pitfall
  - holdout trace: Code Reviewer on logging-pii
  - treat the lane as promising, not fully clean, until rerun/adjudication

Unblocked (2026-03-18):
- Anthropic API: working
- Qwen API: working
- Gemini API: working
- GitHub token: present (not yet re-tested for discovery)

Current Claude next moves:
1. Run tournaments with v2 JD-backed tasks (both lanes have generated tasks ready)
2. Build semiconductor agent pool
3. Scale agent discovery to increase source diversity
4. Build winner analysis / coaching pipeline (study what top agents do differently)

## Claude Sprint 6 Completed (JD→Tasks Pipeline + O*NET Lane Seeding)

Done (2026-03-19):

### 1. JD → Task Generation Pipeline (`ingest/jd/extract.py`)
- LLM-powered extraction: reads real JD postings, uses Gemini to extract structured role blueprints
- Extracts: responsibilities, tools, deliverables, failure modes, seniority levels
- Generates tournament tasks with real code scenarios at different difficulty/seniority:
  - easy (junior, 0-2 yrs): single-concept, clear requirements
  - medium (mid, 3-5 yrs): multi-step, tradeoff reasoning
  - hard (senior, 6-8 yrs): system-level, architecture judgment
  - adversarial (staff, 9+ yrs): ambiguous requirements, conflicting constraints
- Each generated task includes actual code context (1000-8000 chars), specific acceptance criteria (5-7 per task), and stack metadata
- Saved to `data/jd_generated_tasks_{role}.json` for inspection and versioning

Generated tasks:
- **code-review-agent v2**: 10 tasks from 20 JD postings / 9 companies (security reviews, SSRF, path traversal, threat modeling, CI/CD pipeline review)
- **software-engineer-agent v2**: 10 tasks from 25 JD postings / 10 companies (API implementation, concurrency bugs, performance optimization, data pipelines, a11y)
- Tasks are role-specific: CR tasks test security review skills, SWE tasks test implementation and debugging skills

### 2. v2 Task Packs Wired Into Tournament System
- `benchmark/jd_taskpacks.py`: loader that converts generated JSON into BenchmarkJob objects
- `benchmark/taskpacks.py`: v2 (JD-generated) is now the default for new tournaments, v1 (hand-authored) kept for comparison
- `get_task_pack()` defaults to v2, falls back to v1 if v2 not available
- `TournamentConfig.task_pack_version` defaults to "v2"
- Runner validates `requires_jd_corpus` flag — v2 packs require live JD data before running standardized tournaments

### 3. O*NET / BLS Lane Seeding (`ingest/onet.py`)
- 11 occupation seeds mapped from official O*NET SOC codes to AgentArena lanes
- Each seed includes: BLS median salary, growth rate, employment count, priority tier, JD/agent search terms
- Priority tiers:
  - **Immediate** (3): Software Developers ($132K, 17% growth), Info Security ($120K, 33% growth), Electronics Engineers ($116K, semiconductor)
  - **Next** (4): QA ($102K, 20% growth), Frontend ($81K), Data Science ($108K, 36% growth), Hardware ($138K)
  - **Future** (4): DBA, SysAdmin, Network Architect, Systems Analyst
- Saved to `data/lane_seeds.json` for driving discovery and JD sourcing per lane

### 4. Code-Review JD Source Config
- Created `data/jd_sources.code-review.json` with 11 boards across 3 ATSes
- Companies: GitLab, Cloudflare, Elastic, MongoDB, Twilio, Airtable, Coinbase (Greenhouse), Palantir (Lever), 1Password, Semgrep, Render (Ashby)
- Ran first refresh: 20 postings from 9 companies now in corpus
- Roles include: Application Security Engineer, Product Security Engineer, Security Research Manager

### Test Coverage: 267 passed (up from 265)

### The Correct Pipeline Order (Now Implemented)
1. **O*NET/BLS** → seed which lanes to build (occupation taxonomy + salary/growth priority)
2. **ATS/JD postings** → ingest real job descriptions for each lane
3. **JD → blueprint → tasks** → LLM extracts responsibilities, generates work-sample tasks with code scenarios
4. **Agent discovery** → find agents from GitHub, GitLab, registries, leads
5. **Dedup + review** → remove duplicates, review role fit
6. **Tournament** → run with JD-backed tasks, same-role only
7. **Study winners** → analyze top performer traces (NOT BUILT YET)
8. **Coach builders** → apply learnings to help build better agents (NOT BUILT YET)

### What Codex Should Surface Next
- v2 task pack metadata on tournament detail (blueprint source, corpus version, seniority distribution)
- Task transparency: show what questions were asked and what agents answered on leaderboard/trace pages
- O*NET lane roadmap on the Control Room (which lanes are immediate/next/future)
- Lane maturity indicator: hand-authored (v1) vs JD-backed (v2) task packs

### Still To Build
- Winner analysis pipeline (compare top vs bottom traces to extract what works)
- Coaching module connected to real tournament data
- More agent discovery to increase source diversity (agency-agents still dominates)
- Semiconductor agent pool (0 agents, task pack exists)

## Claude Sprint 5 Completed (Dedup + SWE Tournament + JD Corpus)

Done (2026-03-18):

### 1. Fuzzy Duplicate Control
- Added `duplicate_groups` table for recording duplicate relationships (canonical, duplicate, similarity_score, match_type, review_state)
- DB functions: `find_exact_duplicates()`, `find_name_duplicates()`, `record_duplicate()`, `scan_and_record_duplicates()`, `list_duplicate_groups()`
- API: `GET /api/duplicates` (list with review_state filter), `POST /api/duplicates/scan` (trigger scan)
- Initial scan found 5 same-name duplicates (local copies mirroring agency-agents originals)
- All 5 retired through the review system with audit trail — not ad hoc DB edits
- Off-role agents also removed via review: Null Baseline and Reality Checker from SWE lane

### 2. First Real SWE Agent Tournament
- Pool after cleanup: 15 agents (deduped, off-role removed)
- Tournament ID: `f4834a5f-087d-4abf-82d6-24f1070fae59`
- 0 errors, $0.08 cost
- Top: Technical Writer (0.946), Rapid Prototyper (0.942), AI Engineer (0.934)
- Bottom: Git Workflow Master (0.212), Embedded Firmware Engineer (0.162) — declined out-of-scope tasks
- Baseline avg: 0.889

### 3. JD Corpus — Both Lanes Now Backed
- SWE corpus: 25 postings, 10 companies, 3 ATS sources (Codex did the first refresh)
- CR corpus: 20 postings, 9 companies, 3 ATS sources (Claude did this refresh)
- CR source config: `data/jd_sources.code-review.json` — 11 boards across Greenhouse (GitLab, Cloudflare, Elastic, MongoDB, Twilio, Airtable, Coinbase), Lever (Palantir), Ashby (1Password, Semgrep, Render)
- CR JD roles include: Application Security Engineer, Product Security Engineer, Security Research Manager, Software Engineer Security, Threat Intelligence
- Total JD corpus: 45 postings across 19 companies

### Provisional Status
- Both lanes have 1-2 tournaments — Glicko-2 RD still high
- Semiconductor: still 0 agents
- Source diversity weak: agency-agents dominates both pools

### Duplicate Risks
- agency-agents is ~60-85% of both pools
- Only exact-hash and same-name detection exists — no embedding similarity yet
- Template copies with minor edits would pass current detection

### Test Coverage: 265 passed (10 new duplicate tests)

### What Codex Should Surface Next
- Duplicate backlog on `/ops`
- SWE tournament results on the leaderboard
- JD corpus data in lane/Control Room views
- Source diversity metrics per lane

## Claude Sprint 4 Completed (Source Expansion)

Done (2026-03-18):

### Source Expansion Overview

Discovery was too narrow (GitHub-only + hand-curated). Now broadened to a tiered model:
- **Tier 1 (benchmark-ingestable)**: GitHub, GitLab, registries, curated collections
- **Tier 2 (convertible)**: framework galleries, docs with configs
- **Tier 3 (lead-gen)**: YouTube, Reddit, HN, blogs, awesome-lists → CandidateLead records only
- **Tier 4 (role-definition)**: O*NET, BLS, ATS job boards (already built in Sprint 3)

### 1. GitLab Adapter (`ingest/gitlab.py`)
- Search public GitLab projects by agent-role queries (`code review agent`, `software engineer agent`, `verification agent`, `AGENTS.md`, `CLAUDE.md`)
- Scan project trees for SKILL.md, AGENTS.md, and agent-related markdown files
- Fetch file content via GitLab REST API v4 (public, no auth for public repos)
- Produces `GitLabDiscovery` records for the normalization pipeline

### 2. Registry Adapters (`ingest/registry.py`)
- **SmitheryAdapter**: searches Smithery registry API for MCP servers/agent tools
- **AwesomeListAdapter**: parses GitHub awesome-list READMEs and extracts repo/registry links
- Both now filter toward role-like agents and reject generic prompt / skills / rules collections

### 3. CandidateLead Persistence
- Added `candidate_leads` table with: source_type, source_url, title, outbound_links, extracted_artifact_links, mention_count, signal_strength, review_state, resolution_state, resolved_artifact_url, content_hash
- Dedup by (source_type, content_hash) — repeat mentions increment mention_count
- DB functions: `upsert_candidate_lead()`, `list_candidate_leads()`, `resolve_candidate_lead()`, `get_lead_stats()`
- API endpoints: `GET /api/leads`, `GET /api/leads/stats`

### 4. Lead-Gen Adapters (`ingest/leads.py`)
- **YouTube**: searches via Data API v3 (requires YOUTUBE_API_KEY), extracts GitHub/GitLab links from video descriptions
- **Reddit**: searches subreddits (ClaudeAI, ChatGPT, LocalLLaMA, programming, etc.) via public JSON API, extracts repo links from posts
- **Hacker News**: searches via public Algolia API, extracts story URLs and classifies repo links
- **Awesome-lists**: parses markdown link lists and extracts GitHub/GitLab references
- All adapters produce CandidateLead-shaped dicts — NOT benchmark-ready agents

### Source Guardrail Reminder
- Skills, prompts, rules, and GPT collections can help us discover ideas, but they are not first-class tournament competitors
- Keep public benchmarking focused on same-role agents, not generic prompt packs
- If a source mostly yields prompts/rules/skills, treat it as lead-gen or builder inspiration unless it resolves into a real agent artifact
- GitLab and registry filters now reject generic prompt / skills / rules collections unless they still read like a role-scoped agent
- Discovery registration now deduplicates mirrored artifacts by sanitized content hash so the same agent does not enter as multiple competitors just because it appears in multiple sources

### 5. Lead → Artifact Resolution (`ingest/resolver.py`)
- Link classifier: categorizes URLs as repo, registry, docs, demo, dead, irrelevant
- Repo checker: uses `gh api` to scan GitHub repos for SKILL.md/AGENTS.md files
- Resolution pipeline: processes unresolved leads, checks best artifact links, marks leads as resolved/no-artifact/dead-link
- Resolved leads get an `resolved_artifact_url` that can enter the review + normalization pipeline
- Unresolved leads stay in queue, never enter tournaments

### 6. Agency-Agents Ingestion (`ingest/agency_agents.py`)
- Ingested 24 agents from msitarzewski/agency-agents (52K stars)
- Mapped to our taxonomy: 9 → code-review-agent, 15 → software-engineer-agent
- Current pool sizes: code-review 18 agents, SWE 20 agents

### 7. Gemini Judge Fix
- Bumped `max_output_tokens` from 4096 to 16384 to account for Gemini 2.5 Flash internal thinking tokens
- W13 tournament ran with **0 errors** (was 2 errors in W12)

### Test Coverage
- 19 new tests in `tests/test_source_expansion.py`
- Full suite: **220 passed** (up from 201)

### What Is Now Active
- GitHub: active (widened discovery)
- GitLab: adapter built, ready for first run
- Smithery: adapter built, ready for first run
- Awesome-lists: adapter built, ready for first run
- Lead-gen (YouTube, Reddit, HN): adapters built, ready for first run
- Lead resolution: pipeline built, ready for first run
- Agency-agents collection: ingested (24 agents)

### What Is Still Stubbed
- YouTube requires YOUTUBE_API_KEY env var
- No leads have been ingested yet — adapters ready but not run
- No GitLab discovery run yet
- No Smithery discovery run yet
- Lead → artifact → normalization → registration is end-to-end ready but untested on real leads

### How Leads Are Stored
- `candidate_leads` table with review_state (new/reviewing/resolved/dismissed) and resolution_state (unresolved/resolved/no-artifact/dead-link)
- Leads are NOT benchmark-ready — they must be resolved into artifact URLs first
- Resolved leads point to repos/registries that can be ingested through the normal pipeline

### How Leads Resolve Into Artifacts
1. Lead has `extracted_artifact_links` (GitHub/GitLab URLs found during ingestion)
2. `resolver.py` classifies each link (repo/registry/docs/demo/irrelevant)
3. For repo links: checks the repo for SKILL.md/AGENTS.md files
4. If found: marks lead as resolved with artifact URL
5. Resolved artifact URL enters the existing discovery → normalization → review → tournament pipeline
6. If no agent files found: marks lead as no-artifact

### What Codex Should Surface Next
- Lead pipeline stats on the Control Room page (unresolved/resolved/no-artifact counts)
- Source provenance badges on agent detail (where was this agent discovered?)
- Lead review queue (separate from the agent review queue)
- Resolution state on lead detail

## Claude Sprint 3 Completed (Review + JD + SWE Tasks + Judge Robustness)

Done (2026-03-18):

### 1. Human Review Backend (Phase 3)
- Added `ReviewState` enum to `agents/contracts.py` (pending-review, qualification-required, approved-public, approved-private-only, relabelled, rejected, unsupported)
- Added `ReviewDecision` model to `store/models.py` for immutable audit records
- Added `review_decisions` table with full audit trail (reviewer, timestamps, previous/new state, reason, note)
- Added review fields to `agent_versions` table via migration: `review_state`, `predicted_field`, `predicted_role`, `jd_fit_score`, `qualification_fit_score`, `work_sample_fit_score`, `manual_review_required`, `reviewed_by`, `reviewed_at`
- Added DB functions: `list_review_queue()`, `get_review_candidate_detail()`, `apply_review_decision()`, `get_review_history()`
- `apply_review_decision()` handles approve (sets eligible), reject (sets ineligible), relabel (updates profile field/role), send-to-qualification
- Relabel updates the `agent_profiles` table so the agent moves lanes
- Every decision is persisted as an immutable `review_decisions` row with previous state
- Added API endpoints:
  - `GET /api/review/queue` — filterable by review_state, field, role
  - `GET /api/review/candidate/{version_id}` — full detail with sanitized content + review history
  - `POST /api/review/candidate/{version_id}/decide` — approve, relabel, reject, send-to-qualification, unsupported
  - `GET /api/review/candidate/{version_id}/history` — audit trail

### 2. ATS / JD Ingestion (Phase 4)
- Added `jd_postings` table with full schema: source_ats, company_name, company_size_bucket, title, content, content_hash, responsibilities/tools/skills JSON, corpus_version, dedup unique constraint
- Added `jd_corpus_versions` table for versioned snapshots per field/role
- Added DB functions: `upsert_jd_posting()`, `list_jd_postings()`, `create_corpus_version()`, `get_latest_corpus_version()`, `get_jd_corpus_stats()`
- Created `ingest/jd/` adapter framework:
  - `base.py` — `ATSAdapter` base class + `RawPosting` dataclass
  - `greenhouse.py` — Greenhouse Job Board API adapter (public, no auth)
  - `lever.py` — Lever Postings API adapter (public, no auth)
  - `ashby.py` — Ashby Job Postings API adapter (public, no auth)
  - `refresh.py` — orchestrator: fetches from configured sources, deduplicates, persists, creates corpus version snapshots
- Added API endpoints:
  - `GET /api/jd/postings` — filterable by field, role, source_ats
  - `GET /api/jd/corpus/{field}/{role}` — latest corpus version + stats

### 3. Software Engineer Agent Lane Fix (Phase 2)
- Created `tournament/swe_tasks.py` with 7 real SWE benchmark tasks aligned to BLS/JD role matrix:
  - `swe-implement-pagination` (anchor, medium) — implement from spec
  - `swe-fix-race-condition` (anchor, hard) — fix concurrent bug
  - `swe-add-tests` (rotating, medium) — write pytest tests
  - `swe-debug-prod-issue` (rotating, hard) — analyze production failure chain
  - `swe-design-tradeoff` (rotating, medium) — evaluate caching strategy
  - `swe-refactor-extract` (rotating, easy) — refactor duplicated code
  - `swe-fix-test-flake` (holdout, medium) — fix timing-dependent test
- Updated `benchmark/taskpacks.py` to use real SWE tasks instead of reusing code-review tasks
- Task pack has proper bucket distribution: 2 anchors, 4 rotating, 1 holdout

### 4. Judge Robustness
- Added `repair_truncated_json()` to `evaluate/rubric.py` — closes unclosed braces/brackets from truncated judge output
- Updated `evaluate/sandbox.py` judge parsing: tries repair before retry, tries repair on retry too
- Verified: both failed traces from the code-review tournament (f69c6414, 5295ca44) now parse successfully with the repair function
- Root cause was Gemini truncating output at token limit — repair recovers partial scores

### Test Coverage
- 30 new tests in `tests/test_review.py` covering:
  - Review queue filtering and metadata
  - Candidate detail with review history
  - Approve/reject/relabel/send-to-qualification decisions
  - Audit trail immutability
  - Rejected candidates excluded from benchmark-ready pool
  - JD posting CRUD and deduplication
  - Corpus version creation and stats
  - SWE task pack validation (no code-review tasks, proper metadata)
  - Review and JD API endpoints
- Full suite: **201 passed** (up from 171)

### What Is Now Unblocked
- Codex can build the review console UI using the new review APIs
- Codex can display JD corpus data when postings are ingested
- SWE agent lane is ready for a real tournament with aligned tasks
- Future judge parse failures will recover partial scores instead of zeroing

### What Is Still Provisional
- The code-review-agent tournament is still provisional until the 2 failed traces are rerun in a new tournament
- SWE agent lane has tasks but no tournament has been run yet with the new pack
- JD postings have not been ingested yet — adapters are built but no sources configured
- Review console has APIs but no frontend UI yet
- Semiconductor lane still has 0 benchmark-ready agents

## Execution Board

This is the current implementation order. Specs are written; the work below is
what remains to ship the product honestly.

### Phase 1: Benchmark Integrity

Status:
- spec done
- implementation incomplete

Tasks:
- add hidden holdouts, anchor tasks, and rotating private task support
- persist `task_pack_version`, `runtime_class`, and `tournament_type`
- make only `standardized` tournaments affect public ratings
- improve judge parse reliability and retry behavior

Owner:
- Claude

### Phase 2: Lane Credibility

Status:
- spec done
- code-review-agent: first credible tournament complete, 9 agents
- software-engineer-agent: task pack replaced with real SWE tasks, needs first tournament
- semiconductor/verification-debug-agent: still 0 benchmark-ready agents

Remaining:
- build semiconductor candidate pool
- run SWE agent tournament with new task pack
- run more code-review tournaments for Glicko-2 stability

Owner:
- Claude

### Phase 3: Human Review + Role Fit

Status:
- spec done
- **backend complete** — persistence, decisions, audit trail, APIs all implemented
- frontend not started

Done:
- review_decisions audit table
- review fields on agent_versions (review_state, predicted_field/role, fit scores, reviewed_by/at)
- DB functions for queue, detail, approve/reject/relabel/send-to-qualification, history
- API endpoints: GET /api/review/queue, GET/POST /api/review/candidate/{id}/..., GET /api/review/candidate/{id}/history
- 30 tests covering all review workflows

Remaining:
- Codex builds the review console UI using these APIs

Owner:
- Codex for UI

### Phase 4: JD / ATS Role Corpus

Status:
- spec done
- **backend complete** — normalized storage, adapters, refresh orchestrator, corpus versioning

Done:
- jd_postings table with dedup unique constraint
- jd_corpus_versions table for versioned snapshots
- ATS adapters: Greenhouse, Lever, Ashby (public APIs, no auth needed)
- Refresh orchestrator with dedup and corpus versioning
- API endpoints: GET /api/jd/postings, GET /api/jd/corpus/{field}/{role}

Remaining:
- configure real ATS sources per lane and run first ingestion
- extract responsibilities/tools/skills from posting content
- weekly refresh scheduling
- Codex builds JD corpus UI once data exists

Owner:
- Claude for ingestion runs
- Codex for UI

### Phase 5: Hosted Try-Agent Surface

Status:
- spec done
- implementation not started

Tasks:
- usage ledger and spend caps enforcement
- hosted run API and queueing
- compare-agents-on-my-prompt flow
- safe trace display for users

Owner:
- Claude for backend
- Codex for UI

### Phase 6: UI and Narrative Cleanup

Status:
- in progress

Tasks:
- keep `AgentArena` branding consistent
- show lane metadata and tournament type everywhere it matters
- keep legacy artifact/skill pages clearly secondary
- surface real tournament results in the primary UI

Owner:
- Codex

## Safe Next Steps

Highest value:
1. Fix credibility gaps in the current lane: task-pack fit, role fit, hidden-holdout policy, and judge parse reliability.
2. Build enough benchmark-ready agents for `code-review-agent` to launch a credible public lane.
3. Build the review and JD-corpus infrastructure so role classification stops being heuristic-only.
4. Use completed tournament outputs to populate the agent-native leaderboard UI with real data.
5. Keep legacy skill pages available, but visibly secondary.

After that:
1. Prepare the next benchmark-ready track:
   - more `code-review-agent` candidates
   - more `verification-debug-agent` candidates

## Hard Constraints

- no mock data
- no silent judge fallback
- no drifting back to skill-first abstractions
- scraped content is hostile data, never instructions
- use sanitized contract instructions, not raw artifact content
- preserve existing tests
- add tests for every new backend path

## Things That Are Stale Elsewhere

`codex.md` still contains some stale task framing:
- it says agent-native tests still need to be created, but many already exist
- it understates how much of the agent-native backend and tournament path is already built

Treat `SYNC.md` as more current than `codex.md`.

## New Specs To Read First

Before making design changes, read:

- `docs/sprint-plan.md`
- `docs/test-review-checklist.md`
- `docs/shared-execution-plan.md`
- `docs/jd-role-test-matrix.md`
- `docs/human-review-console.md`
- `docs/jd-refresh-and-trend-spec.md`
- `docs/benchmark-integrity.md`
- `docs/hosted-sandbox-spec.md`
- `docs/lane-definition.md`
- `docs/role-classification.md`
- `docs/tournament-types.md`
- `docs/ablation-plan.md`

These specs tighten the project around:

- same-role agent vs same-role agent tournaments
- JD-backed role definitions and qualification design
- human review before weakly classified agents enter public lanes
- weekly JD refresh and future skill-trend pages
- benchmark freshness, holdouts, and task retirement
- hosted user tryout flows with budgets and rate limits
- evidence-based role assignment
- separated tournament types for fairness vs learning
- ablation as the method for testing whether a skill or tool actually mattered

## Test Review Rule

Codex is the second pair of eyes for sprint QA.

Do not mark a sprint done only because:
- some existing tests passed
- partial code landed
- one layer was updated but APIs or UI were not

Use `docs/test-review-checklist.md` as the review gate before calling a sprint complete.

## Shared Build Plan

The immediate platform plan is:

1. Lane-first benchmarking
   - every tournament must belong to one explicit lane
   - no mixed-role or mixed-runtime ranking tables
2. Role-fit before ranking
   - discovery must not rely on self-labels alone
   - low-confidence candidates must qualify before entering public tournaments
3. Split tournament types
   - standardized tournaments for public ratings
   - native tournaments for discovery
   - ablations for causal learning
4. Learn from winners
   - promote only evidence-backed insights
   - do not claim a skill mattered until ablation or controlled comparison supports it

## Source Expansion Rule

Discovery breadth was too narrow. The active rule from here is:

- benchmark-ingestable sources first
- lead-gen sources second
- role-definition sources separately

Do not confuse:
- source discovery breadth
- with direct benchmark eligibility

Use `docs/source-expansion-plan.md` as the execution guide.

Current truth:
- default discovery is no longer GitHub-only
- default discovery now includes:
  - GitHub
  - `data/external-agents`
  - `data/code-review-agents`
- Smithery is still a stub
- SkillsMP is still a stub
- no active lead queue exists yet for YouTube / Reddit / HN / blogs

Hard rule:
- YouTube, Reddit, HN, blogs, and directories are lead-gen sources
- they should produce candidate links, not direct tournament entries

Next backend order for source expansion:
1. Add GitLab adapter
2. Add first real registry adapter
3. Build `CandidateLead` persistence for lead-gen sources
4. Build lead -> artifact link resolution
5. Route resolved artifacts into review + normalization

## Concrete Split From Here

### Codex Next

- build review console UI using the new review APIs (queue, detail, approve/reject/relabel)
- display JD corpus data once ingestion runs
- surface lane metadata and tournament type in the frontend
- verify completed tournament outputs and make sure they display correctly
- keep docs and active copy aligned with the specs above

### Claude Next

- run SWE agent tournament with the new real task pack
- run more code-review tournaments for Glicko-2 stability
- configure real ATS sources and run first JD ingestion
- build semiconductor verification-debug-agent candidate pool
- add weekly refresh scheduling for JD corpus
- add qualification prompts for lane admission
- implement `docs/source-expansion-plan.md` in this order:
  - GitLab adapter
  - first real registry adapter
  - `CandidateLead` persistence
  - lead-gen source adapters for YouTube / Reddit / HN / blogs
  - lead -> artifact resolution into review queue

### Future Shared Work

- build the human review console
- build skill-trend and role-trend views from weekly JD refreshes
- build hosted sandbox and compare-agent flows
- surface discovery-source provenance and lead-resolution state in the UI
