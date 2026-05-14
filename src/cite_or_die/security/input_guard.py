import re
import unicodedata

from cite_or_die.core.models import GuardrailDecision, GuardrailStatus

ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")
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


def normalize_user_text(text: str) -> tuple[str, GuardrailDecision]:
    normalized = unicodedata.normalize("NFKC", ZERO_WIDTH.sub("", text))
    changed = normalized != text
    return normalized, GuardrailDecision(
        name="input_normalization",
        status=GuardrailStatus.repaired if changed else GuardrailStatus.accepted,
        reason="removed zero-width/control confusables" if changed else "input unchanged",
    )


def scan_user_text(text: str) -> GuardrailDecision:
    if PROMPT_INJECTION.search(text):
        return GuardrailDecision(
            name="input_prompt_injection",
            status=GuardrailStatus.rejected,
            reason="prompt-injection pattern detected",
        )
    return GuardrailDecision(
        name="input_prompt_injection",
        status=GuardrailStatus.accepted,
        reason="no prompt-injection pattern detected",
    )
