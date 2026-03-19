"""Base ATS adapter interface and shared types."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RawPosting:
    """Normalized posting from any ATS source."""

    source_ats: str
    source_board_id: str
    company_name: str
    title: str
    content: str
    location: str = ""
    department: str = ""
    posted_at: str = ""
    expires_at: str = ""
    url: str = ""
    raw_json: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


class ATSAdapter:
    """Base class for ATS job board adapters.

    Each adapter must implement:
      - fetch_postings(board_id, **kwargs) -> list[RawPosting]

    Optionally:
      - list_boards(**kwargs) -> list[dict]
    """

    source_ats: str = ""

    def fetch_postings(
        self,
        board_id: str,
        role_filter: str = "",
        max_results: int = 50,
    ) -> list[RawPosting]:
        raise NotImplementedError

    def list_boards(self, **kwargs: object) -> list[dict]:
        raise NotImplementedError


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
