"""
Tune set — 20 benchmark jobs for the 'coding skills for solo builders' wedge.

These jobs are used for development and iteration. It's OK to look at
results from these jobs when improving skills or the harness.

DO NOT use holdout jobs (fixtures_holdout.py) for tuning.
"""
from __future__ import annotations

from evaluate.sandbox import BenchmarkJob

# ── Category: Feature Implementation ─────────────────────────────────────────

JOB_PAGINATION = BenchmarkJob(
    id="feat-pagination",
    name="Add pagination to REST endpoint",
    category="feature",
    test_set="tune",
    input_prompt=(
        "Add limit/offset pagination to the /items endpoint. "
        "Defaults: limit=20, max limit=100. "
        "Return total count in response so the client knows how many pages exist."
    ),
    input_context='''from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3

app = FastAPI()

DB_PATH = "items.db"

class Item(BaseModel):
    id: int
    name: str
    price: float

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/items")
def list_items():
    """Return all items."""
    db = get_db()
    rows = db.execute("SELECT id, name, price FROM items").fetchall()
    db.close()
    return [dict(r) for r in rows]
''',
    acceptance_criteria=[
        "Endpoint accepts limit and offset query parameters",
        "Default limit is 20, max limit is 100",
        "Negative offset is rejected with 422 or 400",
        "Response includes total count of items",
        "Response includes the paginated items list",
        "Existing behavior preserved when no params passed (returns first 20)",
    ],
    risk_level="low",
    stack="python/fastapi",
    good_looks_like=(
        "Uses FastAPI Query() with validation (ge=0, le=100). "
        "Returns a response model with items, total, limit, offset. "
        "Uses SQL LIMIT/OFFSET. Doesn't load all rows into memory. "
        "Adds type hints. Handles edge case where offset > total."
    ),
)

JOB_DARK_MODE = BenchmarkJob(
    id="feat-dark-mode",
    name="Add dark mode toggle to React app",
    category="feature",
    test_set="tune",
    input_prompt=(
        "Add a toggle that switches between light and dark mode. "
        "Persist the user's preference so it survives page reload. "
        "Use the system preference as the default if no saved preference exists."
    ),
    input_context='''// App.tsx
import React from "react";

function App() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <nav className="bg-gray-100 p-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">My App</h1>
        {/* TODO: dark mode toggle */}
      </nav>
      <main className="p-8">
        <div className="bg-gray-50 rounded-lg p-6 shadow">
          <h2 className="text-lg font-semibold mb-4">Dashboard</h2>
          <p className="text-gray-600">Welcome to the app.</p>
        </div>
      </main>
    </div>
  );
}

export default App;

// tailwind.config.js
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
''',
    acceptance_criteria=[
        "Toggle button is visible and accessible (keyboard navigable)",
        "Clicking toggle switches between light and dark themes",
        "Preference is saved to localStorage and persists across page reloads",
        "System preference (prefers-color-scheme) is used as default when no saved preference exists",
        "No flash of wrong theme on page load",
    ],
    risk_level="low",
    stack="react/typescript/tailwind",
    good_looks_like=(
        "Enables darkMode: 'class' in tailwind config. Uses dark: variants. "
        "Reads system preference via matchMedia. Saves to localStorage. "
        "Uses useEffect to apply class to document root before first paint."
    ),
)

JOB_RATE_LIMITING = BenchmarkJob(
    id="feat-rate-limiting",
    name="Add rate limiting to API endpoints",
    category="feature",
    test_set="tune",
    input_prompt=(
        "Add rate limiting to this API. Requirements:\n"
        "- Public endpoints: 60 requests/minute\n"
        "- Authenticated endpoints: 200 requests/minute\n"
        "- Return proper 429 responses with Retry-After header"
    ),
    input_context='''from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

app = FastAPI()
security = HTTPBearer(auto_error=False)
SECRET_KEY = "changeme"

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not creds:
        return None
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        return None

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/items")
def list_items():
    return {"items": [{"id": 1, "name": "Widget"}]}

@app.get("/dashboard")
def dashboard(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(401, "Authentication required")
    return {"message": f"Welcome {user['sub']}"}

@app.post("/orders")
def create_order(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(401, "Authentication required")
    return {"order_id": 42, "status": "created"}
''',
    acceptance_criteria=[
        "Public endpoints (/health, /items) limited to 60 req/min",
        "Authenticated endpoints (/dashboard, /orders) limited to 200 req/min",
        "Returns HTTP 429 with Retry-After header when limit exceeded",
        "Rate limits are per-client (by IP or user ID), not global",
        "Existing endpoint behavior and auth are unchanged",
    ],
    risk_level="medium",
    stack="python/fastapi",
    good_looks_like=(
        "Uses slowapi or custom middleware. Different limits for auth vs unauth. "
        "Returns Retry-After header. Limits per client, not global. "
        "Handles edge case where auth check fails (falls back to public limit)."
    ),
)

