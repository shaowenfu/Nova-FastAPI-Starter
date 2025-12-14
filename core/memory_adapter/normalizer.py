"""
Simple normalization helper.

TODO: Extend with your own normalization rules (regex, replacements) if needed.
"""
from __future__ import annotations

from typing import Mapping, Optional, Any


def normalize_query(
    query: str,
    context: Optional[Mapping[str, Any]] = None,
) -> str:
    text = " ".join(query.strip().split())
    if not text:
        return ""

    if context:
        extra = context.get("replacements") if isinstance(context, Mapping) else None
        if isinstance(extra, Mapping):
            for source, target in extra.items():
                text = text.replace(str(source), str(target))

    return text.strip()
