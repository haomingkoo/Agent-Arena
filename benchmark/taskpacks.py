"""
Versioned field-role task packs for agent-native benchmarking.

Two task pack versions:
  - v1: hand-authored tasks (legacy, kept for longitudinal comparison)
  - v2: JD-generated tasks from real ATS postings via LLM extraction

v2 is the default for new tournaments. v1 is available for comparison.
The correct order is: JD → responsibilities → tasks → tournament.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from evaluate.sandbox import BenchmarkJob
from tournament.tasks import CODE_REVIEW_TASKS
from tournament.swe_tasks import SOFTWARE_ENGINEER_TASKS


@dataclass(frozen=True)
class TaskPack:
    field: str
    role: str
    version: str
    grading_method: str
    benchmark_version: str
    role_blueprint_source: str = "hand-authored"
    requires_jd_corpus: bool = False
    tasks: tuple[BenchmarkJob, ...] = field(default_factory=tuple)


SEMICONDUCTOR_VERIFICATION_DEBUG_TASKS: tuple[BenchmarkJob, ...] = (
    BenchmarkJob(
        id="sv-assertion-root-cause",
        name="Debug failing assertion from simulation log",
        category="verification-debug",
        skill_domain="verification-debug-agent",
        test_set="agent-pack-v1",
        input_prompt=(
            "Analyze the failing assertion and simulation log. "
            "Identify the most likely root cause and propose the minimal fix."
        ),
        input_context="""\
Simulation log excerpt:
[120 ns] INFO: Starting AXI write burst, len=4 addr=0x1000
[125 ns] WARN: awready deasserted for 3 cycles
[130 ns] ERROR: Assertion failed: p_wlast_alignment
Assertion:
property p_wlast_alignment;
  @(posedge clk) disable iff (!rst_n)
    wvalid && wready && (beat_count == awlen) |-> wlast;
endproperty

Observed notes:
- beat_count increments on every wvalid, even when wready is low
- awlen is sampled from the previous transaction until awvalid && awready
- failure happens when awready stalls mid-burst
""",
        acceptance_criteria=[
            "Identifies beat_count incrementing without handshake as the primary bug",
            "Explains why stalled wready causes wlast misalignment",
            "Notes that awlen sampling from a previous transaction can worsen the mismatch",
            "Proposes gating beat_count increments on wvalid && wready",
            "Suggests a minimal RTL or counter update fix rather than a full redesign",
        ],
        risk_level="high",
        stack="systemverilog/verification",
    ),
    BenchmarkJob(
        id="sv-reset-handshake-bug",
        name="Explain reset-related handshake failure",
        category="verification-debug",
        skill_domain="verification-debug-agent",
        test_set="agent-pack-v1",
        input_prompt=(
            "Inspect this waveform summary and debug the reset or handshake issue. "
            "Propose the smallest safe fix."
        ),
        input_context="""\
Waveform summary:
- rst_n deasserts at cycle 10
- req_valid rises at cycle 11
- req_ready remains X until cycle 13
- grant fires at cycle 12 despite req_ready not being known-good
- scoreboard mismatch: expected no transfer before cycle 13

Relevant RTL:
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    req_ready <= 1'b0;
    grant <= 1'b0;
  end else begin
    if (grant_condition)
      grant <= 1'b1;
    req_ready <= ready_from_fifo;
  end
end
""",
        acceptance_criteria=[
            "Identifies that grant can assert before req_ready is valid after reset release",
            "Explains the X-propagation or initialization gap around ready_from_fifo",
            "Notes that the handshake should not complete until req_ready is known-good",
            "Recommends sequencing or gating grant on a valid ready signal after reset",
            "Provides a minimal fix or reset-stabilization approach",
        ],
        risk_level="medium",
        stack="systemverilog/verification",
    ),
    BenchmarkJob(
        id="sv-testbench-objection-hang",
        name="Find root cause of UVM testbench hang",
        category="verification-debug",
        skill_domain="verification-debug-agent",
        test_set="agent-pack-v1",
        input_prompt=(
            "Review this UVM failure summary and explain why the test hangs. "
            "Recommend the most targeted fix."
        ),
        input_context="""\
Run summary:
- sequence starts successfully
- driver sends 16 items
- monitor observes 16 items
- scoreboard compares 16 items and reports PASS
- simulation never exits; timeout at 1 ms

