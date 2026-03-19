# Test Strategy

## Goal

Validate that AgentArena is fair, secure, reproducible, and cost-controlled.

Testing must cover:

- correctness
- security
- fairness
- stability
- cost containment
- migration safety

## Test Layers

### Unit Tests

Focus:

- model validation
- contract validation
- scoring math
- sanitization rules
- rate-limit logic

Targets:

- `store/`
- `agents/`
- `security/`
- `tournament/ranking.py`
- `runtime/`

### Integration Tests

Focus:

- discovery -> normalization -> benchmark eligibility
- benchmark execution -> judging -> persistence
- tournament run -> leaderboard update
- hosted run -> usage ledger -> limit enforcement

### End-to-End Tests

Focus:

- leaderboard browsing
- tournament detail viewing
- trace visibility
- builder create -> test -> publish flow
- hosted run limit handling

### Security Tests

Focus:

- prompt injection in scraped content
- malicious markdown and HTML
- hostile tool arguments
- denial-of-wallet behavior
- provider routing and no-fallback guarantees

### Fairness Tests

Focus:

- all agents in same tournament use same contract
- task pack version is fixed per tournament
- ranking changes only when inputs change
- unsupported candidates are excluded consistently

## Core Test Cases

## A. Data Model Tests

- creating an `AgentProfile` persists field and role correctly
- creating an `AgentVersion` without a valid profile fails
- creating a `RunnerContract` without explicit permissions fails
- saving a `RunTrace` without provider metadata fails

## B. Discovery Tests

- GitHub adapter records provenance for a candidate artifact
- unsupported packaging type is stored as discovered but unbenchmarked
- duplicate artifacts collapse into one canonical candidate

## C. Prompt Injection and Ingestion Tests

- scraped markdown containing `ignore previous instructions` is flagged
- HTML with hidden text is sanitized before storage
- embedded code fences do not become privileged instructions
- malicious content cannot widen tool permissions during normalization

## D. Runner Contract Tests

- markdown prompt bundle normalizes into a contract for supported roles
- candidate requiring forbidden network access is rejected
- candidate missing role classification is rejected
- contract token cap is enforced

## E. Benchmark Execution Tests

- one supported candidate can complete one task and persist a trace
- trace includes task prompt, final answer, provider, token usage, and runtime
- execution failure still produces a persisted error trace
- judge failure leaves run marked incomplete, not silently rerouted

## F. Judge Behavior Tests

- `JUDGE_MODEL=gemini` without `GEMINI_API_KEY` fails closed
- judge provider is persisted to the trace
- judge token usage is persisted to the trace
- unsupported judge model configuration raises immediately

## G. Tournament Tests

- tournament with fewer than two eligible agents fails explicitly
- tournament uses one fixed task pack version
- tournament leaderboard orders by scoped tournament results
- rating updates are reproducible from the same score map

## H. Hosted Use and Budget Tests

- per-user run cap is enforced
- per-user daily spend cap is enforced
- per-run token cap terminates execution
- concurrency cap blocks new runs when limit is reached

## I. API Tests

- field-role leaderboard endpoint returns scoped results only
- trace detail endpoint omits secret values
- builder endpoint rejects invalid contracts
- search endpoint does not expose unsupported candidates as benchmarked

## J. Frontend Tests

- leaderboard keyboard navigation still works
- route error boundaries catch failed API responses
- tournament page displays benchmark metadata and trace availability
- builder flow surfaces budget and limit errors clearly

## Role-Specific Benchmark Test Cases

### Software Engineering -> Code Reviewer Agent

- detect SQL injection in a diff
- detect race condition in a checkout path
- detect hardcoded secret and rollback gap in payment code
- detect auth bypass and weak session handling
- prioritize issues correctly by severity

Expected grading mix:

- deterministic checks for required findings
- rubric checks for explanation quality

### Semiconductor -> Verification Debug Agent

- identify root cause from simulation log and failing assertion
- explain mismatch between expected and observed waveform behavior
- propose minimal RTL or testbench fix
- identify reset, handshake, or timing bug from provided artifacts
- admit uncertainty when fixture is insufficient

Expected grading mix:

- deterministic checks for root-cause tokens and fix targets
- expert-reviewed samples for explanation quality

## Regression Suite

Keep a fixed regression pack for:

- previously misranked agents
- previously exploited prompt injection samples
- previously expensive runaway runs
- previously mis-scoped leaderboard results

## Test File Plan

Recommended future files:

- `tests/test_agent_models.py`
- `tests/test_ingest_security.py`
- `tests/test_runner_contracts.py`
- `tests/test_benchmark_executor.py`
- `tests/test_tournament_pipeline.py`
- `tests/test_hosted_run_limits.py`
- `tests/test_api_agents.py`
- `frontend/tests/leaderboard.spec.ts`
- `frontend/tests/tournament.spec.ts`
- `frontend/tests/builder.spec.ts`

## Release Gates

Before public launch of a field-role track:

- all unit tests green
- all integration tests green
- security injection suite green
- hosted budget enforcement green
- one sampled expert review pass completed
- benchmark version and contract version frozen
