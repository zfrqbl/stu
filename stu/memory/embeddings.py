"""Embedding abstraction layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from loguru import logger
from ..config import EmbeddingConfig

class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        pass

    @abstractmethod
    def dimension(self) -> int:
        pass

class NoOpEmbedder(Embedder):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]
    def dimension(self) -> int:
        return 384

class SentenceTransformerEmbedder(Embedder):
    def __init__(self, config: EmbeddingConfig, cache_dir: Path):
        self.config = config
        self.cache_dir = cache_dir
        self._model = None

    def _load(self):
        if self._model is None:
            import os
            os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(self.cache_dir)
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading sentence-transformers model: {self.config.model}")
            self._model = SentenceTransformer(self.config.model, device=self.config.device)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        embeddings = model.encode(texts, batch_size=self.config.batch_size, show_progress_bar=False)
        return embeddings.tolist()

    def dimension(self) -> int:
        return 384 # Standard for MiniLM

def get_embedder(config: EmbeddingConfig, enabled: bool, cache_dir: Path) -> Embedder:
    if not enabled:
        return NoOpEmbedder()
    if config.provider == "sentence-transformers":
        return SentenceTransformerEmbedder(config, cache_dir)
    raise ValueError(f"Unsupported embedding provider: {config.provider}")
