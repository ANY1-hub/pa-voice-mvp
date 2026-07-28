"""Input validation and sanitization layer (Prompt Injection protection etc.)."""

from typing import Any

from .exceptions import InputValidationError


def sanitize_user_input(text: str) -> str:
    """Basic sanitization of user input.

    Conservative checks for the MVP against obvious prompt-injection patterns.

    Args:
        text: Raw user input.

    Returns:
        Stripped text.

    Raises:
        InputValidationError: If input is not a string or matches a blocked pattern.
    """
    if not isinstance(text, str):
        raise InputValidationError("Input must be a string")

    # Very basic protection against obvious prompt injection attempts
    dangerous_patterns = [
        "ignore previous instructions",
        "ignore all previous rules",
        "system:",
        "assistant:",
        "you are now",
    ]

    lowered = text.lower()
    for pattern in dangerous_patterns:
        if pattern in lowered:
            raise InputValidationError(
                f"Potential prompt injection detected: '{pattern}'"
            )

    return text.strip()


def validate_memory_fact(fact: dict[str, Any]) -> None:
    """Validate that a fact about to be written to memory is structurally safe.

    Args:
        fact: Dict that must contain a non-empty ``content`` key.

    Raises:
        InputValidationError: If structure or content fails validation.
    """
    if not isinstance(fact, dict):
        raise InputValidationError("Memory fact must be a dictionary")

    if "content" not in fact or not fact["content"]:
        raise InputValidationError("Memory fact must contain .content.")
    sanitize_user_input(fact["content"])
