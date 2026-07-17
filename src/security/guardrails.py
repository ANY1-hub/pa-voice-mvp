"""Central guardrail orchestrator with proper error handling."""

import logging
from typing import Any

from .exceptions import InputValidationError, MemoryWritePolicyViolation
from .input_validator import sanitize_user_input, validate_memory_fact
from .memory_policy import can_write_to_memory

logger = logging.getLogger(__name__)


def process_user_message(message: str) -> str:
    """
    Process and validate incoming user messages.

    Raises InputValidationError on failure.
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
    """
    Validate and apply policy before writing to memory.

    Raises MemoryWritePolicyViolation or InputValidationError on failure.
    """
    try:
        validate_memory_fact(fact)

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
    """
    Safe wrapper around process_user_message.

    Returns (success, sanitized_message, error_message).
    """
    try:
        sanitized = process_user_message(message)
        return True, sanitized, None
    except InputValidationError as e:
        return False, None, str(e)
    except Exception:
        logger.exception("Unexpected error in try_process_user_message")
        return False, None, "Internal processing error"
