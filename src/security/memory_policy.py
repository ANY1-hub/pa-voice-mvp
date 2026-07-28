"""Policy rules for writing to Semantic / Working Memory."""

from typing import Any

from .exceptions import MemoryWritePolicyViolation


def can_write_to_memory(
    fact: dict[str, Any],
    importance_score: float,
    source: str = "user",
) -> bool:
    """Decide whether a piece of information may be written to memory.

    Simple MVP policy:
    - importance must be >= 0.3
    - source must be one of the allowed values

    Args:
        fact: Candidate memory payload (currently unused beyond structure).
        importance_score: Proposed importance in ``[0.0, 1.0]``.
        source: Origin of the write (``"user"``, ``"system"``, ``"consolidation"``).

    Returns:
        ``True`` if the write is allowed, ``False`` if importance is too low.

    Raises:
        MemoryWritePolicyViolation: If the source is not in the allow-list.
    """
    # Minimum importance threshold for long-term storage
    if importance_score < 0.3:
        return False

    # Only allow certain sources for now
    allowed_sources = {"user", "system", "consolidation"}
    if source not in allowed_sources:
        raise MemoryWritePolicyViolation(f"Source '{source}' not allowed")

    # more rules later (content filtering, user consent checks, etc.)
    return True
