"""
Memory adapter configuration placeholders.

This file intentionally avoids provider-specific defaults. Engineers should
decide the vector store + embedding/LLM stack, then extend `MemorySettings`
and `_build_backend` accordingly.

TODO:
- Add your memory backend configuration fields (API keys, endpoints, models).
- Implement a concrete backend in `connector.py` that uses these fields.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class MemorySettings:
    """
    Minimal memory adapter settings.

    Fields:
    - enabled: Toggle memory adapter usage.
    - default_user_id: Fallback user id when none is provided.
    - vector_store_path: Local path for vector store/persistence (if used).
    - backend: Optional backend name for your implementation.
    - extra: Optional dict-like string for custom config (JSON or key=value pairs).
    """

    enabled: bool
    default_user_id: str
    vector_store_path: Path
    backend: Optional[str]
    extra: Optional[str]


_settings: Optional[MemorySettings] = None


def load_settings() -> MemorySettings:
    """Load memory settings from environment variables."""

    enabled_raw = os.getenv("MEMORY_ENABLED", "false").lower()
    enabled = enabled_raw not in {"0", "false", "off", "no"}
    base_dir = Path(os.getenv("MEMORY_BASE_DIR", Path(__file__).resolve().parent))
    vector_store_path = Path(
        os.getenv(
            "MEMORY_VECTOR_STORE_PATH",
            base_dir / "storage" / "memories_db",
        )
    ).resolve()
    vector_store_path.mkdir(parents=True, exist_ok=True)

    return MemorySettings(
        enabled=enabled,
        default_user_id=os.getenv("MEMORY_DEFAULT_USER_ID", "demo-user"),
        vector_store_path=vector_store_path,
        backend=os.getenv("MEMORY_BACKEND"),
        extra=os.getenv("MEMORY_EXTRA"),
    )


def get_memory_settings() -> MemorySettings:
    """Lazy singleton accessor."""

    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
