from fastapi.testclient import TestClient

from cite_or_die.api.app import app
from cite_or_die.core.config import get_settings


def test_diligence_api_upload_classify_run_and_read_outputs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CITE_OR_DIE_APP_ENV", "test")
    monkeypatch.setenv("CITE_OR_DIE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CITE_OR_DIE_AUTH_SECRET", "test-secret-with-at-least-32-bytes")
    get_settings.cache_clear()

    with TestClient(app) as client:
        token = client.post(
            "/dev/token",
            data={
                "tenant_id": "tenant-a",
                "matter_id": "matter-alpha",
                "subject": "analyst-a",
            },
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        for filename, content in {
            "financials.txt": (
                b"FY26 revenue is GBP 180m. Reported EBITDA is GBP 24m. "
                b"Management normalisation adds GBP 5m for restructuring costs. "
                b"Vendor response states recurring restructuring costs are GBP 4m."
            ),
            "customer-contract.txt": (
                b"Top customer represents 34 percent of revenue. "
                b"Change of control consent is required before assignment."
            ),
            "request-log.txt": (
                b"Information request HR attrition schedule remains open and delayed by 12 days."
            ),
        }.items():
            upload = client.post(
                "/upload",
                files={"file": (filename, content, "text/plain")},
                headers=headers,
            )
            assert upload.status_code == 200

        deal = client.post(
            "/diligence/deals",
            json={
                "name": "Project Northstar",
                "target_business": "Northstar Managed Services",
                "target_revenue_gbp_m": 180,
                "horizon_weeks": 6,
            },
            headers=headers,
        )
        deal_id = deal.json()["deal_id"]
        classify = client.post(
            f"/diligence/deals/{deal_id}/sources/classify", headers=headers
        )
        run = client.post(f"/diligence/deals/{deal_id}/run", headers=headers)
        findings = client.get(f"/diligence/deals/{deal_id}/findings", headers=headers)
        reports = client.get(f"/diligence/deals/{deal_id}/reports", headers=headers)

    assert deal.status_code == 200
    assert classify.status_code == 200
    assert run.status_code == 200
    assert findings.status_code == 200
    assert reports.status_code == 200
    assert {finding["risk_code"] for finding in findings.json()} >= {
        "customer_concentration",
        "earnings_normalisation",
        "contract_consent",
        "open_information_request",
    }
    assert reports.json()[0]["review_status"] == "needs_review"
    assert reports.json()[0]["claims"][0]["evidence"][0]["quote"]
