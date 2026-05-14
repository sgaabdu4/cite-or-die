from prometheus_client import Counter, Histogram, generate_latest

UPLOADS = Counter("cite_or_die_uploads_total", "Documents uploaded", ["tenant"])
CHATS = Counter("cite_or_die_chats_total", "Chat requests", ["tenant", "status"])
CHAT_LATENCY = Histogram("cite_or_die_chat_latency_seconds", "Chat request latency")
TOKENS = Counter(
    "cite_or_die_tokens_total",
    "Approximate provider input tokens",
    ["tenant", "provider", "model"],
)
AUDIT_EVENTS = Counter(
    "cite_or_die_audit_events_total",
    "Audit events written",
    ["tenant", "event_type"],
)
FAITHFULNESS_FAILURES = Counter(
    "cite_or_die_faithfulness_gate_failures_total",
    "Citation faithfulness gate failures",
    ["tenant"],
)


def metrics_response() -> bytes:
    return generate_latest()
