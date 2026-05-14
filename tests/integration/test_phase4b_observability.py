from pathlib import Path

from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.core.config import get_settings


def test_observability_endpoints_and_metrics(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        token = client.post("/dev/token", data={"tenant_id": "obs", "subject": "alice"}).json()[
            "access_token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/upload",
            files={"file": ("obs.txt", b"Observability traces cited answers.", "text/plain")},
            headers=headers,
        )
        chat = client.post(
            "/chat",
            json={"question": "What does observability trace?"},
            headers=headers,
        )
        health = client.get("/healthz")
        ready = client.get("/readyz")
        metrics = client.get("/metrics")

    assert upload.status_code == 200
    assert chat.status_code == 200
    assert health.status_code == 200
    assert ready.status_code == 200
    assert metrics.status_code == 200
    assert "cite_or_die_chat_latency_seconds" in metrics.text
    assert "cite_or_die_tokens_total" in metrics.text
    assert "cite_or_die_audit_events_total" in metrics.text
    assert "query.text" not in metrics.text


def test_phase4b_observability_config_is_allowlisted() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    collector = Path("ops/otel/collector.yaml").read_text(encoding="utf-8")
    prometheus = Path("ops/prometheus/prometheus.yml").read_text(encoding="utf-8")

    for service in ["otel-collector:", "prometheus:", "loki:", "tempo:", "grafana:"]:
        assert service in compose
    assert "redaction/pii_allowlist" in collector
    assert "allow_all_keys: false" in collector
    assert "query.text" in collector
    assert "response.body" in collector
    assert "/etc/prometheus/alerts.yml" in prometheus
    assert Path("ops/grafana/provisioning/dashboards/rag-latency.json").exists()
    assert Path("ops/grafana/provisioning/dashboards/token-spend.json").exists()
    assert Path("ops/grafana/provisioning/dashboards/audit-event-rate.json").exists()
