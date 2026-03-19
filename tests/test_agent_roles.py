from __future__ import annotations

from evaluate.rubric import parse_skill_md
from ingest.agent_roles import assign_field_role
from ingest.categorize import categorize_skill


def test_assign_field_role_maps_code_review_to_software_engineering():
    skill = parse_skill_md(
        """\
---
name: Review Master
description: Reviews pull requests for security and correctness
triggers:
  - review my diff
---

# Review Master

Review pull requests, inspect diffs, and explain the highest-severity issues.
"""
    )

    category = categorize_skill(skill)
    assignment = assign_field_role(skill, category)

    assert assignment.field == "software-engineering"
    assert assignment.role == "code-review-agent"
    assert assignment.source_category == "code-review"


def test_assign_field_role_detects_semiconductor_debug_signal():
    skill = parse_skill_md(
        """\
---
name: Waveform Detective
description: Debug RTL failures from waveforms and simulation logs
---

# Waveform Detective

Analyze SystemVerilog assertions, waveforms, UVM testbench failures, and
simulation logs to identify the root cause.
"""
    )

    assignment = assign_field_role(skill)

    assert assignment.field == "semiconductor"
    assert assignment.role == "verification-debug-agent"
    assert assignment.method == "semiconductor-rule"
