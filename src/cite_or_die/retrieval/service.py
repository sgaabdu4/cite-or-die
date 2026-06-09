from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk, RetrievalHit
from cite_or_die.graph.index import CitationGraphRegistry
from cite_or_die.retrieval.bm25 import Bm25Registry
from cite_or_die.retrieval.embeddings import EmbeddingProvider, make_embedding_provider, tokenize
from cite_or_die.retrieval.rerank import Reranker, make_reranker
from cite_or_die.retrieval.vector_store import VectorStore, make_vector_store


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
        reranker: Reranker | None = None,
    ):
        self.settings = settings
        self.embeddings = embeddings or make_embedding_provider(
            settings.embedding_provider, settings.embedding_dim
        )
        self.vector_store = vector_store or make_vector_store(
            settings.vector_backend,
            settings.qdrant_url,
            self.embeddings.dim,
        )
        self.bm25 = Bm25Registry()
        self.graph = CitationGraphRegistry()
        self.reranker = reranker or make_reranker(settings.reranker_provider)

    async def index_chunks(
        self, tenant_id: str, chunks: list[DocumentChunk], matter_id: str = "m_default"
    ) -> list[DocumentChunk]:
        vectors = await self.embeddings.embed([chunk.text for chunk in chunks])
        embedded = [
            chunk.model_copy(update={"embedding": vector})
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        scope = scope_id(tenant_id, matter_id)
        await self.vector_store.upsert(scope, embedded)
        self.bm25.rebuild(scope, embedded)
        self.graph.rebuild(scope, embedded)
        return embedded

    def rebuild_sparse(
        self, tenant_id: str, chunks: list[DocumentChunk], matter_id: str = "m_default"
    ) -> None:
        scope = scope_id(tenant_id, matter_id)
        self.bm25.rebuild(scope, chunks)
        self.graph.rebuild(scope, chunks)

    async def retrieve(
        self,
        tenant_id: str,
        query: str,
        top_k: int,
        matter_id: str = "m_default",
        doc_ids: set[str] | None = None,
    ) -> list[RetrievalHit]:
        scope = scope_id(tenant_id, matter_id)
        query_embedding = (await self.embeddings.embed([query]))[0]
        dense = filter_ranked_by_doc_ids(
            await self.vector_store.search(
                scope, query_embedding, self.settings.retrieval_candidate_k
            ),
            doc_ids,
        )
        sparse = filter_ranked_by_doc_ids(
            self.bm25.search(scope, query, self.settings.retrieval_candidate_k),
            doc_ids,
        )
        graph = (
            filter_ranked_by_doc_ids(
                self.graph.search(scope, query, self.settings.retrieval_candidate_k),
                doc_ids,
            )
            if self.settings.citation_graph_enabled
            else []
        )

        fused: dict[str, RetrievalHit] = {}
        self._add_ranked(fused, dense, "dense_score")
        self._add_ranked(fused, sparse, "sparse_score")
        self._add_ranked(
            fused,
            graph,
            "graph_score",
            weight=self.settings.citation_graph_rrf_weight,
        )

        query_terms = set(tokenize(query))
        for hit in fused.values():
            overlap = len(query_terms.intersection(tokenize(hit.chunk.text)))
            hit.score += min(overlap, 5) * 0.02

        # Source: https://arxiv.org/pdf/2605.12028 uses cross-encoder reranking after fusion.
        candidates = sorted(fused.values(), key=lambda hit: hit.score, reverse=True)[
            : self.settings.rerank_input_k
        ]
        return await self.reranker.rerank(query, candidates, top_k)

    @staticmethod
    def _add_ranked(
        fused: dict[str, RetrievalHit],
        ranked: list[tuple[DocumentChunk, float]],
        score_attr: str,
        weight: float = 1.0,
    ) -> None:
        for rank, (chunk, raw_score) in enumerate(ranked, start=1):
            hit = fused.setdefault(
                chunk.chunk_id,
                RetrievalHit(chunk=chunk, score=0.0),
            )
            reciprocal_rank = weight / (60 + rank)
            hit.score += reciprocal_rank
            if score_attr == "graph_score":
                hit.score += min(float(raw_score), 1.0) * 0.25
            setattr(hit, score_attr, float(raw_score))


def scope_id(tenant_id: str, matter_id: str) -> str:
    # Source: https://qdrant.tech/documentation/manage-data/multitenancy/
    return f"{tenant_id}::{matter_id}"


def filter_ranked_by_doc_ids(
    ranked: list[tuple[DocumentChunk, float]], doc_ids: set[str] | None
) -> list[tuple[DocumentChunk, float]]:
    if not doc_ids:
        return ranked
    return [(chunk, score) for chunk, score in ranked if chunk.doc_id in doc_ids]
