"""
Memory adapter façade.

This is a framework-only placeholder. It exposes a minimal API and a trivial
in-memory backend to keep the project runnable without pulling provider SDKs.

TODO:
- Replace `_InMemoryBackend` with your own implementation (e.g., Mem0/Chroma + embeddings).
- Wire your backend construction logic in `_build_backend(settings)`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableSequence, Optional, Sequence

from core.logger import get_logger

from .config import MemorySettings, get_memory_settings
from .normalizer import normalize_query

logger = get_logger(__name__)


class MemoryBackend:
    """Backend contract; implement add/search for your storage."""

    def add(self, messages: Sequence[Mapping[str, str]], user_id: str, agent_id: Optional[str]) -> None:
        raise NotImplementedError("Implement memory add() for your backend.")

    def search(self, query: str, user_id: str, agent_id: Optional[str], limit: int) -> list[str]:
        raise NotImplementedError("Implement memory search() for your backend.")


class _InMemoryBackend(MemoryBackend):
    """Minimal in-memory backend for bootstrapping."""

    def __init__(self) -> None:
        self._store: Dict[tuple[str, Optional[str]], list[str]] = {}

    def add(self, messages: Sequence[Mapping[str, str]], user_id: str, agent_id: Optional[str]) -> None:
        key = (user_id, agent_id)
        bucket = self._store.setdefault(key, [])
        for msg in messages:
            bucket.append(f"{msg.get('role','')}: {msg.get('content','')}")

    def search(self, query: str, user_id: str, agent_id: Optional[str], limit: int) -> list[str]:
        key = (user_id, agent_id)
        bucket = self._store.get(key, [])
        return bucket[-limit:] if limit > 0 else bucket


@dataclass(frozen=True)
class MemoryClients:
    backend: MemoryBackend
    default_user_id: str
    enabled: bool


_clients: Optional[MemoryClients] = None


def _build_backend(settings: MemorySettings) -> MemoryBackend:
    """
    TODO: Replace this constructor with your real backend wiring.
    """
    logger.info(
        "Memory adapter using in-memory backend. Set MEMORY_BACKEND and implement _build_backend to change."
    )
    return _InMemoryBackend()


def init_memory_adapter(settings: Optional[MemorySettings] = None) -> MemoryClients:
    """Initialize the shared memory backend (idempotent)."""

    global _clients
    if _clients is not None:
        return _clients

    effective_settings = settings or get_memory_settings()
    backend = _build_backend(effective_settings)
    _clients = MemoryClients(
        backend=backend,
        default_user_id=effective_settings.default_user_id,
        enabled=effective_settings.enabled,
    )
    return _clients


def _require_clients() -> MemoryClients:
    if _clients is None:
        init_memory_adapter()
    return _clients  # type: ignore


def store_memories(
    messages: Sequence[Mapping[str, str]],
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> None:
    if not messages:
        return
    clients = _require_clients()
    if not clients.enabled:
        raise RuntimeError("Memory adapter is disabled; enable it before storing memories.")

    normalized: MutableSequence[dict[str, str]] = []
    for msg in messages:
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "")).strip()
        if not role or not content:
            continue
        normalized.append({"role": role, "content": content})

    if not normalized:
        return

    clients.backend.add(
        normalized,
        user_id=user_id or clients.default_user_id,
        agent_id=agent_id,
    )


def fetch_memories(
    query: str,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 3,
    context: Optional[Mapping[str, Any]] = None,
) -> list[str]:
    cleaned_query = normalize_query(query, context=context)
    if not cleaned_query:
        return []
    clients = _require_clients()
    if not clients.enabled:
        raise RuntimeError("Memory adapter is disabled; enable it before fetching memories.")

    limit = max(1, limit)
    return clients.backend.search(
        query=cleaned_query,
        user_id=user_id or clients.default_user_id,
        agent_id=agent_id,
        limit=limit,
    )


def build_memory_block(
    query: str,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 3,
    header: str = "Relevant memories:",
    context: Optional[Mapping[str, Any]] = None,
) -> str:
    snippets = fetch_memories(query=query, user_id=user_id, agent_id=agent_id, limit=limit, context=context)
    if not snippets:
        return ""
    lines = "\n".join(f"- {snippet}" for snippet in snippets)
    return f"{header}\n{lines}\n"


def is_memory_enabled() -> bool:
    return _require_clients().enabled
