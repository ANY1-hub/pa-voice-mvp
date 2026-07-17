"""Policy rules for writing to Semantic / Working Memory."""

from typing import Any

from .exceptions import MemoryWritePolicyViolation


def can_write_to_memory(
    fact: dict[str, Any],
    importance_score: float,
    source: str = "user",
) -> bool:
    """
    Decide whether a piece of information is allowed to be written to memory.

    This is a first, simple policy for the MVP.
    """
    # Minimum importance threshold for long-term storage
    if importance_score < 0.3:
        return False

    # Only allow certain sources for now
    allowed_sources = {"user", "system", "consolidation"}
    if source not in allowed_sources:
        raise MemoryWritePolicyViolation(f"Source '{source}' not allowed")

    # more rules later (e.g. content filtering, user consent checks, etc.)
    return True