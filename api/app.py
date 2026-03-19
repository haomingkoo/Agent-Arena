"""
AgentArena API — FastAPI backend for the AI agent benchmark leaderboard.

Serves the React frontend and provides endpoints for leaderboard data,
agent tournament data, legacy artifact details, safety scanning, and heuristic scoring.

Run: uvicorn api.app:app --port 8000
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from evaluate.heuristic import score_skill_stage1
from evaluate.rubric import ParsedSkill, parse_skill_md
from evaluate.safety import scan_text
from evaluate.sandbox import RESULTS_PATH, get_leaderboard_data
from store.db import (
    get_stats, init_db, list_skills, get_skill, search_skills,
    list_categories, list_tournaments, get_tournament, get_tournament_entries,
    get_category_leaderboard, get_coaching_for_skill, get_rating_history,
    list_skills_by_category,
    get_agent_leaderboard, get_agent_version_detail, get_run_trace,
    list_agent_fields_roles,
    list_review_queue, get_review_candidate_detail, apply_review_decision,
    get_review_history,
    list_jd_postings, get_jd_corpus_stats, get_latest_corpus_version,
    list_candidate_leads, get_lead_stats, resolve_candidate_lead,
    list_duplicate_groups, scan_and_record_duplicates,
)
from store.models import CertTier

# ── Rate limiter ─────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AgentArena API",
    description="AI agent benchmark leaderboard and quality scoring",
    version="2.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Security headers middleware ──────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = "default-src 'none'"
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# CORS
ALLOWED_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
def startup():
    init_db()


# ── Input validation ─────────────────────────────────────────────────────────

SEARCH_MAX_LEN = 200
CONTENT_MAX_LEN = 50_000


def _sanitize(text: str, max_len: int = SEARCH_MAX_LEN) -> str:
    """Sanitize user input: strip, truncate, remove control chars."""
    text = text.strip()[:max_len]
    return re.sub(r"[\x00-\x1f\x7f]", "", text)


ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")


def _require_admin(request: Request) -> None:
    """Verify admin API key for state-changing endpoints.

    Checks the Authorization header for a Bearer token matching ADMIN_API_KEY.
    If ADMIN_API_KEY is not set, all admin requests are blocked in production.
    """
    if not ADMIN_API_KEY:
        raise HTTPException(403, "Admin API key not configured")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != ADMIN_API_KEY:
        raise HTTPException(401, "Invalid or missing admin API key")


def _lane_metadata(field: str, role: str) -> dict[str, str]:
    """Return latest lane metadata for a field/role with sane defaults."""
    category = f"{field}/{role}"
    tournaments = list_tournaments(category=category, limit=1)
    if tournaments:
        tournament = tournaments[0]
        return {
            "runtime_class": tournament.get("runtime_class") or "standard",
            "task_pack_version": tournament.get("task_pack_version") or "v1",
            "tournament_type": tournament.get("tournament_type") or "standardized",
        }
    return {
        "runtime_class": "standard",
        "task_pack_version": "v1",
        "tournament_type": "standardized",
    }


# ── Request/response models ──────────────────────────────────────────────────

class ScanRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def limit_content(cls, v: str) -> str:
        return v[:CONTENT_MAX_LEN]


class ScoreRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def limit_content(cls, v: str) -> str:
        return v[:CONTENT_MAX_LEN]


# ── API endpoints ────────────────────────────────────────────────────────────

@app.get("/api/health")
@limiter.limit("30/minute")
def health(request: Request):
    return {"status": "ok", "service": "agentarena", "version": "2.0.0"}


@app.get("/api/leaderboard")
@limiter.limit("60/minute")
def leaderboard(request: Request):
    """Legacy prompt-artifact leaderboard ranked by upgrade over baseline."""
    data = get_leaderboard_data()
    return {"skills": data, "count": len(data)}


@app.get("/api/skill/{name}")
@limiter.limit("60/minute")
def skill_detail(request: Request, name: str, response: Response):
    """Legacy prompt-artifact detail: scores, per-job results, certification."""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-12-31"
    response.headers["Link"] = '</api/agents/fields>; rel="successor-version"'
    name = _sanitize(name, max_len=200)

    # Try leaderboard data first (has benchmark results)
    leaderboard_data = get_leaderboard_data()
    bench_entry = None
    for entry in leaderboard_data:
        if entry.get("skill_name") == name:
            bench_entry = entry
            break

    # Try DB for certification data
    db_skills = search_skills(name, limit=1)
    db_skill = db_skills[0] if db_skills else None

    if not bench_entry and not db_skill:
        raise HTTPException(404, f"Skill not found: {name}")

    result: dict = {"name": name}

    if bench_entry:
        result["benchmark"] = {
            "avg_overall": bench_entry.get("avg_overall", 0),
            "avg_baseline": bench_entry.get("avg_baseline"),
            "avg_upgrade": bench_entry.get("avg_upgrade"),
            "jobs_run": bench_entry.get("jobs_run", 0),
            "jobs_passed": bench_entry.get("jobs_passed", 0),
            "paired": bench_entry.get("paired", False),
            "timestamp": bench_entry.get("timestamp", ""),
            "results": bench_entry.get("results", []),
        }

    if db_skill:
        result["certification"] = {
            "tier": db_skill.cert_tier.value,
            "overall_score": db_skill.overall_score,
            "confidence": db_skill.confidence,
            "dimensions": {
                "frequency_value": db_skill.frequency_value,
                "capability_upgrade": db_skill.capability_upgrade,
                "specificity": db_skill.specificity,
                "token_efficiency": db_skill.token_efficiency,
                "source_credibility": db_skill.source_credibility,
                "trigger_clarity": db_skill.trigger_clarity,
                "methodology_depth": db_skill.methodology_depth,
                "llm_quality": db_skill.llm_quality,
            },
            "flags": json.loads(db_skill.flags_json),
            "strengths": json.loads(db_skill.strengths_json),
            "llm_reasoning": db_skill.llm_reasoning,
            "cert_date": db_skill.cert_date,
        }
        result["source"] = {
            "repo": db_skill.source_repo,
            "url": db_skill.source_url,
            "stars": db_skill.github_stars,
            "lines": db_skill.line_count,
            "tokens": db_skill.token_estimate,
        }

    return result


@app.get("/api/stats")
@limiter.limit("30/minute")
def stats(request: Request):
    """Aggregate stats across legacy artifact benchmarks, certifications, and tournaments."""
    db_stats = get_stats()

    # Benchmark stats
    bench_data = get_leaderboard_data()
    bench_stats = {
        "skills_benchmarked": len(bench_data),
        "avg_score": round(
            sum(e["avg_overall"] for e in bench_data) / len(bench_data), 3
        ) if bench_data else 0,
        "paired_count": sum(1 for e in bench_data if e.get("paired")),
    }

    if bench_data:
        upgrades = [
            e["avg_upgrade"] for e in bench_data
            if e.get("avg_upgrade") is not None
        ]
        if upgrades:
            bench_stats["avg_upgrade"] = round(
                sum(upgrades) / len(upgrades), 3
            )
            bench_stats["best_upgrade"] = round(max(upgrades), 3)

    # Tournament stats
    cats = list_categories()
    tournaments = list_tournaments(limit=100)

    return {
        "certification": db_stats,
        "benchmark": bench_stats,
        "tournaments": {"total": len(tournaments), "categories": len(cats)},
    }


@app.post("/api/scan")
@limiter.limit("10/minute")
def scan_content(request: Request, req: ScanRequest):
    """Safety scan of pasted prompt-artifact content such as SKILL.md. No API key needed."""
    threats = scan_text(req.content)
    return {
        "safe": len(threats) == 0,
        "threats": threats,
        "threat_count": len(threats),
    }


@app.post("/api/score")
@limiter.limit("10/minute")
def score_content(request: Request, req: ScoreRequest):
    """Stage 1 heuristic score of pasted prompt-artifact content. No API key needed."""
    parsed = parse_skill_md(req.content, source_repo="user-submitted")
    score = score_skill_stage1(parsed)

    return {
        "name": parsed.name or "untitled",
        "grade": score.grade,
        "overall": score.overall,
        "confidence": score.confidence,
        "dimensions": {
            "frequency_value": score.frequency_value,
            "capability_upgrade": score.capability_upgrade,
            "specificity": score.specificity,
            "token_efficiency": score.token_efficiency,
            "source_credibility": score.source_credibility,
            "trigger_clarity": score.trigger_clarity,
            "methodology_depth": score.methodology_depth,
        },
        "flags": score.flags,
        "strengths": score.strengths,
        "line_count": parsed.line_count,
        "token_estimate": parsed.token_estimate,
    }


# ── Category endpoints ───────────────────────────────────────────────────────


@app.get("/api/categories")
@limiter.limit("60/minute")
def list_all_categories(request: Request):
    """List legacy prompt-artifact categories with counts."""
    cats = list_categories()
    return {"categories": cats, "count": len(cats)}


@app.get("/api/categories/{slug}")
@limiter.limit("60/minute")
def category_detail(request: Request, slug: str):
    """Legacy category detail: artifacts, latest tournament, rating leaderboard."""
    slug = _sanitize(slug)

    # Verify category exists
    cats = list_categories(active_only=False)
    cat = next((c for c in cats if c["slug"] == slug), None)
    if not cat:
        raise HTTPException(404, f"Category not found: {slug}")

    skills = list_skills_by_category(slug, limit=50)
    leaderboard = get_category_leaderboard(slug)
    tournaments = list_tournaments(category=slug, limit=10)

    return {
        "category": cat,
        "skills": [
            {"id": s.id, "name": s.name, "overall_score": s.overall_score}
            for s in skills
        ],
        "leaderboard": leaderboard,
        "recent_tournaments": tournaments,
    }


# ── Tournament endpoints ────────────────────────────────────────────────────


@app.get("/api/tournaments")
@limiter.limit("60/minute")
def list_all_tournaments(request: Request, category: str = Query(None)):
    """List recent tournaments, optionally filtered by category."""
    cat = _sanitize(category) if category else None
    tournaments = list_tournaments(category=cat, limit=20)
    return {"tournaments": tournaments, "count": len(tournaments)}


@app.get("/api/tournaments/{tournament_id}")
@limiter.limit("60/minute")
def tournament_detail(request: Request, tournament_id: str):
    """Full tournament results: entries, task breakdowns."""
    tournament_id = _sanitize(tournament_id)

    t = get_tournament(tournament_id)
    if not t:
        raise HTTPException(404, "Tournament not found")

    entries = get_tournament_entries(tournament_id)
    return {"tournament": t, "entries": entries}


# ── Category leaderboard (Glicko-2) ─────────────────────────────────────────


@app.get("/api/leaderboard/{category}")
@limiter.limit("60/minute")
def category_leaderboard(request: Request, category: str):
    """Legacy artifact Glicko-2 leaderboard within a category."""
    category = _sanitize(category)
    leaderboard = get_category_leaderboard(category)
    return {"category": category, "leaderboard": leaderboard}


# ── Coaching ─────────────────────────────────────────────────────────────────


@app.get("/api/coaching/{skill_id}")
@limiter.limit("60/minute")
def skill_coaching(request: Request, skill_id: str):
    """Coaching recommendations for a legacy prompt artifact."""
    skill_id = _sanitize(skill_id)
    coaching = get_coaching_for_skill(skill_id, limit=5)
    return {"skill_id": skill_id, "coaching": coaching}


# ── Rating history ───────────────────────────────────────────────────────────


@app.get("/api/skill/{skill_id}/rating-history")
@limiter.limit("60/minute")
def rating_history(
    request: Request,
    skill_id: str,
    response: Response,
    category: str = Query(...),
):
    """Rating over time for sparkline charts."""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-12-31"
    response.headers["Link"] = '</api/agents/fields>; rel="successor-version"'
    skill_id = _sanitize(skill_id)
    category = _sanitize(category)
    history = get_rating_history(skill_id, category, limit=52)
    return {"skill_id": skill_id, "category": category, "history": history}


# ── Agent-native endpoints ──────────────────────────────────────────────────


@app.get("/api/agents/fields")
@limiter.limit("60/minute")
def list_fields(request: Request):
    """List available fields with their roles and agent counts."""
    fields_roles = list_agent_fields_roles()

    # Group by field
    fields: dict[str, dict] = {}
    for row in fields_roles:
        field = row["field"]
        if field not in fields:
            fields[field] = {
                "field": field,
                "roles": [],
                "total_agents": 0,
            }
        fields[field]["roles"].append({
            "role": row["role"],
            "agent_count": row["agent_count"],
            **_lane_metadata(field, row["role"]),
        })
        fields[field]["total_agents"] += row["agent_count"]

    return {
        "fields": list(fields.values()),
        "count": len(fields),
    }


@app.get("/api/agents/leaderboard/{field}/{role}")
@limiter.limit("60/minute")
def agent_leaderboard(request: Request, field: str, role: str):
    """Agent-native Glicko-2 leaderboard for a field/role."""
    field = _sanitize(field)
    role = _sanitize(role)

    leaderboard = get_agent_leaderboard(field, role)
    lane_metadata = _lane_metadata(field, role)
    return {
        "field": field,
        "role": role,
        **lane_metadata,
        "leaderboard": leaderboard,
        "count": len(leaderboard),
    }


@app.get("/api/agents/{version_id}")
@limiter.limit("60/minute")
def agent_detail(request: Request, version_id: str):
    """Full agent version detail with benchmark results and rating history."""
    version_id = _sanitize(version_id)

    detail = get_agent_version_detail(version_id)
    if not detail:
        raise HTTPException(404, f"Agent version not found: {version_id}")

    return detail


@app.get("/api/traces/{trace_id}")
@limiter.limit("60/minute")
def trace_detail(request: Request, trace_id: str):
    """Full benchmark trace detail for one agent task execution."""
    trace_id = _sanitize(trace_id)

    trace = get_run_trace(trace_id)
    if not trace:
        raise HTTPException(404, f"Trace not found: {trace_id}")

    payload = trace.model_dump()
    if trace.tournament_id:
        tournament = get_tournament(trace.tournament_id)
        if tournament:
            payload["runtime_class"] = tournament.get("runtime_class") or "standard"
            payload["task_pack_version"] = tournament.get("task_pack_version") or "v1"
            payload["tournament_type"] = tournament.get("tournament_type") or "standardized"

    return {"trace": payload}


# ── Human Review API ────────────────────────────────────────────────────────


class ReviewActionRequest(BaseModel):
    reviewer: str
    action: str  # approve | relabel | reject | send-to-qualification | unsupported
    reason: str = ""
    note: str = ""
    new_field: str = ""
    new_role: str = ""

    @field_validator("reviewer")
    @classmethod
    def reviewer_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reviewer is required")
        return v.strip()

    @field_validator("action")
    @classmethod
    def action_valid(cls, v: str) -> str:
        allowed = {"approve", "relabel", "reject", "send-to-qualification", "unsupported"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v


_ACTION_TO_STATE = {
    "approve": "approved-public",
    "relabel": "relabelled",
    "reject": "rejected",
    "send-to-qualification": "qualification-required",
    "unsupported": "unsupported",
}


@app.get("/api/review/queue")
@limiter.limit("30/minute")
def review_queue(
    request: Request,
    review_state: str = "",
    field: str = "",
    role: str = "",
    limit: int = Query(default=50, le=200),
):
    """List agent versions needing or having review."""
    candidates = list_review_queue(
        review_state=_sanitize(review_state) if review_state else "",
        field=_sanitize(field) if field else "",
        role=_sanitize(role) if role else "",
        limit=limit,
    )
    return {"candidates": candidates, "count": len(candidates)}


@app.get("/api/review/candidate/{version_id}")
@limiter.limit("30/minute")
def review_candidate_detail(request: Request, version_id: str):
    """Full review detail for one agent version (admin-only — exposes system prompts)."""
    _require_admin(request)
    version_id = _sanitize(version_id)
    detail = get_review_candidate_detail(version_id)
    if not detail:
        raise HTTPException(404, f"Agent version not found: {version_id}")
    return detail


@app.post("/api/review/candidate/{version_id}/decide")
@limiter.limit("10/minute")
def review_decide(request: Request, version_id: str, body: ReviewActionRequest):
    """Apply a review decision (approve, relabel, reject, etc.)."""
    _require_admin(request)
    version_id = _sanitize(version_id)
    new_state = _ACTION_TO_STATE.get(body.action)
    if not new_state:
        raise HTTPException(400, f"Unknown action: {body.action}")

    try:
        decision_id = apply_review_decision(
            version_id=version_id,
            reviewer=body.reviewer,
            action=body.action,
            new_state=new_state,
            reason=body.reason,
            note=body.note,
            new_field=body.new_field,
            new_role=body.new_role,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"decision_id": decision_id, "new_state": new_state, "action": body.action}


@app.get("/api/review/candidate/{version_id}/history")
@limiter.limit("30/minute")
def review_history(request: Request, version_id: str):
    """All review decisions for a version, newest first."""
    version_id = _sanitize(version_id)
    decisions = get_review_history(version_id)
    return {"decisions": decisions, "count": len(decisions)}


# ── JD Corpus API ──────────────────────────────────────────────────────────


@app.get("/api/jd/postings")
@limiter.limit("30/minute")
def jd_postings(
    request: Request,
    field: str = "",
    role: str = "",
    source_ats: str = "",
    limit: int = Query(default=50, le=200),
):
    """List job postings with optional filters."""
    postings = list_jd_postings(
        field=_sanitize(field) if field else "",
        role=_sanitize(role) if role else "",
        source_ats=_sanitize(source_ats) if source_ats else "",
        limit=limit,
    )
    return {"postings": postings, "count": len(postings)}


@app.get("/api/jd/corpus/{field}/{role}")
@limiter.limit("30/minute")
def jd_corpus_detail(request: Request, field: str, role: str):
    """Latest corpus version and stats for a field/role."""
    field = _sanitize(field)
    role = _sanitize(role)
    latest = get_latest_corpus_version(field, role)
    stats = get_jd_corpus_stats(field, role)
    return {
        "field": field,
        "role": role,
        "latest_version": latest,
        "stats": stats,
    }


# ── Candidate Lead API ─────────────────────────────────────────────────────


@app.get("/api/leads")
@limiter.limit("30/minute")
def leads_list(
    request: Request,
    source_type: str = "",
    review_state: str = "",
    resolution_state: str = "",
    limit: int = Query(default=50, le=200),
):
    """List candidate leads from lead-gen sources."""
    leads = list_candidate_leads(
        source_type=_sanitize(source_type) if source_type else "",
        review_state=_sanitize(review_state) if review_state else "",
        resolution_state=_sanitize(resolution_state) if resolution_state else "",
        limit=limit,
    )
    return {"leads": leads, "count": len(leads)}


@app.get("/api/leads/stats")
@limiter.limit("30/minute")
def leads_stats(request: Request):
    """Summary stats for the lead pipeline."""
    return get_lead_stats()


# ── Duplicate Detection API ────────────────────────────────────────────────


@app.get("/api/duplicates")
@limiter.limit("30/minute")
def duplicates_list(
    request: Request,
    review_state: str = "",
    limit: int = Query(default=50, le=200),
):
    """List recorded duplicate groups."""
    groups = list_duplicate_groups(
        review_state=_sanitize(review_state) if review_state else "",
        limit=limit,
    )
    return {"duplicates": groups, "count": len(groups)}


@app.post("/api/duplicates/scan")
@limiter.limit("5/minute")
def duplicates_scan(request: Request):
    """Scan all lanes for duplicates and record them."""
    _require_admin(request)
    result = scan_and_record_duplicates()
    return result


# ── Static frontend (SPA) ───────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    # Serve static assets (JS, CSS, images)
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIR / "assets")),
        name="assets",
    )

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve the SPA — all non-API routes return index.html."""
        file_path = (FRONTEND_DIR / path).resolve()
        # Prevent path traversal: resolved path must stay within FRONTEND_DIR
        if file_path.is_file() and str(file_path).startswith(str(FRONTEND_DIR.resolve())):
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