JOB_CSV_EXPORT = BenchmarkJob(
    id="feat-csv-export",
    name="Add CSV export to data table",
    category="feature",
    test_set="tune",
    input_prompt=(
        "Add a CSV download endpoint for the sales report. "
        "It should export the same data shown on the /reports page. "
        "The download filename should include today's date."
    ),
    input_context='''from flask import Flask, render_template_string
import sqlite3

app = Flask(__name__)

TEMPLATE = """
<html><body>
<h1>Sales Report</h1>
<table border="1">
  <tr><th>Date</th><th>Product</th><th>Quantity</th><th>Revenue</th></tr>
  {% for row in rows %}
  <tr><td>{{row.date}}</td><td>{{row.product}}</td><td>{{row.qty}}</td><td>${{row.revenue}}</td></tr>
  {% endfor %}
</table>
</body></html>
"""

def get_sales():
    conn = sqlite3.connect("sales.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT date, product, quantity as qty, revenue FROM sales ORDER BY date DESC"
    ).fetchall()
    conn.close()
    return rows

@app.route("/reports")
def reports():
    rows = get_sales()
    return render_template_string(TEMPLATE, rows=rows)
''',
    acceptance_criteria=[
        "New endpoint (e.g. /reports/csv) returns CSV with Content-Type text/csv",
        "Content-Disposition header sets filename with today's date",
        "CSV includes header row matching the table columns",
        "Fields with commas or special characters are properly escaped",
        "CSV data matches what the /reports page shows",
    ],
    risk_level="low",
    stack="python/flask",
    good_looks_like=(
        "Uses csv module or streaming response. Proper Content-Disposition. "
        "Reuses get_sales() to ensure consistency. Handles special chars in product names."
    ),
)


# ── Category: Bug Fix ────────────────────────────────────────────────────────

JOB_DATE_BUG = BenchmarkJob(
    id="fix-date-range",
    name="Fix off-by-one in date range filter",
    category="bugfix",
    test_set="tune",
    input_prompt=(
        "Bug: querying sales from 2026-01-01 to 2026-01-31 excludes records on Jan 31. "
        "Reproduction: insert a sale with created_at='2026-01-31 10:00:00', "
        "query with start_date=2026-01-01 and end_date=2026-01-31, record is missing. "
        "Fix the bug without breaking other date range queries."
    ),
    input_context='''from datetime import date
from fastapi import FastAPI, Query
import sqlite3

app = FastAPI()

@app.get("/sales")
def get_sales(
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    """Return sales within a date range."""
    conn = sqlite3.connect("sales.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM sales WHERE created_at >= ? AND created_at <= ?",
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
''',
    acceptance_criteria=[
        "Records on the end_date are included in results",
        "The fix handles timestamps (not just dates) — e.g. 2026-01-31 23:59:59",
        "The fix doesn't break queries where start_date == end_date",
        "The fix explains WHY the bug occurred (date vs datetime comparison)",
    ],
    risk_level="medium",
    stack="python/fastapi/sqlite",
    good_looks_like=(
        "Changes the upper bound to < end_date + 1 day (not <= end_date 23:59:59). "
        "Explains that SQLite stores datetimes as strings and '2026-01-31' < '2026-01-31 10:00:00'. "
        "Suggests adding a test for this edge case."
    ),
)

JOB_CORS = BenchmarkJob(
    id="fix-cors",
    name="Fix CORS error on preflight requests",
    category="bugfix",
    test_set="tune",
    input_prompt=(
        "Bug: POST requests from our React frontend (http://localhost:3000) to the API "
        "fail with a CORS error. GET requests work fine.\n"
        "Browser console shows: 'Access-Control-Allow-Headers' does not include 'Content-Type'.\n"
        "Fix the CORS configuration without opening it too wide."
    ),
    input_context='''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=[],
)

@app.get("/api/items")
def list_items():
    return [{"id": 1, "name": "Widget"}]

@app.post("/api/items")
def create_item(item: dict):
    return {"id": 2, **item}

@app.put("/api/items/{item_id}")
def update_item(item_id: int, item: dict):
    return {"id": item_id, **item}

@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    return {"deleted": True}
''',
    acceptance_criteria=[
        "POST requests from http://localhost:3000 succeed without CORS errors",
        "Content-Type header is allowed in requests",
        "PUT and DELETE methods also work from the frontend",
        "Does NOT use wildcard '*' for origins",
        "Explains what preflight requests are and why POST was failing",
    ],
    risk_level="medium",
    stack="python/fastapi",
    good_looks_like=(
        "Adds 'Content-Type' to allow_headers (or uses reasonable defaults). "
        "Adds POST/PUT/DELETE to allow_methods. Explains that POST with JSON body "
        "triggers a preflight OPTIONS request. Keeps origins restricted."
    ),
)

