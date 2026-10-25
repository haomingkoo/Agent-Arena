# AgentArena

Agent-vs-agent benchmarking: compare agent configurations for the same role under the same constraints.

## Rules

- `docs/project-steering.md` is the anti-drift contract. Read it before planning or re-scoping; it wins over chat summaries and other docs.
- The unit of evaluation is an agent configuration for a role. `SKILL.md` is one packaging format, and much of the code still evaluates it as a legacy artifact. Don't reframe agent questions as skill certification unless asked.
- No mock, placeholder or invented data, stats, URLs or product claims. Use real DB data or verified sources; say so when unsure.
- No silent fallbacks. Surface failures.
- Never print secret values, even prefixes. Report presence as a boolean.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd frontend && npm install && npm run build      # or `npm run dev` (proxies API to :8000)
uvicorn api.app:app --port 8000                  # API + built SPA
pytest tests/

python curate.py --benchmark SKILL.md --paired [--jobs feat-pagination,fix-date-range]
python curate.py --leaderboard
python curate.py --certify-file SKILL.md [--deep]
```

## Deploy

Railway (nixpacks, `railway.toml`). `start.sh` builds the frontend only if `frontend/dist` is missing, runs `init_db`, then serves on `$PORT`. Healthcheck is `/api/health`.

Keys live in `.env` (template `.env.example`): `ANTHROPIC_API_KEY` is required for benchmarks and the LLM judge; `GEMINI_API_KEY` and `GITHUB_TOKEN` are optional.
