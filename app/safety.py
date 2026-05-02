"""Lightweight content-safety guards for the assistant.

Election information is sensitive, so we apply both *input* and *output*
filters. The goal is not to be a full moderation service, but to:

* refuse to discuss who to vote *for* (we educate, we do not campaign)
* block obvious prompt-injection and PII leakage
* flag (not silently rewrite) outputs that look unsafe

For deeper moderation, plug in Vertex AI safety filters or Perspective API.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# Refuse to provide partisan voting recommendations.
_PARTISAN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bwho\s+should\s+i\s+vote\s+for\b", re.I),
    re.compile(r"\bbest\s+(party|candidate)\b", re.I),
    re.compile(r"\bwhich\s+party\s+is\s+(best|better|good)\b", re.I),
)

# Block obvious prompt-injection.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"system\s*prompt\s*[:=]", re.I),
    re.compile(r"reveal\s+your\s+(system\s+)?prompt", re.I),
)

# Strip simple PII from user input before sending to the model.
_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b\d{12}\b"), "[AADHAAR_REDACTED]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN_REDACTED]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?\d{10}\b"), "[PHONE_REDACTED]"),
)


@dataclass(frozen=True)
class SafetyVerdict:
    """Result of a safety check.

    `allowed=False` means the caller must refuse to forward `text` to the
    LLM; `reason` is a user-safe explanation. When `allowed=True`,
    `sanitized_text` carries the (possibly redacted) text that is safe
    to send onwards.
    """

    allowed: bool
    reason: str | None = None
    sanitized_text: str | None = None


def _matches_any(text: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    """Return True if any of the compiled regex patterns matches `text`."""
    return any(p.search(text) for p in patterns)


def check_input(text: str) -> SafetyVerdict:
    """Validate and sanitize user input before sending to the LLM."""

    if _matches_any(text, _INJECTION_PATTERNS):
        return SafetyVerdict(
            allowed=False,
            reason="Possible prompt-injection detected. Please rephrase your question.",
        )

    if _matches_any(text, _PARTISAN_PATTERNS):
        return SafetyVerdict(
            allowed=False,
            reason=(
                "I can explain how the election process works, but I won't "
                "recommend a specific candidate or party. Try asking about "
                "voter registration, polling locations, or election dates."
            ),
        )

    sanitized = text
    for pattern, replacement in _PII_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return SafetyVerdict(allowed=True, sanitized_text=sanitized)


def check_output(text: str) -> SafetyVerdict:
    """Final pass on the model's reply."""

    if _matches_any(text, _PARTISAN_PATTERNS):
        return SafetyVerdict(
            allowed=False,
            reason="Output rewritten to remain non-partisan.",
        )
    return SafetyVerdict(allowed=True, sanitized_text=text)