JOB_WEBSOCKET_LEAK = BenchmarkJob(
    id="fix-websocket-leak",
    name="Fix memory leak in WebSocket handler",
    category="bugfix",
    test_set="tune",
    input_prompt=(
        "Bug: Memory usage grows ~10MB/hour in production. "
        "The app handles frequent WebSocket connections and disconnections. "
        "Memory never reclaims even after clients disconnect.\n"
        "Find and fix the memory leak."
    ),
    input_context='''from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio

app = FastAPI()

# Track all connected clients
connected_clients: dict[str, WebSocket] = {}
message_history: list[dict] = []

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    connected_clients[client_id] = websocket
    message_history.append({"client": client_id, "event": "connected"})

    try:
        while True:
            data = await websocket.receive_text()
            message_history.append({"client": client_id, "message": data})

            # Broadcast to all connected clients
            for cid, ws in connected_clients.items():
                try:
                    await ws.send_text(f"{client_id}: {data}")
                except Exception:
                    pass  # Client might have disconnected
    except WebSocketDisconnect:
        message_history.append({"client": client_id, "event": "disconnected"})
        # BUG: client is never removed from connected_clients
        # BUG: message_history grows unbounded

@app.get("/stats")
def stats():
    return {
        "connected": len(connected_clients),
        "total_messages": len(message_history),
    }
''',
    acceptance_criteria=[
        "Disconnected clients are removed from connected_clients dict",
        "message_history does not grow unbounded (capped or rotated)",
        "The fix identifies BOTH leak sources (stale clients + unbounded history)",
        "Broadcast loop handles stale connections gracefully",
        "No data races introduced in the cleanup logic",
    ],
    risk_level="high",
    stack="python/fastapi/websockets",
    good_looks_like=(
        "Removes client from connected_clients in the disconnect handler. "
        "Caps message_history with a max size (deque or manual trim). "
        "Cleans up stale clients found during broadcast. "
        "Explains why both leaks cause memory growth."
    ),
)

JOB_RACE_CONDITION = BenchmarkJob(
    id="fix-race-condition",
    name="Fix race condition in counter endpoint",
    category="bugfix",
    test_set="tune",
    input_prompt=(
        "Bug: Under load, our hit counter falls behind. "
        "100 concurrent requests to /increment should produce count=100 "
        "but often produces 85-95.\n"
        "Fix the race condition."
    ),
    input_context='''from flask import Flask, jsonify
import sqlite3

app = Flask(__name__)
DB_PATH = "counter.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER)")
    conn.execute("INSERT OR IGNORE INTO counters (name, value) VALUES ('hits', 0)")
    conn.commit()
    conn.close()

@app.route("/increment", methods=["POST"])
def increment():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT value FROM counters WHERE name = 'hits'").fetchone()
    new_value = row[0] + 1
    conn.execute("UPDATE counters SET value = ? WHERE name = 'hits'", (new_value,))
    conn.commit()
    conn.close()
    return jsonify({"count": new_value})

@app.route("/count")
def count():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT value FROM counters WHERE name = 'hits'").fetchone()
    conn.close()
    return jsonify({"count": row[0]})

init_db()
''',
    acceptance_criteria=[
        "100 concurrent requests always produce count=100 (no lost updates)",
        "Uses atomic operation (UPDATE SET value = value + 1) or proper locking",
        "Explains WHY the original read-modify-write pattern fails under concurrency",
        "Does not introduce deadlock risk",
    ],
    risk_level="medium",
    stack="python/flask/sqlite",
    good_looks_like=(
        "Uses 'UPDATE counters SET value = value + 1' instead of read-modify-write. "
        "Returns the new value using RETURNING clause or a follow-up SELECT. "
        "Explains the lost update problem."
    ),
)


# ── Category: Testing ────────────────────────────────────────────────────────

JOB_WRITE_TESTS = BenchmarkJob(
    id="test-url-shortener",
    name="Write tests for URL shortener",
    category="testing",
    test_set="tune",
    input_prompt=(
        "Write a comprehensive test suite for this URL shortener module. "
        "Cover happy path, edge cases, and error cases. Use pytest."
    ),
    input_context='''import hashlib
import sqlite3
from datetime import datetime

DB_PATH = "urls.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            short_code TEXT PRIMARY KEY,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            clicks INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def shorten(url: str) -> str:
    """Create a short code for a URL. Returns existing code if URL already shortened."""
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL: must start with http:// or https://")

    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute(
        "SELECT short_code FROM urls WHERE original_url = ?", (url,)
    ).fetchone()
    if existing:
        conn.close()
        return existing[0]

    short_code = hashlib.sha256(url.encode()).hexdigest()[:8]
    conn.execute(
        "INSERT INTO urls (short_code, original_url, created_at) VALUES (?, ?, ?)",
        (short_code, url, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return short_code

def resolve(short_code: str) -> str | None:
    """Look up the original URL and increment click count."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT original_url FROM urls WHERE short_code = ?", (short_code,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?", (short_code,)
        )
        conn.commit()
        conn.close()
        return row[0]
    conn.close()
    return None

def get_stats(short_code: str) -> dict | None:
    """Get click stats for a short code."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT original_url, clicks, created_at FROM urls WHERE short_code = ?",
        (short_code,),
    ).fetchone()
    conn.close()
    if row:
        return {"url": row[0], "clicks": row[1], "created_at": row[2]}
    return None
''',
    acceptance_criteria=[
        "Tests cover shorten() happy path — valid URL returns 8-char code",
        "Tests cover shorten() with invalid URL — raises ValueError",
        "Tests cover shorten() with duplicate URL — returns same code",
        "Tests cover resolve() with valid code — returns original URL",
        "Tests cover resolve() with missing code — returns None",
        "Tests cover resolve() increments click count",
        "Tests cover get_stats() returns correct data",
        "Tests use a separate test database (not production DB)",
        "All tests pass when run",
    ],
    risk_level="low",
    stack="python/pytest",
    good_looks_like=(
        "Uses a pytest fixture to create a temporary database. "
        "Tests each function independently. "
        "Tests edge cases: empty string, URL without protocol, very long URL. "
        "Uses AAA pattern (Arrange/Act/Assert). "
        "Descriptive test names like test_shorten_valid_url_returns_8_char_code."
    ),
)

