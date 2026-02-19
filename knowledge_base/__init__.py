"""Knowledge Base Agent (RAG) — AI-253.

Project-specific context retrieval using retrieval-augmented generation.
Provides all agents with access to historical codebase context.

Exports:
    KnowledgeBaseAgent  — main RAG query interface
    DocumentIndexer     — indexes documents into the vector store
    VectorStore         — in-memory per-project vector store
    ChunkingStrategy    — text/markdown chunking helpers
    EmbeddingProvider   — mock or OpenAI embeddings
    KBWebhookHandler    — webhook trigger for automatic reindexing
"""

from knowledge_base.chunker import ChunkingStrategy
from knowledge_base.embeddings import EmbeddingProvider
from knowledge_base.vector_store import VectorStore
from knowledge_base.indexer import DocumentIndexer
from knowledge_base.agent import KnowledgeBaseAgent
from knowledge_base.webhook_handler import KBWebhookHandler

__all__ = [
    "KnowledgeBaseAgent",
    "DocumentIndexer",
    "VectorStore",
    "ChunkingStrategy",
    "EmbeddingProvider",
    "KBWebhookHandler",
]
