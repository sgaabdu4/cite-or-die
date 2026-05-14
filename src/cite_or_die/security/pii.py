from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")


@dataclass(frozen=True)
class PiiRedaction:
    text: str
    count: int


def redact_pii(text: str) -> PiiRedaction:
    # Source: https://github.com/microsoft/presidio documents local PII detection before use.
    count = 0
    redacted = text
    for label, pattern in (
        ("EMAIL", EMAIL),
        ("SSN", SSN),
        ("PHONE", PHONE),
    ):
        redacted, replacements = pattern.subn(f"<{label}>", redacted)
        count += replacements
    return PiiRedaction(text=redacted, count=count)


def redact_pii_pages(
    pages: list[tuple[str, int | None]],
) -> tuple[list[tuple[str, int | None]], int]:
    total = 0
    redacted_pages: list[tuple[str, int | None]] = []
    for text, page in pages:
        redaction = redact_pii(text)
        total += redaction.count
        redacted_pages.append((redaction.text, page))
    return redacted_pages, total
