from cite_or_die.core.models import DocumentChunk
from cite_or_die.graph.index import CitationGraphIndex


def test_citation_graph_promotes_referenced_section() -> None:
    graph = CitationGraphIndex()
    graph.rebuild(
        [
            DocumentChunk(
                chunk_id="source",
                tenant_id="tenant-a",
                doc_id="deal",
                filename="deal.md",
                text="Project Redwood is governed by Section 9.",
                ordinal=0,
            ),
            DocumentChunk(
                chunk_id="target",
                tenant_id="tenant-a",
                doc_id="deal",
                filename="deal.md",
                text="Section 9 requires board consent before closing.",
                ordinal=1,
            ),
        ]
    )

    ranked = graph.search("What requirement applies to Project Redwood?", limit=2)

    assert ranked[0][0].chunk_id == "target"
    assert ranked[0][1] > ranked[1][1]
