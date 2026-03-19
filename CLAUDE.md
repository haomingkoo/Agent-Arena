# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL RULES

- **NO mock data, placeholder data, or hallucinated information.** Always verify facts online before including them.
- **NO fabricated examples.** If you need example data, use real data from the database or real sources.
- **Always check factual claims** against online sources. Do not invent statistics, URLs, company names, or product features.
- If unsure about something, say so — do not guess or make up an answer.
- **No hidden fallbacks.** If something fails, surface it explicitly — never silently degrade.
- **Document before/after** when making structural changes.
- **Do not collapse "agent" into "skill" unless the user explicitly asks about skill artifacts.** `SKILL.md` is one packaging format, not the product abstraction.
- **Never print, echo, or inspect secret values in terminal output.** If you need to confirm a credential is present, only report a boolean or provider availability, never the secret or any visible prefix.
- **Read `docs/project-steering.md` before planning or re-scoping major work.** If a chat summary conflicts with the steering doc, the steering doc wins.

## What This Is

**AgentArena** is an agent-vs-agent benchmarking project.

The primary goal is to compare **agent configurations** for the same role under the same constraints, rank them on real tasks, and study what the top performers do differently.

Current repo reality:

- Much of the existing implementation still evaluates `SKILL.md`-style instruction bundles.
- That is an intermediate artifact, not the final product abstraction.
- When in doubt, read [docs/agent-vs-agent-problem-statement.md](/Users/koohaoming/dev/workflow-harvester/docs/agent-vs-agent-problem-statement.md) first and keep work aligned to agent-vs-agent benchmarking.

**Positioning:** We want a credible benchmark for role-based agents, then an improvement loop for learning from the winners.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# Benchmark a markdown-packaged external agent config (paired A/B vs baseline)
python curate.py --benchmark SKILL.md --paired
python curate.py --benchmark SKILL.md --paired --jobs feat-pagination,fix-date-range
python curate.py --leaderboard

# Certify a prompt artifact (legacy skill pipeline)
python curate.py --certify-file SKILL.md
python curate.py --certify-file SKILL.md --deep

# Discover and certify from GitHub
python curate.py --search --max 200

# API server (serves frontend + API)
uvicorn api.app:app --port 8000

# Frontend dev (proxies API to :8000)
cd frontend && npm run dev

# Run tests
pytest tests/
```

## Architecture

```
curate.py                # CLI entry point

evaluate/                # Multi-stage benchmark + artifact evaluation
  rubric.py              # Legacy SKILL.md parser and quality scoring helpers
  heuristic.py           # Stage 1: fast regex/structure (7 dimensions)
  llm_judge.py           # Stage 2: Claude Haiku deep evaluation (blended 60/40)
  safety.py              # Content safety scanner (20 patterns, multiline)
  sandbox.py             # Stage 3: work-sample benchmarks + paired A/B comparison

certify/                 # WH-CERT Bronze/Silver/Gold certification
  checks.py              # Tier-specific check definitions
  engine.py              # Certification pipeline orchestrator

store/                   # Persistence
  models.py              # Legacy skill models + tournament/category models
  db.py                  # SQLite CRUD, Wilson score voting, anti-gaming, column whitelists

learn/                   # Adaptive learning
  feedback.py            # Prediction recording + weight adjustment
  insights.py            # Pattern analysis across certified skills

ingest/                  # Skill discovery
  github.py              # GitHub prompt-artifact scraper (current focus: SKILL.md-style repos)

api/                     # Web API (FastAPI)
  app.py                 # REST API + serves frontend SPA

frontend/                # React + Vite + Tailwind SPA
  src/pages/             # Leaderboard, SkillDetail, Scanner, About
  src/components/        # NavBar, DimensionBars, CertBadge, UpgradeChip, StatCard
  src/lib/api.ts         # API client

benchmarks/              # Benchmark job definitions
  fixtures.py            # Registry: ALL_JOBS, TUNE_JOBS, HOLDOUT_JOBS
  fixtures_tune.py       # 20 tuning jobs
  fixtures_holdout.py    # 10 holdout jobs

tests/                   # pytest test suite

data/                    # Generated data (gitignored)
  certified.db           # Legacy skill-oriented database
  benchmark_results.json # Benchmark leaderboard data
  baseline_cache.json    # Cached baseline results (< 7 days)
  skill_weights.json     # Learned scoring weights
  external-agents/       # 10 markdown-packaged external agent configs for benchmarking

_archive/                # Archived code (BMAD, legacy, research)
```

### API Endpoints

| Endpoint | Method | Description | Rate Limit |
|----------|--------|-------------|------------|
| `/api/health` | GET | Service health | 30/min |
| `/api/leaderboard` | GET | Ranked benchmark candidates by upgrade (legacy skill naming in payloads) | 60/min |
| `/api/skill/{name}` | GET | Current candidate detail route (legacy path name) | 60/min |
| `/api/stats` | GET | Aggregate stats | 30/min |
| `/api/scan` | POST | Safety scan of pasted content | 10/min |
| `/api/score` | POST | Stage 1 heuristic score | 10/min |

### Scoring Dimensions (7 heuristic + 1 LLM)

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| frequency_value | 0.10 | Solves a common problem? |
| capability_upgrade | 0.20 | Gives Claude new abilities? |
| specificity | 0.20 | Concrete and opinionated? |
| token_efficiency | 0.10 | Concise and well-structured? |
| source_credibility | 0.10 | From a trusted source? |
| trigger_clarity | 0.10 | Clear activation conditions? |
| methodology_depth | 0.10 | Encodes real methodology? |
| llm_quality | 0.10 | LLM safety + uniqueness assessment |

## Environment

Requires `.env` with:

```
# Required for benchmarks & Stage 2
ANTHROPIC_API_KEY=...

# Recommended for cross-model judging
GEMINI_API_KEY=...

# Recommended for GitHub discovery
GITHUB_TOKEN=...
```

See `.env.example` for template. Never commit `.env`.
