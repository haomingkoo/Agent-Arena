"""
Benchmark job registry — imports from tune and holdout sets.

This is the backward-compatible entry point. Use TUNE_JOBS for development
and ALL_JOBS when running the full suite. NEVER tune on HOLDOUT_JOBS.
"""
from __future__ import annotations

from benchmarks.fixtures_tune import TUNE_JOBS
from benchmarks.fixtures_holdout import HOLDOUT_JOBS

ALL_JOBS = TUNE_JOBS + HOLDOUT_JOBS

JOBS_BY_ID = {j.id: j for j in ALL_JOBS}
JOBS_BY_CATEGORY: dict[str, list] = {}
for j in ALL_JOBS:
    JOBS_BY_CATEGORY.setdefault(j.category, []).append(j)

# Convenience re-exports for backward compat
TUNE_JOBS = TUNE_JOBS
HOLDOUT_JOBS = HOLDOUT_JOBS
