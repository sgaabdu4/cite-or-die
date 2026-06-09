from collections.abc import Mapping
from typing import Any

ALLOWED_AUDIT_KEYS = {
    "request_id",
    "doc_id",
    "matter_id",
    "filename",
    "chunk_count",
    "pii_entities_redacted",
    "retrieved_chunk_ids",
    "selected_doc_ids",
    "model_provider",
    "model_version",
    "guardrail",
    "status",
    "reason",
    "latency_ms",
    "cost_usd",
    "top_k",
}


def redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Allowlist audit payloads so raw prompts and document text are never logged."""

    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key in ALLOWED_AUDIT_KEYS:
            redacted[key] = value
        else:
            redacted[key] = "[redacted]"
    return redacted