JOB_TEST_AUTH = BenchmarkJob(
    id="test-auth-module",
    name="Write tests for authentication module",
    category="testing",
    test_set="tune",
    input_prompt=(
        "Write a comprehensive test suite for this authentication module. "
        "Cover registration, login, token generation, and token validation. "
        "Include security edge cases. Use pytest."
    ),
    input_context='''import hashlib
import hmac
import json
import time
import base64
import os

SECRET_KEY = os.environ.get("AUTH_SECRET", "dev-secret-key")
TOKEN_EXPIRY = 3600  # 1 hour

# In-memory user store (would be a DB in production)
users: dict[str, dict] = {}

def register(username: str, password: str) -> dict:
    """Register a new user. Returns user dict."""
    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if username in users:
        raise ValueError("Username already exists")

    salt = os.urandom(16).hex()
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    users[username] = {"username": username, "salt": salt, "password_hash": hashed}
    return {"username": username}

def login(username: str, password: str) -> str:
    """Validate credentials and return a token."""
    user = users.get(username)
    if not user:
        raise ValueError("Invalid credentials")

    expected = hashlib.sha256(f"{user['salt']}{password}".encode()).hexdigest()
    if not hmac.compare_digest(expected, user["password_hash"]):
        raise ValueError("Invalid credentials")

    return _create_token(username)

def _create_token(username: str) -> str:
    """Create a signed token."""
    payload = {"sub": username, "exp": int(time.time()) + TOKEN_EXPIRY}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def validate_token(token: str) -> dict:
    """Validate token and return payload. Raises ValueError on failure."""
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed token")

    payload_b64, sig = parts
    expected_sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Invalid signature")

    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")

    return payload
''',
    acceptance_criteria=[
        "Tests cover register() happy path — new user created successfully",
        "Tests cover register() with invalid inputs (short username, short password, duplicate)",
        "Tests cover login() with correct credentials returns a token",
        "Tests cover login() with wrong password raises ValueError",
        "Tests cover login() with nonexistent user raises ValueError",
        "Tests cover validate_token() with valid token returns payload",
        "Tests cover validate_token() with expired token raises ValueError",
        "Tests cover validate_token() with tampered token raises ValueError",
        "Tests isolate state (each test starts with clean user store)",
    ],
    risk_level="low",
    stack="python/pytest",
    good_looks_like=(
        "Uses fixtures to reset user store between tests. Tests security edge cases: "
        "tampered signature, expired token, empty strings. Doesn't test internal "
        "implementation details (hashing algorithm). Uses descriptive test names."
    ),
)

JOB_TEST_PIPELINE = BenchmarkJob(
    id="test-data-pipeline",
    name="Write tests for data processing pipeline",
    category="testing",
    test_set="tune",
    input_prompt=(
        "Write a comprehensive test suite for this CSV-to-JSON data pipeline. "
        "Test each stage: reading, validation, transformation, and output. "
        "Use pytest. Include edge cases like malformed data and empty files."
    ),
    input_context='''import csv
import json
import io
from dataclasses import dataclass

@dataclass
class PipelineError:
    row: int
    field: str
    message: str

def read_csv(content: str) -> list[dict]:
    """Parse CSV string into list of dicts."""
    if not content.strip():
        return []
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)

def validate_rows(rows: list[dict]) -> tuple[list[dict], list[PipelineError]]:
    """Validate rows. Returns (valid_rows, errors)."""
    valid = []
    errors = []
    required_fields = {"name", "email", "amount"}

    for i, row in enumerate(rows):
        missing = required_fields - set(row.keys())
        if missing:
            errors.append(PipelineError(i, ",".join(missing), "Missing required field"))
            continue

        if not row["email"] or "@" not in row["email"]:
            errors.append(PipelineError(i, "email", "Invalid email format"))
            continue

        try:
            float(row["amount"])
        except (ValueError, TypeError):
            errors.append(PipelineError(i, "amount", f"Invalid number: {row.get('amount')}"))
            continue

        valid.append(row)
    return valid, errors

def transform(rows: list[dict]) -> list[dict]:
    """Transform validated rows into output format."""
    return [
        {
            "full_name": row["name"].strip().title(),
            "email": row["email"].strip().lower(),
            "amount_cents": int(float(row["amount"]) * 100),
        }
        for row in rows
    ]

def pipeline(csv_content: str) -> dict:
    """Run full pipeline: read → validate → transform → output."""
    rows = read_csv(csv_content)
    valid, errors = validate_rows(rows)
    transformed = transform(valid)
    return {
        "data": transformed,
        "total_rows": len(rows),
        "valid_rows": len(valid),
        "error_count": len(errors),
        "errors": [{"row": e.row, "field": e.field, "message": e.message} for e in errors],
    }
''',
    acceptance_criteria=[
        "Tests cover read_csv() with valid input, empty input, and single-row input",
        "Tests cover validate_rows() with valid rows, missing fields, invalid email, invalid amount",
        "Tests cover transform() — name is title-cased, email lowered, amount converted to cents",
        "Tests cover pipeline() end-to-end with mixed valid and invalid rows",
        "Tests handle edge cases: empty string, whitespace-only, header-only CSV",
        "All tests pass when run",
    ],
    risk_level="low",
    stack="python/pytest",
    good_looks_like=(
        "Tests each function independently. Uses parameterize for edge cases. "
        "Small inline CSV fixtures, not large test files. "
        "Tests boundary: row with all required fields but blank values."
    ),
)


