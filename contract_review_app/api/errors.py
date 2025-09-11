"""Custom exceptions for API error handling."""


class UpstreamTimeoutError(Exception):
    """Raised when an external provider does not respond in time."""

    pass

