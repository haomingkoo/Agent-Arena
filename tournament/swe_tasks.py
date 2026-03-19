"""
Software engineer agent benchmark tasks.

Aligned with BLS software developer duties and the JD role-test matrix:
- implement a feature from a spec
- fix a failing defect
- add or repair tests
- analyze a production issue
- reason about system tradeoffs

Each task tests a different competency from the role blueprint.
"""
from __future__ import annotations

from evaluate.sandbox import BenchmarkJob

SOFTWARE_ENGINEER_TASKS: list[BenchmarkJob] = [
    BenchmarkJob(
        id="swe-implement-pagination",
        name="Implement cursor-based pagination from spec",
        category="software-engineering",
        skill_domain="software-engineer-agent",
        task_bucket="anchor",
        difficulty="medium",
        test_set="agent-pack-v1",
        input_prompt=(
            "Implement cursor-based pagination for this endpoint. "
            "Follow the spec exactly. Return the updated code."
        ),
        input_context="""\
Current endpoint:

```python
from fastapi import FastAPI, Query
from datetime import datetime

app = FastAPI()

ITEMS = []  # populated at startup from DB

@app.get("/api/items")
def list_items():
    return {"items": ITEMS}
```

Spec:
- Add `cursor` (optional str) and `limit` (int, default 20, max 100) query params
- Cursor is the ISO timestamp of the last item seen
- Items are sorted by `created_at` descending
- Response must include `items`, `next_cursor` (str or null), and `has_more` (bool)
- If cursor is provided, only return items with `created_at` < cursor
- Each item is a dict with keys: id, name, created_at (ISO string)
- Return 400 if limit < 1 or limit > 100
""",
        acceptance_criteria=[
            "Adds cursor and limit query parameters with correct types and defaults",
            "Filters items by created_at < cursor when cursor is provided",
            "Sorts items by created_at descending",
            "Returns next_cursor from the last item in the page",
            "Returns has_more boolean indicating if more items exist",
            "Validates limit range (1-100) and returns 400 on invalid input",
        ],
        risk_level="low",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="swe-fix-race-condition",
        name="Fix concurrent counter bug",
        category="software-engineering",
        skill_domain="software-engineer-agent",
        task_bucket="anchor",
        difficulty="hard",
        test_set="agent-pack-v1",
        input_prompt=(
            "This counter service has a race condition that causes lost updates "
            "under concurrent load. Identify the bug and provide a corrected implementation."
        ),
        input_context="""\
Bug report: Counter loses increments under concurrent requests.
Expected: 1000 concurrent increments should result in count=1000.
Actual: count varies between 970-995.

```python
import asyncio
from fastapi import FastAPI

app = FastAPI()

counter = {"value": 0}

@app.post("/increment")
async def increment():
    current = counter["value"]
    await asyncio.sleep(0.001)  # simulates async DB read
    counter["value"] = current + 1
    return {"count": counter["value"]}

@app.get("/count")
async def get_count():
    return {"count": counter["value"]}

@app.post("/reset")
async def reset():
    counter["value"] = 0
    return {"count": 0}
```
""",
        acceptance_criteria=[
            "Identifies the TOCTOU race: read-then-write with an await in between",
            "Explains why concurrent requests can read the same 'current' value",
            "Provides a fix using asyncio.Lock or equivalent synchronization",
            "The fix preserves the async nature of the endpoint",
            "Does not introduce deadlock or remove the async sleep inappropriately",
        ],
        risk_level="high",
        stack="python/asyncio",
    ),
    BenchmarkJob(
        id="swe-add-tests",
        name="Write tests for untested utility module",
        category="software-engineering",
        skill_domain="software-engineer-agent",
        task_bucket="rotating",
        difficulty="medium",
        test_set="agent-pack-v1",
        input_prompt=(
            "Write comprehensive pytest tests for this utility module. "
            "Cover normal cases, edge cases, and error handling."
        ),
        input_context="""\
```python
# utils/slug.py

import re
import unicodedata

def slugify(text: str, max_length: int = 80) -> str:
    \"\"\"Convert text to a URL-safe slug.

    Rules:
    - Normalize unicode to ASCII equivalents
    - Lowercase
    - Replace spaces and special chars with hyphens
    - Collapse multiple hyphens
    - Strip leading/trailing hyphens
    - Truncate to max_length without breaking mid-word
    - Raise ValueError if text is empty or all special chars
    \"\"\"
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

    lowered = ascii_text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = slug.strip("-")

    if not slug:
        raise ValueError("text contains no slugifiable characters")

    if len(slug) > max_length:
        truncated = slug[:max_length]
        if "-" in truncated:
            slug = truncated[:truncated.rfind("-")]
        else:
            slug = truncated

    return slug
```
""",
        acceptance_criteria=[
            "Tests normal ASCII input produces expected slug",
            "Tests unicode input (accented chars) converts to ASCII equivalents",
            "Tests spaces and special chars become hyphens",
            "Tests multiple consecutive special chars collapse to single hyphen",
            "Tests max_length truncation without breaking mid-word",
            "Tests ValueError on empty string and all-special-char input",
            "Tests leading/trailing hyphens are stripped",
        ],
        risk_level="low",
        stack="python/pytest",
    ),
    BenchmarkJob(
        id="swe-debug-prod-issue",
        name="Analyze production error from logs",
        category="software-engineering",
        skill_domain="software-engineer-agent",
        task_bucket="rotating",
        difficulty="hard",
        test_set="agent-pack-v1",
        input_prompt=(
            "Analyze these production error logs and identify the root cause. "
            "Explain the failure chain and recommend a fix."
        ),
        input_context="""\
Service: order-processor (Python 3.12, FastAPI, PostgreSQL)
Alert: 5xx error rate spike from 0.1% to 12% starting 2026-03-15 14:30 UTC

Error logs (sampled):

14:30:01 ERROR order_service: Failed to process order ord-8821
  Traceback:
    File "services/order.py", line 45, in process_order
      inventory = await inventory_client.reserve(items)
    File "clients/inventory.py", line 23, in reserve
      resp = await self.session.post(url, json=payload, timeout=5.0)
    httpx.ReadTimeout: Read timed out

14:30:03 ERROR order_service: Failed to process order ord-8824
  Traceback:
    File "services/order.py", line 45, in process_order
      inventory = await inventory_client.reserve(items)
    File "clients/inventory.py", line 28, in reserve
      resp.raise_for_status()
    httpx.HTTPStatusError: 503 Service Unavailable

14:31:15 WARN connection_pool: Pool exhausted, 50/50 connections in use
14:31:16 ERROR order_service: Failed to process order ord-8830
  Traceback:
    File "services/order.py", line 42, in process_order
      async with db.transaction():
    asyncpg.exceptions.TooManyConnectionsError: too many connections

14:32:00 INFO order_service: Circuit breaker OPEN for inventory-service
14:32:01 ERROR order_service: order ord-8835 rejected: circuit breaker open

Deployment log:
14:25 - inventory-service deployed v2.4.1 (added new index on items table)
14:28 - inventory-service health check: OK
14:30 - inventory-service response times p99: 200ms -> 8500ms

Infrastructure:
- order-processor: 3 replicas, connection pool max=50
- inventory-service: 2 replicas, PostgreSQL shared with order-processor
""",
        acceptance_criteria=[
            "Identifies the inventory-service deployment at 14:25 as the trigger",
            "Explains the cascade: slow inventory -> read timeouts -> connection pool exhaustion -> 503s",
            "Notes the shared PostgreSQL connection pool as a failure amplifier",
            "Recognizes the circuit breaker eventually activated but too late to prevent cascade",
            "Recommends at least one of: separate connection pools, lower timeout thresholds, load shedding, or deployment canary checks",
        ],
        risk_level="high",
        stack="python/fastapi/postgresql",
    ),
    BenchmarkJob(
        id="swe-design-tradeoff",
        name="Evaluate caching strategy tradeoffs",
        category="software-engineering",
        skill_domain="software-engineer-agent",
        task_bucket="rotating",
        difficulty="medium",
        test_set="agent-pack-v1",
        input_prompt=(
            "Evaluate the proposed caching approach. Identify tradeoffs, "
            "failure modes, and suggest improvements."
        ),
        input_context="""\
Proposal: Add Redis caching to our user profile API

Current state:
- 10K req/s to GET /api/users/{id}
- p99 latency: 45ms (direct PostgreSQL)
- PostgreSQL CPU at 70% from these reads
- Profiles update ~50 times/day per user
- 500K total users

Proposed implementation:

```python
CACHE_TTL = 3600  # 1 hour

async def get_user(user_id: str) -> dict:
    cached = await redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)

    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    if user:
        await redis.set(f"user:{user_id}", json.dumps(dict(user)), ex=CACHE_TTL)
    return dict(user) if user else None

async def update_user(user_id: str, data: dict) -> dict:
    await db.execute("UPDATE users SET ... WHERE id = $1", user_id, *data.values())
    await redis.delete(f"user:{user_id}")
    return await get_user(user_id)
```

Questions:
1. Is the TTL appropriate?
2. What failure modes exist?
3. Should we use write-through or cache-aside?
4. What about cache stampedes?
""",
        acceptance_criteria=[
            "Evaluates TTL: 1 hour is reasonable given 50 updates/day (~30 min avg freshness)",
            "Identifies cache stampede risk when popular keys expire simultaneously",
            "Identifies Redis failure mode: should degrade to DB reads, not error",
            "Identifies race condition in update_user: delete + re-read can serve stale data",
            "Discusses at least one improvement: stampede protection, error fallback, or shorter TTL",
        ],
        risk_level="medium",
        stack="python/redis/postgresql",
    ),
    BenchmarkJob(
        id="swe-refactor-extract",
        name="Refactor duplicated validation logic",
        category="software-engineering",
        skill_domain="software-engineer-agent",
        task_bucket="rotating",
        difficulty="easy",
        test_set="agent-pack-v1",
        input_prompt=(
            "Refactor the duplicated validation logic in these endpoints "
            "into a shared validator. Keep the same behavior."
        ),
        input_context="""\
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

class CreateOrder(BaseModel):
    customer_id: str
    items: list[dict]
    shipping_address: str
    requested_delivery: str  # ISO date

class CreateReturn(BaseModel):
    order_id: str
    items: list[dict]
    reason: str
    pickup_address: str
    requested_pickup: str  # ISO date

@app.post("/orders")
def create_order(order: CreateOrder):
    if not order.items:
        raise HTTPException(400, "items must not be empty")
    if len(order.items) > 50:
        raise HTTPException(400, "max 50 items per order")
    for item in order.items:
        if "sku" not in item:
            raise HTTPException(400, "each item must have a sku")
        if "quantity" not in item or item["quantity"] < 1:
            raise HTTPException(400, "each item must have quantity >= 1")
        if item.get("quantity", 0) > 999:
            raise HTTPException(400, "quantity must be <= 999")
    try:
        dt = datetime.fromisoformat(order.requested_delivery)
    except ValueError:
        raise HTTPException(400, "invalid date format")
    if dt < datetime.now():
        raise HTTPException(400, "date must be in the future")
    # ... process order
    return {"status": "created"}

@app.post("/returns")
def create_return(ret: CreateReturn):
    if not ret.items:
        raise HTTPException(400, "items must not be empty")
    if len(ret.items) > 50:
        raise HTTPException(400, "max 50 items per return")
    for item in ret.items:
        if "sku" not in item:
            raise HTTPException(400, "each item must have a sku")
        if "quantity" not in item or item["quantity"] < 1:
            raise HTTPException(400, "each item must have quantity >= 1")
        if item.get("quantity", 0) > 999:
            raise HTTPException(400, "quantity must be <= 999")
    try:
        dt = datetime.fromisoformat(ret.requested_pickup)
    except ValueError:
        raise HTTPException(400, "invalid date format")
    if dt < datetime.now():
        raise HTTPException(400, "date must be in the future")
    # ... process return
    return {"status": "created"}
```
""",
        acceptance_criteria=[
            "Extracts item validation into a shared function or Pydantic validator",
            "Extracts date validation into a shared function",
            "Both endpoints call the shared validator(s)",
            "Behavior is preserved: same error messages, same validation rules",
            "The refactored code is shorter than the original",
        ],
        risk_level="low",
        stack="python/fastapi",
    ),
    BenchmarkJob(
        id="swe-fix-test-flake",
        name="Fix flaky test with timing dependency",
        category="software-engineering",
        skill_domain="software-engineer-agent",
        task_bucket="holdout",
        difficulty="medium",
        test_set="agent-pack-v1",
        input_prompt=(
            "This test passes locally but fails intermittently in CI. "
            "Identify the flake source and provide a reliable fix."
        ),
        input_context="""\
CI failure rate: ~15% (passes locally, fails in slower CI environments)

```python
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from services.cache import CacheService

@pytest.mark.asyncio
async def test_cache_expiry():
    store = {}
    cache = CacheService(store=store, ttl_seconds=1)

    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"

    # Wait for expiry
    await asyncio.sleep(1.1)

    # Should be expired
    result = await cache.get("key1")
    assert result is None, f"Expected None after TTL, got {result}"

@pytest.mark.asyncio
async def test_cache_refresh_extends_ttl():
    store = {}
    cache = CacheService(store=store, ttl_seconds=2)

    await cache.set("key1", "value1")
    await asyncio.sleep(1.0)

    # Refresh should extend TTL
    await cache.refresh("key1")
    await asyncio.sleep(1.5)

    # Should still be alive (1.0 + 1.5 = 2.5s, but refresh reset the clock)
    result = await cache.get("key1")
    assert result == "value1", f"Expected value1 after refresh, got {result}"
```

CacheService stores entries with expiry timestamps. The `get` method checks
`datetime.now()` against the stored expiry. The `refresh` method updates the
expiry to `now + ttl`.
""",
        acceptance_criteria=[
            "Identifies the flake: real-time sleeps are unreliable in slow CI environments",
            "Explains that 1.1s may not be enough if CI runs slower than expected",
            "Proposes mocking or injecting the clock instead of using real sleeps",
            "The fix avoids fragile timing by controlling the time source",
            "Does not simply increase the sleep duration as a workaround",
        ],
        risk_level="low",
        stack="python/pytest/asyncio",
    ),
]
