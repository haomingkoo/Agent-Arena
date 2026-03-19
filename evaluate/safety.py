"""
Content safety scanner for skills.

Scans skill text content for prompt injection, data exfiltration,
malicious code execution, and social engineering patterns.

Ported from registry/quality.py and adapted to work with ParsedSkill
instead of Agent — scans skill.name, skill.description,
skill.instructions, and skill.triggers.
"""
from __future__ import annotations

import re

from evaluate.rubric import ParsedSkill

# ── Content safety patterns ──────────────────────────────────────────────────
# Each tuple: (compiled regex, threat label)

_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
     "prompt injection: ignore previous instructions"),
    (re.compile(r"disregard\s+(all\s+)?(above|prior|previous)", re.I),
     "prompt injection: disregard prior context"),
    (re.compile(r"you\s+are\s+now\s+(a\s+)?new", re.I),
     "prompt injection: role override"),
    (re.compile(r"system\s*prompt\s*[:=]", re.I),
     "prompt injection: system prompt override"),
    (re.compile(r"override\s+(safety|security|guardrail|filter)", re.I),
     "prompt injection: safety bypass"),
    (re.compile(r"\[INST\]|\[\/INST\]|<\|im_start\|>|<\|im_end\|>", re.I),
     "prompt injection: raw model tokens"),
]

_EXFILTRATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(steal|exfiltrate|harvest|keylog)\s.*(password|credential|key|token|secret)", re.I | re.DOTALL),
     "data exfiltration: credential theft"),
    (re.compile(r"send\s+(all\s+)?(data|info|content|files|keys|secrets)\s+to\s+", re.I),
     "data exfiltration: send data to external"),
    (re.compile(r"(curl|wget|fetch|http)\s.*(api[_\-]?key|password|token|secret)", re.I | re.DOTALL),
     "data exfiltration: credential upload"),
    (re.compile(r"(read|access|dump)\s+(the\s+)?\.env", re.I),
     "data exfiltration: env file access"),
    (re.compile(r"(process|os)\.env(iron)?", re.I),
     "data exfiltration: environment variable access"),
]

_MALICIOUS_CODE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(eval|exec)\s*\(", re.I),
     "code execution: eval/exec call"),
    (re.compile(r"os\.(system|popen|exec)", re.I),
     "code execution: os command"),
    (re.compile(r"subprocess\.(run|call|Popen)", re.I),
     "code execution: subprocess"),
    (re.compile(r"rm\s+-rf\s+/", re.I),
     "destructive: recursive delete"),
    (re.compile(r"curl\s.*\|\s*(ba)?sh", re.I | re.DOTALL),
     "code execution: pipe to shell"),
    (re.compile(r"reverse\s+shell|bind\s+shell|netcat\s+-[el]", re.I),
     "exploitation: shell access"),
]

_SOCIAL_ENGINEERING_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(impersonate|pretend\s+to\s+be)\s+(a\s+)?(bank|support|admin|staff)", re.I),
     "social engineering: impersonation"),
    (re.compile(r"phishing\s+(email|page|site|link|template)", re.I),
     "social engineering: phishing"),
    (re.compile(r"(bypass|disable|circumvent)\s+(auth|authentication|security|2fa|mfa)", re.I),
     "privilege escalation: auth bypass"),
]

ALL_SAFETY_PATTERNS = (
    _INJECTION_PATTERNS
    + _EXFILTRATION_PATTERNS
    + _MALICIOUS_CODE_PATTERNS
    + _SOCIAL_ENGINEERING_PATTERNS
)


# ── Safety scanner ───────────────────────────────────────────────────────────

def check_content_safety(skill: ParsedSkill) -> list[str]:
    """
    Scan all skill text content for prompt injection, data exfiltration,
    malicious code execution, and social engineering patterns.

    Scans: skill.name, skill.description, skill.instructions, skill.triggers.

    Returns list of threat descriptions (empty = safe).
    """
    text_fields = [
        skill.name,
        skill.description,
        skill.instructions,
    ]
    # Add trigger text
    text_fields.extend(skill.triggers)

    combined_text = "\n".join(text_fields)
    threats: list[str] = []

    for pattern, label in ALL_SAFETY_PATTERNS:
        if pattern.search(combined_text):
            threats.append(label)

    return threats


def scan_text(text: str) -> list[str]:
    """Scan raw text content for safety threats.

    Lower-level alternative to check_content_safety() — accepts a plain
    string instead of a ParsedSkill, so callers can compose their own
    text before scanning.

    Returns list of threat descriptions (empty = safe).
    """
    threats: list[str] = []
    for pattern, label in ALL_SAFETY_PATTERNS:
        if pattern.search(text):
            threats.append(label)
    return threats