# ── Category: Code Review ────────────────────────────────────────────────────

JOB_REVIEW_DIFF = BenchmarkJob(
    id="review-caching-diff",
    name="Review PR that adds caching (contains data leak)",
    category="review",
    test_set="tune",
    input_prompt=(
        "Review this pull request that adds Redis caching to our user profile endpoint. "
        "Check for correctness, security, and performance issues."
    ),
    input_context='''# PR: Add Redis caching to user profiles
# Description: Cache user profiles for 5 minutes to reduce DB load

# BEFORE (existing code):
@app.get("/users/{user_id}/profile")
def get_profile(user_id: int, current_user: User = Depends(get_current_user)):
    """Get a user's profile. Users can only see their own profile unless admin."""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(403, "Not authorized")
    profile = db.query(UserProfile).filter_by(user_id=user_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile.to_dict()

# AFTER (proposed change):
import redis
import json

cache = redis.Redis(host="localhost", port=6379, db=0)
CACHE_TTL = 300  # 5 minutes

@app.get("/users/{user_id}/profile")
def get_profile(user_id: int, current_user: User = Depends(get_current_user)):
    """Get a user's profile with caching."""
    cache_key = f"profile:{user_id}"

    # Try cache first
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss — fetch from DB
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(403, "Not authorized")
    profile = db.query(UserProfile).filter_by(user_id=user_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")

    result = profile.to_dict()
    cache.set(cache_key, json.dumps(result), ex=CACHE_TTL)
    return result
''',
    acceptance_criteria=[
        "Identifies the authorization bypass — cache check happens BEFORE auth check, so any authenticated user can see any cached profile",
        "Rates the auth bypass as CRITICAL severity",
        "Notes that cache key should include the requesting user's access level or auth should run before cache",
        "Identifies at least one other issue (missing cache error handling, no invalidation on profile update, etc.)",
    ],
    risk_level="high",
    stack="python/fastapi/redis",
    good_looks_like=(
        "Immediately identifies that the authorization check was moved AFTER the cache check, "
        "creating a data leak. Explains that User A can now see User B's profile if it's cached. "
        "Suggests: either run auth before cache, or include auth context in cache key. "
        "Also notes: no error handling if Redis is down, no cache invalidation on profile update."
    ),
)

JOB_REVIEW_SCHEMA = BenchmarkJob(
    id="review-schema-change",
    name="Review PR that changes database schema",
    category="review",
    test_set="tune",
    input_prompt=(
        "Review this database migration that adds a status column to the orders table. "
        "Check for correctness, performance, and deployment safety."
    ),
    input_context='''# PR: Add order status tracking
# Description: Add a status column to orders so we can track fulfillment

# Migration file: migrations/versions/003_add_order_status.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column("orders", sa.Column("status", sa.String(50)))
    op.execute("UPDATE orders SET status = 'unknown'")

def downgrade():
    # Can't easily undo this
    pass

# Updated model: models/order.py
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50))  # new

# Updated query in routes/orders.py
@app.get("/orders")
def list_orders(status: str = None):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    return [o.to_dict() for o in query.all()]
''',
    acceptance_criteria=[
        "Identifies that the new column has no default value (NULL for existing rows if UPDATE fails or is incomplete)",
        "Identifies that filtering by status will be slow without an index on the status column",
        "Identifies that the downgrade function is empty (migration is not reversible)",
        "Catches at least 2 of these 3 issues",
    ],
    risk_level="medium",
    stack="python/sqlalchemy/alembic",
    good_looks_like=(
        "Identifies all 3 issues. Explains WHY each matters: NULL status breaks app logic, "
        "unindexed column means full table scan on every filtered query, "
        "irreversible migration means no rollback if deployment fails."
    ),
)

