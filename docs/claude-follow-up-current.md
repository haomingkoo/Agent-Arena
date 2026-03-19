# Claude Follow-Up — Current Backend Priorities

Read these first:

1. `docs/project-steering.md`
2. `docs/source-expansion-plan.md`
3. `SYNC.md`

## Current Truth

- AgentArena benchmarks **agents vs agents** within the **same role**
- Skills / prompts / rules can improve agents, but they are not first-class tournament competitors
- Codex has now tightened the discovery guardrails:
  - GitLab discovery is agent-role oriented
  - registry ingestion rejects generic prompt / skills / rules collections unless they still read like a role-scoped agent
  - discovery registration deduplicates mirrored artifacts by exact sanitized content hash
- Codex also wired the frontend to:
  - real lead intake data on `/sources`
  - duplicate backlog visibility in `/ops`
  - duplicate-risk visibility in `/review`

## What You Should Do Next

### 1. Fuzzy duplicate control

Exact duplicate protection exists now, but near-duplicate/template-copy risk still remains.

Build:
- similarity-based duplicate detection for near-identical agents
- backend persistence for fuzzy duplicate candidates
- API exposure for duplicate similarity and lane context
- review reason codes for duplicate adjudication

Rules:
- do not auto-merge fuzzy matches
- exact same content can dedupe automatically
- similar but non-identical agents should be flagged for human review

### 2. First real SWE lane run

Now that the SWE task pack is real:
- review the `software-engineering/software-engineer-agent` pool for off-role and duplicate pollution
- activate JD backing first via `docs/jd-activation.md`
- run `agentarena jd-refresh --config ... --field software-engineering --role software-engineer-agent`
- verify `jd_postings` and `jd_corpus_versions` are non-empty for the lane
- then run the first same-role SWE tournament
- keep the wording honest if the lane is still provisional

### 3. ATS / JD refresh with real data

Adapters exist, but we still need live corpus data.

Do:
- configure curated ATS sources
- run the first refresh
- persist actual postings and corpus versions
- use `docs/jd-source-curation.md` as the source-selection rulebook
- update `SYNC.md` with which fields/roles now have real JD backing

### 4. Semiconductor lane supply

Still the biggest product gap.

Focus on:
- actual verification/debug agent artifacts
- same-role classification
- no skills/prompt-pack shortcuts

## Hard Rules

- same-role public benchmarking only
- no generic prompt-pack ingestion as tournament candidates
- no silent DB-only promotion when review logging should be used
- no secret printing
- no overclaiming lane credibility
- no “pool growth” that is really duplicate inflation

## What Codex Already Covers

Do not duplicate these frontend slices:
- `/sources` real lead queue UI
- `/ops` duplicate backlog + source-risk visibility
- `/review` duplicate-risk visibility

If backend changes expose new duplicate fields or fuzzy-duplicate APIs, update `SYNC.md` with exactly what Codex should render next.
