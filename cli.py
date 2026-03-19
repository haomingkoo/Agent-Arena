"""
AgentArena CLI — AI agent benchmark tool.

Clean subcommand interface for scoring, scanning, and benchmarking
SKILL.md files. Wraps the existing evaluation pipeline.

Usage:
    agentarena score SKILL.md              # Stage 1 heuristic score (no API key)
    agentarena scan SKILL.md               # Safety scan (no API key)
    agentarena benchmark SKILL.md          # Work-sample benchmark (needs ANTHROPIC_API_KEY)
    agentarena benchmark SKILL.md --paired # Paired A/B benchmark
    agentarena leaderboard                 # Show leaderboard
    agentarena serve                       # Start the API server

Legacy alias:
    wh-bench ...                           # Backward-compatible command
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _read_skill(file_path: str) -> tuple[str, Path]:
    """Read a SKILL.md file and return (content, path). Exits on error."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: file not found: {file_path}")
        sys.exit(1)
    return path.read_text(), path


def cmd_score(args: argparse.Namespace) -> None:
    """Stage 1 heuristic score — no API key needed."""
    from evaluate.heuristic import score_skill_stage1
    from evaluate.rubric import parse_skill_md

    content, path = _read_skill(args.file)
    parsed = parse_skill_md(content, source_repo="local", source_url=str(path))

    print(f"\n  Scoring: {parsed.name or path.name}")
    print(f"  Lines: {parsed.line_count}  Tokens: ~{parsed.token_estimate}")

    score = score_skill_stage1(parsed)

    print(f"\n  Overall: {score.overall:.2f}  Grade: {score.grade}  Confidence: {score.confidence:.2f}")
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
    for dim_name, val in dims:
        bar = "\u2588" * int(val * 20) + "\u2591" * (20 - int(val * 20))
        print(f"    {dim_name:<22} {bar} {val:.2f}")

    if score.flags:
        print(f"\n  Flags:")
        for flag in score.flags:
            print(f"    ! {flag}")
    if score.strengths:
        print(f"\n  Strengths:")
        for s in score.strengths:
            print(f"    + {s}")
    print()


def cmd_scan(args: argparse.Namespace) -> None:
    """Safety scan — no API key needed."""
    from evaluate.rubric import parse_skill_md
    from evaluate.safety import check_content_safety

    content, path = _read_skill(args.file)
    parsed = parse_skill_md(content, source_repo="local", source_url=str(path))

    print(f"\n  Safety scan: {parsed.name or path.name}")

    threats = check_content_safety(parsed)

    if threats:
        print(f"\n  THREATS DETECTED ({len(threats)}):")
        for threat in threats:
            print(f"    !! {threat}")
    else:
        print(f"\n  No threats detected. Skill passes safety scan.")
    print()


def cmd_benchmark(args: argparse.Namespace) -> None:
    """Work-sample benchmark — needs ANTHROPIC_API_KEY."""
    from curate import run_benchmark_cli

    run_benchmark_cli(
        file_path=args.file,
        job_ids=args.jobs,
        test_set=args.test_set,
        runs_per_job=args.runs,
        paired=args.paired,
    )


