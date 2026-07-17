"""Custom security-related exceptions."""


class SecurityException(Exception):
    """Base exception for all security-related errors."""

    pass


class InputValidationError(SecurityException):
    """Raised when input validation fails (e.g. potential prompt injection)."""

    pass


class MemoryWritePolicyViolation(SecurityException):
    """Raised when a memory write violates the defined security policy."""

    pass
