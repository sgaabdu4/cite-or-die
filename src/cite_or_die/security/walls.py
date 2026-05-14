from fastapi import HTTPException

from cite_or_die.core.models import Citation, DocumentChunk


class WallBreachError(HTTPException):
    def __init__(self, detail: str = "retrieval wall breach") -> None:
        super().__init__(status_code=403, detail=detail)


class MatterMismatchError(HTTPException):
    def __init__(self, detail: str = "session matter mismatch") -> None:
        super().__init__(status_code=403, detail=detail)


class OutputScopeError(HTTPException):
    def __init__(self, detail: str = "output scope violation") -> None:
        super().__init__(status_code=403, detail=detail)


class TamperDetectedError(RuntimeError):
    pass


def require_matter_scope(ctx_matter_id: str, requested_matter_id: str) -> None:
    # Source: https://www.mexc.com/news/920094 describes matter walls at retrieval/context/output.
    if ctx_matter_id != requested_matter_id:
        raise MatterMismatchError()


def verify_citation_scope(
    citations: list[Citation], tenant_id: str, matter_id: str
) -> None:
    for citation in citations:
        if citation.tenant_id != tenant_id or citation.matter_id != matter_id:
            raise OutputScopeError()


def verify_retrieval_scope(
    chunks: list[DocumentChunk], tenant_id: str, matter_id: str
) -> None:
    for chunk in chunks:
        if chunk.tenant_id != tenant_id or chunk.matter_id != matter_id:
            raise WallBreachError()
