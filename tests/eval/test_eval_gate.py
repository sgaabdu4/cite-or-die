import pytest

from cite_or_die.core.models import AuthContext, ChatRequest, GuardrailStatus, Role
from cite_or_die.core.service import CiteOrDieService


@pytest.mark.asyncio()
async def test_bundled_eval_gate(settings) -> None:
    service = CiteOrDieService(settings)
    ctx = AuthContext(tenant_id="eval", subject="eval-runner", roles=[Role.admin])
    await service.upload(
        ctx,
        "golden.txt",
        "text/plain",
        b"The contract renewal date is 30 September 2026. The governing law is English law.",
    )

    questions = [
        "What is the contract renewal date?",
        "What is the governing law?",
    ]
    responses = [await service.chat(ctx, ChatRequest(question=question)) for question in questions]
    citation_valid = sum(bool(response.citations) for response in responses) / len(responses)
    accepted = sum(
        response.guardrails[-1].status == GuardrailStatus.accepted for response in responses
    ) / len(responses)

    assert citation_valid >= 0.95
    assert accepted >= 0.95
