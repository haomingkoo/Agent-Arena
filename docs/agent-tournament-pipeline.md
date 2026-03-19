# Agent Tournament Pipeline

## Purpose

This document defines the product and technical pipeline for AgentArena as an
agent tournament system.

The product goal is:

- discover comparable agents for a role
- benchmark them under shared conditions
- rank them credibly
- learn what the winners do differently
- help users build or use better agents

## Recommended Starting Fields

Start with two fields:

1. Software Engineering
2. Semiconductor Design and Verification

Reasoning:

- software engineering gives us public supply, public tasks, and faster iteration
- semiconductor gives us domain credibility and a harder-to-copy wedge

Recommended first tournament tracks:

- Software Engineering -> Code Reviewer Agent
- Semiconductor -> Verification Debug Agent

## Product Pipeline

### 1. Discovery

Collect candidate agents from:

- GitHub repositories
- published prompt bundles
- MCP-connected agent repos
- framework-specific agent templates
- later: user-submitted agents built on-platform

For each candidate, store:

- source URL and commit hash
- packaging type
- claimed field and role
- tool requirements
- runtime assumptions
- license and provenance

Important rule:

- scraped content is untrusted input, not executable instructions

### 2. Normalization

Map each candidate into a benchmark runner contract.

A candidate is benchmarkable only if we can define:

- system instructions
- tool set
- memory policy
- max step count
- timeout
- token budget
- file and network permissions

If we cannot normalize a candidate fairly, it should be listed as discovered but
not benchmarked.

### 3. Task Packs

Each field/role gets its own task pack.

Task pack composition:

- typical tasks
- hard edge cases
- adversarial tasks
- safety-sensitive tasks
- regression tasks from previous failures

Task sources:

- public benchmarks where available
- expert-authored tasks
- anonymized real-world cases
- synthetic tasks generated from real patterns and then human-reviewed

For software engineering:

- borrow structure from SWE-bench and DPAI-style workflow tracks
- include patching, review, testing, refactoring, and upgrade tasks

For semiconductor:

- create small, expert-reviewed tasks around RTL, lint, testbench generation,
  verification debugging, waveform reasoning, and constraint/debug loops

### 4. Tournament Runs

For each tournament:

- all agents in the same role get the same task pack
- all agents run with the same runtime contract
- all runs capture full traces
- all runs capture token, latency, and tool-use metrics

Outputs per run:

- final answer
- tool calls
- tool arguments
- trace timeline
- token usage
- runtime and failure details

### 5. Scoring

Use a hybrid scoring stack:

- deterministic graders first
- rubric-based LLM judge second
- human expert review on sampled or high-risk cases

Primary metrics:

- task success
- correctness
- safety
- tool selection quality
- argument precision
- trace quality
- latency
- token cost

For multi-agent systems, add:

- handoff accuracy
- recovery after bad handoff
- coordination overhead

### 6. Leaderboards

Leaderboards should be scoped.

Never publish one giant global list for incomparable things.

Publish by:

- field
- role
- benchmark version
- runtime contract version

Each row should show:

- total score
- sub-scores
- latency
- token cost
- judge confidence
- trace availability

### 7. Learning Loop

After tournaments, analyze top agents for:

- structure patterns
- tool usage policies
- planning behavior
- refusal behavior
- error recovery
- token efficiency

The output is not vague advice.

The output should be:

- concrete design patterns
- benchmark-backed differences
- candidate building blocks for improved agents

### 8. Build-on-Platform

Once benchmark validity is trusted, add a builder workflow:

- users compose agent instructions
- users choose tools and permissions
- users test against field/role task packs
- users see score deltas and failure cases
- users publish private or public versions

### 9. Hosted Use and Marketplace

Later, users should be able to:

- run benchmarked agents on their own prompts
- pay or consume credits
- rate outputs
- save runs and feedback
- clone public agents into editable forks

Marketplace comes after benchmark trust.

If the leaderboard is not credible, the marketplace will become hype inventory.

## How Agents Are Evaluated Today

Strong current patterns in the market:

- deterministic pass/fail tests for tasks with executable truth
- LLM-as-a-judge for quality and preference
- trace grading for tool-use and workflow-level analysis
- task-specific evals rather than generic metrics
- continuous evaluation using production logs and edge cases

AgentArena should follow the same pattern, but apply it to role-based external
agent tournaments.

## Security and Guardrails

### Prompt Injection Defense

Apply defense in layers:

- remote content sanitization before storage
- strict separation of instructions from scraped data
- injection scanning for HTML, markdown, comments, encoded text, and hidden text
- do not let scraped content modify system prompts
- do not persist untrusted content into long-term memory without review

### Agent Security

- least privilege by default
- no arbitrary shell or network unless the benchmark explicitly requires it
- allowlisted tools only
- parameter validation for tool calls
- human approval for high-impact actions
- monitoring for loops and denial-of-wallet behavior

### Cost Guardrails

For hosted user runs:

- per-user rate limits
- daily spend caps
- hard token caps per run
- timeout caps
- concurrency caps
- cached benchmark results where valid
- explicit usage display before long runs

### Judge and Data Handling

- no hidden judge fallback
- provider used for judging must be explicit in logs
- if judging would route data to a different provider, fail unless configured

## Immediate Repo Priorities

1. Define the agent runner contract
2. Rename product docs and UI copy around agents, not skills
3. Separate legacy prompt-artifact evaluation from tournament infrastructure
4. Add ingestion security filters before broader scraping
5. Build the first role-specific tournament with saved traces and explicit costs
