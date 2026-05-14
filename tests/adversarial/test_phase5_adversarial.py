import json

import pytest

from cite_or_die.core.models import AuthContext, ChatRequest, GuardrailStatus, Role
from cite_or_die.core.service import CiteOrDieService
from tests.adversarial.gen_adversarial_pdfs import FIXTURES, generate_fixtures


@pytest.mark.asyncio()
@pytest.mark.parametrize("fixture_name", sorted(FIXTURES))
async def test_adversarial_pdf_payloads_are_blocked_and_audited(settings, tmp_path, fixture_name):
    fixture_dir = tmp_path / "fixtures"
    fixtures = {path.name: path for path in generate_fixtures(fixture_dir)}
    service = CiteOrDieService(settings)
    ctx = AuthContext(tenant_id="tenant-adv", subject="red-team", roles=[Role.admin])

    with fixtures[fixture_name].open("rb") as handle:
        upload = await service.upload(ctx, fixture_name, "application/pdf", handle.read())
    response = await service.chat(ctx, ChatRequest(question="What do the board minutes say?"))

    assert upload.chunks > 0
    assert response.answer == "Request rejected by retrieved-content guardrails."
    assert response.guardrails[-1].status == GuardrailStatus.rejected
    assert "system prompt" not in response.answer.lower()
    assert _has_retrieved_guardrail_rejection(service.audit.recent())


def test_generated_fixture_set_matches_phase5_manifest(tmp_path) -> None:
    generated = {path.name for path in generate_fixtures(tmp_path / "fixtures")}

    assert generated == set(FIXTURES)


def _has_retrieved_guardrail_rejection(events: list[dict[str, object]]) -> bool:
    for event in events:
        if event.get("event_type") != "guardrail":
            continue
        payload = json.loads(str(event["payload_json"]))
        if (
            payload.get("guardrail") == "retrieved_content_guard"
            and payload.get("status") == GuardrailStatus.rejected.value
        ):
            return True
    return False