JOB_REVIEW_USER_INPUT = BenchmarkJob(
    id="review-user-input",
    name="Review PR that handles user input (contains SQLi)",
    category="review",
    test_set="tune",
    input_prompt=(
        "Review this pull request that adds a search endpoint. "
        "Check for security, correctness, and best practices."
    ),
    input_context='''# PR: Add product search endpoint
# Description: Allow users to search products by name

from fastapi import FastAPI, Query
import sqlite3

app = FastAPI()

@app.get("/search")
def search_products(q: str = Query(..., description="Search query")):
    """Search products by name."""
    conn = sqlite3.connect("products.db")
    conn.row_factory = sqlite3.Row

    # Search for products matching the query
    rows = conn.execute(
        f"SELECT id, name, price, description FROM products WHERE name LIKE '%{q}%'"
    ).fetchall()
    conn.close()

    if not rows:
        return {"error": f"No products found in table 'products' for query: {q}", "count": 0}

    return {"results": [dict(r) for r in rows], "count": len(rows)}

@app.get("/product/{product_id}")
def get_product(product_id: int):
    conn = sqlite3.connect("products.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        f"SELECT * FROM products WHERE id = {product_id}"
    ).fetchone()
    conn.close()
    if not row:
        return {"error": "Not found"}
    return dict(row)
''',
    acceptance_criteria=[
        "Identifies SQL injection in the search endpoint (string interpolation in query)",
        "Identifies SQL injection in the product endpoint (f-string for product_id)",
        "Identifies information leakage in error message (exposes table name 'products')",
        "Provides the parameterized query fix",
        "Rates SQL injection as CRITICAL severity",
    ],
    risk_level="high",
    stack="python/fastapi/sqlite",
    good_looks_like=(
        "Immediately catches both SQL injection vectors. Explains the attack: "
        "search?q=' OR 1=1 -- would dump all products. Provides parameterized query fix. "
        "Notes the info leak in the error message. Rates as CRITICAL."
    ),
)


# ── Category: Refactoring ────────────────────────────────────────────────────

JOB_REFACTOR_VALIDATION = BenchmarkJob(
    id="refactor-extract-validation",
    name="Extract duplicated validation logic",
    category="refactor",
    test_set="tune",
    input_prompt=(
        "Extract the duplicated input validation into a shared function. "
        "Don't change any behavior — the endpoints should work exactly as before."
    ),
    input_context='''from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class UserInput(BaseModel):
    name: str
    email: str
    age: int

@app.post("/users")
def create_user(data: UserInput):
    # Validation (duplicated in 3 places)
    if not data.name or len(data.name.strip()) < 2:
        raise HTTPException(400, "Name must be at least 2 characters")
    if not data.email or "@" not in data.email:
        raise HTTPException(400, "Invalid email format")
    if data.age < 0 or data.age > 150:
        raise HTTPException(400, "Age must be between 0 and 150")
    name = data.name.strip().title()
    email = data.email.strip().lower()

    return {"id": 1, "name": name, "email": email, "age": data.age}

@app.put("/users/{user_id}")
def update_user(user_id: int, data: UserInput):
    # Validation (same as above)
    if not data.name or len(data.name.strip()) < 2:
        raise HTTPException(400, "Name must be at least 2 characters")
    if not data.email or "@" not in data.email:
        raise HTTPException(400, "Invalid email format")
    if data.age < 0 or data.age > 150:
        raise HTTPException(400, "Age must be between 0 and 150")
    name = data.name.strip().title()
    email = data.email.strip().lower()

    return {"id": user_id, "name": name, "email": email, "age": data.age}

@app.post("/users/bulk")
def create_users_bulk(users: list[UserInput]):
    results = []
    for data in users:
        # Validation (same as above — third copy!)
        if not data.name or len(data.name.strip()) < 2:
            raise HTTPException(400, f"Name must be at least 2 characters (got: {data.name})")
        if not data.email or "@" not in data.email:
            raise HTTPException(400, f"Invalid email format: {data.email}")
        if data.age < 0 or data.age > 150:
            raise HTTPException(400, f"Age must be between 0 and 150 (got: {data.age})")
        name = data.name.strip().title()
        email = data.email.strip().lower()
        results.append({"name": name, "email": email, "age": data.age})
    return results
''',
    acceptance_criteria=[
        "Duplicated validation logic is extracted into a single shared function",
        "All three endpoints use the shared function",
        "Behavior is identical — same error messages, same HTTP status codes",
        "The shared function has clear parameter and return types",
        "No over-engineering (one function, not a validation framework)",
    ],
    risk_level="low",
    stack="python/fastapi",
    good_looks_like=(
        "Extracts a validate_and_normalize(data) function that returns cleaned name/email "
        "or raises HTTPException. All 3 endpoints call it. Type hints included. "
        "No unnecessary abstraction layers."
    ),
)

