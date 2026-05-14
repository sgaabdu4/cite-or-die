from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk, RetrievalHit
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
        self.reranker = reranker or make_reranker(settings.reranker_provider)

    async def index_chunks(
        self, tenant_id: str, chunks: list[DocumentChunk]
    ) -> list[DocumentChunk]:
        vectors = await self.embeddings.embed([chunk.text for chunk in chunks])
        embedded = [
            chunk.model_copy(update={"embedding": vector})
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self.vector_store.upsert(tenant_id, embedded)
        self.bm25.rebuild(tenant_id, embedded)
        return embedded

    def rebuild_sparse(self, tenant_id: str, chunks: list[DocumentChunk]) -> None:
        self.bm25.rebuild(tenant_id, chunks)

    async def retrieve(self, tenant_id: str, query: str, top_k: int) -> list[RetrievalHit]:
        query_embedding = (await self.embeddings.embed([query]))[0]
        dense = await self.vector_store.search(
            tenant_id, query_embedding, self.settings.retrieval_candidate_k
        )
        sparse = self.bm25.search(tenant_id, query, self.settings.retrieval_candidate_k)

        fused: dict[str, RetrievalHit] = {}
        self._add_ranked(fused, dense, "dense_score")
        self._add_ranked(fused, sparse, "sparse_score")

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
    ) -> None:
        for rank, (chunk, raw_score) in enumerate(ranked, start=1):
            hit = fused.setdefault(
                chunk.chunk_id,
                RetrievalHit(chunk=chunk, score=0.0),
            )
            reciprocal_rank = 1.0 / (60 + rank)
            hit.score += reciprocal_rank
            setattr(hit, score_attr, float(raw_score))
