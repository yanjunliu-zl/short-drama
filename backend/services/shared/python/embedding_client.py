"""
Embedding 服务客户端 — 统一接入本地 embedding 模型和 TEI 服务。

支持后端:
  - local: HuggingFaceEmbeddings (CPU, 每进程加载 1.3GB 模型)
  - tei: Text Embeddings Inference (GPU, HTTP API, 10ms 延迟)
  - openai: OpenAI Embeddings API (远程)

切换: 设置 EMBEDDING_BACKEND=tei 并指向 EMBEDDING_API_BASE。
"""
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Unified embedding client supporting multiple backends."""

    def __init__(self, backend: str = "", model_name: str = "BAAI/bge-large-zh-v1.5"):
        self._backend = backend or os.getenv("EMBEDDING_BACKEND", "local")
        self._model_name = model_name
        self._instance = None

    def _create_local(self):
        """Create local HuggingFace embeddings (CPU)."""
        from langchain_huggingface import HuggingFaceEmbeddings
        logger.info(f"EmbeddingClient: loading local model {self._model_name}")
        return HuggingFaceEmbeddings(model_name=self._model_name)

    def _create_tei(self):
        """Create TEI client via HTTP API.

        TEI exposes an OpenAI-compatible /v1/embeddings endpoint.
        """
        from langchain_huggingface import HuggingFaceEndpointEmbeddings
        api_url = os.getenv("EMBEDDING_API_BASE", "http://tei-server:8080")
        logger.info(f"EmbeddingClient: using TEI at {api_url}")
        return HuggingFaceEndpointEmbeddings(
            model=api_url,
            huggingfacehub_api_token=os.getenv("HF_TOKEN", ""),
        )

    def _create_openai(self):
        """Create OpenAI embeddings client."""
        from langchain_openai import OpenAIEmbeddings
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        logger.info(f"EmbeddingClient: using OpenAI {model}")
        return OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key,
        )

    def get(self):
        """Get or create the embedding instance."""
        if self._instance is None:
            if self._backend == "tei":
                self._instance = self._create_tei()
            elif self._backend == "openai":
                self._instance = self._create_openai()
            else:
                self._instance = self._create_local()
        return self._instance

    async def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        import asyncio
        embeddings = self.get()
        # All LangChain embedding backends are sync; run in thread
        return await asyncio.to_thread(embeddings.embed_query, str(text)[:10000])

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents."""
        import asyncio
        embeddings = self.get()
        truncated = [str(t)[:10000] for t in texts]
        return await asyncio.to_thread(embeddings.embed_documents, truncated)


# Global instance
_embedding_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client
