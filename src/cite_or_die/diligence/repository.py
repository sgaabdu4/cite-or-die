import json
import sqlite3
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from cite_or_die.diligence.models import (
    CommercialMetric,
    CrossWorkstreamInsight,
    DateTerm,
    Deal,
    DiligenceKnowledgeBase,
    ExtractedFact,
    ExtractionField,
    FinancialMetric,
    Finding,
    InformationRequest,
    Obligation,
    OperationalMetric,
    ReportDraft,
    SourceDocument,
    VendorResponse,
)

ModelT = TypeVar("ModelT")


class DiligenceRepository:
    """Tenant, matter, and deal scoped storage for diligence domain objects."""

    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS diligence_deals (
                    deal_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    matter_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_diligence_deals_scope
                ON diligence_deals(tenant_id, matter_id)
                """
            )
            for table, id_column in _TABLE_IDS.items():
                if table == "diligence_deals":
                    continue
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        {id_column} TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        matter_id TEXT NOT NULL,
                        deal_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_scope
                    ON {table}(tenant_id, matter_id, deal_id)
                    """
                )

    def save_deal(self, deal: Deal) -> Deal:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO diligence_deals (
                    deal_id, tenant_id, matter_id, payload_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    deal.deal_id,
                    deal.tenant_id,
                    deal.matter_id,
                    _dump(deal),
                ),
            )
        return deal

    def get_deal(self, tenant_id: str, matter_id: str, deal_id: str) -> Deal | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json FROM diligence_deals
                WHERE tenant_id = ? AND matter_id = ? AND deal_id = ?
                """,
                (tenant_id, matter_id, deal_id),
            ).fetchone()
        if row is None:
            return None
        return Deal.model_validate(json.loads(row["payload_json"]))

    def list_deals(self, tenant_id: str, matter_id: str) -> list[Deal]:
        return self._list(
            "diligence_deals", Deal, tenant_id=tenant_id, matter_id=matter_id
        )

    def replace_sources(
        self,
        sources: list[SourceDocument],
        *,
        tenant_id: str,
        matter_id: str,
        deal_id: str,
    ) -> None:
        self._replace_collection(
            "diligence_sources",
            "source_id",
            sources,
            tenant_id=tenant_id,
            matter_id=matter_id,
            deal_id=deal_id,
        )

    def list_sources(
        self, tenant_id: str, matter_id: str, deal_id: str
    ) -> list[SourceDocument]:
        return self._list(
            "diligence_sources",
            SourceDocument,
            tenant_id=tenant_id,
            matter_id=matter_id,
            deal_id=deal_id,
        )

    def replace_outputs(
        self,
        *,
        knowledge_base: DiligenceKnowledgeBase,
        findings: list[Finding],
        insights: list[CrossWorkstreamInsight],
        reports: list[ReportDraft],
    ) -> None:
        deal_id = knowledge_base.deal.deal_id
        tenant_id = knowledge_base.deal.tenant_id
        matter_id = knowledge_base.deal.matter_id
        with self._connect() as conn:
            self._replace_collection_with_connection(
                conn,
                "diligence_facts",
                "fact_id",
                knowledge_base.facts,
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )
            self._replace_collection_with_connection(
                conn,
                "diligence_information_requests",
                "request_id",
                knowledge_base.information_requests,
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )
            self._replace_collection_with_connection(
                conn,
                "diligence_vendor_responses",
                "response_id",
                knowledge_base.vendor_responses,
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )
            self._replace_collection_with_connection(
                conn,
                "diligence_findings",
                "finding_id",
                findings,
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )
            self._replace_collection_with_connection(
                conn,
                "diligence_insights",
                "insight_id",
                insights,
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )
            self._replace_collection_with_connection(
                conn,
                "diligence_reports",
                "report_id",
                reports,
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )

    def list_facts(
        self, tenant_id: str, matter_id: str, deal_id: str
    ) -> list[ExtractedFact]:
        return [
            _load_fact(json.loads(payload))
            for payload in self._list_payloads(
                "diligence_facts",
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )
        ]

    def list_information_requests(
        self, tenant_id: str, matter_id: str, deal_id: str
    ) -> list[InformationRequest]:
        return self._list(
            "diligence_information_requests",
            InformationRequest,
            tenant_id=tenant_id,
            matter_id=matter_id,
            deal_id=deal_id,
        )

    def list_vendor_responses(
        self, tenant_id: str, matter_id: str, deal_id: str
    ) -> list[VendorResponse]:
        return self._list(
            "diligence_vendor_responses",
            VendorResponse,
            tenant_id=tenant_id,
            matter_id=matter_id,
            deal_id=deal_id,
        )

    def list_findings(
        self, tenant_id: str, matter_id: str, deal_id: str
    ) -> list[Finding]:
        return self._list(
            "diligence_findings",
            Finding,
            tenant_id=tenant_id,
            matter_id=matter_id,
            deal_id=deal_id,
        )

    def list_insights(
        self, tenant_id: str, matter_id: str, deal_id: str
    ) -> list[CrossWorkstreamInsight]:
        return self._list(
            "diligence_insights",
            CrossWorkstreamInsight,
            tenant_id=tenant_id,
            matter_id=matter_id,
            deal_id=deal_id,
        )

    def list_reports(
        self, tenant_id: str, matter_id: str, deal_id: str
    ) -> list[ReportDraft]:
        return self._list(
            "diligence_reports",
            ReportDraft,
            tenant_id=tenant_id,
            matter_id=matter_id,
            deal_id=deal_id,
        )

    def _replace_collection(
        self,
        table: str,
        id_column: str,
        items: list,
        *,
        tenant_id: str,
        matter_id: str,
        deal_id: str,
    ) -> None:
        with self._connect() as conn:
            self._replace_collection_with_connection(
                conn,
                table,
                id_column,
                items,
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )

    def _replace_collection_with_connection(
        self,
        conn: sqlite3.Connection,
        table: str,
        id_column: str,
        items: list,
        *,
        tenant_id: str,
        matter_id: str,
        deal_id: str,
    ) -> None:
        table_name, record_id_column = _validated_table(table, id_column)
        delete_sql = f"DELETE FROM {table_name} WHERE tenant_id = ? AND matter_id = ? AND deal_id = ?"  # noqa: E501, S608
        insert_sql = f"INSERT OR REPLACE INTO {table_name} ({record_id_column}, tenant_id, matter_id, deal_id, payload_json) VALUES (?, ?, ?, ?, ?)"  # noqa: E501, S608
        for item in items:
            if (
                item.tenant_id != tenant_id
                or item.matter_id != matter_id
                or item.deal_id != deal_id
            ):
                raise ValueError("diligence item scope does not match replacement scope")
        conn.execute(delete_sql, (tenant_id, matter_id, deal_id))
        conn.executemany(
            insert_sql,
            [
                (
                    getattr(item, record_id_column),
                    item.tenant_id,
                    item.matter_id,
                    item.deal_id,
                    _dump(item),
                )
                for item in items
            ],
        )

    def _list(
        self,
        table: str,
        model_cls: type[ModelT],
        *,
        tenant_id: str,
        matter_id: str,
        deal_id: str | None = None,
    ) -> list[ModelT]:
        return [
            model_cls.model_validate(json.loads(payload))  # type: ignore[attr-defined]
            for payload in self._list_payloads(
                table,
                tenant_id=tenant_id,
                matter_id=matter_id,
                deal_id=deal_id,
            )
        ]

    def _list_payloads(
        self,
        table: str,
        *,
        tenant_id: str,
        matter_id: str,
        deal_id: str | None = None,
    ) -> list[str]:
        table_name, _ = _validated_table(table)
        query = f"SELECT payload_json FROM {table_name} WHERE tenant_id = ? AND matter_id = ?"  # noqa: S608
        params: tuple[str, ...]
        if deal_id is None:
            params = (tenant_id, matter_id)
        else:
            query += " AND deal_id = ?"
            params = (tenant_id, matter_id, deal_id)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [row["payload_json"] for row in rows]


def _dump(item: BaseModel) -> str:
    return json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _load_fact(payload: dict[str, object]) -> ExtractedFact:
    model_cls = _FACT_MODELS.get(str(payload.get("field")), ExtractedFact)
    return model_cls.model_validate(payload)


def _validated_table(table: str, id_column: str | None = None) -> tuple[str, str]:
    expected_id = _TABLE_IDS.get(table)
    if expected_id is None:
        raise ValueError(f"unknown diligence table: {table}")
    if id_column is not None and id_column != expected_id:
        raise ValueError(f"invalid id column for {table}")
    return table, expected_id


_TABLE_IDS = {
    "diligence_deals": "deal_id",
    "diligence_sources": "source_id",
    "diligence_facts": "fact_id",
    "diligence_information_requests": "request_id",
    "diligence_vendor_responses": "response_id",
    "diligence_findings": "finding_id",
    "diligence_insights": "insight_id",
    "diligence_reports": "report_id",
}

_FACT_MODELS: dict[str, type[ExtractedFact]] = {
    ExtractionField.commercial_metric.value: CommercialMetric,
    ExtractionField.date_term.value: DateTerm,
    ExtractionField.financial_metric.value: FinancialMetric,
    ExtractionField.obligation.value: Obligation,
    ExtractionField.operational_metric.value: OperationalMetric,
}
