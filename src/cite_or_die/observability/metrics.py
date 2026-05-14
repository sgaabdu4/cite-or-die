from prometheus_client import Counter, Histogram, generate_latest

UPLOADS = Counter("cite_or_die_uploads_total", "Documents uploaded", ["tenant"])
CHATS = Counter("cite_or_die_chats_total", "Chat requests", ["tenant", "status"])
CHAT_LATENCY = Histogram("cite_or_die_chat_latency_seconds", "Chat request latency")


def metrics_response() -> bytes:
    return generate_latest()
