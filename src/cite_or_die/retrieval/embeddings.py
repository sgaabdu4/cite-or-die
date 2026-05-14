import hashlib
import math
import re
from abc import ABC, abstractmethod

TOKEN = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN.findall(text)]


class EmbeddingProvider(ABC):
    dim: int
    name: str

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding fallback for dev/test and air-gapped smoke tests."""

    name = "hash"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class BgeM3EmbeddingProvider(EmbeddingProvider):
    """Lazy BGE-M3 provider. Install with `uv sync --extra local-models`."""

    name = "bge-m3"

    def __init__(self, dim: int = 1024) -> None:
        from FlagEmbedding import BGEM3FlagModel  # type: ignore[import-not-found]

        self.dim = dim
        self._model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        output = self._model.encode(
            texts, return_dense=True, return_sparse=False, return_colbert_vecs=False
        )
        return [list(map(float, row)) for row in output["dense_vecs"]]


def make_embedding_provider(name: str, dim: int) -> EmbeddingProvider:
    if name == "bge-m3":
        return BgeM3EmbeddingProvider()
    return HashEmbeddingProvider(dim=dim)
