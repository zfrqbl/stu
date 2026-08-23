"""Semantic Tool RAG with deterministic core fallback."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from ..config import EmbeddingConfig, ToolsConfig
from ..models import ToolDescriptor
from .catalog import ToolCatalog


class ToolRagService:
    def __init__(
        self,
        catalog: ToolCatalog,
        tools_config: ToolsConfig,
        embedding_config: EmbeddingConfig,
        models_dir: Path,
    ):
        self.catalog = catalog
        self.tools_config = tools_config
        self.embedding_config = embedding_config
        self.models_dir = models_dir

        self.enabled = tools_config.rag.enabled
        self.top_k = tools_config.rag.top_k
        self.uri = models_dir / tools_config.rag.vector_subdir / "lancedb"

        self._embedder = None
        self._db = None
        self._table = None
        self._ready = False
        self._failed = False

    def prepare(self) -> None:
        if not self.enabled or self._ready or self._failed:
            return

        try:
            from ..memory.embeddings import get_embedder

            self._embedder = get_embedder(self.embedding_config, True, self.models_dir)

            descriptors = self.catalog.list_tools(include_disabled=False)
            if not descriptors:
                self._ready = True
                return

            texts = [f"{d.name}: {d.description}" for d in descriptors]
            vectors = self._embedder.embed(texts)

            import lancedb

            self.uri.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self.uri))

            data = []
            for descriptor, text, vector in zip(descriptors, texts, vectors):
                data.append(
                    {
                        "name": descriptor.name,
                        "text": text,
                        "vector": vector,
                    }
                )

            self._table = self._db.create_table("tools", data=data, mode="overwrite")
            self._ready = True
            logger.info("Tool RAG index prepared.")
        except Exception as exc:
            logger.warning(f"Tool RAG initialization failed; using core fallback. {exc}")
            self._failed = True
            self.enabled = False

    def select_tools(self, query: str) -> list[ToolDescriptor]:
        if not query.strip():
            return self._fallback()

        self.prepare()

        if not self.enabled or not self._ready or self._table is None or self._embedder is None:
            return self._fallback()

        try:
            vector = self._embedder.embed([query])[0]
            rows = self._table.search(vector).limit(self.top_k).to_list()

            selected: list[ToolDescriptor] = []
            for row in rows:
                descriptor = self.catalog.get_enabled_descriptor(row.get("name", ""))
                if descriptor:
                    selected.append(descriptor)

            if selected:
                return selected[: self.top_k]
        except Exception as exc:
            logger.warning(f"Tool RAG search failed; using core fallback. {exc}")

        return self._fallback()

    def _fallback(self) -> list[ToolDescriptor]:
        descriptors: list[ToolDescriptor] = []

        for name in self.catalog.core_fallback_names:
            descriptor = self.catalog.get_enabled_descriptor(name)
            if descriptor:
                descriptors.append(descriptor)

        if not descriptors:
            descriptors = self.catalog.list_tools(include_disabled=False)

        return descriptors[: self.top_k]
