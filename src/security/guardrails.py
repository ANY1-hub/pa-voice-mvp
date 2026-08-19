"""Central guardrail orchestrator with proper error handling."""

import logging
from typing import Any

from .exceptions import InputValidationError, MemoryWritePolicyViolation
from .input_validator import sanitize_user_input, validate_memory_fact
from .memory_policy import can_write_to_memory

logger = logging.getLogger(__name__)


def process_user_message(message: str) -> str:
    """Process and validate an incoming user message.

    Args:
        message: Raw user text.

    Returns:
        Sanitized message string.

    Raises:
        InputValidationError: On validation failure or unexpected errors.
    """
    try:
        return sanitize_user_input(message)
    except InputValidationError as e:
        logger.warning("Input validation failed: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during input validation: %s", e)
        raise InputValidationError("Unexpected input processing error") from e


def validate_memory_write(
    fact: dict[str, Any],
    importance_score: float,
    source: str = "user",
) -> None:
    """Validate structure and policy before writing to memory.

    Args:
        fact: Dict that must contain a non-empty ``content`` key.
        importance_score: Proposed importance in ``[0.0, 1.0]``.
        source: Origin of the write (``"user"``, ``"system"``, ``"consolidation"``).

    Raises:
        InputValidationError: If the fact structure or content is invalid.
        MemoryWritePolicyViolation: If the write is rejected by policy.
    """
    try:
        validate_memory_fact(fact, sanitize=(source == "user"))

        if not can_write_to_memory(fact, importance_score, source):
            raise MemoryWritePolicyViolation(
                f"Memory write rejected by policy "
                f"(importance={importance_score}, source={source})"
            )

    except (InputValidationError, MemoryWritePolicyViolation):
        # Re-raise security-related exceptions
        raise
    except Exception as e:
        logger.error("Unexpected error during memory write validation: %s", e)
        raise MemoryWritePolicyViolation(
            "Unexpected error while validating memory write"
        ) from e


def try_process_user_message(
    message: str,
) -> tuple[bool, str | None, str | None]:
    """Safe wrapper around ``process_user_message`` that never raises.

    Args:
        message: Raw user text.

    Returns:
        Tuple ``(success, sanitized_message, error_message)``.
        On success: ``(True, sanitized, None)``.
        On failure: ``(False, None, error_string)``.
    """
    try:
        sanitized = process_user_message(message)
        return True, sanitized, None
    except InputValidationError as e:
        return False, None, str(e)
    except Exception:
        logger.exception("Unexpected error in try_process_user_message")
        return False, None, "Internal processing error"
