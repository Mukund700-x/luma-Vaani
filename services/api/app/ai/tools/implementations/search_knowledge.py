"""
SearchKnowledgeTool — AI tool for semantic retrieval from hospital knowledge base.

This tool gives the AI access to hospital-specific factual knowledge:
  - FAQs
  - Policies
  - Visiting hours
  - Contact information
  - Insurance plans
  - Doctor biographies

The AI MUST call this tool when a patient asks a factual question about
the hospital. It MUST NOT make up hospital-specific facts.

Only PUBLIC-scoped documents are returned (STAFF/INTERNAL are not AI-accessible).
"""

from typing import Any

from app.ai.tools.base import AITool, ToolContext


class SearchKnowledgeTool(AITool):
    name = "search_hospital_knowledge"
    description = (
        "Search the hospital's knowledge base for factual information. "
        "Use this when patients ask about: visiting hours, hospital policies, "
        "FAQs, accepted insurance plans, contact information, doctor specializations, "
        "or any hospital-specific facts. "
        "NEVER make up hospital facts — always call this tool first. "
        "If no relevant results are found, say so and offer to connect to staff."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": (
                    "The patient's question or topic to search for. "
                    "Be specific — e.g. 'visiting hours ICU', 'accepted insurance', "
                    "'cancellation policy'."
                ),
            },
        },
        "required": ["query"],
    }

    async def execute(
        self,
        context: ToolContext,
        *,
        query: str,
        **_: Any,
    ) -> dict[str, Any]:
        from app.ai.knowledge.embeddings import EmbeddingService
        from app.ai.knowledge.retriever import KnowledgeRetriever
        from app.core.config import settings

        if not query.strip():
            return {"found": False, "message": "Empty query provided."}

        try:
            emb_svc = EmbeddingService(api_key=settings.GEMINI_API_KEY or "")
            retriever = KnowledgeRetriever(
                db=context.db,
                embedding_service=emb_svc,
                top_k=settings.KNOWLEDGE_TOP_K,
                min_similarity=settings.KNOWLEDGE_MIN_SIMILARITY,
            )

            results = await retriever.search(
                hospital_id=context.hospital_id,
                query=query,
                access_scope="PUBLIC",
            )

            if not results:
                return {
                    "found": False,
                    "total": 0,
                    "message": (
                        f"No relevant information found for '{query}'. "
                        "I can connect you to our reception team for more details."
                    ),
                }

            return {
                "found": True,
                "total": len(results),
                "results": [
                    {
                        "title": r.document_title,
                        "source_type": r.source_type,
                        "content": r.content,
                        "relevance": f"{r.similarity:.0%}",
                    }
                    for r in results
                ],
            }

        except Exception as exc:
            return {"error": f"Knowledge search failed: {exc}"}
