# AgentArena Frontend

This frontend is the operator and user surface for AgentArena.

Its job is to make agent tournaments understandable and trustworthy.

Core product surfaces:

- leaderboard views
- category and tournament views
- benchmark detail views
- scanner and score utilities
- about and methodology pages

The frontend should reflect the actual product abstraction:

- benchmark agents against agents
- scope comparisons by field and role
- show costs, traces, and benchmark context where relevant
- avoid implying that a markdown prompt file is the whole agent

## Development

```bash
npm install
npm run dev
```

## Quality Checks

```bash
npm run lint
npm run build
```

## Design Guidance

- keep leaderboards scoped and explain what is being compared
- expose benchmark metadata, not just a score
- prefer transparent failure states over optimistic placeholders
- preserve route-level error boundaries and loading skeletons
