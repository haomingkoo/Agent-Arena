"""
Curate — legacy artifact-certification CLI plus benchmark runner.

This CLI still contains the older WH-CERT skill-quality pipeline, but it is
also being used to benchmark markdown-packaged external agent candidates.

Today it can:
- discover `SKILL.md`-style prompt artifacts from GitHub
- score and certify those artifacts with the legacy rubric
- benchmark markdown-packaged external agent configs on real tasks

Usage:
    python curate.py                         # scrape seed repos, certify all
    python curate.py --search                # also search GitHub for SKILL.md
    python curate.py --search --max 200      # search with higher limit
    python curate.py --certify-file FILE     # certify a single local SKILL.md
    python curate.py --certify-file FILE --deep  # include LLM judge (Stage 2)
    python curate.py --show-registry         # show certified skills from DB
    python curate.py --stats                 # show certification statistics
    python curate.py --show-audit            # show last raw audit (JSON)
    python curate.py --grade A               # filter audit by grade
    python curate.py --benchmark FILE        # run work-sample benchmark on an agent candidate
    python curate.py --benchmark FILE --jobs feat-pagination,fix-date-range
    python curate.py --leaderboard           # show benchmark leaderboard
    python curate.py --tournament            # run weekly tournaments (all active categories)
    python curate.py --tournament --tournament-category code-review  # single category
    python curate.py --tournament --dry-run  # estimate costs without running
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from certify.checks import CertificationResult
from certify.engine import (
    BRONZE,
    GOLD,
    NONE,
    SILVER,
    certify,
    certify_batch,
    print_certification_summary,
)
from evaluate.heuristic import score_skill_stage1
from evaluate.rubric import ParsedSkill, parse_skill_md
from ingest.github import save_results, scrape_all
from store.db import add_skill, get_stats, init_db, list_skills
from store.models import CertTier, Skill

# Map engine tier constants to CertTier enum
_TIER_MAP = {
    GOLD: CertTier.gold,
    SILVER: CertTier.silver,
    BRONZE: CertTier.bronze,
    NONE: CertTier.uncertified,
}


def _result_to_skill(
    parsed: ParsedSkill,
    result: CertificationResult,
) -> Skill:
    """Convert a CertificationResult + ParsedSkill to a Skill model for DB."""
    score = result.score
    now = datetime.now(tz=None).isoformat()
    expires = (datetime.now(tz=None) + timedelta(days=90)).isoformat()

    return Skill(
        name=parsed.name or "unknown",
        description=parsed.description,
        raw_content=parsed.raw_content,
        instructions=parsed.instructions,
        triggers=parsed.triggers,
        allowed_tools=parsed.allowed_tools,
        line_count=parsed.line_count,
        token_estimate=parsed.token_estimate,
        source_repo=parsed.source_repo,
        source_url=parsed.source_url,
        github_stars=parsed.github_stars,
        install_count=parsed.install_count,
        overall_score=score.overall if score else 0,
        confidence=score.confidence if score else 0,
        frequency_value=score.frequency_value if score else 0,
        capability_upgrade=score.capability_upgrade if score else 0,
        specificity=score.specificity if score else 0,
        token_efficiency=score.token_efficiency if score else 0,
        source_credibility=score.source_credibility if score else 0,
        trigger_clarity=score.trigger_clarity if score else 0,
        methodology_depth=score.methodology_depth if score else 0,
        llm_quality=score.llm_quality if score else 0,
        cert_tier=_TIER_MAP.get(result.tier, CertTier.uncertified),
        cert_checks_json=json.dumps(result.to_dict().get("bronze_checks", [])),
        cert_date=now,
        cert_expires=expires,
        flags_json=json.dumps(score.flags if score else []),
        strengths_json=json.dumps(score.strengths if score else []),
        llm_reasoning=score.llm_reasoning if score else "",
        needs_review=score.needs_review if score else False,
    )


def certify_local_file(file_path: str, deep: bool = False) -> None:
    """Certify a single local SKILL.md file and show full audit."""
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    content = path.read_text()
    parsed = parse_skill_md(content, source_repo="local", source_url=str(path))

    print(f"\n  Certifying: {parsed.name or path.name}")
    print(f"  Lines: {parsed.line_count}  Tokens: ~{parsed.token_estimate}")
    print(f"  Deep (LLM Stage 2): {'yes' if deep else 'no'}")

    result = certify(parsed, deep=deep)
    print(result.summary())

    # Show dimension scores
    if result.score:
        score = result.score
        print(f"\n  Dimensions:")
        dims = [
            ("frequency_value", score.frequency_value),
            ("capability_upgrade", score.capability_upgrade),
            ("specificity", score.specificity),
            ("token_efficiency", score.token_efficiency),
            ("source_credibility", score.source_credibility),
            ("trigger_clarity", score.trigger_clarity),
            ("methodology_depth", score.methodology_depth),
        ]
        if score.stage >= 2:
            dims.append(("llm_quality", score.llm_quality))
        for dim_name, val in dims:
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"    {dim_name:<22} {bar} {val:.2f}")

        if score.flags:
            print(f"\n  Flags:")
            for flag in score.flags:
                print(f"    ⚠ {flag}")
        if score.strengths:
            print(f"\n  Strengths:")
            for s in score.strengths:
                print(f"    ✓ {s}")

    # Persist to DB
    init_db()
    skill_model = _result_to_skill(parsed, result)
    skill_id = add_skill(skill_model)
    print(f"\n  Saved to DB: {skill_id}")
    print()


def run_full_pipeline(
    search: bool = False,
    max_results: int = 100,
    deep: bool = False,
) -> None:
    """Scrape → parse → certify → persist."""
    print("\n[WH-CERT] Starting full certification pipeline...")

    # Step 1: Discover skills
    discovered = scrape_all(include_search=search, max_search_results=max_results)
    save_results(discovered)

    if not discovered:
        print("  No skills discovered.")
        return

    # Step 2: Certify all discovered skills
    parsed_skills = [d.parsed for d in discovered if d.parsed]
    print(f"\n[WH-CERT] Certifying {len(parsed_skills)} skills...")
    results = certify_batch(parsed_skills, deep=deep)

    # Step 3: Persist to DB
    init_db()
    saved = 0
    for parsed, result in zip(parsed_skills, results):
        skill_model = _result_to_skill(parsed, result)
        add_skill(skill_model)
        saved += 1

    print(f"\n[WH-CERT] {saved} skills saved to database")

    # Step 4: Print summary
    print_certification_summary(results)


def show_registry(
    tier_filter: str | None = None,
    limit: int = 50,
) -> None:
    """Show certified skills from the database."""
    init_db()
    kwargs: dict = {"limit": limit, "sort_by": "overall_score"}
    if tier_filter:
        kwargs["cert_tier"] = tier_filter.lower()

    skills = list_skills(**kwargs)
    if not skills:
        print("  No certified skills found. Run `python curate.py` first.")
        return

    print(f"\n{'='*75}")
    print(f"  WH-CERT Registry — {len(skills)} skills")
    if tier_filter:
        print(f"  Filter: {tier_filter.upper()} tier only")
    print(f"{'='*75}\n")

    for s in skills:
        tier_display = s.cert_tier.value.upper()
        stars_str = f"★{s.github_stars:,}" if s.github_stars else ""
        print(
            f"  [{tier_display:>12}]  {s.overall_score:.2f}  "
            f"{s.name:<35} {stars_str:>10}  "
            f"{s.line_count:>4}L  {s.source_repo}"
        )
        if s.description:
            print(f"                  {s.description[:65]}")
    print()


def show_stats() -> None:
    """Show certification statistics."""
    init_db()
    stats = get_stats()
    total = stats["total_skills"]

    print(f"\n{'='*50}")
    print(f"  WH-CERT Statistics")
    print(f"{'='*50}")
    print(f"  Total skills:    {total}")
    print(f"  GOLD:            {stats['gold']}")
    print(f"  SILVER:          {stats['silver']}")
    print(f"  BRONZE:          {stats['bronze']}")
    print(f"  UNCERTIFIED:     {stats['uncertified']}")
    if total > 0:
        certified = total - stats["uncertified"]
        print(f"  Cert rate:       {certified/total:.0%} ({certified}/{total})")
    print(f"  Avg score:       {stats['avg_score']:.3f}")
    print(f"  Avg confidence:  {stats['avg_confidence']:.3f}")
    print(f"{'='*50}\n")


def show_audit(grade_filter: str | None = None) -> None:
    """Display the last raw skill audit from JSON."""
    audit_path = Path("data/skill_audit.json")
    if not audit_path.exists():
        print("No audit found. Run `python curate.py` first.")
        sys.exit(1)

    with open(audit_path) as f:
        results = json.load(f)

    if grade_filter:
        grade_filter = grade_filter.upper()
        results = [
            r for r in results
            if r.get("score", {}).get("grade") == grade_filter
        ]

    print(f"\n{'='*80}")
    print(f"  Skill Quality Audit — {len(results)} skills")
    if grade_filter:
        print(f"  Filtered: grade {grade_filter} only")
    print(f"{'='*80}\n")

    grades: dict[str, int] = {}
    for r in results:
        g = r.get("score", {}).get("grade", "?")
        grades[g] = grades.get(g, 0) + 1

    for g in ["S", "A", "B", "C", "D", "F"]:
        count = grades.get(g, 0)
        if count > 0:
            bar = "█" * count
            print(f"  {g}: {bar} ({count})")
    print()

    for r in results:
        score_data = r.get("score", {})
        grade = score_data.get("grade", "?")
        overall = score_data.get("overall", 0)
        name = r.get("name", "unknown")
        repo = r.get("source_repo", "")
        lines = r.get("line_count", 0)
        stars = r.get("github_stars", 0)
        desc = r.get("description", "")[:60]

        stars_str = f"★{stars:,}" if stars else ""
        print(f"  [{grade}] {overall:.2f}  {name:<35} {stars_str:>10}  {lines:>4}L  {repo}")
        if desc:
            print(f"          {desc}")
        flags = score_data.get("flags", [])
        if flags:
            for flag in flags[:2]:
                print(f"          ⚠ {flag}")
        print()


def run_benchmark_cli(
    file_path: str,
    job_ids: str | None = None,
    test_set: str = "tune",
    runs_per_job: int = 1,
    paired: bool = False,
) -> None:
    """Run work-sample benchmark on a markdown-packaged agent candidate."""
    from benchmarks.fixtures import ALL_JOBS, TUNE_JOBS, HOLDOUT_JOBS, JOBS_BY_ID
    from evaluate.sandbox import (
        print_leaderboard,
        run_benchmark_suite,
        run_paired_benchmark_suite,
        save_results,
    )

    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    content = path.read_text()
    parsed = parse_skill_md(content, source_repo="local", source_url=str(path))

    # Select jobs
    if job_ids:
        ids = [j.strip() for j in job_ids.split(",")]
        jobs = [JOBS_BY_ID[jid] for jid in ids if jid in JOBS_BY_ID]
        missing = [jid for jid in ids if jid not in JOBS_BY_ID]
        if missing:
            print(f"  Unknown job IDs: {missing}")
            print(f"  Available: {list(JOBS_BY_ID.keys())}")
            sys.exit(1)
    elif test_set == "tune":
        jobs = TUNE_JOBS
    elif test_set == "holdout":
        jobs = HOLDOUT_JOBS
    else:
        jobs = ALL_JOBS

    mode = "Paired" if paired else "Standard"
    print(f"\n[AgentArena] Work-Sample Benchmark ({mode})")
    print(f"  Skill: {parsed.name or path.name}")
    print(f"  Jobs:  {len(jobs)} ({test_set} set)")
    if runs_per_job > 1:
        print(f"  Runs per job: {runs_per_job}")

    if paired:
        results = run_paired_benchmark_suite(
            parsed, jobs, runs_per_job=runs_per_job,
        )
    else:
        results = run_benchmark_suite(parsed, jobs, runs_per_job=runs_per_job)

    save_results(parsed.name or path.name, results)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Legacy artifact certification plus markdown-packaged agent benchmarking"
    )
    parser.add_argument(
        "--search", action="store_true",
        help="Also search GitHub for SKILL.md files (slower)",
    )
    parser.add_argument(
        "--max", type=int, default=100,
        help="Max results from GitHub search (default: 100)",
    )
    parser.add_argument(
        "--deep", action="store_true",
        help="Run Stage 2 LLM evaluation (required for Silver+)",
    )
    parser.add_argument(
        "--certify-file", type=str,
        help="Certify a single local SKILL.md file",
    )
    parser.add_argument(
        "--show-registry", action="store_true",
        help="Show certified skills from database",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show certification statistics",
    )
    parser.add_argument(
        "--show-audit", action="store_true",
        help="Show last raw audit results (JSON)",
    )
    parser.add_argument(
        "--grade", type=str,
        help="Filter audit/registry by grade or tier",
    )
    parser.add_argument(
        "--benchmark", type=str, metavar="FILE",
        help="Run work-sample benchmark on a markdown-packaged agent config or SKILL.md artifact",
    )
    parser.add_argument(
        "--jobs", type=str,
        help="Comma-separated job IDs to run (default: all)",
    )
    parser.add_argument(
        "--leaderboard", action="store_true",
        help="Show work-sample benchmark leaderboard",
    )
    parser.add_argument(
        "--test-set", type=str, choices=["tune", "holdout", "all"],
        default="tune",
        help="Which benchmark jobs to run: tune (default), holdout, or all",
    )
    parser.add_argument(
        "--runs", type=int, default=1,
        help="Number of runs per job (scores are averaged)",
    )
    parser.add_argument(
        "--paired", action="store_true",
        help="Run paired A/B benchmark (skill vs no-skill baseline)",
    )
    parser.add_argument(
        "--tournament", action="store_true",
        help="Run weekly AgentArena tournaments for active categories",
    )
    parser.add_argument(
        "--tournament-category", type=str, metavar="CAT",
        help="Run tournament for a specific category only (e.g., code-review)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Estimate tournament costs without running (use with --tournament)",
    )
    args = parser.parse_args()

    if args.tournament:
        from tournament.scheduler import (
            run_weekly_agent_tournaments,
            run_weekly_tournaments,
        )
        if args.tournament_category and "/" in args.tournament_category:
            # Agent-native: --tournament-category software-engineering/software-engineer-agent
            field, role = args.tournament_category.split("/", 1)
            run_weekly_agent_tournaments(
                fields_roles=[(field, role)],
                dry_run=args.dry_run,
            )
        elif args.tournament_category:
            # Legacy: --tournament-category code-review
            run_weekly_tournaments(
                categories=[args.tournament_category],
                dry_run=args.dry_run,
                runs_per_task=args.runs,
            )
        else:
            # Default: run agent-native tournaments for all active field/role pairs
            run_weekly_agent_tournaments(dry_run=args.dry_run)
        return

    if args.benchmark:
        run_benchmark_cli(
            args.benchmark,
            job_ids=args.jobs,
            test_set=args.test_set,
            runs_per_job=args.runs,
            paired=args.paired,
        )
        return

    if args.leaderboard:
        from evaluate.sandbox import print_leaderboard
        print_leaderboard()
        return

    if args.certify_file:
        certify_local_file(args.certify_file, deep=args.deep)
        return

    if args.show_registry:
        show_registry(tier_filter=args.grade)
        return

    if args.stats:
        show_stats()
        return

    if args.show_audit or (args.grade and not args.show_registry):
        show_audit(grade_filter=args.grade)
        return

    # Full pipeline: scrape → certify → persist
    run_full_pipeline(
        search=args.search,
        max_results=args.max,
        deep=args.deep,
    )


if __name__ == "__main__":
    main()
