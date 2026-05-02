"""Common service-layer exceptions."""

from __future__ import annotations


class ServiceUnavailable(RuntimeError):
    """Raised when an upstream Google API is mis-configured or unreachable."""

    def __init__(self, service: str, detail: str = "") -> None:
        super().__init__(f"{service} unavailable: {detail}".rstrip(": "))
        self.service = service
        self.detail = detail
