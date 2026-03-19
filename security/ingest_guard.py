"""
Ingestion guardrails for hostile external content.

The main rule is simple: scraped content is untrusted data, not instructions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "instruction_override",
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    ),
    (
        "system_prompt_reference",
        re.compile(r"\bsystem\s+prompt\b|\bdeveloper\s+message\b", re.IGNORECASE),
    ),
    (
        "tool_override",
        re.compile(r"\bcall\s+this\s+tool\b|\binvoke\s+tool\b", re.IGNORECASE),
    ),
    (
        "credential_request",
        re.compile(r"\b(api[_ -]?key|secret|token|password)\b", re.IGNORECASE),
    ),
    (
        "hidden_html",
        re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE),
    ),
    (
        "script_tag",
        re.compile(r"<script\b", re.IGNORECASE),
    ),
]


@dataclass
class IngestScanResult:
    sanitized_text: str
    findings: list[str] = field(default_factory=list)
    suspicious: bool = False


def sanitize_untrusted_text(text: str) -> str:
    """Remove control characters and obvious active HTML we should never preserve."""
    cleaned = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    cleaned = re.sub(r"<script.*?>.*?</script>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()


def scan_untrusted_content(text: str) -> IngestScanResult:
    """Scan external content for prompt-injection and hostile-content markers."""
    sanitized = sanitize_untrusted_text(text)
    findings: list[str] = []
    for label, pattern in INJECTION_PATTERNS:
        if pattern.search(sanitized):
            findings.append(label)
    return IngestScanResult(
        sanitized_text=sanitized,
        findings=findings,
        suspicious=bool(findings),
    )

