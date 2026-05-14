from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Role(str, Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class AuthContext(BaseModel):
    tenant_id: str
    matter_id: str = "m_default"
    subject: str
    roles: list[Role] = Field(default_factory=lambda: [Role.analyst])


class DocumentRecord(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str = "m_default"
    filename: str
    content_type: str
    sha256: str
    page_count: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DocumentChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str = "m_default"
    doc_id: str
    filename: str
    text: str
    page: int | None = None
    ordinal: int
    embedding: list[float] | None = None

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("chunk text must not be empty")
        return value


class UploadResponse(BaseModel):
    document: DocumentRecord
    chunks: int
    pii_entities_redacted: int = 0


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    tenant_id: str | None = None
    matter_id: str | None = None
    session_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    stream: bool = False


class Citation(BaseModel):
    citation_id: str = Field(default_factory=lambda: str(uuid4()))
    chunk_id: str
    doc_id: str
    filename: str
    tenant_id: str = ""
    matter_id: str = "m_default"
    page: int | None = None
    quote: str
    text_excerpt: str = ""

    def model_post_init(self, __context: Any) -> None:
        self.text_excerpt = self.quote


class Claim(BaseModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)


class LLMAnswer(BaseModel):
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    refusal: str | None = None


class RetrievalHit(BaseModel):
    chunk: DocumentChunk
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    graph_score: float = 0.0
    rerank_score: float = 0.0


class GuardrailStatus(str, Enum):
    accepted = "accepted"
    rejected = "rejected"
    repaired = "repaired"


class GuardrailDecision(BaseModel):
    name: str
    status: GuardrailStatus
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    claims: list[Claim]
    citations: list[Citation]
    guardrails: list[GuardrailDecision]
    model_provider: str
    model_version: str
    tenant_id: str
    matter_id: str = "m_default"
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    citation_valid_count: int = 0

    def model_post_init(self, __context: Any) -> None:
        self.citation_valid_count = len(self.citations)


class AuditEventType(str, Enum):
    upload = "upload"
    retrieve = "retrieve"
    generate = "generate"
    guardrail = "guardrail"
    authz = "authz"
    chat = "chat"


class AuditEvent(BaseModel):
    tenant_id: str
    actor: str
    event_type: AuditEventType
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    dependencies: dict[str, str] = Field(default_factory=dict)