Code excerpt:
task run_phase(uvm_phase phase);
  phase.raise_objection(this);
  seq.start(seqr);
  wait (scoreboard.done);
  `uvm_info("TEST", "Scoreboard done", UVM_MEDIUM)
endtask

Scoreboard:
always @(posedge clk) begin
  if (compared_count == expected_count)
    done <= 1'b1;
end
""",
        acceptance_criteria=[
            "Identifies the missing drop_objection in run_phase",
            "Explains why simulation hangs even though the scoreboard passes",
            "Notes that done may stay asserted but objections still keep the phase alive",
            "Recommends adding phase.drop_objection(this) on completion or failure paths",
            "Mentions reset/initialization only as secondary if raised",
        ],
        risk_level="medium",
        stack="uvm/verification",
    ),
)


def _load_jd_tasks_safe(role: str) -> tuple[BenchmarkJob, ...]:
    """Load JD-generated tasks if they exist, otherwise return empty tuple."""
    try:
        from benchmark.jd_taskpacks import load_jd_tasks
        tasks = load_jd_tasks(role)
        if tasks:
            return tuple(tasks)
    except (FileNotFoundError, ImportError):
        pass
    return ()


# ── Task Pack Registry ──────────────────────────────────────────────
#
# v1: hand-authored (legacy, kept for longitudinal comparison)
# v2: JD-generated from real ATS postings (default for new tournaments)


TASK_PACKS: dict[tuple[str, str, str], TaskPack] = {
    # ── Code Review: v1 (hand-authored) ──
    (
        "software-engineering",
        "code-review-agent",
        "v1",
    ): TaskPack(
        field="software-engineering",
        role="code-review-agent",
        version="v1",
        grading_method="deterministic+llm-rubric",
        benchmark_version="wh-se-code-review-v1",
        role_blueprint_source="hand-authored-role-pack",
        tasks=tuple(CODE_REVIEW_TASKS),
    ),
    # ── SWE: v1 (hand-authored) ──
    (
        "software-engineering",
        "software-engineer-agent",
        "v1",
    ): TaskPack(
        field="software-engineering",
        role="software-engineer-agent",
        version="v1",
        grading_method="deterministic+llm-rubric",
        benchmark_version="wh-se-swe-agent-v1",
        role_blueprint_source="hand-authored-role-pack",
        tasks=tuple(SOFTWARE_ENGINEER_TASKS),
    ),
    # ── Semiconductor: v1 (expert-seeded) ──
    (
        "semiconductor",
        "verification-debug-agent",
        "v1",
    ): TaskPack(
        field="semiconductor",
        role="verification-debug-agent",
        version="v1",
        grading_method="deterministic+expert-sampled",
        benchmark_version="wh-semi-verif-debug-v1",
        role_blueprint_source="expert-seeded-pilot-pack",
        tasks=SEMICONDUCTOR_VERIFICATION_DEBUG_TASKS,
    ),
}


def _register_jd_packs() -> None:
    """Register v2 JD-backed task packs if generated task files exist."""
    jd_lanes = [
        ("software-engineering", "code-review-agent"),
        ("software-engineering", "software-engineer-agent"),
    ]
    for field_name, role in jd_lanes:
        tasks = _load_jd_tasks_safe(role)
        if tasks:
            TASK_PACKS[(field_name, role, "v2")] = TaskPack(
                field=field_name,
                role=role,
                version="v2",
                grading_method="deterministic+llm-rubric",
                benchmark_version=f"jd-backed-{role}-v2",
                role_blueprint_source="jd-corpus-extraction",
                requires_jd_corpus=True,
                tasks=tasks,
            )


_register_jd_packs()


# ── Public API ──────────────────────────────────────────────────────


def get_task_pack(field: str, role: str, version: str = "v2") -> TaskPack:
    """Fetch one task pack by field, role, and version.

    Default version is v2 (JD-generated). Falls back to v1 if v2 not available.
    """
    key = (field, role, version)
    if key in TASK_PACKS:
        return TASK_PACKS[key]
    # Fallback: try v1 if v2 requested but not available
    if version == "v2":
        fallback_key = (field, role, "v1")
        if fallback_key in TASK_PACKS:
            return TASK_PACKS[fallback_key]
    raise KeyError(f"Unknown task pack: {field}/{role}/{version}")


def list_task_packs(
    field: str | None = None,
    role: str | None = None,
) -> list[TaskPack]:
    """List registered task packs with optional field/role filtering."""
    packs = list(TASK_PACKS.values())
    if field:
        packs = [pack for pack in packs if pack.field == field]
    if role:
        packs = [pack for pack in packs if pack.role == role]
    packs.sort(key=lambda pack: (pack.field, pack.role, pack.version))
    return packs


def select_task_pack_jobs(
    field: str,
    role: str,
    *,
    version: str = "v2",
    count: int | None = None,
    seed: int | None = None,
    exclude_holdouts: bool = True,
    exclude_ids: set[str] | None = None,
) -> list[BenchmarkJob]:
    """Select jobs from a task pack for a tournament.

    Default version is v2 (JD-generated). Falls back to v1.
    Excludes holdout tasks from public tournament packs.
    Anchors always included, rotating tasks sampled.
    """
    pack = get_task_pack(field, role, version=version)
    tasks = list(pack.tasks)

    if exclude_holdouts:
        tasks = [t for t in tasks if t.task_bucket != "holdout"]

    if count is None or count >= len(tasks):
        return tasks

    anchors = [t for t in tasks if t.task_bucket == "anchor"]
    rotating = [t for t in tasks if t.task_bucket != "anchor"]
    if exclude_ids:
        rotating = [t for t in rotating if t.id not in exclude_ids]

    if len(anchors) >= count:
        return anchors[:count]

    remaining = count - len(anchors)
    rng = random.Random(seed)
    sampled_rotating = rng.sample(rotating, min(remaining, len(rotating)))
    return anchors + sampled_rotating


def select_holdout_jobs(
    field: str,
    role: str,
    *,
    version: str = "v2",
) -> list[BenchmarkJob]:
    """Return only holdout tasks for internal validation checks."""
    pack = get_task_pack(field, role, version=version)
    return [t for t in pack.tasks if t.task_bucket == "holdout"]
