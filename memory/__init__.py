"""Shared cross-tenant memory system.

Captures patterns, architectural decisions, and error resolutions across all
tenant builds. Platform team has direct access; tenants benefit indirectly
through AI-powered spec recommendations.

Exports:
    - MemoryEntry (data model)
    - SharedMemoryStore (persistence and search)
    - MemoryCollector (session lifecycle hooks)
"""

from memory.models import MemoryEntry, MemoryCategory
from memory.shared_store import SharedMemoryStore, get_shared_memory_store, reset_shared_memory_store
from memory.collector import MemoryCollector

__all__ = [
    "MemoryCategory",
    "MemoryCollector",
    "MemoryEntry",
    "SharedMemoryStore",
    "get_shared_memory_store",
    "reset_shared_memory_store",
]