JOB_REFACTOR_CALLBACKS = BenchmarkJob(
    id="refactor-callbacks-to-async",
    name="Convert callback-based code to async/await",
    category="refactor",
    test_set="tune",
    input_prompt=(
        "Convert this callback-based Node.js code to use async/await. "
        "Keep the same behavior — same inputs, same outputs, same error handling."
    ),
    input_context='''const fs = require("fs");
const https = require("https");

function fetchAndSave(url, outputPath, callback) {
  https.get(url, (res) => {
    if (res.statusCode !== 200) {
      callback(new Error(`HTTP ${res.statusCode}`));
      return;
    }

    let data = "";
    res.on("data", (chunk) => {
      data += chunk;
    });

    res.on("end", () => {
      let parsed;
      try {
        parsed = JSON.parse(data);
      } catch (err) {
        callback(new Error("Invalid JSON response"));
        return;
      }

      const output = JSON.stringify(parsed, null, 2);
      fs.writeFile(outputPath, output, (err) => {
        if (err) {
          callback(new Error(`Write failed: ${err.message}`));
          return;
        }
        callback(null, { path: outputPath, size: output.length });
      });
    });

    res.on("error", (err) => {
      callback(new Error(`Network error: ${err.message}`));
    });
  }).on("error", (err) => {
    callback(new Error(`Request failed: ${err.message}`));
  });
}

// Usage:
// fetchAndSave("https://api.example.com/data", "output.json", (err, result) => {
//   if (err) console.error(err);
//   else console.log(result);
// });
''',
    acceptance_criteria=[
        "Converted to async/await syntax — no callbacks remain",
        "Error handling is preserved (same error types and messages)",
        "HTTP status check is preserved",
        "JSON parse error is caught and wrapped",
        "File write error is caught and wrapped",
        "Returns the same result object { path, size }",
    ],
    risk_level="medium",
    stack="node/javascript",
    good_looks_like=(
        "Uses node:fs/promises or util.promisify. Wraps https.get in a Promise. "
        "Uses try/catch for error handling. Maintains the same error messages. "
        "Clean, readable async function."
    ),
)

JOB_REFACTOR_GOD_FUNCTION = BenchmarkJob(
    id="refactor-god-function",
    name="Split a god function into smaller functions",
    category="refactor",
    test_set="tune",
    input_prompt=(
        "This function does too much. Break it into smaller, focused functions. "
        "Same behavior — don't change what it does, just how it's organized."
    ),
    input_context='''import json
import os
import re
from pathlib import Path

def process_config(config_path: str) -> dict:
    """Load, validate, transform, and save a config file."""
    # Step 1: Load
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        raw = f.read()
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {config_path}: {e}")

    # Step 2: Validate required fields
    required = ["name", "version", "database", "features"]
    missing = [f for f in required if f not in config]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    if not re.match(r"^\\d+\\.\\d+\\.\\d+$", config["version"]):
        raise ValueError(f"Invalid version format: {config['version']}")
    db = config["database"]
    if "host" not in db or "port" not in db:
        raise ValueError("Database config must include host and port")
    if not isinstance(db["port"], int) or db["port"] < 1 or db["port"] > 65535:
        raise ValueError(f"Invalid port: {db['port']}")

    # Step 3: Transform
    config["name"] = config["name"].strip().lower().replace(" ", "-")
    config["database"]["connection_string"] = (
        f"postgresql://{db['host']}:{db['port']}/{db.get('name', 'default')}"
    )
    config["features"] = [f.strip().lower() for f in config["features"] if f.strip()]
    config["_metadata"] = {
        "source": config_path,
        "processed": True,
    }

    # Step 4: Save
    output_path = Path(config_path).with_suffix(".processed.json")
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    return config
''',
    acceptance_criteria=[
        "Function is split into 3-5 smaller functions (load, validate, transform, save)",
        "Each function has a single responsibility and clear name",
        "The main function calls the sub-functions in sequence",
        "Behavior is identical — same errors, same output, same side effects",
        "Functions have type hints on parameters and return values",
        "No unnecessary classes or over-abstraction",
    ],
    risk_level="low",
    stack="python",
    good_looks_like=(
        "4 functions: load_config, validate_config, transform_config, save_config. "
        "Main process_config calls them in order. Clear data flow. "
        "Each function under 20 lines. Type hints on all signatures."
    ),
)


# ── Category: Documentation / Setup ──────────────────────────────────────────

