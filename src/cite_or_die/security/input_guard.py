import os
import re
import unicodedata
from functools import lru_cache
from typing import Protocol

from cite_or_die.core.models import DocumentChunk, GuardrailDecision, GuardrailStatus

ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")
HOMOGLYPH_TRANSLATION = str.maketrans(
    {
        "а": "a",
        "А": "A",
        "е": "e",
        "Е": "E",
        "і": "i",
        "І": "I",
        "о": "o",
        "О": "O",
        "р": "p",
        "Р": "P",
        "с": "c",
        "С": "C",
        "у": "y",
        "У": "Y",
        "х": "x",
        "Х": "X",
    }
)
PROMPT_INJECTION = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)|disregard\s+(all\s+)?(previous|prior)|"
    r"system\s+prompt|developer\s+message|exfiltrate|jailbreak|"
    r"\bdan\b|act\s+as\s+(an?\s+)?unrestricted|bypass\s+(all\s+)?(rules|policy)|"
    r"override\s+(the\s+)?(system|developer|instruction)|"
    r"reveal\s+(the\s+)?(prompt|secret|key|confidential)|"
    r"print\s+(hidden|system|developer)|disable\s+guardrails|"
    r"begin\s+system\s+message|###\s*system)",
    re.IGNORECASE,
)
INDIRECT_INJECTION = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)|disregard\s+(all\s+)?(previous|prior)|"
    r"system\s+prompt|developer\s+message|jailbreak|"
    r"override\s+(the\s+)?(system|developer|instruction)|"
    r"print\s+(hidden|system|developer)|disable\s+guardrails|"
    r"begin\s+system\s+message|###\s*system)",
    re.IGNORECASE,
)
TEMPLATE_INJECTION = re.compile(
    r"(\{\{.*?(system|prompt|secret|config).*?\}\}|\{%.*?(include|import|exec).*?%\}|"
    r"\$\{.*?(system|prompt|secret|config).*?\})",
    re.IGNORECASE,
)
BANNED_TOPICS = ["credential theft", "malware", "self-harm instructions"]


class GuardScanner(Protocol):
    def scan_prompt_injection(self, text: str) -> tuple[bool, float]:
        """Return validity and risk score."""
        ...

    def scan_ban_topics(self, text: str) -> tuple[bool, float]:
        """Return validity and risk score."""
        ...


class LlmGuardScanner:
    def __init__(self) -> None:
        from llm_guard.input_scanners import (  # type: ignore[import-untyped]
            BanTopics,
            PromptInjection,
        )

        # Source: https://github.com/protectai/llm-guard is the brief's self-hosted guardrail.
        self.prompt_injection = PromptInjection(threshold=0.5, match_type="full")
        self.ban_topics = BanTopics(topics=BANNED_TOPICS, threshold=0.5)

    def scan_prompt_injection(self, text: str) -> tuple[bool, float]:
        _, is_valid, risk_score = self.prompt_injection.scan(text)
        return is_valid, risk_score

    def scan_ban_topics(self, text: str) -> tuple[bool, float]:
        _, is_valid, risk_score = self.ban_topics.scan(text)
        return is_valid, risk_score


def normalize_user_text(text: str) -> tuple[str, GuardrailDecision]:
    normalized = _normalize_for_guard(text)
    changed = normalized != text
    return normalized, GuardrailDecision(
        name="input_normalization",
        status=GuardrailStatus.repaired if changed else GuardrailStatus.accepted,
        reason="removed zero-width/control confusables" if changed else "input unchanged",
    )


@lru_cache(maxsize=1)
def _llm_guard_scanner() -> GuardScanner | None:
    if os.getenv("CITE_OR_DIE_ENABLE_LLM_GUARD_MODELS") != "1":
        return None
    try:
        return LlmGuardScanner()
    except Exception:
        return None


def scan_user_text(text: str) -> GuardrailDecision:
    guard_text = _normalize_for_guard(text)
    regex_rejected = (
        PROMPT_INJECTION.search(guard_text) is not None
        or TEMPLATE_INJECTION.search(guard_text) is not None
    )
    scanner = _llm_guard_scanner()
    llm_guard_valid = True
    llm_guard_risk = 0.0
    if scanner is not None:
        llm_guard_valid, llm_guard_risk = scanner.scan_prompt_injection(guard_text)

    if regex_rejected or not llm_guard_valid:
        return GuardrailDecision(
            name="input_prompt_injection",
            status=GuardrailStatus.rejected,
            reason="prompt-injection pattern detected",
            metadata={
                "regex_rejected": regex_rejected,
                "llm_guard_enabled": scanner is not None,
                "llm_guard_risk": llm_guard_risk,
            },
        )
    return GuardrailDecision(
        name="input_prompt_injection",
        status=GuardrailStatus.accepted,
        reason="no prompt-injection pattern detected",
        metadata={
            "regex_rejected": False,
            "llm_guard_enabled": scanner is not None,
            "llm_guard_risk": llm_guard_risk,
        },
    )


def scan_retrieved_chunks(chunks: list[DocumentChunk]) -> GuardrailDecision:
    scanner = _llm_guard_scanner()
    rejected_chunk_ids: list[str] = []
    max_risk = 0.0
    for chunk in chunks:
        guard_text = _normalize_for_guard(chunk.text)
        regex_rejected = (
            INDIRECT_INJECTION.search(guard_text) is not None
            or TEMPLATE_INJECTION.search(guard_text) is not None
        )
        topic_valid = True
        topic_risk = 0.0
        if scanner is not None:
            topic_valid, topic_risk = scanner.scan_ban_topics(guard_text)
            max_risk = max(max_risk, topic_risk)
        if regex_rejected or not topic_valid:
            rejected_chunk_ids.append(chunk.chunk_id)

    if rejected_chunk_ids:
        return GuardrailDecision(
            name="retrieved_content_guard",
            status=GuardrailStatus.rejected,
            reason="retrieved chunk matched indirect-injection or banned-topic pattern",
            metadata={
                "rejected_chunk_ids": rejected_chunk_ids,
                "llm_guard_enabled": scanner is not None,
                "llm_guard_risk": max_risk,
            },
        )
    return GuardrailDecision(
        name="retrieved_content_guard",
        status=GuardrailStatus.accepted,
        reason="retrieved chunks passed indirect-injection scan",
        metadata={
            "checked_chunk_count": len(chunks),
            "llm_guard_enabled": scanner is not None,
            "llm_guard_risk": max_risk,
        },
    )


def _normalize_for_guard(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", ZERO_WIDTH.sub("", text))
    return normalized.translate(HOMOGLYPH_TRANSLATION)
