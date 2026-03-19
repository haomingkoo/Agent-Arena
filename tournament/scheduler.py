"""
Weekly tournament scheduler.

Supports two scheduling modes:
  1. Agent-native (field/role): Uses benchmark-ready agents from the agent table
  2. Legacy (category): Uses skills from the skills table

Designed to be called via CLI or cron.
"""
from __future__ import annotations

from datetime import date

from benchmark.taskpacks import list_task_packs
from store.db import (
    get_tournament_by_week,
    init_db,
    list_benchmark_ready_agents,
    list_skills_by_category,
)
from tournament.cost import estimate_cost
from tournament.runner import TournamentConfig, run_tournament
from tournament.tasks import DOMAIN_TASK_POOLS


def get_week_id(d: date | None = None) -> str:
    """Current ISO week string like '2026-W12'.

    Uses the ISO 8601 week numbering where Monday is the first day
    of the week and the first week of the year contains January 4.
    """
    if d is None:
        d = date.today()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# ── Agent-native scheduling ─────────────────────────────────────────────────


def get_active_fields_roles(min_agents: int = 2) -> list[tuple[str, str]]:
    """Return (field, role) pairs that have enough benchmark-ready agents.

    A field/role pair is active if:
      1. A task pack is registered for it.
      2. It has at least `min_agents` eligible agent versions in the DB.
    """
    active: list[tuple[str, str]] = []
    for pack in list_task_packs():
        agents = list_benchmark_ready_agents(
            field=pack.field, role=pack.role, limit=min_agents,
        )
        if len(agents) >= min_agents:
            active.append((pack.field, pack.role))
    return active


def run_weekly_agent_tournaments(
    fields_roles: list[tuple[str, str]] | None = None,
    dry_run: bool = False,
    week: str | None = None,
    tasks_per_tournament: int = 5,
    runs_per_task: int = 1,
    max_agents: int = 30,
) -> list[str]:
    """Run agent-native tournaments for all active field/role pairs.

    Args:
        fields_roles: Override which (field, role) pairs to run.
            If None, auto-detect from DB.
        dry_run: If True, print what would happen without running.
        week: Override the week ID. Defaults to current ISO week.
        tasks_per_tournament: Number of tasks per tournament.
        runs_per_task: Number of execution runs per task (averaged).
        max_agents: Maximum agents per tournament.

    Returns:
        List of tournament IDs for completed tournaments.
    """
    init_db()

    current_week = week or get_week_id()

    if fields_roles is None:
        fields_roles = get_active_fields_roles()

    if not fields_roles:
        print("  No field/role pairs with enough agents for tournaments.")
        return []

    print(f"\n{'='*70}")
    print(f"  AgentArena Weekly Agent Tournaments — {current_week}")
    print(f"{'='*70}")
    for field, role in fields_roles:
        print(f"  - {field}/{role}")

    # Check for already-completed tournaments this week
    to_run: list[tuple[str, str]] = []
    for field, role in fields_roles:
        category = f"{field}/{role}"
        existing = get_tournament_by_week(category, current_week)
        if existing and existing.get("status") == "completed":
            print(f"  {category}: already completed this week (skipping)")
        else:
            to_run.append((field, role))

    if not to_run:
        print("  All agent tournaments already completed this week.")
        return []

    # Cost estimate
    total_estimated = 0.0
    for field, role in to_run:
        agents = list_benchmark_ready_agents(
            field=field, role=role, limit=max_agents,
        )
        cost = estimate_cost(
            num_skills=len(agents),
            num_tasks=tasks_per_tournament,
            runs_per_task=runs_per_task,
        )
        total_estimated += cost["total_cost_usd"]
        print(
            f"  {field}/{role}: {len(agents)} agents, "
            f"est. ${cost['total_cost_usd']:.4f}"
        )

    print(f"\n  Total estimated cost: ${total_estimated:.4f}")

    if dry_run:
        print("  [DRY RUN] No tournaments executed.")
        return []

    # Run tournaments
    tournament_ids: list[str] = []
    for field, role in to_run:
        try:
            config = TournamentConfig(
                field=field,
                role=role,
                week=current_week,
                tasks_per_tournament=tasks_per_tournament,
                runs_per_task=runs_per_task,
                max_agents=max_agents,
            )
            tid = run_tournament(config)
            tournament_ids.append(tid)
        except Exception as e:
            print(f"\n  ERROR in {field}/{role} tournament: {e}")
            continue

    print(
        f"\n  Completed {len(tournament_ids)}/{len(to_run)} "
        f"agent tournaments."
    )
    return tournament_ids


