"""Document search service abstraction with extensible keyword and vector providers."""

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import DocumentRepository


class BaseSearchProvider(ABC):
    """Abstract interface for document search backends (BM25, Vector DB, hybrid)."""

    @abstractmethod
    async def search(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Perform search and return list of scored document dictionaries."""
        pass


class KeywordDatabaseSearchProvider(BaseSearchProvider):
    """Database-backed full-text / ILIKE keyword search provider."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = DocumentRepository(session)

    async def search(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        docs = await self.repo.search(query=query, category=category, limit=top_k)
        results: list[dict[str, Any]] = []

        query_terms = set(query.lower().split())

        for doc in docs:
            # Simple keyword relevance score based on query term frequency in title + content
            text = f"{doc.title} {doc.content}".lower()
            matches = sum(1 for term in query_terms if term in text)
            score = round(min(1.0, 0.5 + 0.5 * (matches / max(len(query_terms), 1))), 2)

            results.append(
                {
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "content": doc.content,
                    "score": score,
                    "source": doc.source,
                    "category": doc.category,
                }
            )

        # Sort by relevance score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


class VectorSearchProvider(BaseSearchProvider):
    """Extensible vector search provider interface for future FAISS/Qdrant/Pinecone integration."""

    def __init__(self, embedding_dimension: int = 1536) -> None:
        self.dimension = embedding_dimension

    async def search(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        # Vector hook placeholder: can be populated when external vector embeddings are enabled
        return []


class DocumentService:
    """Document search service coordinating keyword and vector search providers."""

    def __init__(
        self,
        session: AsyncSession,
        search_provider: BaseSearchProvider | None = None,
    ) -> None:
        self.session = session
        self.provider = search_provider or KeywordDatabaseSearchProvider(session)

    async def search_documents(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Search documents across enterprise knowledge base."""
        results = await self.provider.search(query=query, category=category, top_k=top_k)
        return {
            "results": results,
            "query": query,
            "total_found": len(results),
        }
