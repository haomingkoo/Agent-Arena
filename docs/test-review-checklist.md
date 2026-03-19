# Test Review Checklist

This is the QA gate for AgentArena sprint work.

Codex owns this review pass unless explicitly reassigned.

## Rule

A sprint is not "done" just because:
- code was written
- some existing tests still pass
- a partial implementation landed

A sprint is only ready to call done when:
- the implementation matches the sprint exit criteria
- the new behavior is covered by targeted tests
- the affected APIs and UI surfaces are wired through if the sprint requires them

## What Codex Reviews

For each claimed sprint completion:

1. Implementation completeness
- does the code actually satisfy the sprint goal?
- are the new fields or behaviors persisted, exposed, and used where required?

2. Test relevance
- were new tests added for the new behavior?
- do the tests check the thing that changed, not just nearby old behavior?
- do the tests protect against regression?

3. Exit criteria
- do the sprint exit criteria in `docs/sprint-plan.md` actually hold?

4. Credibility
- does the implementation make the benchmark more honest?
- did we accidentally add abstraction without closing the real product gap?

## Sprint 1 Review Gate

Sprint 1 is `Benchmark Integrity`.

Do not mark Sprint 1 done unless all of these are true:

- tournament rows persist:
  - `runtime_class`
  - `task_pack_version`
  - `tournament_type`
- active APIs expose the lane metadata needed by UI and downstream consumers
- only `standardized` tournaments affect public ratings
- agent-native task freshness exists in code:
  - hidden holdouts
  - anchors or equivalent continuity mechanism
  - rotating private/public task behavior
- judge parse robustness is improved and tested

Required tests for Sprint 1:

- DB/persistence test for lane metadata on tournaments
- runner test proving non-`standardized` tournaments do not update ratings
- API test proving lane metadata is returned
- task-selection test proving freshness or exclusion behavior works
- judge parsing/retry test for malformed judge output

## Sprint 2 Review Gate

Sprint 2 is `First Credible Lane`.

Do not mark Sprint 2 done unless all of these are true:

- the public lane has enough benchmark-ready same-role agents
- the lane name matches the actual task pack
- off-role artifacts are blocked from public entry
- the first public lane can be explained honestly from the UI

Required tests for Sprint 2:

- candidate-pool qualification tests
- role-fit routing tests
- tournament admission tests
- API/UI tests showing the lane identity clearly

## Review Output Format

When Codex reviews Claude's sprint work, report:

- `What is solid`
- `What is incomplete`
- `What is untested`
- `Can we call this sprint done? yes/no`

## Claude Expectation

When Claude says a sprint is complete, Claude should include:

- the exact files changed
- the exact tests added
- the exact commands run
- which sprint exit criteria are now satisfied
- what is still intentionally not done