JOB_README = BenchmarkJob(
    id="docs-readme",
    name="Generate a README for an API project",
    category="docs",
    test_set="tune",
    input_prompt=(
        "Write a README that lets a new developer clone this repo and have the API "
        "running in 5 minutes. Include setup, env vars, how to run, and endpoint docs."
    ),
    input_context='''# Project structure:
# ├── app.py
# ├── models.py
# ├── requirements.txt
# └── .env.example

# app.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import os

app = FastAPI(title="Task Tracker API")

DATABASE_URL = os.environ["DATABASE_URL"]
API_KEY = os.environ.get("API_KEY", "")

# ... database setup with SQLAlchemy ...

@app.get("/tasks")
def list_tasks(status: str = None, db: Session = Depends(get_db)):
    """List all tasks, optionally filtered by status."""
    ...

@app.post("/tasks")
def create_task(title: str, description: str = "", db: Session = Depends(get_db)):
    """Create a new task."""
    ...

@app.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get a specific task by ID."""
    ...

@app.put("/tasks/{task_id}")
def update_task(task_id: int, title: str = None, status: str = None, db: Session = Depends(get_db)):
    """Update a task's title or status."""
    ...

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Delete a task."""
    ...

# requirements.txt:
# fastapi==0.109.0
# uvicorn==0.27.0
# sqlalchemy==2.0.25
# python-dotenv==1.0.0

# .env.example:
# DATABASE_URL=sqlite:///tasks.db
# API_KEY=your-api-key-here
''',
    acceptance_criteria=[
        "README includes prerequisites (Python version, pip)",
        "Setup commands are copy-pasteable and would actually work",
        "All required environment variables are documented",
        "Each endpoint is documented with method, path, params, and example response",
        "No missing steps — following the README from scratch, the app would run",
    ],
    risk_level="low",
    stack="python/fastapi",
    good_looks_like=(
        "Step-by-step setup: clone, venv, install, env vars, run. "
        "Endpoint table or list with method, path, description. "
        "Example curl commands. No assumptions about pre-installed tools."
    ),
)

JOB_DOCKERFILE = BenchmarkJob(
    id="docs-dockerfile",
    name="Write a Dockerfile for a Python app",
    category="docs",
    test_set="tune",
    input_prompt=(
        "Add a Dockerfile and docker-compose.yml so this Flask app can be run with "
        "'docker compose up'. The app runs on port 5000."
    ),
    input_context='''# Project structure:
# ├── app.py
# ├── requirements.txt
# ├── static/
# │   └── style.css
# └── templates/
#     └── index.html

# app.py
from flask import Flask, render_template, jsonify
import os

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def status():
    return jsonify({"status": "ok", "db": DATABASE_URL.split("://")[0]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

# requirements.txt:
# flask==3.0.0
# gunicorn==21.2.0
# sqlalchemy==2.0.25
''',
    acceptance_criteria=[
        "Dockerfile builds successfully (valid syntax, correct base image)",
        "docker-compose.yml starts the app accessible on localhost:5000",
        "Uses a production WSGI server (gunicorn), not Flask dev server",
        "Environment variables are configurable (not hardcoded in Dockerfile)",
        "Reasonable image size (not using full ubuntu base when python:slim works)",
    ],
    risk_level="low",
    stack="python/flask/docker",
    good_looks_like=(
        "Multi-stage or slim base image. COPY requirements first for layer caching. "
        "Non-root user. .dockerignore file. Health check. "
        "docker-compose.yml with environment variables and port mapping."
    ),
)


# ── Category: Adversarial ────────────────────────────────────────────────────

JOB_VAGUE_SPEC = BenchmarkJob(
    id="adversarial-vague",
    name="Handle deliberately vague spec",
    category="adversarial",
    test_set="tune",
    input_prompt="Make the API faster.",
    input_context='''from fastapi import FastAPI
import sqlite3
import time

app = FastAPI()

@app.get("/dashboard")
def dashboard():
    conn = sqlite3.connect("app.db")
    users = conn.execute("SELECT * FROM users").fetchall()
    orders = conn.execute("SELECT * FROM orders").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return {
        "user_count": len(users),
        "order_count": len(orders),
        "product_count": len(products),
        "recent_orders": orders[-10:],
    }
''',
    acceptance_criteria=[
        "Does NOT immediately start optimizing without asking questions",
        "Asks what 'faster' means — response time? throughput? specific endpoint?",
        "Identifies at least one real performance issue in the code (loading all rows to count them)",
        "Suggests measuring before optimizing (profiling, timing, baseline metrics)",
    ],
    risk_level="low",
    stack="python/fastapi",
    good_looks_like=(
        "Asks clarifying questions: which endpoint is slow? what's the current latency? "
        "what's acceptable? Points out that SELECT * fetches all rows just to count them — "
        "should use SELECT COUNT(*). Notes that loading all orders into memory to slice "
        "the last 10 is wasteful — should use ORDER BY + LIMIT in SQL. "
        "Suggests adding timing middleware before optimizing."
    ),
)


# ── Registry ─────────────────────────────────────────────────────────────────

TUNE_JOBS = [
    JOB_PAGINATION,
    JOB_DARK_MODE,
    JOB_RATE_LIMITING,
    JOB_CSV_EXPORT,
    JOB_DATE_BUG,
    JOB_CORS,
    JOB_WEBSOCKET_LEAK,
    JOB_RACE_CONDITION,
    JOB_WRITE_TESTS,
    JOB_TEST_AUTH,
    JOB_TEST_PIPELINE,
    JOB_REVIEW_DIFF,
    JOB_REVIEW_SCHEMA,
    JOB_REVIEW_USER_INPUT,
    JOB_REFACTOR_VALIDATION,
    JOB_REFACTOR_CALLBACKS,
    JOB_REFACTOR_GOD_FUNCTION,
    JOB_README,
    JOB_DOCKERFILE,
    JOB_VAGUE_SPEC,
]

assert len(TUNE_JOBS) == 20, f"Expected 20 tune jobs, got {len(TUNE_JOBS)}"
