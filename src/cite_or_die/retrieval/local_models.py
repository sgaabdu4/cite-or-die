from importlib.util import find_spec

_LOCAL_MODEL_INSTALL = "uv sync --extra local-models"


def local_model_dependency_error(embedding_provider: str, reranker_provider: str) -> str | None:
    missing: list[str] = []
    if embedding_provider == "bge-m3" and find_spec("sentence_transformers") is None:
        missing.append("sentence-transformers")
    if reranker_provider == "bge-reranker-v2-m3" and find_spec("FlagEmbedding") is None:
        missing.append("FlagEmbedding")
    if not missing:
        return None
    return (
        f"{', '.join(missing)} required for selected local retrieval models. "
        f"Install them with `{_LOCAL_MODEL_INSTALL}`."
    )
