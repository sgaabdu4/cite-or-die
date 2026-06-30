from typing import cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from cite_or_die.auth.jwt import get_auth_context
from cite_or_die.core.models import AuthContext
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.diligence.models import (
    Deal,
    DiligenceRunResult,
    Finding,
    ReportDraft,
    SourceDocument,
)
from cite_or_die.diligence.service import DiligenceService

router = APIRouter(prefix="/diligence", tags=["diligence"])


class CreateDealRequest(BaseModel):
    name: str = Field(min_length=1)
    target_business: str = Field(min_length=1)
    target_revenue_gbp_m: int = Field(ge=100, le=250)
    horizon_weeks: int = Field(ge=4, le=8)
    source_doc_ids: list[str] = Field(default_factory=list, max_length=50)


def get_diligence_service(request: Request) -> DiligenceService:
    core = cast(CiteOrDieService, request.app.state.service)
    return DiligenceService(core.settings, core_service=core)


@router.post("/deals")
def create_deal(
    request: CreateDealRequest,
    ctx: AuthContext = Depends(get_auth_context),
    service: DiligenceService = Depends(get_diligence_service),
) -> Deal:
    return service.create_deal(
        ctx,
        name=request.name,
        target_business=request.target_business,
        target_revenue_gbp_m=request.target_revenue_gbp_m,
        horizon_weeks=request.horizon_weeks,
        source_doc_ids=request.source_doc_ids,
    )


@router.post("/deals/{deal_id}/sources/classify")
def classify_sources(
    deal_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: DiligenceService = Depends(get_diligence_service),
) -> list[SourceDocument]:
    return service.classify_sources(ctx, deal_id)


@router.post("/deals/{deal_id}/run")
def run_acceleration(
    deal_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: DiligenceService = Depends(get_diligence_service),
) -> DiligenceRunResult:
    return service.run_acceleration(ctx, deal_id)


@router.get("/deals/{deal_id}/findings")
def list_findings(
    deal_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: DiligenceService = Depends(get_diligence_service),
) -> list[Finding]:
    return service.list_findings(ctx, deal_id)


@router.get("/deals/{deal_id}/reports")
def list_reports(
    deal_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    service: DiligenceService = Depends(get_diligence_service),
) -> list[ReportDraft]:
    return service.list_reports(ctx, deal_id)
