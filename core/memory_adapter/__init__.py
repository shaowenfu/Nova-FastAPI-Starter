"""
Memory adapter entry points.

This package ships a minimal scaffold only. Replace the in-memory backend and
extend configuration to wire your own memory stack.
"""

from .config import MemorySettings, get_memory_settings
from .connector import (
    build_memory_block,
    fetch_memories,
    init_memory_adapter,
    is_memory_enabled,
    store_memories,
)
from .normalizer import normalize_query

__all__ = [
    "MemorySettings",
    "get_memory_settings",
    "init_memory_adapter",
    "build_memory_block",
    "fetch_memories",
    "store_memories",
    "normalize_query",
    "is_memory_enabled",
]