def cmd_leaderboard(args: argparse.Namespace) -> None:
    """Show benchmark leaderboard."""
    from evaluate.sandbox import print_leaderboard

    print_leaderboard()


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the API server."""
    import uvicorn

    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def cmd_jd_refresh(args: argparse.Namespace) -> None:
    """Refresh one or more JD corpora from ATS sources."""
    from ingest.jd.refresh import refresh_lane_corpus

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config file not found: {args.config}")
        sys.exit(1)

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {args.config}: {exc}")
        sys.exit(1)

    lanes = config.get("lanes", [])
    if not isinstance(lanes, list) or not lanes:
        print("Error: config must contain a non-empty 'lanes' list")
        sys.exit(1)

    selected = []
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        if args.field and lane.get("field") != args.field:
            continue
        if args.role and lane.get("role") != args.role:
            continue
        selected.append(lane)

    if not selected:
        target = f"{args.field or '*'} / {args.role or '*'}"
        print(f"Error: no lanes matched selection: {target}")
        sys.exit(1)

    for lane in selected:
        field = lane["field"]
        role = lane["role"]
        role_filter = lane.get("role_filter", "")
        max_per_source = args.max_per_source or lane.get("max_per_source", 50)
        sources = lane.get("sources", [])

        print(f"\nRefreshing JD corpus for {field}/{role}")
        print(f"  Sources: {len(sources)}  Role filter: {role_filter or '—'}")

        result = refresh_lane_corpus(
            field=field,
            role=role,
            sources=sources,
            role_filter=role_filter,
            max_per_source=max_per_source,
        )

        print(
            "  Result: "
            f"fetched={result['total_fetched']} "
            f"new={result['new_postings']} "
            f"deduped={result['deduped']} "
            f"corpus={result['corpus_version']}"
        )
        if result["errors"]:
            print("  Errors:")
            for err in result["errors"]:
                print(f"    - {err}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agentarena",
        description="AgentArena — AI agent benchmark tool",
    )
    parser.add_argument(
        "--version", action="version", version="AgentArena 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── score ─────────────────────────────────────────────────────────────
    p_score = subparsers.add_parser(
        "score",
        help="Stage 1 heuristic score (no API key needed)",
    )
    p_score.add_argument("file", help="Path to a SKILL.md file")
    p_score.set_defaults(func=cmd_score)

    # ── scan ──────────────────────────────────────────────────────────────
    p_scan = subparsers.add_parser(
        "scan",
        help="Safety scan for prompt injection and threats (no API key needed)",
    )
    p_scan.add_argument("file", help="Path to a SKILL.md file")
    p_scan.set_defaults(func=cmd_scan)

    # ── benchmark ─────────────────────────────────────────────────────────
    p_bench = subparsers.add_parser(
        "benchmark",
        help="Run work-sample benchmark (needs ANTHROPIC_API_KEY)",
    )
    p_bench.add_argument("file", help="Path to a SKILL.md file")
    p_bench.add_argument(
        "--jobs", type=str, default=None,
        help="Comma-separated job IDs to run (default: all in test set)",
    )
    p_bench.add_argument(
        "--test-set", type=str, choices=["tune", "holdout", "all"],
        default="tune",
        help="Which benchmark jobs to run (default: tune)",
    )
    p_bench.add_argument(
        "--runs", type=int, default=1,
        help="Number of runs per job (scores are averaged)",
    )
    p_bench.add_argument(
        "--paired", action="store_true",
        help="Run paired A/B benchmark (skill vs no-skill baseline)",
    )
    p_bench.set_defaults(func=cmd_benchmark)

    # ── leaderboard ───────────────────────────────────────────────────────
    p_lb = subparsers.add_parser(
        "leaderboard",
        help="Show benchmark leaderboard",
    )
    p_lb.set_defaults(func=cmd_leaderboard)

    # ── serve ─────────────────────────────────────────────────────────────
    p_serve = subparsers.add_parser(
        "serve",
        help="Start the API server",
    )
    p_serve.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    p_serve.add_argument(
        "--port", type=int, default=8000,
        help="Port to bind to (default: 8000)",
    )
    p_serve.add_argument(
        "--reload", action="store_true",
        help="Enable auto-reload for development",
    )
    p_serve.set_defaults(func=cmd_serve)

    # ── jd-refresh ────────────────────────────────────────────────────────
    p_jd = subparsers.add_parser(
        "jd-refresh",
        help="Refresh JD corpora from configured ATS sources",
    )
    p_jd.add_argument(
        "--config",
        required=True,
        help="Path to lane/source JSON config",
    )
    p_jd.add_argument(
        "--field",
        type=str,
        default="",
        help="Optional field filter",
    )
    p_jd.add_argument(
        "--role",
        type=str,
        default="",
        help="Optional role filter",
    )
    p_jd.add_argument(
        "--max-per-source",
        type=int,
        default=0,
        help="Optional override for max postings per ATS source",
    )
    p_jd.set_defaults(func=cmd_jd_refresh)

    # ── dispatch ──────────────────────────────────────────────────────────
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
