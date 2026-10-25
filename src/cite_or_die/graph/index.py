from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol, cast

from cite_or_die.core.models import DocumentChunk
from cite_or_die.core.text import tokenize

CONCEPT = re.compile(
    r"\b(project\s+[A-Z][A-Za-z0-9_-]+|section\s+\d+(?:\.\d+)?|"
    r"covenant\s+[A-Z][A-Za-z0-9_-]+)\b",
    re.IGNORECASE,
)


class _WeightedGraph(Protocol):
    @property
    def nodes(self) -> Iterable[str]: ...

    def add_node(self, node: str) -> None: ...

    def add_edge(self, left: str, right: str, *, weight: float) -> None: ...

    def __getitem__(self, node: str) -> Mapping[str, Mapping[str, float]]: ...


@dataclass
class CitationGraphIndex:
    chunks: dict[str, DocumentChunk] = field(default_factory=dict)
    graph: _WeightedGraph | None = None

    def rebuild(self, chunks: list[DocumentChunk]) -> None:
        from networkx import Graph

        graph = cast(_WeightedGraph, Graph())
        self.chunks = {chunk.chunk_id: chunk for chunk in chunks}
        for chunk in chunks:
            graph.add_node(chunk.chunk_id)

        by_doc = sorted(chunks, key=lambda chunk: (chunk.doc_id, chunk.ordinal))
        for left, right in zip(by_doc, by_doc[1:], strict=False):
            if left.doc_id == right.doc_id and right.ordinal == left.ordinal + 1:
                graph.add_edge(left.chunk_id, right.chunk_id, weight=0.4)

        concept_nodes: dict[str, list[str]] = {}
        for chunk in chunks:
            for concept in _concepts(chunk.text):
                concept_nodes.setdefault(concept, []).append(chunk.chunk_id)
        for nodes in concept_nodes.values():
            for index, left_id in enumerate(nodes):
                for right_id in nodes[index + 1 :]:
                    graph.add_edge(left_id, right_id, weight=1.0)
        self.graph = graph

    def search(self, query: str, limit: int) -> list[tuple[DocumentChunk, float]]:
        if self.graph is None or not self.chunks:
            return []
        query_terms = set(tokenize(query))
        seed_scores = {
            chunk_id: _lexical_overlap(query_terms, chunk.text)
            for chunk_id, chunk in self.chunks.items()
        }
        seed_scores = {chunk_id: score for chunk_id, score in seed_scores.items() if score > 0.0}
        if not seed_scores:
            return []

        total = sum(seed_scores.values())
        personalization = {
            chunk_id: seed_scores.get(chunk_id, 0.0) / total for chunk_id in self.chunks
        }
        page_rank = _weighted_pagerank(self.graph, personalization)
        scores = {chunk_id: page_rank.get(chunk_id, 0.0) * 0.25 for chunk_id in self.chunks}
        for source_id, seed_score in seed_scores.items():
            scores[source_id] += seed_score * 0.1
            for neighbor_id, edge in self.graph[source_id].items():
                scores[neighbor_id] += seed_score * edge.get("weight", 1.0)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [(self.chunks[chunk_id], score) for chunk_id, score in ranked if score > 0.0]


class CitationGraphRegistry:
    def __init__(self) -> None:
        self._indexes: dict[str, CitationGraphIndex] = {}

    def rebuild(self, scope: str, chunks: list[DocumentChunk]) -> None:
        index = self._indexes.setdefault(scope, CitationGraphIndex())
        index.rebuild(chunks)

    def search(self, scope: str, query: str, limit: int) -> list[tuple[DocumentChunk, float]]:
        return self._indexes.get(scope, CitationGraphIndex()).search(query, limit)


def _concepts(text: str) -> set[str]:
    return {match.group(1).casefold() for match in CONCEPT.finditer(text)}


def _lexical_overlap(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    text_terms = set(tokenize(text))
    return len(query_terms.intersection(text_terms)) / len(query_terms)


def _weighted_pagerank(
    graph: _WeightedGraph,
    personalization: dict[str, float],
    *,
    alpha: float = 0.85,
    iterations: int = 25,
) -> dict[str, float]:
    nodes = list(graph.nodes)
    if not nodes:
        return {}
    scores = {node: 1.0 / len(nodes) for node in nodes}
    for _ in range(iterations):
        next_scores = {node: (1.0 - alpha) * personalization.get(node, 0.0) for node in nodes}
        for source in nodes:
            neighbors = list(graph[source].items())
            total_weight = sum(edge.get("weight", 1.0) for _, edge in neighbors)
            if total_weight == 0.0:
                for node in nodes:
                    next_scores[node] += alpha * scores[source] * personalization.get(node, 0.0)
                continue
            for target, edge in neighbors:
                edge_weight = edge.get("weight", 1.0) / total_weight
                next_scores[target] += alpha * scores[source] * edge_weight
        scores = next_scores
    return scores
