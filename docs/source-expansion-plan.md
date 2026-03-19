# Source Expansion Plan

## Purpose

Broaden AgentArena's candidate supply without corrupting the benchmark.

We need more agents, but "more sources" does not mean "throw everything
directly into tournaments." Each source type should enter the funnel at the
right stage.

## Core Rule

Do not confuse:

- where we discover candidates
- with what we can benchmark directly

AgentArena should only benchmark:

- runnable or normalizable agent artifacts
- that can be assigned to one role
- under one comparable runner contract

Videos, social posts, and newsletters are useful for discovery, not for direct
benchmark admission.

## Source Tiers

### Tier 1: Benchmark-Ingestable Sources

These are the highest-priority sources because they can yield a real artifact
that may become benchmark-ready after sanitization, normalization, and review.

Examples:

- GitHub
- GitLab
- Smithery or similar registries
- Skills marketplaces with exportable configs
- Hugging Face repos or Spaces when the config is recoverable
- local curated markdown/config bundles
- known repo collections such as `agency-agents`

Expected output:

- `RawAgentArtifact`
- or `RawSkillRecord` convertible into a comparable agent candidate

### Tier 2: Convertible Sources

These often contain a usable agent reference, but usually need extraction or a
follow-up fetch.

Examples:

- framework galleries
- builder project templates
- docs pages with downloadable prompt/config artifacts
- demo sites that expose prompts or configs

Expected output:

- candidate links
- exported configs
- artifact references requiring normalization

### Tier 3: Lead-Generation Sources

These are useful for finding candidates and trends, but should not feed public
tournaments directly.

Examples:

- YouTube
- Reddit
- Hacker News
- X / Twitter
- blogs
- newsletters
- Product Hunt
- "awesome" lists
- agency / directory pages

Expected output:

- candidate mentions
- outbound links to repos, registries, docs, demos
- trend signals and title variants

### Tier 4: Role-Definition Sources

These do not expand the agent pool. They define what the role actually is.

Examples:

- O*NET
- BLS
- ATS-backed company job boards

Expected output:

- role blueprint inputs
- JD corpora
- responsibility / tool / skill trends

## Funnel Design

The correct source-expansion funnel is:

1. Discover broadly
2. Extract real artifact links
3. Resolve the linked artifact
4. Sanitize and dedupe
5. Assign or predict field / role
6. Human review when confidence is weak
7. Normalize into runner contracts
8. Admit only same-role eligible agents into tournaments

Do not skip from lead-gen directly to benchmark-ready.

## Immediate Reality

Current repo state:

- default discovery now includes:
  - GitHub
  - `data/external-agents`
  - `data/code-review-agents`
- Smithery is still a stub
- SkillsMP is still a stub
- there is no active lead-gen queue for YouTube / Reddit / HN / blogs
- GitLab is not implemented

That means discovery is better than "GitHub only," but still too narrow for
the long-term vision.

## Phase Plan

### Phase A: Widen Benchmark-Ingestable Sources

Goal:

- increase the number of real runnable candidates

Tasks:

- keep GitHub in the default adapter stack
- include curated local agent directories in the default stack
- add GitLab adapter
- implement first real registry adapter:
  - Smithery first if practical
  - otherwise another registry with stable public access
- add agency-collection adapter so known curated repos feed the same pipeline

Success metric:

- at least 3 distinct benchmark-ingestable source types in active use

### Phase B: Lead-Generation Queue

Goal:

- discover more candidate agents than we can get from repos alone

Tasks:

- define `CandidateLead` persistence
- add lead ingestion adapters for:
  - YouTube
  - Reddit
  - Hacker News
  - blogs / awesome lists
- store:
  - title
  - source URL
  - outbound links
  - extracted repo / registry links
  - mention count
  - recency

Success metric:

- leads can be reviewed and resolved into real artifact URLs

### Phase C: Link Resolution

Goal:

- turn lead-gen into real benchmark candidates

Tasks:

- extract outbound links from lead records
- classify links into:
  - repo
  - registry page
  - docs page
  - demo page
  - dead / irrelevant
- fetch the best candidate artifact
- feed the resolved artifact back into the normal discovery pipeline

Success metric:

- one lead can result in one reviewable agent candidate without manual copy/paste

### Phase D: Review and Admission Hardening

Goal:

- stop noisy source expansion from polluting public lanes

Tasks:

- add review reason codes for source-origin issues
- distinguish:
  - discovered from benchmark-ingestable source
  - discovered from lead-gen source and resolved
- block unresolved lead-gen items from direct tournament admission
- require review logging for manual promotion decisions

Success metric:

- source expansion increases pool size without increasing lane pollution

## Claude vs Codex Split

### Claude Should Own

- backend adapter implementation
- lead persistence and link resolution
- registry and GitLab adapters
- review-state and admission logic tied to source provenance
- tests for source expansion and resolution

### Codex Should Own

- source-expansion plan and anti-drift documentation
- UI for source provenance, lead review, and lane readiness
- review-console display of discovery source and lead-resolution state
- QA review on whether broader discovery is actually increasing same-role pools

## Guardrails

- never benchmark a YouTube video or Reddit post directly
- never let lead-gen sources bypass review
- keep source provenance visible
- dedupe aggressively across sources
- do not count raw scrape volume as lane readiness
- count benchmark-ready same-role agents, not mentions

## Launch Threshold Reminder

A lane should be public only when it has enough benchmark-ready same-role
agents, not just lots of source mentions.

Suggested thresholds:

- public lane:
  - `>= 8` benchmark-ready agents
  - `>= 4` distinct owners or sources
- pilot lane:
  - `5-7` benchmark-ready agents
- do not market publicly:
  - `< 5` benchmark-ready agents

## Immediate Next Order

1. Keep the widened default discovery stack in place.
2. Add GitLab as the next benchmark-ingestable source.
3. Implement the first real registry adapter.
4. Build `CandidateLead` storage for YouTube / Reddit / HN / blogs.
5. Add a resolver from lead -> artifact -> review queue.

This is the order that broadens supply without turning the benchmark into
garbage.
