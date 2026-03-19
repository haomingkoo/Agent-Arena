# AgentArena

AgentArena is an agent tournament platform.

The goal is not to rate isolated prompts in the abstract. The goal is to bring
comparable agents into the same benchmark harness, run them on the same tasks
under the same constraints, rank them on real outcomes, and study why the best
agents win.

## Refined Problem Statement

People are publishing many agents for the same role, but there is still no
trustworthy way to compare them head-to-head.

That creates three problems:

- buyers cannot tell which agent is actually better for a role
- builders cannot tell whether their agent design is improving or regressing
- marketplaces reward packaging and hype more than real performance

AgentArena solves this by running role-based agent tournaments with:

- a shared runtime contract
- shared task packs
- explicit judging criteria
- full traces and token accounting
- reproducible leaderboards

## Current Wedge

Start with two fields that are both credible:

1. Software Engineering
2. Semiconductor Design and Verification

Why these two:

- software engineering has the deepest public supply of benchmarkable agents
- semiconductor is a real domain moat and matches the founder's expertise
- both domains can support role-based tasks with concrete acceptance criteria

Recommended first roles:

- Software Engineering -> Code Reviewer Agent or Software Engineer Agent
- Semiconductor -> Verification Debug Agent

## Product Direction

The long-term product loop is:

1. Discover agents
2. Normalize them into a benchmark runner contract
3. Run tournaments by field and role
4. Publish leaderboards and traces
5. Learn what top agents do differently
6. Help users build stronger agents on-platform
7. Eventually host and marketplace high-performing agents

## Evaluation Principles

The benchmark should follow a few hard rules:

- no hidden fallbacks
- no mock leaderboard data
- no apples-to-oranges comparisons across different runtime privileges
- no broad cross-industry claims without domain expertise
- no silent data leakage to unintended model providers

Current judging rule:

- if Gemini judging is selected, `GEMINI_API_KEY` must be present
- the system must fail closed rather than silently falling back to another judge
- Qwen execution and judging are supported via DashScope's OpenAI-compatible API
  using `QWEN_API_KEY` and `QWEN_BASE_URL`

## How Agents Should Be Evaluated

An agent benchmark should score more than final output.

Core dimensions:

- task success
- correctness
- safety
- tool selection
- argument precision
- handoff quality for multi-agent systems
- latency
- token cost
- recovery behavior on ambiguous or adversarial inputs

The benchmark should combine:

- deterministic checks where possible
- pairwise or rubric-based LLM judging where needed
- expert review for domain-specific gold labels

## Security Posture

AgentArena must assume scraped content is hostile.

Guardrails:

- treat external content as untrusted data, never as instructions
- sanitize remote HTML, markdown, comments, and hidden text before ingestion
- isolate discovery from execution
- disable dangerous tools by default
- enforce least privilege for benchmark tools
- log all tool calls, outputs, and judge prompts
- rate limit user-triggered runs and hosted agent usage
- cap per-user budget, per-run budget, and per-day spend

Relevant references are linked in [docs/agent-tournament-pipeline.md](/Users/koohaoming/dev/workflow-harvester/docs/agent-tournament-pipeline.md).

## Repo Reality

This repository is mid-transition.

Already aligned:

- judge fallback now fails closed in `evaluate/sandbox.py`
- token accounting now separates execution and judge usage
- top-level guidance docs point to agent-vs-agent benchmarking

Still legacy:

- parts of the data model and CLI are still `skill`-named
- `evaluate/rubric.py` still parses `SKILL.md` artifacts
- some routes and payloads still use `skill` naming

That is acceptable only as a transition state, not as the final abstraction.

## Key Docs

- [Problem Statement](/Users/koohaoming/dev/workflow-harvester/docs/agent-vs-agent-problem-statement.md)
- [Tournament Pipeline](/Users/koohaoming/dev/workflow-harvester/docs/agent-tournament-pipeline.md)
- [Platform Architecture](/Users/koohaoming/dev/workflow-harvester/docs/agent-platform-architecture.md)
- [Runner Contract](/Users/koohaoming/dev/workflow-harvester/docs/agent-runner-contract.md)
- [Implementation Backlog](/Users/koohaoming/dev/workflow-harvester/docs/implementation-backlog.md)
- [Test Strategy](/Users/koohaoming/dev/workflow-harvester/docs/test-strategy.md)
- [Agent Swarm Playbook](/Users/koohaoming/dev/workflow-harvester/AGENTS.md)
- [Claude Guidance](/Users/koohaoming/dev/workflow-harvester/CLAUDE.md)

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
npm run lint
npm run build
cd ..

pytest tests/
```

## Model Providers

AgentArena currently supports:

- Anthropic for execution and judging
- Gemini for judging
- Qwen via DashScope's OpenAI-compatible API for execution and judging

Legacy markdown execution defaults come from:

```bash
EXEC_MODEL_PROVIDER=anthropic
EXEC_MODEL_NAME=claude-haiku-4-5-20251001
```

To use Qwen for legacy execution defaults:

```bash
EXEC_MODEL_PROVIDER=qwen
EXEC_MODEL_NAME=qwen-plus
QWEN_API_KEY=...
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

To use Qwen as the judge:

```bash
JUDGE_MODEL=qwen
QWEN_JUDGE_MODEL=qwen-plus
QWEN_API_KEY=...
```

Judge routing is explicit and fail-closed. No hidden fallback is allowed.

## Benchmarking

Current benchmark runner for markdown-packaged external agent candidates:

```bash
python curate.py --benchmark data/external-agents/engineering-code-reviewer.md --paired
python curate.py --leaderboard
```

This is a transition harness. The long-term target is a true agent runner
contract that can support richer agent configurations than a single markdown
artifact.
# Agent-Arena