# ── Legacy category-based scheduling ────────────────────────────────────────


def get_active_categories(min_skills: int = 3) -> list[str]:
    """Return categories that have enough active skills for a tournament.

    A category is active if:
      1. It exists in DOMAIN_TASK_POOLS (has benchmark tasks defined).
      2. It has at least `min_skills` active skills in the database.

    Args:
        min_skills: Minimum number of skills required per category.

    Returns:
        List of category slugs that are tournament-ready.
    """
    active: list[str] = []
    for category in DOMAIN_TASK_POOLS:
        skills = list_skills_by_category(category, limit=min_skills)
        if len(skills) >= min_skills:
            active.append(category)
    return active


def run_weekly_tournaments(
    categories: list[str] | None = None,
    dry_run: bool = False,
    week: str | None = None,
    tasks_per_tournament: int = 5,
    runs_per_task: int = 1,
    max_skills: int = 30,
) -> list[str]:
    """Run legacy skill-based tournaments for all active categories this week.

    Args:
        categories: Override which categories to run. If None, auto-detect.
        dry_run: If True, print what would happen without running anything.
        week: Override the week ID. Defaults to current ISO week.
        tasks_per_tournament: Number of tasks per tournament.
        runs_per_task: Number of execution runs per task (averaged).
        max_skills: Maximum skills per tournament.

    Returns:
        List of tournament IDs for completed tournaments.
    """
    init_db()

    current_week = week or get_week_id()

    if categories is None:
        categories = get_active_categories()

    if not categories:
        print("  No categories with enough skills for tournaments.")
        return []

    print(f"\n{'='*70}")
    print(f"  AgentArena Weekly Tournaments (legacy) — {current_week}")
    print(f"{'='*70}")
    print(f"  Categories: {', '.join(categories)}")

    # Check for already-completed tournaments this week
    to_run: list[str] = []
    for cat in categories:
        existing = get_tournament_by_week(cat, current_week)
        if existing and existing.get("status") == "completed":
            print(f"  {cat}: already completed this week (skipping)")
        else:
            to_run.append(cat)

    if not to_run:
        print("  All tournaments already completed this week.")
        return []

    # Cost estimate
    total_estimated = 0.0
    for cat in to_run:
        skills = list_skills_by_category(cat, limit=max_skills)
        cost = estimate_cost(
            num_skills=len(skills),
            num_tasks=tasks_per_tournament,
            runs_per_task=runs_per_task,
        )
        total_estimated += cost["total_cost_usd"]
        print(
            f"  {cat}: {len(skills)} skills, "
            f"est. ${cost['total_cost_usd']:.4f}"
        )

    print(f"\n  Total estimated cost: ${total_estimated:.4f}")

    if dry_run:
        print("  [DRY RUN] No tournaments executed.")
        return []

    # Run tournaments
    tournament_ids: list[str] = []
    for cat in to_run:
        try:
            config = TournamentConfig(
                category=cat,
                week=current_week,
                tasks_per_tournament=tasks_per_tournament,
                runs_per_task=runs_per_task,
                max_skills=max_skills,
            )
            tid = run_tournament(config)
            tournament_ids.append(tid)
        except Exception as e:
            print(f"\n  ERROR in {cat} tournament: {e}")
            continue

    print(f"\n  Completed {len(tournament_ids)}/{len(to_run)} tournaments.")
    return tournament_ids
