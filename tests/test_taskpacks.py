from __future__ import annotations

from benchmark.taskpacks import (
    get_task_pack,
    list_task_packs,
    select_holdout_jobs,
    select_task_pack_jobs,
)


def test_get_task_pack_for_code_review_returns_expected_metadata():
    pack = get_task_pack("software-engineering", "code-review-agent")

    assert pack.field == "software-engineering"
    assert pack.role == "code-review-agent"
    assert pack.version in ("v1", "v2")
    assert len(pack.tasks) >= 5


def test_get_task_pack_for_semiconductor_verification_debug():
    pack = get_task_pack("semiconductor", "verification-debug-agent")

    assert pack.field == "semiconductor"
    assert pack.role == "verification-debug-agent"
    assert pack.grading_method == "deterministic+expert-sampled"
    assert {task.id for task in pack.tasks} == {
        "sv-assertion-root-cause",
        "sv-reset-handshake-bug",
        "sv-testbench-objection-hang",
    }


def test_select_task_pack_jobs_is_deterministic_with_seed():
    first = select_task_pack_jobs(
        "software-engineering",
        "code-review-agent",
        count=3,
        seed=7,
    )
    second = select_task_pack_jobs(
        "software-engineering",
        "code-review-agent",
        count=3,
        seed=7,
    )

    assert [task.id for task in first] == [task.id for task in second]


def test_list_task_packs_filters_by_field():
    packs = list_task_packs(field="semiconductor")

    assert len(packs) == 1
    assert packs[0].role == "verification-debug-agent"


def test_select_task_pack_jobs_excludes_holdouts_and_keeps_anchors():
    pack = get_task_pack("software-engineering", "code-review-agent")
    anchor_ids = {task.id for task in pack.tasks if task.task_bucket == "anchor"}
    holdout_ids = {task.id for task in pack.tasks if task.task_bucket == "holdout"}

    selected = select_task_pack_jobs(
        "software-engineering",
        "code-review-agent",
        count=3,
        seed=11,
    )
    selected_ids = {task.id for task in selected}

    assert anchor_ids.issubset(selected_ids)
    assert selected_ids.isdisjoint(holdout_ids)


def test_select_task_pack_jobs_excludes_previous_rotating_tasks():
    pack = get_task_pack("software-engineering", "code-review-agent")
    rotating_id = next(task.id for task in pack.tasks if task.task_bucket == "rotating")

    selected = select_task_pack_jobs(
        "software-engineering",
        "code-review-agent",
        count=3,
        seed=7,
        exclude_ids={rotating_id},
    )

    assert rotating_id not in {task.id for task in selected}


def test_select_holdout_jobs_returns_only_holdouts():
    holdouts = select_holdout_jobs("software-engineering", "code-review-agent")

    assert holdouts
    assert all(task.task_bucket == "holdout" for task in holdouts)
