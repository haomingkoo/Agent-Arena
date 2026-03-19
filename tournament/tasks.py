"""
Category-specific benchmark task pools for tournaments.

Each category has 8 tasks. Tournaments use 5 at a time,
rotating to prevent overfitting. Tasks are tagged with
skill_domain to match against the appropriate tournament category.
"""
from __future__ import annotations

import random
from evaluate.sandbox import BenchmarkJob

# ── Code Review Tasks ────────────────────────────────────────────────────────

CODE_REVIEW_TASKS: list[BenchmarkJob] = [
    BenchmarkJob(
        id="cr-sql-injection",
        name="Review endpoint with SQL injection vulnerability",
        category="review",
        skill_domain="code-review",
        task_bucket="anchor",
        difficulty="medium",
        test_set="tournament",
        input_prompt=(
            "Review this code for security issues. "
            "Focus on data handling, input validation, and query safety."
        ),
        input_context='''from fastapi import FastAPI, Query
import sqlite3

app = FastAPI()

@app.get("/users/search")
def search_users(name: str = Query(...), role: str = Query(default="")):
    conn = sqlite3.connect("app.db")
    query = f"SELECT id, name, email, role FROM users WHERE name LIKE '%{name}%'"
    if role:
        query += f" AND role = '{role}'"
    rows = conn.execute(query).fetchall()
    conn.close()
    return {"users": [dict(zip(["id", "name", "email", "role"], r)) for r in rows]}

@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    conn = sqlite3.connect("app.db")
    conn.execute(f"DELETE FROM users WHERE id = {user_id}")
    conn.commit()
    conn.close()
    return {"deleted": user_id}

@app.put("/users/{user_id}/role")
def update_role(user_id: int, new_role: str):
    conn = sqlite3.connect("app.db")
    conn.execute(f"UPDATE users SET role = '{new_role}' WHERE id = {user_id}")
    conn.commit()
    conn.close()
    return {"updated": user_id, "role": new_role}
''',
        acceptance_criteria=[
            "Identifies SQL injection in the search endpoint (string interpolation in WHERE clause)",
            "Identifies SQL injection in the delete endpoint",
            "Identifies SQL injection in the update_role endpoint",
            "Recommends parameterized queries (? placeholders) for all three endpoints",
            "Notes missing authentication/authorization on destructive operations (DELETE, PUT)",
            "Provides corrected code examples using parameterized queries",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="cr-race-condition",
        name="Review inventory update with race condition",
        category="review",
        skill_domain="code-review",
        task_bucket="rotating",
        difficulty="hard",
        test_set="tournament",
        input_prompt=(
            "Review this checkout handler for correctness. "
            "Multiple users may be checking out the same item simultaneously."
        ),
        input_context='''from fastapi import FastAPI, HTTPException
import sqlite3

app = FastAPI()
DB = "shop.db"

def get_stock(product_id: int) -> int:
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT stock FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0

def reduce_stock(product_id: int, qty: int):
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE products SET stock = stock - ? WHERE id = ?",
        (qty, product_id),
    )
    conn.commit()
    conn.close()

@app.post("/checkout")
def checkout(product_id: int, quantity: int):
    stock = get_stock(product_id)
    if stock < quantity:
        raise HTTPException(400, "Not enough stock")
    reduce_stock(product_id, quantity)
    return {"message": f"Purchased {quantity} units", "remaining": stock - quantity}
''',
        acceptance_criteria=[
            "Identifies the TOCTOU race condition (check-then-act between get_stock and reduce_stock)",
            "Explains how two concurrent requests could oversell inventory",
            "Recommends atomic UPDATE with WHERE stock >= quantity check",
            "Points out that separate connections mean no transaction isolation",
            "Provides a corrected implementation using a single atomic query",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="cr-error-handling",
        name="Review API with poor error handling",
        category="review",
        skill_domain="code-review",
        task_bucket="rotating",
        difficulty="easy",
        test_set="tournament",
        input_prompt=(
            "Review this payment processing endpoint for robustness. "
            "Consider error handling, edge cases, and failure modes."
        ),
        input_context='''from fastapi import FastAPI
import requests
import sqlite3

app = FastAPI()

@app.post("/process-payment")
def process_payment(user_id: int, amount: float, card_token: str):
    # Step 1: Charge the card
    resp = requests.post(
        "https://api.stripe.com/v1/charges",
        data={"amount": int(amount * 100), "source": card_token, "currency": "usd"},
        auth=("sk_live_abc123", ""),
    )
    charge = resp.json()

    # Step 2: Record in database
    conn = sqlite3.connect("payments.db")
    conn.execute(
        "INSERT INTO payments (user_id, amount, charge_id, status) VALUES (?, ?, ?, ?)",
        (user_id, amount, charge["id"], "completed"),
    )
    conn.commit()
    conn.close()

    # Step 3: Send receipt email
    requests.post(
        "https://api.mailgun.net/v3/example.com/messages",
        auth=("api", "key-xyz123"),
        data={"from": "billing@example.com", "to": f"user_{user_id}@example.com",
              "subject": "Payment Receipt", "text": f"Charged ${amount}"},
    )

    return {"status": "success", "charge_id": charge["id"]}
''',
        acceptance_criteria=[
            "Identifies hardcoded API keys (Stripe sk_live, Mailgun key)",
            "Identifies no error checking on the Stripe API response (could be a failure/decline)",
            "Identifies that if DB insert fails after charging, the payment is lost (no rollback)",
            "Identifies that if email fails, the entire endpoint may error despite successful payment",
            "Identifies floating-point amount calculation issue (amount * 100 rounding)",
            "Recommends try/except blocks with proper error handling for each step",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="cr-memory-leak",
        name="Review code with resource/memory leak",
        category="review",
        skill_domain="code-review",
        task_bucket="rotating",
        difficulty="medium",
        test_set="tournament",
        input_prompt=(
            "Review this file processing service for issues. "
            "It will process thousands of files per day in production."
        ),
        input_context='''from fastapi import FastAPI, UploadFile
import tempfile
import json
from pathlib import Path

app = FastAPI()

# In-memory cache for processed results
processed_files: dict[str, dict] = {}

@app.post("/process")
async def process_file(file: UploadFile):
    # Save to temp dir
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=file.filename)
    content = await file.read()
    tmp.write(content)
    tmp_path = tmp.name

    # Parse and validate
    data = json.loads(content)
    result = {
        "filename": file.filename,
        "size": len(content),
        "keys": list(data.keys()),
        "records": len(data) if isinstance(data, list) else 1,
    }

    # Cache the result
    processed_files[file.filename] = result

    return result

@app.get("/results")
def list_results():
    return {"processed": len(processed_files), "files": list(processed_files.keys())}

@app.get("/results/{filename}")
def get_result(filename: str):
    if filename not in processed_files:
        from fastapi import HTTPException
        raise HTTPException(404, "File not processed")
    return processed_files[filename]
''',
        acceptance_criteria=[
            "Identifies the temp file leak (NamedTemporaryFile with delete=False, never cleaned up)",
            "Identifies the unbounded in-memory cache (processed_files grows forever)",
            "Identifies that UploadFile content is read fully into memory (no streaming for large files)",
            "Identifies missing file handle closure (tmp file handle not closed before use)",
            "Recommends cleanup: delete temp files after processing, use LRU cache or TTL eviction",
            "Recommends size validation before reading entire file into memory",
        ],
        risk_level="medium",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="cr-auth-bypass",
        name="Review authentication with bypass vulnerability",
        category="review",
        skill_domain="code-review",
        task_bucket="anchor",
        difficulty="medium",
        test_set="tournament",
        input_prompt=(
            "Review this authentication system for security issues. "
            "This is used in production to protect admin endpoints."
        ),
        input_context='''from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import hashlib
import time

app = FastAPI()

ADMIN_USERS = {"admin": "5f4dcc3b5aa765d61d8327deb882cf99"}  # md5("password")
SESSIONS: dict[str, dict] = {}

@app.post("/login")
def login(username: str, password: str):
    hashed = hashlib.md5(password.encode()).hexdigest()
    if username in ADMIN_USERS and ADMIN_USERS[username] == hashed:
        session_id = hashlib.md5(f"{username}{time.time()}".encode()).hexdigest()
        SESSIONS[session_id] = {"user": username, "role": "admin", "created": time.time()}
        return {"session_id": session_id}
    raise HTTPException(401, "Invalid credentials")

def require_admin(request: Request):
    session_id = request.headers.get("X-Session-ID") or request.query_params.get("session")
    if not session_id:
        raise HTTPException(401, "No session")
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(401, "Invalid session")
    return session

@app.get("/admin/dashboard")
def admin_dashboard(request: Request):
    session = require_admin(request)
    return {"message": f"Welcome {session['user']}", "active_sessions": len(SESSIONS)}

@app.get("/admin/users")
def admin_users(request: Request):
    require_admin(request)
    return {"users": list(ADMIN_USERS.keys())}
''',
        acceptance_criteria=[
            "Identifies MD5 for password hashing (weak, no salt)",
            "Identifies MD5 for session ID generation (predictable, time-based)",
            "Identifies sessions never expire (no TTL check in require_admin)",
            "Identifies session ID accepted via query parameter (leaks in URL/logs)",
            "Identifies no brute-force protection on login endpoint",
            "Recommends bcrypt/argon2 for passwords, secrets.token_urlsafe for sessions",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="cr-async-pitfall",
        name="Review async code with blocking calls",
        category="review",
        skill_domain="code-review",
        task_bucket="rotating",
        difficulty="hard",
        test_set="tournament",
        input_prompt=(
            "Review this async FastAPI application for performance issues. "
            "The team reports it handles far fewer concurrent requests than expected."
        ),
        input_context='''from fastapi import FastAPI
import sqlite3
import time
import requests

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    conn = sqlite3.connect("app.db")
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "User not found")
    return dict(zip(["id", "name", "email"], row))

@app.get("/users/{user_id}/enriched")
async def get_enriched_user(user_id: int):
    conn = sqlite3.connect("app.db")
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "User not found")
    user = dict(zip(["id", "name", "email"], row))
    # Enrich with external data
    resp = requests.get(f"https://api.clearbit.com/v1/people/find?email={user['email']}")
    if resp.ok:
        user["company"] = resp.json().get("company", {}).get("name", "")
    return user

@app.post("/reports/generate")
async def generate_report(report_type: str):
    conn = sqlite3.connect("app.db")
    rows = conn.execute("SELECT * FROM large_table").fetchall()
    conn.close()
    # Process rows (CPU-intensive)
    time.sleep(5)  # simulates heavy processing
    return {"report": report_type, "rows_processed": len(rows)}
''',
        acceptance_criteria=[
            "Identifies that async def with synchronous sqlite3 calls blocks the event loop",
            "Identifies that requests.get in async context blocks the event loop",
            "Identifies that time.sleep blocks the event loop (should use asyncio.sleep or run in executor)",
            "Recommends either using def (non-async) for sync code or running blocking calls in executor",
            "Recommends using httpx.AsyncClient or aiohttp instead of requests for the enrichment call",
            "Explains why this pattern destroys FastAPI's concurrency advantage",
        ],
        risk_level="medium",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="cr-pagination-bug",
        name="Review pagination implementation with off-by-one bugs",
        category="review",
        skill_domain="code-review",
        task_bucket="rotating",
        difficulty="easy",
        test_set="tournament",
        input_prompt=(
            "Review this pagination implementation. "
            "Users report seeing duplicate items and missing items when paging through results."
        ),
        input_context='''from fastapi import FastAPI, Query
import sqlite3

app = FastAPI()

@app.get("/products")
def list_products(page: int = Query(default=1), size: int = Query(default=10)):
    conn = sqlite3.connect("shop.db")
    # Get total
    total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    # Get page
    offset = page * size  # page 1 starts at offset 10, skipping first 10 items
    rows = conn.execute(
        "SELECT id, name, price FROM products ORDER BY id LIMIT ? OFFSET ?",
        (size, offset),
    ).fetchall()
    conn.close()
    total_pages = total // size  # 25 items / 10 per page = 2 pages (misses page 3)
    return {
        "items": [dict(zip(["id", "name", "price"], r)) for r in rows],
        "page": page,
        "size": size,
        "total": total,
        "total_pages": total_pages,
    }

@app.get("/products/cursor")
def list_products_cursor(after_id: int = Query(default=0), size: int = Query(default=10)):
    conn = sqlite3.connect("shop.db")
    rows = conn.execute(
        "SELECT id, name, price FROM products WHERE id > ? LIMIT ?",
        (after_id, size),
    ).fetchall()
    conn.close()
    items = [dict(zip(["id", "name", "price"], r)) for r in rows]
    next_cursor = items[-1]["id"] if items else None
    return {"items": items, "next_cursor": next_cursor}
''',
        acceptance_criteria=[
            "Identifies the off-by-one in offset calculation (page * size skips first page of results)",
            "Identifies the truncation bug in total_pages (integer division drops remainder)",
            "Identifies that page=0 and negative page values are not validated",
            "Identifies that size has no upper bound (allows fetching entire table)",
            "Provides corrected offset formula: (page - 1) * size",
            "Provides corrected total_pages: math.ceil(total / size) or -(-total // size)",
        ],
        risk_level="low",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="cr-logging-pii",
        name="Review code that logs sensitive user data",
        category="review",
        skill_domain="code-review",
        task_bucket="holdout",
        difficulty="medium",
        test_set="tournament",
        input_prompt=(
            "Review this user management code for data privacy compliance. "
            "We need to pass a security audit."
        ),
        input_context='''from fastapi import FastAPI, HTTPException
import logging
import json

app = FastAPI()
logger = logging.getLogger("user_service")
logging.basicConfig(level=logging.DEBUG)

@app.post("/users/register")
def register(name: str, email: str, password: str, ssn: str, phone: str):
    logger.info(f"Registering user: name={name}, email={email}, ssn={ssn}, phone={phone}")
    # Validate
    if len(password) < 8:
        logger.warning(f"Weak password attempt: {password} for user {email}")
        raise HTTPException(400, "Password too short")
    user = {"name": name, "email": email, "ssn": ssn, "phone": phone, "password": password}
    logger.debug(f"Created user record: {json.dumps(user)}")
    return {"message": "User created", "user": user}

@app.post("/users/login")
def login(email: str, password: str):
    logger.info(f"Login attempt: email={email}, password={password}")
    # simulate auth
    return {"token": "jwt-token-here"}

@app.get("/users/{user_id}/profile")
def get_profile(user_id: int):
    user = {"id": user_id, "name": "John", "email": "john@example.com",
            "ssn": "123-45-6789", "phone": "+1234567890", "credit_card": "4111111111111111"}
    logger.info(f"Profile accessed: {json.dumps(user)}")
    return user
''',
        acceptance_criteria=[
            "Identifies SSN logged in plaintext during registration",
            "Identifies password logged in plaintext (both registration and login)",
            "Identifies that the full user record (including SSN, credit card) is logged on profile access",
            "Identifies that the response from /register returns password and SSN to the client",
            "Identifies that /profile returns credit card number in the response",
            "Recommends structured logging with PII redaction/masking",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
]

# ── Testing Tasks ────────────────────────────────────────────────────────────

TESTING_TASKS: list[BenchmarkJob] = [
    BenchmarkJob(
        id="test-cart-logic",
        name="Write tests for shopping cart business logic",
        category="testing",
        skill_domain="testing",
        test_set="tournament",
        input_prompt=(
            "Write comprehensive pytest tests for this shopping cart module. "
            "Cover the core flows: add, remove, discount application, and total calculation."
        ),
        input_context='''class Cart:
    def __init__(self):
        self.items: list[dict] = []
        self.discount_code: str | None = None
        self.discount_pct: float = 0.0

    def add_item(self, name: str, price: float, qty: int = 1) -> None:
        if price < 0:
            raise ValueError("Price cannot be negative")
        if qty < 1:
            raise ValueError("Quantity must be at least 1")
        for item in self.items:
            if item["name"] == name:
                item["qty"] += qty
                return
        self.items.append({"name": name, "price": price, "qty": qty})

    def remove_item(self, name: str) -> None:
        self.items = [i for i in self.items if i["name"] != name]

    def apply_discount(self, code: str) -> bool:
        discounts = {"SAVE10": 0.10, "SAVE20": 0.20, "HALF": 0.50}
        if code in discounts:
            self.discount_code = code
            self.discount_pct = discounts[code]
            return True
        return False

    def subtotal(self) -> float:
        return sum(i["price"] * i["qty"] for i in self.items)

    def total(self) -> float:
        st = self.subtotal()
        if self.discount_pct > 0:
            st *= (1 - self.discount_pct)
        return round(st, 2)

    def item_count(self) -> int:
        return sum(i["qty"] for i in self.items)
''',
        acceptance_criteria=[
            "Tests add_item: single item, multiple items, duplicate item merges quantity",
            "Tests remove_item: existing item, non-existent item (no error)",
            "Tests apply_discount: valid code, invalid code, discount applied to total",
            "Tests total: empty cart returns 0, with items, with discount applied",
            "Tests edge cases: negative price raises ValueError, zero quantity raises ValueError",
            "Tests are independent (each test creates its own Cart instance)",
        ],
        risk_level="low",
        stack="python/pytest",
    ),
    BenchmarkJob(
        id="test-auth-middleware",
        name="Write tests for JWT authentication middleware",
        category="testing",
        skill_domain="testing",
        test_set="tournament",
        input_prompt=(
            "Write pytest tests for this JWT authentication dependency. "
            "Test both valid and invalid token scenarios using FastAPI TestClient."
        ),
        input_context='''from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

app = FastAPI()
security = HTTPBearer()
SECRET = "test-secret-key"

def create_token(user_id: int, role: str = "user", expires_minutes: int = 30) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, SECRET, algorithms=["HS256"])
        return {"id": payload["sub"], "role": payload["role"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

def require_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return user

@app.get("/profile")
def profile(user: dict = Depends(get_current_user)):
    return {"user": user}

@app.get("/admin/settings")
def admin_settings(admin: dict = Depends(require_admin)):
    return {"settings": {"max_users": 100}, "admin": admin}
''',
        acceptance_criteria=[
            "Tests /profile with valid token returns 200 and user data",
            "Tests /profile with no token returns 401 or 403",
            "Tests /profile with expired token returns 401 with 'expired' message",
            "Tests /profile with malformed token returns 401",
            "Tests /admin/settings with admin token returns 200",
            "Tests /admin/settings with non-admin token returns 403",
            "Uses FastAPI TestClient and creates tokens with create_token helper",
        ],
        risk_level="low",
        stack="python/pytest/fastapi",
    ),
    BenchmarkJob(
        id="test-rate-limiter",
        name="Write tests for rate limiter utility",
        category="testing",
        skill_domain="testing",
        test_set="tournament",
        input_prompt=(
            "Write pytest tests for this rate limiter. Test the window behavior, "
            "multi-key isolation, and cleanup. Mock time.monotonic for deterministic tests."
        ),
        input_context='''import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        # Remove expired timestamps
        self._timestamps[key] = [
            ts for ts in self._timestamps[key] if ts > cutoff
        ]
        if len(self._timestamps[key]) >= self.max_requests:
            return False
        self._timestamps[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        active = [ts for ts in self._timestamps[key] if ts > cutoff]
        return max(0, self.max_requests - len(active))

    def reset(self, key: str) -> None:
        self._timestamps.pop(key, None)

    def cleanup(self) -> int:
        """Remove all expired entries. Returns number of keys cleaned."""
        now = time.monotonic()
        to_remove = []
        for key, timestamps in self._timestamps.items():
            active = [ts for ts in timestamps if ts > (now - self.window_seconds)]
            if not active:
                to_remove.append(key)
            else:
                self._timestamps[key] = active
        for key in to_remove:
            del self._timestamps[key]
        return len(to_remove)
''',
        acceptance_criteria=[
            "Tests that requests within limit are allowed",
            "Tests that requests exceeding limit are denied",
            "Tests that the window slides (old requests expire, new ones allowed)",
            "Tests multi-key isolation (different keys have independent limits)",
            "Tests remaining() returns correct count",
            "Tests reset() clears a specific key",
            "Tests cleanup() removes only expired entries",
            "Uses monkeypatch or mock to control time.monotonic for deterministic behavior",
        ],
        risk_level="low",
        stack="python/pytest",
    ),
    BenchmarkJob(
        id="test-csv-parser",
        name="Write tests for CSV parser with edge cases",
        category="testing",
        skill_domain="testing",
        test_set="tournament",
        input_prompt=(
            "Write pytest tests for this CSV parser. It needs to handle "
            "quoted fields, escaped quotes, empty fields, and various line endings."
        ),
        input_context='''def parse_csv(text: str, delimiter: str = ",") -> list[list[str]]:
    """Parse CSV text into rows of fields.

    Handles:
    - Quoted fields (can contain delimiter and newlines)
    - Escaped quotes (doubled: "")
    - Empty fields
    - Both \\n and \\r\\n line endings
    """
    rows: list[list[str]] = []
    current_row: list[str] = []
    current_field = ""
    in_quotes = False
    i = 0

    while i < len(text):
        char = text[i]

        if in_quotes:
            if char == '"' and i + 1 < len(text) and text[i + 1] == '"':
                current_field += '"'
                i += 2
                continue
            elif char == '"':
                in_quotes = False
                i += 1
                continue
            else:
                current_field += char
                i += 1
                continue

        if char == '"':
            in_quotes = True
            i += 1
        elif char == delimiter:
            current_row.append(current_field)
            current_field = ""
            i += 1
        elif char == '\\r' and i + 1 < len(text) and text[i + 1] == '\\n':
            current_row.append(current_field)
            rows.append(current_row)
            current_row = []
            current_field = ""
            i += 2
        elif char == '\\n':
            current_row.append(current_field)
            rows.append(current_row)
            current_row = []
            current_field = ""
            i += 1
        else:
            current_field += char
            i += 1

    # Don't forget the last field/row
    if current_field or current_row:
        current_row.append(current_field)
        rows.append(current_row)

    return rows
''',
        acceptance_criteria=[
            "Tests basic CSV: simple rows with multiple columns",
            "Tests quoted fields containing delimiters (commas inside quotes)",
            "Tests escaped quotes (doubled quotes within quoted fields)",
            "Tests empty fields (adjacent delimiters, trailing delimiter)",
            "Tests multiline values within quoted fields",
            "Tests both \\n and \\r\\n line endings",
            "Tests empty input returns empty list",
            "Tests custom delimiter (e.g., tab-separated)",
        ],
        risk_level="low",
        stack="python/pytest",
    ),
    BenchmarkJob(
        id="test-retry-decorator",
        name="Write tests for retry decorator with backoff",
        category="testing",
        skill_domain="testing",
        test_set="tournament",
        input_prompt=(
            "Write pytest tests for this retry decorator. "
            "Verify retry count, backoff timing, exception filtering, and the final raise behavior."
        ),
        input_context='''import time
import functools
from typing import Type

def retry(
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    """Decorator that retries a function on failure with exponential backoff.

    Args:
        max_attempts: Total attempts (including first call).
        backoff_seconds: Initial wait between retries.
        backoff_multiplier: Multiply wait by this after each retry.
        retryable_exceptions: Only retry on these exception types.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            wait = backoff_seconds
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(wait)
                        wait *= backoff_multiplier
                except Exception:
                    raise  # Non-retryable — don't retry
            raise last_exception
        return wrapper
    return decorator
''',
        acceptance_criteria=[
            "Tests successful call on first attempt (no retries)",
            "Tests retries the correct number of times before raising",
            "Tests that the original exception is re-raised after all attempts fail",
            "Tests that non-retryable exceptions are raised immediately without retry",
            "Tests exponential backoff timing (mock time.sleep to verify wait durations)",
            "Tests that the decorator preserves the wrapped function's name (functools.wraps)",
        ],
        risk_level="low",
        stack="python/pytest",
    ),
    BenchmarkJob(
        id="test-cache-ttl",
        name="Write tests for TTL cache",
        category="testing",
        skill_domain="testing",
        test_set="tournament",
        input_prompt=(
            "Write pytest tests for this TTL cache. Test get/set, expiration, "
            "eviction when max_size is reached, and the stats reporting."
        ),
        input_context='''import time

class TTLCache:
    def __init__(self, max_size: int = 100, default_ttl: float = 60.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: dict[str, tuple[object, float]] = {}  # key -> (value, expires_at)
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> object | None:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.monotonic() < expires_at:
                self._hits += 1
                return value
            else:
                del self._store[key]
        self._misses += 1
        return None

    def set(self, key: str, value: object, ttl: float | None = None) -> None:
        if ttl is None:
            ttl = self.default_ttl
        if len(self._store) >= self.max_size and key not in self._store:
            self._evict_oldest()
        self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }

    def _evict_oldest(self) -> None:
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        del self._store[oldest_key]
''',
        acceptance_criteria=[
            "Tests get/set: store a value, retrieve it, get None for missing key",
            "Tests TTL expiration: value disappears after TTL (mock time.monotonic)",
            "Tests custom TTL: per-key TTL overrides default",
            "Tests max_size eviction: oldest entry removed when cache is full",
            "Tests delete: returns True for existing key, False for missing",
            "Tests stats: hit/miss counts and hit_rate calculation",
            "Tests clear: resets store and counters",
        ],
        risk_level="low",
        stack="python/pytest",
    ),
    BenchmarkJob(
        id="test-form-validation",
        name="Write tests for form validation logic",
        category="testing",
        skill_domain="testing",
        test_set="tournament",
        input_prompt=(
            "Write pytest tests for this form validation module. "
            "Cover valid inputs, each validation rule, and combined error scenarios."
        ),
        input_context='''import re

class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {errors}")

def validate_registration(data: dict) -> dict:
    """Validate user registration data. Raises ValidationError with all errors.

    Returns cleaned data if valid.
    """
    errors: list[str] = []
    cleaned: dict = {}

    # Email
    email = data.get("email", "").strip().lower()
    if not email:
        errors.append("Email is required")
    elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", email):
        errors.append("Invalid email format")
    else:
        cleaned["email"] = email

    # Password
    password = data.get("password", "")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    elif not re.search(r"[A-Z]", password):
        errors.append("Password must contain an uppercase letter")
    elif not re.search(r"[0-9]", password):
        errors.append("Password must contain a number")
    else:
        cleaned["password"] = password

    # Username
    username = data.get("username", "").strip()
    if not username:
        errors.append("Username is required")
    elif len(username) < 3 or len(username) > 20:
        errors.append("Username must be 3-20 characters")
    elif not re.match(r"^[a-zA-Z0-9_]+$", username):
        errors.append("Username can only contain letters, numbers, and underscores")
    else:
        cleaned["username"] = username

    # Age
    age = data.get("age")
    if age is not None:
        try:
            age = int(age)
            if age < 13 or age > 120:
                errors.append("Age must be between 13 and 120")
            else:
                cleaned["age"] = age
        except (ValueError, TypeError):
            errors.append("Age must be a number")

    if errors:
        raise ValidationError(errors)

    return cleaned
''',
        acceptance_criteria=[
            "Tests valid registration data passes and returns cleaned dict",
            "Tests missing email raises ValidationError",
            "Tests invalid email format raises ValidationError",
            "Tests password too short, missing uppercase, missing number each raise specific errors",
            "Tests username length bounds (too short, too long) and invalid characters",
            "Tests age validation: under 13, over 120, non-numeric",
            "Tests that email is lowercased and trimmed in cleaned output",
        ],
        risk_level="low",
        stack="python/pytest",
    ),
    BenchmarkJob(
        id="test-event-emitter",
        name="Write tests for event emitter pattern",
        category="testing",
        skill_domain="testing",
        test_set="tournament",
        input_prompt=(
            "Write pytest tests for this event emitter. Test subscription, emission, "
            "wildcard listeners, and the once() behavior."
        ),
        input_context='''from typing import Callable, Any

class EventEmitter:
    def __init__(self):
        self._listeners: dict[str, list[Callable]] = {}
        self._once_listeners: set[int] = set()  # ids of one-time listeners

    def on(self, event: str, callback: Callable) -> None:
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def once(self, event: str, callback: Callable) -> None:
        self._once_listeners.add(id(callback))
        self.on(event, callback)

    def off(self, event: str, callback: Callable) -> None:
        if event in self._listeners:
            self._listeners[event] = [
                cb for cb in self._listeners[event] if cb is not callback
            ]

    def emit(self, event: str, *args: Any, **kwargs: Any) -> int:
        """Emit event to all listeners. Returns number of listeners called."""
        count = 0
        to_remove = []

        # Specific listeners
        for cb in self._listeners.get(event, []):
            cb(*args, **kwargs)
            count += 1
            if id(cb) in self._once_listeners:
                to_remove.append((event, cb))
                self._once_listeners.discard(id(cb))

        # Wildcard listeners
        for cb in self._listeners.get("*", []):
            cb(event, *args, **kwargs)
            count += 1

        # Clean up once listeners
        for evt, cb in to_remove:
            self.off(evt, cb)

        return count

    def listener_count(self, event: str) -> int:
        return len(self._listeners.get(event, []))
''',
        acceptance_criteria=[
            "Tests on() registers a listener and emit() calls it with correct args",
            "Tests multiple listeners for the same event are all called",
            "Tests off() removes a specific listener",
            "Tests once() listener is called once then auto-removed",
            "Tests wildcard '*' listener receives all events with event name as first arg",
            "Tests emit() returns correct listener count",
            "Tests listener_count() returns 0 for unknown event",
        ],
        risk_level="low",
        stack="python/pytest",
    ),
]

# ── Frontend Tasks ───────────────────────────────────────────────────────────

FRONTEND_TASKS: list[BenchmarkJob] = [
    BenchmarkJob(
        id="fe-accessible-modal",
        name="Build an accessible modal dialog",
        category="feature",
        skill_domain="frontend",
        test_set="tournament",
        input_prompt=(
            "Build an accessible modal dialog component. It must trap focus, "
            "close on Escape, and follow WAI-ARIA dialog pattern. "
            "Use React and TypeScript."
        ),
        input_context='''// App.tsx — current implementation has no modal
import React, { useState } from "react";

function App() {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Product Page</h1>
      <p className="mb-4">A great product for $29.99</p>
      <button
        onClick={() => setShowDetails(true)}
        className="bg-blue-600 text-white px-4 py-2 rounded"
      >
        View Details
      </button>
      {showDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 max-w-md">
            <h2 className="text-xl font-bold mb-2">Product Details</h2>
            <p className="mb-4">Full specifications and reviews go here.</p>
            <button onClick={() => setShowDetails(false)} className="text-blue-600">
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
''',
        acceptance_criteria=[
            "Modal has role='dialog' and aria-modal='true'",
            "Modal has an accessible label (aria-labelledby or aria-label)",
            "Focus is trapped inside the modal when open (Tab cycles through modal elements only)",
            "Pressing Escape closes the modal",
            "Focus returns to the trigger button when modal closes",
            "Clicking the backdrop (outside the modal content) closes the modal",
        ],
        risk_level="low",
        stack="react/typescript",
    ),
    BenchmarkJob(
        id="fe-form-validation",
        name="Add client-side form validation with error messages",
        category="feature",
        skill_domain="frontend",
        test_set="tournament",
        input_prompt=(
            "Add client-side validation to this registration form. "
            "Show inline error messages below each field. "
            "Validate on blur and on submit. Don't submit if there are errors."
        ),
        input_context='''// RegisterForm.tsx
import React, { useState } from "react";

function RegisterForm() {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    username: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: validate before submitting
    fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-md mx-auto space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium">Email</label>
        <input id="email" type="email" value={formData.email}
          onChange={e => setFormData({...formData, email: e.target.value})}
          className="w-full border rounded px-3 py-2" />
      </div>
      <div>
        <label htmlFor="username" className="block text-sm font-medium">Username</label>
        <input id="username" type="text" value={formData.username}
          onChange={e => setFormData({...formData, username: e.target.value})}
          className="w-full border rounded px-3 py-2" />
      </div>
      <div>
        <label htmlFor="password" className="block text-sm font-medium">Password</label>
        <input id="password" type="password" value={formData.password}
          onChange={e => setFormData({...formData, password: e.target.value})}
          className="w-full border rounded px-3 py-2" />
      </div>
      <div>
        <label htmlFor="confirm" className="block text-sm font-medium">Confirm Password</label>
        <input id="confirm" type="password" value={formData.confirmPassword}
          onChange={e => setFormData({...formData, confirmPassword: e.target.value})}
          className="w-full border rounded px-3 py-2" />
      </div>
      <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded">
        Register
      </button>
    </form>
  );
}

export default RegisterForm;
''',
        acceptance_criteria=[
            "Email validation: shows error for invalid format",
            "Username validation: minimum 3 characters",
            "Password validation: minimum 8 characters with at least one number",
            "Confirm password: must match password field",
            "Errors display below each field on blur and on submit",
            "Form does not submit if there are validation errors",
            "Error messages are associated with inputs via aria-describedby",
        ],
        risk_level="low",
        stack="react/typescript",
    ),
    BenchmarkJob(
        id="fe-infinite-scroll",
        name="Implement infinite scroll with loading states",
        category="feature",
        skill_domain="frontend",
        test_set="tournament",
        input_prompt=(
            "Replace the 'Load More' button with infinite scroll. "
            "Show a loading spinner while fetching. Handle errors gracefully. "
            "Don't fire multiple requests simultaneously."
        ),
        input_context='''// ItemList.tsx
import React, { useState, useEffect } from "react";

interface Item {
  id: number;
  title: string;
  description: string;
}

function ItemList() {
  const [items, setItems] = useState<Item[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const loadMore = async () => {
    setLoading(true);
    const res = await fetch(`/api/items?page=${page}&limit=20`);
    const data = await res.json();
    setItems(prev => [...prev, ...data.items]);
    setPage(prev => prev + 1);
    setLoading(false);
  };

  useEffect(() => { loadMore(); }, []);

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Items</h1>
      <div className="space-y-4">
        {items.map(item => (
          <div key={item.id} className="border rounded p-4">
            <h3 className="font-semibold">{item.title}</h3>
            <p className="text-gray-600">{item.description}</p>
          </div>
        ))}
      </div>
      <button onClick={loadMore} disabled={loading}
        className="mt-4 w-full py-2 bg-blue-600 text-white rounded">
        {loading ? "Loading..." : "Load More"}
      </button>
    </div>
  );
}

export default ItemList;
''',
        acceptance_criteria=[
            "Uses IntersectionObserver (or scroll event) to detect when user nears bottom",
            "Shows a loading spinner/indicator while fetching new items",
            "Prevents duplicate requests (doesn't fire while already loading)",
            "Handles fetch errors gracefully (shows error message, allows retry)",
            "Stops fetching when no more items are available (end of list detection)",
            "Cleans up observer/listener on component unmount",
        ],
        risk_level="low",
        stack="react/typescript",
    ),
    BenchmarkJob(
        id="fe-dark-mode-system",
        name="Add system-aware dark mode with persistence",
        category="feature",
        skill_domain="frontend",
        test_set="tournament",
        input_prompt=(
            "Add dark mode to this app. Requirements:\n"
            "1. Toggle button in the nav\n"
            "2. Default to system preference (prefers-color-scheme)\n"
            "3. User choice overrides system and persists via localStorage\n"
            "4. No flash of wrong theme on page load"
        ),
        input_context='''// App.tsx
import React from "react";

function App() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <nav className="bg-gray-100 p-4 flex justify-between items-center border-b">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-4">
          <span>user@example.com</span>
          {/* TODO: dark mode toggle */}
        </div>
      </nav>
      <main className="p-8">
        <div className="grid grid-cols-3 gap-6">
          <div className="bg-gray-50 rounded-lg p-6 shadow">
            <h2 className="font-semibold text-gray-700">Revenue</h2>
            <p className="text-3xl font-bold mt-2">$12,340</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-6 shadow">
            <h2 className="font-semibold text-gray-700">Orders</h2>
            <p className="text-3xl font-bold mt-2">156</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-6 shadow">
            <h2 className="font-semibold text-gray-700">Customers</h2>
            <p className="text-3xl font-bold mt-2">2,340</p>
          </div>
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
            "Enables Tailwind dark mode with class strategy (darkMode: 'class')",
            "Adds dark: variants to all color classes in the template",
            "Reads system preference via window.matchMedia('(prefers-color-scheme: dark)')",
            "Persists user choice in localStorage",
            "User choice overrides system preference when set",
            "No flash of incorrect theme (applies class before first render)",
        ],
        risk_level="low",
        stack="react/typescript/tailwind",
    ),
    BenchmarkJob(
        id="fe-responsive-table",
        name="Make a data table responsive for mobile",
        category="feature",
        skill_domain="frontend",
        test_set="tournament",
        input_prompt=(
            "Make this data table work well on mobile screens (< 640px). "
            "On desktop, show the full table. On mobile, use a card-based layout. "
            "Keep sorting and all data visible."
        ),
        input_context='''// DataTable.tsx
import React, { useState } from "react";

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  status: string;
  lastLogin: string;
}

const USERS: User[] = [
  { id: 1, name: "Alice Chen", email: "alice@example.com", role: "Admin", status: "Active", lastLogin: "2026-03-15" },
  { id: 2, name: "Bob Smith", email: "bob@example.com", role: "Editor", status: "Active", lastLogin: "2026-03-14" },
  { id: 3, name: "Carol Wu", email: "carol@example.com", role: "Viewer", status: "Inactive", lastLogin: "2026-02-20" },
  { id: 4, name: "David Kim", email: "david@example.com", role: "Editor", status: "Active", lastLogin: "2026-03-15" },
];

function DataTable() {
  const [sortBy, setSortBy] = useState<keyof User>("name");
  const sorted = [...USERS].sort((a, b) => String(a[sortBy]).localeCompare(String(b[sortBy])));

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Users</h1>
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-100">
            {["name", "email", "role", "status", "lastLogin"].map(col => (
              <th key={col} onClick={() => setSortBy(col as keyof User)}
                className="px-4 py-2 text-left cursor-pointer hover:bg-gray-200">
                {col} {sortBy === col ? "▼" : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map(user => (
            <tr key={user.id} className="border-t hover:bg-gray-50">
              <td className="px-4 py-2">{user.name}</td>
              <td className="px-4 py-2">{user.email}</td>
              <td className="px-4 py-2">{user.role}</td>
              <td className="px-4 py-2">{user.status}</td>
              <td className="px-4 py-2">{user.lastLogin}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;
''',
        acceptance_criteria=[
            "Desktop (>= 640px) shows a proper table layout",
            "Mobile (< 640px) shows a card-based or stacked layout (not a squished table)",
            "All data fields are visible in both layouts",
            "Sorting functionality works in both layouts",
            "Uses CSS media queries or Tailwind responsive classes (not JS window.innerWidth)",
            "Cards on mobile have clear labels for each data field",
        ],
        risk_level="low",
        stack="react/typescript/tailwind",
    ),
    BenchmarkJob(
        id="fe-toast-notifications",
        name="Build a toast notification system",
        category="feature",
        skill_domain="frontend",
        test_set="tournament",
        input_prompt=(
            "Build a toast notification system. Requirements:\n"
            "- Support success, error, warning, and info types\n"
            "- Auto-dismiss after 5 seconds with a progress bar\n"
            "- Dismissable by clicking\n"
            "- Stack multiple toasts vertically"
        ),
        input_context='''// App.tsx — needs toast system
import React from "react";

function App() {
  const handleSave = () => {
    // TODO: show success toast "Settings saved"
    alert("Settings saved");
  };

  const handleDelete = () => {
    // TODO: show error toast "Failed to delete"
    alert("Failed to delete");
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Settings</h1>
      <div className="space-y-4">
        <button onClick={handleSave}
          className="bg-green-600 text-white px-4 py-2 rounded">
          Save Settings
        </button>
        <button onClick={handleDelete}
          className="bg-red-600 text-white px-4 py-2 rounded">
          Delete Account
        </button>
      </div>
    </div>
  );
}

export default App;
''',
        acceptance_criteria=[
            "Toast component supports at least 4 types: success, error, warning, info",
            "Toasts auto-dismiss after configurable duration (default ~5 seconds)",
            "Toasts include a visible progress bar or countdown indicator",
            "Multiple toasts stack vertically without overlapping",
            "Toasts can be dismissed by clicking a close button",
            "Uses React context or a hook (useToast) for showing toasts from any component",
        ],
        risk_level="low",
        stack="react/typescript",
    ),
    BenchmarkJob(
        id="fe-search-debounce",
        name="Add debounced search with highlight",
        category="feature",
        skill_domain="frontend",
        test_set="tournament",
        input_prompt=(
            "Add a search bar that filters the list as you type. "
            "Debounce the input (300ms). Highlight matching text in results. "
            "Show 'No results' when nothing matches."
        ),
        input_context='''// SearchList.tsx
import React, { useState } from "react";

interface Article {
  id: number;
  title: string;
  summary: string;
  author: string;
}

const ARTICLES: Article[] = [
  { id: 1, title: "Getting Started with React 19", summary: "A guide to the latest React features including Server Components and Actions.", author: "Sarah Chen" },
  { id: 2, title: "Building REST APIs with FastAPI", summary: "Learn to build high-performance Python APIs with automatic OpenAPI docs.", author: "James Wilson" },
  { id: 3, title: "CSS Grid Layout Deep Dive", summary: "Master grid-template-areas, auto-fit, and responsive grid patterns.", author: "Maria Garcia" },
  { id: 4, title: "TypeScript Generics Explained", summary: "Understand generic types, constraints, and real-world utility types.", author: "Tom Anderson" },
  { id: 5, title: "Database Indexing Strategies", summary: "When to add indexes, composite indexes, and covering indexes for performance.", author: "Lisa Park" },
];

function SearchList() {
  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-4">Articles</h1>
      {/* TODO: search input */}
      <div className="space-y-4">
        {ARTICLES.map(article => (
          <div key={article.id} className="border rounded p-4">
            <h3 className="font-semibold">{article.title}</h3>
            <p className="text-gray-600 text-sm">{article.summary}</p>
            <span className="text-xs text-gray-400">by {article.author}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SearchList;
''',
        acceptance_criteria=[
            "Search input filters articles by title, summary, and author",
            "Input is debounced (search fires 300ms after user stops typing)",
            "Matching text is highlighted in results (bold, background color, or mark element)",
            "Shows 'No results found' message when search yields nothing",
            "Clearing the search shows all articles again",
            "Debounce cleanup on unmount (no memory leak from pending timeout)",
        ],
        risk_level="low",
        stack="react/typescript",
    ),
    BenchmarkJob(
        id="fe-keyboard-nav",
        name="Add keyboard navigation to dropdown menu",
        category="feature",
        skill_domain="frontend",
        test_set="tournament",
        input_prompt=(
            "Make this dropdown menu fully keyboard accessible. "
            "Arrow keys to navigate, Enter to select, Escape to close. "
            "Follow the WAI-ARIA Listbox pattern."
        ),
        input_context='''// Dropdown.tsx
import React, { useState, useRef } from "react";

interface Option {
  value: string;
  label: string;
}

const OPTIONS: Option[] = [
  { value: "react", label: "React" },
  { value: "vue", label: "Vue" },
  { value: "angular", label: "Angular" },
  { value: "svelte", label: "Svelte" },
  { value: "solid", label: "SolidJS" },
];

function Dropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const [selected, setSelected] = useState<Option | null>(null);

  return (
    <div className="relative w-64">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2 border rounded text-left bg-white"
      >
        {selected ? selected.label : "Select framework..."}
      </button>
      {isOpen && (
        <ul className="absolute w-full mt-1 border rounded bg-white shadow-lg max-h-60 overflow-auto">
          {OPTIONS.map(opt => (
            <li
              key={opt.value}
              onClick={() => { setSelected(opt); setIsOpen(false); }}
              className="px-4 py-2 hover:bg-blue-100 cursor-pointer"
            >
              {opt.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default Dropdown;
''',
        acceptance_criteria=[
            "Arrow Down/Up navigates through options with visible focus indicator",
            "Enter selects the currently focused option",
            "Escape closes the dropdown without changing selection",
            "Tab moves focus out of the dropdown (closes it)",
            "ARIA attributes: role='listbox' on list, role='option' on items, aria-activedescendant on trigger",
            "Home/End keys jump to first/last option",
        ],
        risk_level="low",
        stack="react/typescript",
    ),
]

# ── Backend Tasks ────────────────────────────────────────────────────────────

BACKEND_TASKS: list[BenchmarkJob] = [
    BenchmarkJob(
        id="be-batch-endpoint",
        name="Add batch processing endpoint with validation",
        category="feature",
        skill_domain="backend",
        test_set="tournament",
        input_prompt=(
            "Add a POST /items/batch endpoint that accepts up to 100 items "
            "and inserts them in a single transaction. Validate each item. "
            "Return which items succeeded and which failed with reasons."
        ),
        input_context='''from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3

app = FastAPI()
DB = "items.db"

class Item(BaseModel):
    name: str
    price: float
    category: str

@app.post("/items")
def create_item(item: Item):
    if item.price < 0:
        raise HTTPException(400, "Price must be positive")
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO items (name, price, category) VALUES (?, ?, ?)",
        (item.name, item.price, item.category),
    )
    conn.commit()
    conn.close()
    return {"status": "created", "item": item.dict()}

@app.get("/items")
def list_items():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM items").fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}
''',
        acceptance_criteria=[
            "POST /items/batch accepts a list of items",
            "Validates each item individually (price >= 0, name non-empty)",
            "Enforces max batch size of 100 items",
            "Uses a single database transaction for all inserts (atomic)",
            "Returns per-item results showing which succeeded and which failed with reasons",
            "Failed items don't prevent valid items from being inserted (partial success)",
        ],
        risk_level="medium",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="be-health-endpoint",
        name="Build a comprehensive health check endpoint",
        category="feature",
        skill_domain="backend",
        test_set="tournament",
        input_prompt=(
            "Add a /health endpoint that checks all dependencies: database, "
            "Redis cache, and external API. Return status for each dependency "
            "and an overall status. Include response time for each check."
        ),
        input_context='''from fastapi import FastAPI
import sqlite3
import redis
import requests
import os

app = FastAPI()

DB_PATH = os.environ.get("DB_PATH", "app.db")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
EXTERNAL_API = os.environ.get("EXTERNAL_API_URL", "https://api.example.com/status")

@app.get("/")
def root():
    return {"service": "my-api", "version": "1.0.0"}

@app.get("/items")
def list_items():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM items").fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}
''',
        acceptance_criteria=[
            "GET /health returns overall status (healthy/degraded/unhealthy)",
            "Checks database connectivity with a simple query (e.g., SELECT 1)",
            "Checks Redis connectivity with PING",
            "Checks external API with a timeout-protected request",
            "Reports individual status for each dependency",
            "Includes response_time_ms for each check",
            "Returns HTTP 200 for healthy/degraded, 503 for unhealthy",
        ],
        risk_level="low",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="be-cursor-pagination",
        name="Implement cursor-based pagination",
        category="feature",
        skill_domain="backend",
        test_set="tournament",
        input_prompt=(
            "Replace offset pagination with cursor-based pagination on this endpoint. "
            "Use the item's created_at + id as the cursor. Support forward and backward navigation."
        ),
        input_context='''from fastapi import FastAPI, Query
import sqlite3
from datetime import datetime

app = FastAPI()
DB = "posts.db"

@app.get("/posts")
def list_posts(page: int = Query(default=1), size: int = Query(default=20, le=100)):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    offset = (page - 1) * size
    rows = conn.execute(
        "SELECT id, title, content, author, created_at FROM posts "
        "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        (size, offset),
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    conn.close()
    return {
        "posts": [dict(r) for r in rows],
        "page": page,
        "total_pages": -(-total // size),
        "total": total,
    }
''',
        acceptance_criteria=[
            "Replaces page/offset params with cursor parameter (opaque string)",
            "Cursor encodes created_at + id for stable ordering",
            "Supports forward navigation (after cursor)",
            "Returns next_cursor and has_more in the response",
            "Handles first page (no cursor provided)",
            "Returns consistent results even when new items are inserted between requests",
        ],
        risk_level="medium",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="be-webhook-retry",
        name="Build webhook delivery with retry logic",
        category="feature",
        skill_domain="backend",
        test_set="tournament",
        input_prompt=(
            "Build a webhook delivery system. When an event occurs, POST it to all "
            "registered webhook URLs. If delivery fails, retry with exponential backoff "
            "(3 retries, 1s/2s/4s delays). Log all delivery attempts."
        ),
        input_context='''from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import json

app = FastAPI()
DB = "webhooks.db"

class WebhookRegistration(BaseModel):
    url: str
    events: list[str]  # e.g. ["order.created", "order.completed"]

@app.post("/webhooks/register")
def register_webhook(reg: WebhookRegistration):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO webhooks (url, events_json) VALUES (?, ?)",
        (reg.url, json.dumps(reg.events)),
    )
    conn.commit()
    conn.close()
    return {"status": "registered", "url": reg.url}

@app.get("/webhooks")
def list_webhooks():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM webhooks").fetchall()
    conn.close()
    return {"webhooks": [dict(r) for r in rows]}
''',
        acceptance_criteria=[
            "Function to deliver event payload to all matching webhook URLs",
            "HTTP POST with JSON body containing event type and payload",
            "Retries failed deliveries with exponential backoff (3 attempts)",
            "Logs each delivery attempt (URL, status code, attempt number, success/failure)",
            "Does not block the main request — delivery runs asynchronously",
            "Includes a signature header for webhook verification (HMAC or similar)",
        ],
        risk_level="medium",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="be-idempotent-endpoint",
        name="Make a payment endpoint idempotent",
        category="feature",
        skill_domain="backend",
        test_set="tournament",
        input_prompt=(
            "Make this payment endpoint idempotent using an idempotency key. "
            "If the same key is used twice, return the original result. "
            "Handle concurrent requests with the same key safely."
        ),
        input_context='''from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import sqlite3
import uuid
import time

app = FastAPI()
DB = "payments.db"

class PaymentRequest(BaseModel):
    amount: float
    currency: str
    recipient: str

@app.post("/payments")
def create_payment(payment: PaymentRequest):
    payment_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO payments (id, amount, currency, recipient, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (payment_id, payment.amount, payment.currency, payment.recipient,
         "completed", time.strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    conn.commit()
    conn.close()
    return {"payment_id": payment_id, "status": "completed", "amount": payment.amount}
''',
        acceptance_criteria=[
            "Accepts Idempotency-Key header on the payment request",
            "First request with a key processes normally and stores the result",
            "Subsequent requests with the same key return the stored result without re-processing",
            "Returns 409 or 422 if same key is used with different payment parameters",
            "Handles concurrent requests with the same key (no double-processing)",
            "Idempotency records expire after a reasonable time (e.g., 24 hours)",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="be-soft-delete",
        name="Implement soft delete with restore capability",
        category="feature",
        skill_domain="backend",
        test_set="tournament",
        input_prompt=(
            "Convert the hard DELETE to soft delete. Items should be marked as deleted "
            "but recoverable. Add a restore endpoint. Soft-deleted items should be hidden "
            "from normal queries but visible via an admin endpoint."
        ),
        input_context='''from fastapi import FastAPI, HTTPException
import sqlite3

app = FastAPI()
DB = "projects.db"

@app.get("/projects")
def list_projects():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name, owner, created_at FROM projects").fetchall()
    conn.close()
    return {"projects": [dict(r) for r in rows]}

@app.get("/projects/{project_id}")
def get_project(project_id: int):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Project not found")
    return dict(row)

@app.delete("/projects/{project_id}")
def delete_project(project_id: int):
    conn = sqlite3.connect(DB)
    result = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(404, "Project not found")
    return {"deleted": project_id}
''',
        acceptance_criteria=[
            "DELETE /projects/{id} sets a deleted_at timestamp instead of removing the row",
            "GET /projects excludes soft-deleted items by default",
            "GET /projects/{id} returns 404 for soft-deleted items",
            "POST /projects/{id}/restore restores a soft-deleted item",
            "GET /admin/projects/deleted lists all soft-deleted items",
            "Explains the schema change needed (adding deleted_at column)",
        ],
        risk_level="low",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="be-api-versioning",
        name="Add API versioning to existing endpoints",
        category="feature",
        skill_domain="backend",
        test_set="tournament",
        input_prompt=(
            "Add versioning to this API. v1 should keep the current behavior. "
            "v2 should change the response format for /users to include pagination metadata "
            "and change the user schema to split 'name' into 'first_name' and 'last_name'. "
            "Both versions must work simultaneously."
        ),
        input_context='''from fastapi import FastAPI
import sqlite3

app = FastAPI()
DB = "users.db"

@app.get("/users")
def list_users():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name, email FROM users LIMIT 100").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/users/{user_id}")
def get_user(user_id: int):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "User not found")
    return dict(row)
''',
        acceptance_criteria=[
            "Both /v1/users and /v2/users work simultaneously",
            "v1 returns the same format as the current API (list of users)",
            "v2 wraps response in pagination metadata (items, total, page)",
            "v2 splits name into first_name and last_name",
            "Uses FastAPI router or similar clean pattern (not if/else per endpoint)",
            "Unversioned paths (/users) either redirect or return v1 for backward compatibility",
        ],
        risk_level="medium",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="be-cache-middleware",
        name="Add response caching middleware",
        category="feature",
        skill_domain="backend",
        test_set="tournament",
        input_prompt=(
            "Add response caching for GET requests. Cache responses for 60 seconds. "
            "Support cache invalidation when data changes. "
            "Include Cache-Control and ETag headers."
        ),
        input_context='''from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import time

app = FastAPI()
DB = "catalog.db"

class Product(BaseModel):
    name: str
    price: float
    description: str

@app.get("/products")
def list_products():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close()
    return {"products": [dict(r) for r in rows]}

@app.get("/products/{product_id}")
def get_product(product_id: int):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Product not found")
    return dict(row)

@app.post("/products")
def create_product(product: Product):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO products (name, price, description) VALUES (?, ?, ?)",
        (product.name, product.price, product.description),
    )
    conn.commit()
    conn.close()
    return {"status": "created"}
''',
        acceptance_criteria=[
            "GET requests are cached with a configurable TTL (default 60s)",
            "Cache-Control header set on cached responses (max-age=60)",
            "ETag header included based on response content hash",
            "POST/PUT/DELETE requests invalidate relevant cache entries",
            "If-None-Match header support returns 304 when content unchanged",
            "Cache is in-memory (dict or similar) — not an external dependency",
        ],
        risk_level="medium",
        stack="python/fastapi",
    ),
]

# ── Security Tasks ───────────────────────────────────────────────────────────

SECURITY_TASKS: list[BenchmarkJob] = [
    BenchmarkJob(
        id="sec-csrf-protection",
        name="Add CSRF protection to form-based endpoints",
        category="feature",
        skill_domain="security",
        test_set="tournament",
        input_prompt=(
            "Add CSRF protection to this application. The API serves both a web form "
            "and JSON API endpoints. Form submissions must include a valid CSRF token."
        ),
        input_context='''from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3

app = FastAPI()
templates = Jinja2Templates(directory="templates")
DB = "app.db"

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "email_notifications": row[1] if row else True,
        "theme": row[2] if row else "light",
    })

@app.post("/settings/update")
async def update_settings(
    email_notifications: bool = Form(default=True),
    theme: str = Form(default="light"),
):
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE settings SET email_notifications = ?, theme = ? WHERE id = 1",
        (email_notifications, theme),
    )
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.post("/account/delete")
async def delete_account(user_id: int = Form(...)):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}
''',
        acceptance_criteria=[
            "Generates a unique CSRF token per session (not a static value)",
            "CSRF token is included in form HTML as a hidden field",
            "POST endpoints validate the CSRF token before processing",
            "Returns 403 if CSRF token is missing or invalid",
            "JSON API endpoints use a different auth mechanism (API key or JWT) unaffected by CSRF",
            "Tokens use a cryptographically secure random generator (secrets module)",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="sec-input-sanitization",
        name="Add input sanitization to prevent XSS",
        category="feature",
        skill_domain="security",
        test_set="tournament",
        input_prompt=(
            "This application renders user-generated content in HTML. "
            "Add proper input sanitization to prevent stored XSS attacks."
        ),
        input_context='''from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3

app = FastAPI()
DB = "comments.db"

@app.post("/comments")
def add_comment(author: str, content: str):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO comments (author, content) VALUES (?, ?)",
        (author, content),
    )
    conn.commit()
    conn.close()
    return {"status": "created"}

@app.get("/comments", response_class=HTMLResponse)
def list_comments():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM comments ORDER BY id DESC").fetchall()
    conn.close()

    html = "<html><body><h1>Comments</h1>"
    for row in rows:
        html += f"<div class='comment'>"
        html += f"<strong>{row['author']}</strong>"
        html += f"<p>{row['content']}</p>"
        html += f"</div>"
    html += "</body></html>"
    return html

@app.get("/profile/{username}", response_class=HTMLResponse)
def profile(username: str):
    return f"<html><body><h1>Profile: {username}</h1></body></html>"
''',
        acceptance_criteria=[
            "Identifies stored XSS in comment rendering (author and content injected raw into HTML)",
            "Identifies reflected XSS in the profile endpoint (username in URL rendered raw)",
            "Implements HTML escaping for all user-provided content before rendering",
            "Uses html.escape() or a template engine with auto-escaping (Jinja2)",
            "Input validation rejects or strips script tags and event handlers",
            "Content-Security-Policy header recommended to mitigate residual XSS risk",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="sec-password-hashing",
        name="Fix insecure password storage",
        category="bugfix",
        skill_domain="security",
        test_set="tournament",
        input_prompt=(
            "Fix the password storage in this auth system. "
            "The current implementation stores passwords insecurely. "
            "Add proper hashing and a migration path for existing users."
        ),
        input_context='''from fastapi import FastAPI, HTTPException
import sqlite3
import hashlib

app = FastAPI()
DB = "users.db"

@app.post("/register")
def register(username: str, password: str, email: str):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(DB)
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, hashed, email),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Username already exists")
    finally:
        conn.close()
    return {"status": "registered"}

@app.post("/login")
def login(username: str, password: str):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, hashed),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "Invalid credentials")
    return {"message": f"Welcome {username}", "token": "some-token"}

@app.post("/change-password")
def change_password(username: str, old_password: str, new_password: str):
    old_hash = hashlib.sha256(old_password.encode()).hexdigest()
    new_hash = hashlib.sha256(new_password.encode()).hexdigest()
    conn = sqlite3.connect(DB)
    result = conn.execute(
        "UPDATE users SET password_hash = ? WHERE username = ? AND password_hash = ?",
        (new_hash, username, old_hash),
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(400, "Invalid current password")
    return {"status": "password changed"}
''',
        acceptance_criteria=[
            "Replaces SHA-256 with bcrypt, argon2, or scrypt (adaptive hashing)",
            "New hashes include a random salt (built into bcrypt/argon2)",
            "Login compares using constant-time comparison (built into bcrypt.checkpw)",
            "Password change verifies old password before setting new one",
            "Provides a migration path for existing SHA-256 hashes (re-hash on next login)",
            "Explains why SHA-256 is insufficient (no salt, too fast, rainbow tables)",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="sec-rate-limit-login",
        name="Add rate limiting and lockout to login endpoint",
        category="feature",
        skill_domain="security",
        test_set="tournament",
        input_prompt=(
            "Add brute-force protection to this login endpoint. "
            "Limit login attempts per IP and per username. "
            "Implement temporary account lockout after too many failures."
        ),
        input_context='''from fastapi import FastAPI, HTTPException, Request
import sqlite3
import bcrypt

app = FastAPI()
DB = "auth.db"

@app.post("/login")
def login(request: Request, username: str, password: str):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(401, "Invalid credentials")

    if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")

    return {"token": "jwt-token-here", "user": row["username"]}
''',
        acceptance_criteria=[
            "Limits login attempts per IP (e.g., 10 per minute)",
            "Limits login attempts per username (e.g., 5 per 15 minutes)",
            "Locks account temporarily after N failed attempts (e.g., 5 failures = 15 min lockout)",
            "Returns 429 Too Many Requests when rate limit exceeded",
            "Returns generic 'Invalid credentials' (doesn't reveal if username exists)",
            "Tracks failed attempts in a store (dict, Redis, or DB) with TTL cleanup",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="sec-jwt-refresh",
        name="Implement JWT access + refresh token rotation",
        category="feature",
        skill_domain="security",
        test_set="tournament",
        input_prompt=(
            "Implement proper JWT token management: short-lived access tokens (15 min) "
            "and long-lived refresh tokens (7 days). Add token refresh endpoint with "
            "rotation (old refresh token is invalidated when a new one is issued)."
        ),
        input_context='''from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import time
import os

app = FastAPI()
security = HTTPBearer()
SECRET = os.environ.get("JWT_SECRET", "dev-secret")

@app.post("/login")
def login(username: str, password: str):
    # Assume password check passes
    token = jwt.encode(
        {"sub": username, "exp": time.time() + 86400},  # 24 hour token
        SECRET, algorithm="HS256",
    )
    return {"token": token}

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

@app.get("/me")
def me(user=Depends(get_current_user)):
    return {"user": user["sub"]}
''',
        acceptance_criteria=[
            "Access token expires in 15 minutes (not 24 hours)",
            "Refresh token issued alongside access token, expires in 7 days",
            "POST /refresh accepts refresh token and returns new access + refresh token pair",
            "Old refresh token is invalidated after rotation (stored in DB or blacklist)",
            "Refresh token is stored securely (not in the same JWT — use opaque token or separate signing)",
            "Token type is distinguishable (access vs refresh — different claims or different secrets)",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="sec-file-upload-validation",
        name="Secure file upload endpoint against attacks",
        category="feature",
        skill_domain="security",
        test_set="tournament",
        input_prompt=(
            "Review and fix this file upload endpoint. "
            "It needs to be hardened against path traversal, "
            "shell injection via filenames, and unrestricted file types."
        ),
        input_context='''from fastapi import FastAPI, UploadFile
from pathlib import Path
import os
import subprocess

app = FastAPI()
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile):
    # Save file
    filepath = UPLOAD_DIR / file.filename
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # Generate thumbnail if image
    if file.filename.endswith((".png", ".jpg", ".jpeg")):
        thumb_path = UPLOAD_DIR / f"thumb_{file.filename}"
        os.system(f"convert {filepath} -resize 200x200 {thumb_path}")

    return {"filename": file.filename, "size": len(content), "path": str(filepath)}

@app.get("/files/{filename}")
def get_file(filename: str):
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "File not found")
    return {"file": filename, "size": filepath.stat().st_size}
''',
        acceptance_criteria=[
            "Identifies path traversal via filename (../../etc/passwd)",
            "Identifies shell injection via os.system with unsanitized filename",
            "Replaces os.system with subprocess.run and proper argument list (no shell=True)",
            "Generates safe filenames (UUID or hash, not user-supplied)",
            "Validates file type by MIME/magic bytes, not just extension",
            "Adds file size limit to prevent denial of service",
            "Ensures filepath stays within UPLOAD_DIR (resolve and check prefix)",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="sec-cors-misconfiguration",
        name="Fix CORS misconfiguration in production API",
        category="bugfix",
        skill_domain="security",
        test_set="tournament",
        input_prompt=(
            "Review and fix the CORS configuration on this API. "
            "The frontend is at https://app.example.com. "
            "The API is at https://api.example.com."
        ),
        input_context='''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/public/status")
def public_status():
    return {"status": "ok", "version": "2.0"}

@app.get("/api/user/profile")
def user_profile():
    # Requires auth cookie
    return {"name": "Test User", "email": "test@example.com", "ssn": "123-45-6789"}

@app.post("/api/user/transfer")
def transfer_funds(to_account: str, amount: float):
    # Requires auth cookie
    return {"status": "transferred", "amount": amount, "to": to_account}

@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int):
    return {"deleted": user_id}
''',
        acceptance_criteria=[
            "Identifies that allow_origins=['*'] with allow_credentials=True is a security vulnerability",
            "Explains that browsers reject credentials with wildcard origin",
            "Restricts allow_origins to specific domains (https://app.example.com)",
            "Restricts allow_methods to only the methods actually used",
            "Restricts allow_headers to only the headers actually needed",
            "Recommends reading allowed origins from environment variable for deployment flexibility",
        ],
        risk_level="high",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="sec-secret-scanning",
        name="Scan codebase for exposed secrets",
        category="review",
        skill_domain="security",
        test_set="tournament",
        input_prompt=(
            "Scan this configuration module for exposed secrets and credentials. "
            "Identify each secret, assess the risk, and provide remediation."
        ),
        input_context='''import os
import boto3
import stripe
import redis

# Database
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = "admin"
DB_PASSWORD = "Pr0d_p@ssw0rd!2026"
DB_NAME = "production"

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# AWS
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
S3_BUCKET = "company-production-data"

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

# Stripe
stripe.api_key = "sk_live_FAKE_EXAMPLE_KEY_FOR_BENCHMARK_TEST"
STRIPE_WEBHOOK_SECRET = "whsec_EXAMPLEKEY1234567890"

# Redis
REDIS_URL = "redis://:SuperSecretRedisPassword@redis.internal:6379/0"

# JWT
JWT_SECRET = "my-super-secret-jwt-key-that-nobody-will-guess"

# Email
SMTP_PASSWORD = "email-app-specific-password-123"
SENDGRID_API_KEY = "SG.EXAMPLEKEY.abcdefghijklmnopqrstuvwxyz012345"

# Internal
ADMIN_API_KEY = "whcert-admin-ak_live_1234567890"
INTERNAL_SERVICE_TOKEN = "svc-token-9f8e7d6c5b4a3210"
''',
        acceptance_criteria=[
            "Identifies all hardcoded secrets (DB password, AWS keys, Stripe keys, Redis password, JWT secret, SMTP password, SendGrid key, admin key, service token)",
            "Rates severity for each (AWS keys and Stripe live key = critical; others = high)",
            "Recommends moving all secrets to environment variables",
            "Recommends .env.example with placeholder values",
            "Recommends checking git history for previously committed secrets",
            "Recommends rotating all exposed credentials immediately",
        ],
        risk_level="high",
        stack="python",
    ),
]

# ── Task Pool Registry ───────────────────────────────────────────────────────

DOMAIN_TASK_POOLS: dict[str, list[BenchmarkJob]] = {
    "code-review": CODE_REVIEW_TASKS,
    "testing": TESTING_TASKS,
    "frontend": FRONTEND_TASKS,
    "backend": BACKEND_TASKS,
    "security": SECURITY_TASKS,
}


def select_tasks(
    domain: str,
    count: int = 5,
    exclude_ids: set[str] | None = None,
) -> list[BenchmarkJob]:
    """Select tasks for a tournament, excluding recently used tasks.

    Randomly samples `count` tasks from the domain pool, avoiding any
    task IDs in `exclude_ids` (typically last week's tasks, to prevent
    overfitting).

    Args:
        domain: Tournament category slug (e.g., "code-review").
        count: Number of tasks to select.
        exclude_ids: Task IDs to exclude (e.g., from the previous tournament).

    Returns:
        List of BenchmarkJob instances. Fewer than `count` if the pool
        is too small after exclusions.

    Raises:
        ValueError: If the domain is not recognized.
    """
    pool = DOMAIN_TASK_POOLS.get(domain)
    if pool is None:
        raise ValueError(
            f"Unknown domain '{domain}'. "
            f"Available: {list(DOMAIN_TASK_POOLS.keys())}"
        )

    if exclude_ids:
        pool = [t for t in pool if t.id not in exclude_ids]

    if len(pool) <= count:
        return list(pool)

    return random.sample(pool, count)
