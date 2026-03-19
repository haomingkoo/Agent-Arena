# AgentArena: Agent-vs-Agent Problem Statement

## Harsh Reality

The repo currently benchmarks markdown instruction bundles well enough to study prompt artifacts, but that is not the product vision.

The real problem is larger:

- People are publishing many AI agents for the same role.
- There is no trustworthy way to compare those agents head-to-head under the same constraints.
- Buyers and builders cannot tell whether a "software engineer agent", "finance analyst agent", or "semiconductor verification agent" is actually better than alternatives.
- Most current tooling focuses on observability, runtime monitoring, or model evaluation, not public role-based comparison of full agent configurations.

## Core Product Thesis

AgentArena should benchmark **agents against agents**.

The unit of evaluation is:

- an agent configuration
- for a clearly defined role
- inside a controlled runtime contract
- measured on shared role-relevant tasks

Examples:

- Software Engineering -> Code Reviewer Agent
- Finance -> Risk Analysis Agent
- Semiconductor -> Verification Debug Agent

## What Counts As An Agent

For AgentArena, an agent is not just a prompt file.

An agent may include:

- system prompts
- instruction files
- tool permissions
- workflow logic
- MCP/tool integrations
- memory policies
- repo-level conventions

`SKILL.md` files are only one possible packaging format. They are a subset, not the whole category.

## Why This Matters

Without a shared benchmark:

- builders cannot tell which agent designs actually work
- users cannot choose the best agent for a role
- improvement advice stays vague and anecdotal
- marketplaces reward packaging and hype, not performance

## The Defensible V1

Do not start with "all agents, all industries".

Start with:

- one public wedge with accessible supply and tasks
- one domain wedge where we have real expertise
- one role per field
- one execution contract per role
- a small but real set of external agents
- full trace capture
- post-run analysis of why the top agents win

That means:

- benchmark 5-10 comparable agents for one role
- run them on real tasks relevant to that role
- rank them using shared judging criteria
- study the top performers for repeatable patterns

Recommended starting fields:

- Software Engineering
- Semiconductor Design and Verification

Recommended first roles:

- Software Engineering -> Code Reviewer Agent or Software Engineer Agent
- Semiconductor -> Verification Debug Agent

## Non-Goals

These are explicitly out of scope for V1:

- benchmarking every agent format on the internet
- claiming broad cross-industry authority without domain experts
- treating prompt files as the same thing as complete agents
- relying on mock data or hidden fallbacks
- building a generic "AI agent observability platform"
- publishing broad coaching advice before benchmark validity is proven

## Product Promise

The long-term promise is:

- find the best agents for a role
- explain why they are best
- help others adopt or improve those agents

But the immediate promise is narrower:

- produce a credible, reproducible, role-based agent benchmark

If AgentArena cannot do that, everything else is branding.
