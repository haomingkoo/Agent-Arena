# AGENTS.md — Agent Swarm Playbook

When working on AgentArena, trigger these agent swarms for different scenarios.

## First Principle

AgentArena is aiming at **agent-vs-agent benchmarking**.

- The primary unit is an **agent configuration for a role**.
- `SKILL.md` files are only one possible packaging format.
- Do not silently reframe product questions about agents into skill-certification work.
- Before launching any research swarm, lock the abstraction first: agent, role, runtime contract, and benchmark audience.

---

## Planning a Major Feature

> Trigger: "plan [feature]", "design [system]", "architect [module]"

Launch **all 6 in parallel only after the unit of evaluation is clear**:

| Agent | Role | Prompt Focus |
|-------|------|-------------|
| **Researcher** | Discovery & landscape | Search web for existing solutions, competitors, APIs, ecosystem state |
| **Architect** | System design | Read codebase, design data model, file-level implementation plan |
| **Critic** | Harsh reality check | Tear apart the idea — market size, business model, risks, alternatives |
| **Legal** | Compliance analysis | Scraping legality, copyright, ToS, Singapore law (PDPA, CMA, IMDA) |
| **QA Lead** | Test strategy | Reliability, fairness, anti-gaming, acceptance criteria, phased rollout |
| **Infra/Cost** | Infrastructure & budget | API costs, hosting, scaling phases, cost optimization |

---

## Before Building Code

> Trigger: "build [feature]", "implement [module]"

Launch **3 in parallel**:

| Agent | Role | Prompt Focus |
|-------|------|-------------|
| **Planner** | Implementation plan | Break into tasks, identify files to modify, dependencies, order |
| **Critic** | Pre-build critique | What could go wrong? Edge cases? What's YAGNI? |
| **Test Writer** | Write tests first | Create test cases BEFORE implementation (TDD) |

---

## After Building Code

> Trigger: after completing implementation

Launch **3 in parallel**:

| Agent | Role | Prompt Focus |
|-------|------|-------------|
| **Auditor** | Code quality review | Rate 1-10, find bugs, security holes, sloppy patterns |
| **Test Runner** | Run tests | Execute pytest, verify all pass, check coverage |
| **Critic** | Post-build critique | Does this actually solve the problem? Over-engineered? Missing anything? |

---

## Weekly Tournament Operations

> Trigger: "run tournament", "weekly benchmark"

Launch **sequentially** (each depends on previous):

1. **Discovery Agent** — Gather candidate agent configurations for a role
2. **Normalizer Agent** — Map each candidate into the benchmark runner contract
3. **Categorizer Agent** — Classify candidates by industry and role
4. **Tournament Runner** — Execute benchmarks per category/role
5. **Coaching Agent** — Analyze results, generate coaching for bottom-half agents
6. **Report Agent** — Compile weekly report, update leaderboard

---

## Researching a Topic

> Trigger: "research [topic]", "what's the landscape for [X]"

Launch **2-3 in parallel**:

| Agent | Role | Prompt Focus |
|-------|------|-------------|
| **Web Researcher** | Current state | Search web for latest data, numbers, competitors |
| **Academic Researcher** | Frameworks & theory | Named methodologies, papers, proven approaches |
| **Critic** | Reality filter | What's hype vs real? What are the unstated assumptions? |

---

## Deploying / Shipping

> Trigger: "deploy", "ship", "push to production"

Launch **3 in parallel**:

| Agent | Role | Prompt Focus |
|-------|------|-------------|
| **Pre-deploy Checker** | Verify readiness | Tests pass? Build works? Env vars set? DB migrations? |
| **Security Scanner** | Security review | Secrets in code? CORS config? Rate limits? Input validation? |
| **Legal Checker** | Compliance | ToS in place? Privacy policy? Disclaimers? PDPA compliance? |

---

## Notes

- Always run **Critic** agents — they prevent building the wrong thing
- **Researcher** agents should always search the web — stale info is worse than no info
- Do not launch broad research swarms until the product question is crisp; otherwise token burn explodes while the abstraction stays muddy
- Save key findings to memory (`/.claude/projects/.../memory/`) for future sessions
- The anti-slop rule applies to agents too: NO mock data, NO hallucinated facts
