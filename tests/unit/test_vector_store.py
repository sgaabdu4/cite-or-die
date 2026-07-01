import re

from cite_or_die.retrieval.service import scope_id
from cite_or_die.retrieval.vector_store import safe_collection_name


def test_qdrant_collection_name_does_not_collapse_scope_separators() -> None:
    left = safe_collection_name(scope_id("a_", "b"))
    right = safe_collection_name(scope_id("a", "_b"))

    assert left != right
    assert safe_collection_name("") != safe_collection_name("z")
    assert re.fullmatch(r"tenant_[A-Za-z0-9_-]+", left)
    assert re.fullmatch(r"tenant_[A-Za-z0-9_-]+", right)
